"""Protocol interfaces for dependency injection."""

from pathlib import Path
from typing import Protocol

from .domain.models import ScanResult, WebArchivePair


class PatternMatcherProtocol(Protocol):
    """Interface for HTML+folder pattern matching."""
    
    def find_matching_folder(self, html_file: Path) -> Path | None:
        """
        Find folder matching the HTML file pattern.
        
        Args:
            html_file: Path to HTML file
            
        Returns:
            Path to matching folder, or None if not found
        """
        ...
    
    def get_pattern_type(self, html_file: Path, folder: Path) -> str:
        """
        Determine which browser pattern was used.
        
        Args:
            html_file: Path to HTML file
            folder: Path to folder
            
        Returns:
            Pattern type identifier
        """
        ...


class DirectoryScannerProtocol(Protocol):
    """Interface for directory scanning operations."""
    
    def scan(
        self,
        path: Path,
        max_depth: int | None = None,
    ) -> ScanResult:
        """
        Scan directory for HTML+folder pairs.
        
        Args:
            path: Directory to scan
            max_depth: Maximum depth (None for unlimited, 0 for root only)
            
        Returns:
            Scan results with pairs and statistics
        """
        ...


class ArchiveCreatorProtocol(Protocol):
    """Interface for archive creation operations."""
    
    def create_archive(
        self,
        pair: WebArchivePair,
        output_dir: Path,
        delete_source: bool = False,
    ) -> Path:
        """
        Create 7zip archive from HTML+folder pair.
        
        Args:
            pair: The HTML+folder pair to archive
            output_dir: Where to save the archive
            delete_source: Whether to delete source after successful archive
            
        Returns:
            Path to created archive
        """
        ...
