"""
CRC32 Calculator.

Calculates CRC32 checksums for files.
"""

import zlib
from pathlib import Path


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


class CRC32Calculator:
    """
    Calculates CRC32 checksums for files.
    
    Following Single Responsibility Principle.
    """
    
    # Read buffer size (1MB)
    BUFFER_SIZE = 1024 * 1024
    
    def calculate_file_crc(self, file_path: Path) -> int:
        """
        Calculate CRC32 for a file.
        
        Args:
            file_path: Path to file
            
        Returns:
            CRC32 checksum as unsigned integer
        """
        crc = 0
        
        with open(file_path, 'rb') as f:
            while True:
                chunk = f.read(self.BUFFER_SIZE)
                if not chunk:
                    break
                crc = zlib.crc32(chunk, crc)
        
        # Ensure unsigned
        return crc & 0xFFFFFFFF
    
    def calculate_directory_crcs(self, directory: Path) -> dict[Path, int]:
        """
        Calculate CRC32 for all files in a directory tree.
        
        Supports Windows long paths (>260 chars) using extended-length format.
        
        Args:
            directory: Root directory
            
        Returns:
            Dictionary mapping relative paths to CRC32 values
        """
        crcs = {}
        
        # Use extended-length path format for Windows long path support
        long_dir = _to_long_path(directory)
        
        for file_path in long_dir.rglob('*'):
            if file_path.is_file():
                try:
                    # Calculate relative path from original directory (not long_dir)
                    # to keep paths clean in the result
                    relative_path = file_path.relative_to(long_dir)
                    crc = self.calculate_file_crc(file_path)
                    crcs[relative_path] = crc
                except (OSError, PermissionError):
                    # Skip files we can't read
                    pass
        
        return crcs
