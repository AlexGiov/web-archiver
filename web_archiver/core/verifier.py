"""
Archive Verifier.

Verifies integrity of 7zip archives with multiple validation methods.
"""

import logging
import re
import subprocess
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from .crc_calculator import CRC32Calculator

logger = logging.getLogger(__name__)


def _to_long_path(path: Path) -> Path:
    r"""
    Convert path to Windows extended-length format to support paths > 260 chars.
    
    Args:
        path: Original path
        
    Returns:
        Path in extended-length format (\\?\UNC\... or \\?\C:\...)
    """
    path_str = str(path.resolve())
    
    # Already in extended format (\\?\...)
    if path_str.startswith('\\\\?\\\\'):
        return path
    
    # UNC path: \\server\share\... → \\?\UNC\server\share\...
    if path_str.startswith('\\\\'):
        return Path('\\\\?\\\\UNC\\\\' + path_str[2:])
    
    # Local path: C:\... → \\?\C:\...
    return Path('\\\\?\\\\' + path_str)


@dataclass(frozen=True)
class VerificationResult:
    """Result of archive verification."""
    
    archive_path: Path
    passed: bool
    integrity_check: bool = False
    file_count_match: bool = False
    crc_check: bool = False
    error_message: str = ""
    expected_files: int = 0
    archived_files: int = 0
    crc_mismatches: int = 0


