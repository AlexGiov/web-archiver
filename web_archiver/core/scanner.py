"""
Web Archive Scanner.

Scans directories for HTML+folder pairs.
"""

import logging
from pathlib import Path

from ..domain.models import (
    OrphanedFile,
    ScanResult,
    ScanStats,
    WebArchivePair,
)
from .pattern_matcher import BrowserPatternMatcher

logger = logging.getLogger(__name__)


def _has_problematic_unicode_chars(path: Path) -> tuple[bool, str]:
    """
    Check if path contains problematic Unicode characters (curly quotes).
    
    Args:
        path: Path to check
        
    Returns:
        Tuple of (has_problems, details_string)
    """
    PROBLEMATIC_CHARS = {
        '\u2018': "' (U+2018 LEFT SINGLE QUOTATION MARK)",
        '\u2019': "' (U+2019 RIGHT SINGLE QUOTATION MARK)",
        '\u201C': '" (U+201C LEFT DOUBLE QUOTATION MARK)',
        '\u201D': '" (U+201D RIGHT DOUBLE QUOTATION MARK)',
    }
    
    path_str = str(path)
    found_chars = []
    
    for char, description in PROBLEMATIC_CHARS.items():
        if char in path_str:
            # Find which part of path contains it
            if char in path.name:
                location = f"filename: {path.name}"
            else:
                location = f"path: {path.parent}"
            found_chars.append(f"{description} in {location}")
    
    if found_chars:
        return True, "; ".join(found_chars)
    return False, ""


