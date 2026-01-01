#!/usr/bin/env python3
"""
Web Archive Analyzer.

Scans directories for saved web pages (HTML + resource folders) and reports findings.

Usage:
    python web_archive_analyzer.py <path> [--max-depth N] [--json output.json]

Examples:
    # Scan current directory (root only)
    python web_archive_analyzer.py . --max-depth 0
    
    # Scan one level deep
    python web_archive_analyzer.py D:/downloads --max-depth 1
    
    # Recursive scan (all levels)
    python web_archive_analyzer.py D:/archives
    
    # Save results to JSON
    python web_archive_analyzer.py D:/downloads --json results.json
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from web_archiver.core import WebArchiveScanner
from web_archiver.domain.models import ScanResult


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)


def format_size(bytes_size: int) -> str:
    """
    Format byte size to human-readable string.
    
    Args:
        bytes_size: Size in bytes
        
    Returns:
        Formatted string (e.g., "1.5 MB")
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} PB"


def print_results(result: ScanResult) -> None:
    """
    Print scan results to console.
    
    Args:
        result: Scan result to display
    """
    print("\n" + "=" * 80)
    print(f"Web Archive Scan Results")
    print("=" * 80)
    print(f"Path: {result.scan_path}")
    print(f"Max Depth: {result.max_depth if result.max_depth is not None else 'Unlimited'}")
    print()
    
    # Statistics
    stats = result.stats
    print("Statistics:")
    print(f"  Valid pairs found: {stats.pairs_found}")
    print(f"  Orphaned HTML files: {stats.orphaned_html}")
    print(f"  Orphaned folders: {stats.orphaned_folders}")
    print(f"  Total size: {format_size(stats.total_size)}")
    print(f"  Files scanned: {stats.files_scanned}")
    print(f"  Directories scanned: {stats.directories_scanned}")
    print()
    
    # Valid pairs
    if result.pairs:
        print("Valid HTML + Folder Pairs:")
        print("-" * 80)
        for i, pair in enumerate(result.pairs, 1):
            print(f"{i}. {pair.html_file.name}")
            print(f"   HTML: {format_size(pair.html_size)}")
            print(f"   Folder: {pair.folder_path.name} ({pair.file_count} files, {format_size(pair.folder_size)})")
            print(f"   Pattern: {pair.pattern_type.value}")
            print(f"   Total: {format_size(pair.total_size)}")
            print()
    
    # Orphans
    if result.orphans:
        print("Orphaned Items:")
        print("-" * 80)
        for orphan in result.orphans:
            item_type = "HTML" if orphan.is_html else "Folder"
            print(f"  [{item_type}] {orphan.path.name}")
            print(f"           Size: {format_size(orphan.size)}")
            print(f"           Reason: {orphan.reason}")
            print()
    
    print("=" * 80)


def save_json(result: ScanResult, output_path: Path) -> None:
    """
    Save scan results to JSON file.
    
    Args:
        result: Scan result to save
        output_path: Where to save JSON
    """
    data = {
        'scan_path': str(result.scan_path),
        'max_depth': result.max_depth,
        'statistics': {
            'pairs_found': result.stats.pairs_found,
            'orphaned_html': result.stats.orphaned_html,
            'orphaned_folders': result.stats.orphaned_folders,
            'total_size': result.stats.total_size,
            'files_scanned': result.stats.files_scanned,
            'directories_scanned': result.stats.directories_scanned,
        },
        'pairs': [
            {
                'html_file': str(pair.html_file),
                'folder_path': str(pair.folder_path),
                'pattern_type': pair.pattern_type.value,
                'html_size': pair.html_size,
                'folder_size': pair.folder_size,
                'file_count': pair.file_count,
                'total_size': pair.total_size,
            }
            for pair in result.pairs
        ],
        'orphans': [
            {
                'path': str(orphan.path),
                'is_html': orphan.is_html,
                'size': orphan.size,
                'reason': orphan.reason,
            }
            for orphan in result.orphans
        ],
    }
    
    output_path.write_text(json.dumps(data, indent=2), encoding='utf-8')
    logger.info(f"Results saved to: {output_path}")


def main() -> int:
    """
    Main entry point.
    
    Returns:
        Exit code (0 for success)
    """
    parser = argparse.ArgumentParser(
        description='Scan directories for saved web pages (HTML + resource folders)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    
    parser.add_argument(
        'path',
        type=Path,
        help='Directory to scan',
    )
    
    parser.add_argument(
        '--max-depth',
        type=int,
        default=None,
        help='Maximum depth to scan (0=root only, 1=one level, omit for unlimited)',
    )
    
    parser.add_argument(
        '--json',
        type=Path,
        metavar='FILE',
        help='Save results to JSON file',
    )
    
    args = parser.parse_args()
    
    # Validate path
    if not args.path.exists():
        logger.error(f"Path does not exist: {args.path}")
        return 1
    
    if not args.path.is_dir():
        logger.error(f"Path is not a directory: {args.path}")
        return 1
    
    # Scan
    logger.info(f"Scanning: {args.path}")
    if args.max_depth is not None:
        logger.info(f"Max depth: {args.max_depth}")
    
    scanner = WebArchiveScanner()
    result = scanner.scan(args.path, args.max_depth)
    
    # Display results
    print_results(result)
    
    # Save JSON if requested
    if args.json:
        save_json(result, args.json)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
