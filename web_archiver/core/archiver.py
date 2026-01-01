"""
7zip Archive Creator.

Creates and manages 7zip archives.
"""

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ArchiveCreationResult:
    """Result of archive creation."""
    
    archive_path: Path
    success: bool
    error_message: str = ""
    original_size: int = 0
    compressed_size: int = 0


class SevenZipArchiver:
    """
    Creates 7zip archives.
    
    Following Single Responsibility Principle.
    """
    
    def __init__(self, seven_zip_path: str = "7z"):
        """
        Initialize archiver.
        
        Args:
            seven_zip_path: Path to 7z executable (default: "7z" from PATH)
        """
        self.seven_zip_path = seven_zip_path
    
    def create_archive(
        self,
        html_file: Path,
        folder: Path,
        output_path: Path,
        compression_level: int = 5,
    ) -> ArchiveCreationResult:
        """
        Create 7zip archive from HTML file and folder.
        
        Args:
            html_file: HTML file to include
            folder: Resource folder to include
            output_path: Where to save the archive
            compression_level: 0-9 (0=store, 5=normal, 9=ultra)
            
        Returns:
            Archive creation result
        """
        # Calculate original size
        original_size = html_file.stat().st_size
        for file in folder.rglob('*'):
            if file.is_file():
                try:
                    original_size += file.stat().st_size
                except OSError:
                    pass
        
        # Build 7z command
        cmd = [
            self.seven_zip_path,
            'a',  # Add to archive
            f'-mx={compression_level}',  # Compression level
            str(output_path),
            str(html_file),
            str(folder),
        ]
        
        try:
            logger.info(f"Creating archive: {output_path.name}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )
            
            # Get compressed size
            compressed_size = output_path.stat().st_size if output_path.exists() else 0
            
            logger.info(f"Archive created: {output_path.name} ({compressed_size:,} bytes)")
            
            return ArchiveCreationResult(
                archive_path=output_path,
                success=True,
                original_size=original_size,
                compressed_size=compressed_size,
            )
            
        except subprocess.CalledProcessError as e:
            error_msg = f"7zip failed: {e.stderr}"
            logger.error(error_msg)
            return ArchiveCreationResult(
                archive_path=output_path,
                success=False,
                error_message=error_msg,
                original_size=original_size,
            )
        
        except FileNotFoundError:
            error_msg = f"7zip not found at: {self.seven_zip_path}"
            logger.error(error_msg)
            return ArchiveCreationResult(
                archive_path=output_path,
                success=False,
                error_message=error_msg,
                original_size=original_size,
            )