class WebArchiveScanner:
    """
    Scans directories for HTML files and their associated resource folders.
    
    Following Single Responsibility Principle and Dependency Injection.
    """
    
    def __init__(self, pattern_matcher: BrowserPatternMatcher | None = None):
        """
        Initialize scanner.
        
        Args:
            pattern_matcher: Pattern matcher to use (creates default if None)
        """
        self.pattern_matcher = pattern_matcher or BrowserPatternMatcher()
    
    def scan(
        self,
        path: Path,
        max_depth: int | None = None,
    ) -> ScanResult:
        """
        Scan directory for HTML+folder pairs.
        
        Two-pass algorithm:
        1. Find all HTML files and identify pairs
        2. Filter orphans excluding HTML files inside paired resource folders
        
        Args:
            path: Directory to scan
            max_depth: Maximum depth (None for unlimited, 0 for root only)
            
        Returns:
            Scan results with pairs, orphans, and statistics
        """
        if not path.exists():
            return ScanResult(
                scan_path=path,
                max_depth=max_depth,
            )
        
        pairs: list[WebArchivePair] = []
        orphaned_html: list[OrphanedFile] = []
        orphaned_folders: list[OrphanedFile] = []
        processed_folders: set[Path] = set()
        
        files_scanned = 0
        dirs_scanned = 0
        
        # PASS 1: Collect all HTML files (no exclusions yet)
        all_html_files = self._find_html_files(path, max_depth)
        
        # PASS 2: Identify pairs and build exclusion set
        paired_resource_folders: set[Path] = set()
        
        for html_file in all_html_files:
            folder, pattern_type = self.pattern_matcher.find_matching_folder(html_file)
            
            if folder:
                # Valid pair found
                html_size = html_file.stat().st_size
                folder_size, file_count = self.pattern_matcher.get_folder_stats(folder)
                # Calculate max path length for Windows path limit detection
                max_path_len = max(
                    len(str(html_file)),
                    max((len(str(f)) for f in folder.rglob('*') if f.is_file()), default=0)
                )
                
                # Check for problematic Unicode characters
                has_prob_html, details_html = _has_problematic_unicode_chars(html_file)
                has_prob_folder = False
                details_folder = ""
                for f in folder.rglob('*'):
                    if f.is_file():
                        has_prob, details = _has_problematic_unicode_chars(f)
                        if has_prob:
                            has_prob_folder = True
                            details_folder = details
                            break
                
                has_problematic = has_prob_html or has_prob_folder
                problematic_details = details_html if has_prob_html else details_folder
                
                logger.debug(f"Pair: {html_file.name}")
                logger.debug(f"  HTML path: {html_file} ({len(str(html_file))} chars)")
                logger.debug(f"  Max folder path: {max_path_len} chars")
                if has_problematic:
                    logger.debug(f"  Problematic chars: {problematic_details}")
                
                pair = WebArchivePair(
                    html_file=html_file,
                    folder_path=folder,
                    pattern_type=pattern_type,
                    html_size=html_size,
                    folder_size=folder_size,
                    file_count=file_count,
                    max_path_length=max_path_len,
                    has_problematic_chars=has_problematic,
                    problematic_chars_details=problematic_details,
                )
                pairs.append(pair)
                processed_folders.add(folder)
                paired_resource_folders.add(folder)
        
        # PASS 3: Filter orphans - exclude HTML files inside paired resource folders
        for html_file in all_html_files:
            # Skip if already paired
            if any(pair.html_file == html_file for pair in pairs):
                continue
            
            # Check if inside any paired resource folder
            if self._is_inside_any_folder(html_file, paired_resource_folders):
                # Skip - it's an embedded component
                continue
            
            # Truly orphaned HTML
            orphaned_html.append(OrphanedFile(
                path=html_file,
                is_html=True,
                size=html_file.stat().st_size,
                reason="No matching resource folder found",
            ))
        
        files_scanned = len(all_html_files)
        
        # Find orphaned folders (folders without HTML)
        orphaned_folders = self._find_orphaned_folders(
            path,
            max_depth,
            processed_folders,
        )
        dirs_scanned = len(processed_folders) + len(orphaned_folders)
        
        # Calculate statistics
        total_size = sum(pair.total_size for pair in pairs)
        stats = ScanStats(
            pairs_found=len(pairs),
            orphaned_html=len(orphaned_html),
            orphaned_folders=len(orphaned_folders),
            total_size=total_size,
            files_scanned=files_scanned,
            directories_scanned=dirs_scanned,
        )
        
        return ScanResult(
            pairs=pairs,
            orphans=orphaned_html + orphaned_folders,
            stats=stats,
            scan_path=path,
            max_depth=max_depth,
        )
    
    def _find_html_files(
        self,
        path: Path,
        max_depth: int | None,
    ) -> list[Path]:
        """
        Find all HTML files in directory without any exclusions.
        
        Args:
            path: Directory to scan
            max_depth: Maximum depth
            
        Returns:
            List of all HTML file paths
        """
        html_files = []
        
        if max_depth == 0:
            # Root only
            for item in path.iterdir():
                if self.pattern_matcher.is_html_file(item):
                    html_files.append(item)
        else:
            # Recursive
            for item in path.rglob('*'):
                # Check depth
                if max_depth is not None:
                    relative = item.relative_to(path)
                    depth = len(relative.parts) - 1  # -1 because file itself doesn't count
                    if depth > max_depth:
                        continue
                
                if self.pattern_matcher.is_html_file(item):
                    html_files.append(item)
        
        return html_files
    
    def _is_inside_any_folder(self, file_path: Path, folders: set[Path]) -> bool:
        """
        Check if file is inside any of the given folders.
        
        Args:
            file_path: File to check
            folders: Set of folder paths
            
        Returns:
            True if file is inside any folder
        """
        for folder in folders:
            try:
                # Check if file is relative to this folder
                file_path.relative_to(folder)
                return True
            except ValueError:
                # Not relative to this folder, try next
                continue
        
        return False
    
    def _find_orphaned_folders(
        self,
        path: Path,
        max_depth: int | None,
        processed_folders: set[Path],
    ) -> list[OrphanedFile]:
        """
        Find folders that look like resource folders but have no HTML.
        
        Args:
            path: Directory to scan
            max_depth: Maximum depth
            processed_folders: Folders already paired with HTML
            
        Returns:
            List of orphaned folders
        """
        orphaned = []
        
        # Get all directories
        if max_depth == 0:
            dirs = [d for d in path.iterdir() if d.is_dir()]
        else:
            dirs = []
            for item in path.rglob('*'):
                if not item.is_dir():
                    continue
                
                # Check depth
                if max_depth is not None:
                    relative = item.relative_to(path)
                    depth = len(relative.parts)
                    if depth > max_depth:
                        continue
                
                dirs.append(item)
        
        # Check each directory
        for dir_path in dirs:
            if dir_path in processed_folders:
                continue
            
            # Check if it looks like a resource folder
            name = dir_path.name
            if any(name.endswith(suffix) for suffix, _ in BrowserPatternMatcher.PATTERNS):
                size, file_count = self.pattern_matcher.get_folder_stats(dir_path)
                orphaned.append(OrphanedFile(
                    path=dir_path,
                    is_html=False,
                    size=size,
                    reason="No matching HTML file found",
                ))
        
        return orphaned
