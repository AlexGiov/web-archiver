"""
Web Archiver Domain Models.

Immutable value objects representing the core domain concepts.
Following The Zen of Python and SOLID principles.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class PatternType(Enum):
    """Browser save pattern variations."""
    
    CHROME_FILES = "_files"  # Chrome/Edge: page_files/
    CHROME_FILE = "_file"    # Chrome alternative: page_file/
    IE_FILES = ".files"      # IE: page.files/
    GENERIC_FILES = "Files"  # Generic: pageFiles/
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class WebArchivePair:
    """
    Immutable representation of an HTML file and its associated resource folder.
    
    Attributes:
        html_file: Path to the HTML file
        folder_path: Path to the associated resource folder
        pattern_type: Which browser pattern was detected
        html_size: Size of HTML file in bytes
        folder_size: Total size of resource folder in bytes
        file_count: Number of files in resource folder
        max_path_length: Maximum path length among all files (for Windows path limit detection)
        has_problematic_chars: True if any path contains problematic Unicode characters (curly quotes)
        problematic_chars_details: Description of problematic characters found
    """
    
    html_file: Path
    folder_path: Path
    pattern_type: PatternType
    html_size: int = 0
    folder_size: int = 0
    file_count: int = 0
    max_path_length: int = 0
    has_problematic_chars: bool = False
    problematic_chars_details: str = ""
    
    @property
    def base_name(self) -> str:
        """Get the common base name without extension or suffix."""
        return self.html_file.stem
    
    @property
    def total_size(self) -> int:
        """Get combined size of HTML and folder."""
        return self.html_size + self.folder_size
    
    @property
    def exceeds_path_limit(self) -> bool:
        """Check if any path exceeds Windows MAX_PATH limit of 260 chars."""
        return self.max_path_length > 260


@dataclass(frozen=True)
class OrphanedFile:
    """
    Immutable representation of an orphaned HTML or folder.
    
    Attributes:
        path: Path to the orphaned item
        is_html: True if HTML file, False if folder
        size: Size in bytes
        reason: Why it's orphaned
    """
    
    path: Path
    is_html: bool
    size: int
    reason: str


@dataclass(frozen=True)
class ScanStats:
    """
    Immutable scan statistics.
    
    Attributes:
        pairs_found: Number of valid HTML+folder pairs
        orphaned_html: Number of HTML files without folders
        orphaned_folders: Number of folders without HTML files
        total_size: Total size of all pairs in bytes
        files_scanned: Total number of files examined
        directories_scanned: Total number of directories examined
    """
    
    pairs_found: int = 0
    orphaned_html: int = 0
    orphaned_folders: int = 0
    total_size: int = 0
    files_scanned: int = 0
    directories_scanned: int = 0
    
    @property
    def total_orphans(self) -> int:
        """Get total number of orphaned items."""
        return self.orphaned_html + self.orphaned_folders


@dataclass(frozen=True)
class ScanResult:
    """
    Immutable result of a directory scan operation.
    
    Attributes:
        pairs: List of valid HTML+folder pairs found
        orphans: List of orphaned files or folders
        stats: Scan statistics
        scan_path: Path that was scanned
        max_depth: Maximum depth used (None for unlimited)
    """
    
    pairs: list[WebArchivePair] = field(default_factory=list)
    orphans: list[OrphanedFile] = field(default_factory=list)
    stats: ScanStats = field(default_factory=ScanStats)
    scan_path: Optional[Path] = None
    max_depth: Optional[int] = None
    
    @property
    def has_pairs(self) -> bool:
        """Check if any valid pairs were found."""
        return bool(self.pairs)
    
    @property
    def has_orphans(self) -> bool:
        """Check if any orphaned items were found."""
        return bool(self.orphans)
