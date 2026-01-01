"""
Browser Pattern Matcher.

Detects HTML+folder pairs using various browser save patterns.
"""

from pathlib import Path

from ..domain.models import PatternType


class BrowserPatternMatcher:
    """
    Matches HTML files with their associated resource folders.
    
    Supports patterns from:
    - Chrome/Edge: page.html + page_files/
    - Chrome alternative: page.html + page_file/
    - Internet Explorer: page.html + page.files/
    - Generic: page.html + pageFiles/
    
    Following Single Responsibility Principle.
    """
    
    # Valid HTML extensions
    HTML_EXTENSIONS = {'.html', '.htm', '.xhtml'}
    
    # Pattern suffixes to try (order matters - most common first)
    PATTERNS = [
        ('_files', PatternType.CHROME_FILES),
        ('_file', PatternType.CHROME_FILE),
        ('.files', PatternType.IE_FILES),
        ('Files', PatternType.GENERIC_FILES),
    ]
    
    def is_html_file(self, path: Path) -> bool:
        """
        Check if path is an HTML file.
        
        Args:
            path: Path to check
            
        Returns:
            True if HTML file, False otherwise
        """
        return path.is_file() and path.suffix.lower() in self.HTML_EXTENSIONS
    
    def find_matching_folder(self, html_file: Path) -> tuple[Path | None, PatternType]:
        """
        Find folder matching the HTML file pattern.
        
        Args:
            html_file: Path to HTML file
            
        Returns:
            Tuple of (folder_path, pattern_type) or (None, UNKNOWN)
        """
        if not self.is_html_file(html_file):
            return None, PatternType.UNKNOWN
        
        base_name = html_file.stem
        parent_dir = html_file.parent
        
        # Try each pattern
        for suffix, pattern_type in self.PATTERNS:
            folder_name = base_name + suffix
            folder_path = parent_dir / folder_name
            
            if folder_path.is_dir():
                return folder_path, pattern_type
        
        return None, PatternType.UNKNOWN
    
    def get_folder_stats(self, folder: Path) -> tuple[int, int]:
        """
        Get statistics for a folder.
        
        Args:
            folder: Path to folder
            
        Returns:
            Tuple of (total_size_bytes, file_count)
        """
        total_size = 0
        file_count = 0
        
        try:
            for item in folder.rglob('*'):
                if item.is_file():
                    file_count += 1
                    try:
                        total_size += item.stat().st_size
                    except OSError:
                        # Skip files we can't read
                        pass
        except OSError:
            # Folder not accessible
            pass
        
        return total_size, file_count