class ArchiveVerifier:
    """
    Verifies 7zip archive integrity using multiple methods.
    
    Three-level verification:
    1. 7zip integrity test (internal CRC check)
    2. File count comparison (all files present)
    3. CRC32 comparison (original vs archived content)
    
    Following Single Responsibility Principle.
    """
    
    def __init__(
        self,
        seven_zip_path: str = "7z",
        crc_calculator: CRC32Calculator | None = None,
    ):
        """
        Initialize verifier.
        
        Args:
            seven_zip_path: Path to 7z executable
            crc_calculator: CRC calculator (creates default if None)
        """
        self.seven_zip_path = seven_zip_path
        self.crc_calculator = crc_calculator or CRC32Calculator()
    
    def verify_archive(
        self,
        archive_path: Path,
        html_file: Path,
        folder: Path,
        skip_crc: bool = False,
    ) -> VerificationResult:
        """
        Verify archive integrity using all available methods.
        
        Args:
            archive_path: Path to archive to verify
            html_file: Original HTML file
            folder: Original resource folder
            skip_crc: Skip CRC comparison (faster but less thorough)
            
        Returns:
            Verification result with detailed status
        """
        # Check 1: Archive integrity test
        integrity_ok = self._test_archive_integrity(archive_path)
        if not integrity_ok:
            return VerificationResult(
                archive_path=archive_path,
                passed=False,
                integrity_check=False,
                error_message="Archive integrity test failed",
            )
        
        # Check 2: File count comparison
        expected_count, archived_count, count_match = self._verify_file_count(
            archive_path,
            html_file,
            folder,
        )
        
        if not count_match:
            return VerificationResult(
                archive_path=archive_path,
                passed=False,
                integrity_check=True,
                file_count_match=False,
                error_message=f"File count mismatch: expected {expected_count}, got {archived_count}",
                expected_files=expected_count,
                archived_files=archived_count,
            )
        
        # Check 3: CRC32 comparison (optional, slower)
        crc_ok = True
        crc_mismatches = 0
        
        if not skip_crc:
            crc_ok, crc_mismatches = self._verify_crc_checksums(
                archive_path,
                html_file,
                folder,
            )
            
            if not crc_ok:
                return VerificationResult(
                    archive_path=archive_path,
                    passed=False,
                    integrity_check=True,
                    file_count_match=True,
                    crc_check=False,
                    error_message=f"CRC mismatch: {crc_mismatches} files differ",
                    expected_files=expected_count,
                    archived_files=archived_count,
                    crc_mismatches=crc_mismatches,
                )
        
        # All checks passed
        return VerificationResult(
            archive_path=archive_path,
            passed=True,
            integrity_check=True,
            file_count_match=True,
            crc_check=not skip_crc,
            expected_files=expected_count,
            archived_files=archived_count,
        )
    
    def _test_archive_integrity(self, archive_path: Path) -> bool:
        """
        Test archive integrity using 7zip test command.
        
        Args:
            archive_path: Path to archive
            
        Returns:
            True if integrity test passed
        """
        cmd = [self.seven_zip_path, 't', str(archive_path)]
        
        try:
            logger.debug(f"Testing archive integrity: {archive_path.name}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )
            
            # Check for "Everything is Ok" in output
            if "Everything is Ok" in result.stdout:
                logger.debug("Archive integrity test: PASS")
                return True
            else:
                logger.warning("Archive integrity test: unclear result")
                return False
                
        except subprocess.CalledProcessError as e:
            logger.error(f"Archive integrity test failed: {e.stderr}")
            return False
        except FileNotFoundError:
            logger.error(f"7zip not found at: {self.seven_zip_path}")
            return False
    
    def _verify_file_count(
        self,
        archive_path: Path,
        html_file: Path,
        folder: Path,
    ) -> tuple[int, int, bool]:
        """
        Compare file count: original vs archived.
        
        Args:
            archive_path: Path to archive
            html_file: Original HTML file
            folder: Original resource folder
            
        Returns:
            Tuple of (expected_count, archived_count, match)
        """
        # Count original files (HTML + ALL files in folder, including embedded HTML)
        # Use extended-length path format for Windows long path support (>260 chars)
        expected_count = 1  # HTML file
        
        # Convert to long path format to access files beyond 260 char limit
        long_folder = _to_long_path(folder)
        folder_files = list(long_folder.rglob('*'))
        for item in folder_files:
            if item.is_file():
                expected_count += 1
        
        logger.debug(f"Counting files - HTML: {html_file.name}, Folder: {folder.name}")
        logger.debug(f"Found {len([f for f in folder_files if f.is_file()])} files in folder")
        
        # Count archived files
        archived_count = self._get_archive_file_count(archive_path)
        
        match = (expected_count == archived_count)
        
        logger.debug(f"File count - Expected: {expected_count}, Archived: {archived_count}, Match: {match}")
        
        return expected_count, archived_count, match
    
    def _get_archive_file_count(self, archive_path: Path) -> int:
        """
        Get file count from archive (excluding directories).
        
        Args:
            archive_path: Path to archive
            
        Returns:
            Number of files in archive
        """
        cmd = [self.seven_zip_path, 'l', str(archive_path)]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )
            
            # Parse summary line: "X files, Y folders"
            # Example: "5 files, 1 folders"
            for line in result.stdout.split('\n'):
                line = line.strip()
                if 'files,' in line and 'folders' in line:
                    # Extract number before "files"
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if part == 'files,' and i > 0:
                            try:
                                return int(parts[i - 1])
                            except ValueError:
                                pass
            
            # Fallback: count lines in listing (less reliable)
            logger.warning("Could not parse file count from summary, using fallback")
            return 0
            
        except subprocess.CalledProcessError:
            logger.error("Failed to list archive contents")
            return 0
    
    def _verify_crc_checksums(
        self,
        archive_path: Path,
        html_file: Path,
        folder: Path,
    ) -> tuple[bool, int]:
        """
        Compare CRC32 checksums: original files vs archived files.
        
        Args:
            archive_path: Path to archive
            html_file: Original HTML file
            folder: Original resource folder
            
        Returns:
            Tuple of (all_match, mismatch_count)
        """
        logger.debug("Starting CRC verification (this may take a while)...")
        
        # Calculate CRC for original files
        original_crcs: dict[str, int] = {}
        
        # HTML file (use original name, not sanitized)
        html_crc = self.crc_calculator.calculate_file_crc(html_file)
        html_name = html_file.name
        logger.info(f"HTML file name: {html_name!r} (bytes: {html_name.encode('utf-8')!r})")
        original_crcs[html_name] = html_crc
        
        # Folder files (use original folder name, not sanitized)
        folder_crcs = self.crc_calculator.calculate_directory_crcs(folder)
        for rel_path, crc in folder_crcs.items():
            # Build path as it appears in archive: folder_name\file (use original names)
            archive_path_str = f"{folder.name}\\{str(rel_path)}"
            original_crcs[archive_path_str] = crc
        
        # Get CRC from archive
        archived_crcs = self._get_archive_crcs(archive_path)
        
        # Normalize all paths (NFKC normalization + curly quote replacement)
        def normalize_path(path_str: str) -> str:
            """Normalize path: NFKC + replace curly quotes with straight quotes."""
            normalized = unicodedata.normalize('NFKC', path_str)
            # Replace curly quotes (U+2018, U+2019) with straight apostrophe (U+0027)
            normalized = normalized.replace('\u2018', "'").replace('\u2019', "'")
            # Replace curly double quotes (U+201C, U+201D) with straight quotes (U+0022)
            normalized = normalized.replace('\u201C', '"').replace('\u201D', '"')
            return normalized
        
        normalized_archived = {
            normalize_path(k): v 
            for k, v in archived_crcs.items()
        }
        normalized_original = {
            normalize_path(k): v 
            for k, v in original_crcs.items()
        }
        
        # Compare
        mismatches = 0
        for path, original_crc in normalized_original.items():
            archived_crc = normalized_archived.get(path)
            
            if archived_crc is None:
                logger.warning(f"File not found in archive: {path}")
                mismatches += 1
            elif archived_crc != original_crc:
                logger.warning(f"CRC mismatch for {path}: {original_crc:08X} vs {archived_crc:08X}")
                mismatches += 1
        
        all_match = (mismatches == 0)
        
        logger.debug(f"CRC verification - Mismatches: {mismatches}, Result: {'PASS' if all_match else 'FAIL'}")
        
        return all_match, mismatches
    
    def _get_archive_crcs(self, archive_path: Path) -> dict[str, int]:
        """
        Extract CRC32 values from archive.
        
        Args:
            archive_path: Path to archive
            
        Returns:
            Dictionary mapping file paths to CRC32 values
        """
        cmd = [self.seven_zip_path, 'l', '-slt', str(archive_path)]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                encoding='utf-8',  # Force UTF-8 encoding
                errors='replace',  # Replace invalid chars instead of failing
                check=True,
            )
            
            crcs = {}
            current_path = None
            current_is_folder = False
            
            for line in result.stdout.split('\n'):
                if line.startswith('Path = '):
                    current_path = line[7:].strip()
                    current_is_folder = False
                elif line.startswith('Folder = +'):
                    current_is_folder = True
                elif line.startswith('CRC = ') and current_path and not current_is_folder:
                    crc_str = line[6:].strip()
                    if crc_str:  # Skip empty CRC (directories)
                        try:
                            crc = int(crc_str, 16)
                            crcs[current_path] = crc
                        except ValueError:
                            logger.warning(f"Invalid CRC value: {crc_str}")
                elif line.strip() == '':
                    # Reset for next entry
                    current_path = None
                    current_is_folder = False
            
            return crcs
            
        except subprocess.CalledProcessError:
            logger.error("Failed to extract CRCs from archive")
            return {}
