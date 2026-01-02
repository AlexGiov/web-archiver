#!/usr/bin/env python3
"""
Web Archive Zipper.

Creates 7zip archives from web page pairs (HTML + resource folders).
Performs comprehensive verification before deleting originals.

Usage:
    python web_archive_zipper.py <path> [options]

Examples:
    # Scan and zip (dry-run)
    python web_archive_zipper.py "D:/downloads" --dry-run
    
    # Create archives without deleting originals
    python web_archive_zipper.py "D:/downloads"
    
    # Create archives and delete originals after verification
    python web_archive_zipper.py "D:/downloads" --delete-source
    
    # Skip CRC verification for speed (less safe)
    python web_archive_zipper.py "D:/downloads" --delete-source --skip-verification
    
    # Custom output directory
    python web_archive_zipper.py "D:/downloads" --output "D:/archives"
"""

import argparse
import logging
import shutil
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path to import renamer's sanitizer
sys.path.insert(0, str(Path(__file__).parent.parent))

from renamer.core.sanitizer import FilenameSanitizer
from web_archiver.core import (
    SevenZipArchiver,
    ArchiveVerifier,
    WebArchiveScanner,
)

# Configure logging - both console and file
log_dir = Path(__file__).parent / 'logs'
log_dir.mkdir(exist_ok=True)

log_filename = f"web_archiver_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
log_path = log_dir / log_filename

# Create formatters
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

# File handler
file_handler = logging.FileHandler(log_path, encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)

# Configure root logger
logging.basicConfig(
    level=logging.DEBUG,
    handlers=[file_handler, console_handler]
)

logger = logging.getLogger(__name__)
logger.info(f"Log file: {log_path}")


def format_size(bytes_size: int) -> str:
    """Format byte size to human-readable string."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} PB"


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Create 7zip archives from web page pairs (HTML + folders)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    
    parser.add_argument(
        'path',
        type=Path,
        help='Directory to scan for web page pairs',
    )
    
    parser.add_argument(
        '--max-depth',
        type=int,
        default=None,
        help='Maximum depth to scan (0=root only, omit for unlimited)',
    )
    
    parser.add_argument(
        '--delete-source',
        action='store_true',
        help='Delete original files after successful verification',
    )
    
    parser.add_argument(
        '--skip-verification',
        action='store_true',
        help='Skip CRC verification (faster but less safe - only integrity test)',
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without creating archives',
    )
    
    parser.add_argument(
        '--7z-path',
        type=str,
        default='C:\\Program Files\\7-Zip\\7z.exe',
        dest='seven_zip_path',
        help='Path to 7z executable (default: "C:\\Program Files\\7-Zip\\7z.exe")',
    )
    
    parser.add_argument(
        '--compression',
        type=int,
        choices=range(0, 10),
        default=5,
        metavar='LEVEL',
        help='Compression level 0-9 (0=store, 5=normal, 9=ultra, default: 5)',
    )
    
    args = parser.parse_args()
    
    # Validate path
    if not args.path.exists():
        logger.error(f"Path does not exist: {args.path}")
        return 1
    
    if not args.path.is_dir():
        logger.error(f"Path is not a directory: {args.path}")
        return 1
    
    # Scan for pairs
    logger.info(f"Scanning: {args.path}")
    scanner = WebArchiveScanner()
    scan_result = scanner.scan(args.path, args.max_depth)
    
    if not scan_result.has_pairs:
        logger.info("No web page pairs found")
        return 0
    
    logger.info(f"Found {scan_result.stats.pairs_found} web page pair(s)")
    print()
    
    # Check for long paths and ask user
    MAX_PATH = 260
    ARCHIVE_SUFFIX = "_web_archive.7z"
    archive_suffix_length = len(ARCHIVE_SUFFIX)
    
    pairs_to_process = []
    skipped_pairs = []
    long_path_pairs = []  # Track pairs with long paths for summary
    problematic_chars_pairs = []  # Track pairs with problematic Unicode chars
    
    for pair in scan_result.pairs:
        # First check for problematic Unicode characters
        if pair.has_problematic_chars:
            logger.warning(f"Problematic Unicode characters detected:")
            logger.warning(f"  Folder: {pair.folder_path.name}")
            logger.warning(f"  Location: {pair.folder_path.parent}")
            logger.warning(f"  Details: {pair.problematic_chars_details}")
            logger.warning(f"  Note: These characters may cause CRC verification issues")
            
            print("⚠️  WARNING: Problematic Unicode characters detected")
            print(f"    Folder: {pair.folder_path.name}")
            print(f"    Location: {pair.folder_path.parent}")
            print(f"    Details: {pair.problematic_chars_details}")
            print()
            print(f"    Note: Curly quotes and similar Unicode characters may cause issues")
            print(f"          during CRC verification. The tool will normalize them, but")
            print(f"          there's a small risk of verification mismatches.")
            print()
            
            response = input("    Process this folder anyway? (y/n): ").strip().lower()
            
            if response == 'y':
                logger.info(f"User chose to process folder with problematic chars: {pair.folder_path.name}")
                print(f"    ✓ Will process with Unicode normalization")
                problematic_chars_pairs.append(pair)
                print()
            else:
                logger.info(f"User chose to skip folder due to problematic chars: {pair.folder_path.name}")
                print(f"    ⊘ Skipped")
                skipped_pairs.append(pair)
                print()
                continue  # Skip to next pair
        
        # Then check if path will exceed limit after adding archive suffix
        effective_max = pair.max_path_length + archive_suffix_length
        exceeds_limit = effective_max > MAX_PATH
        
        if exceeds_limit:
            excess = effective_max - MAX_PATH
            
            # Log warning
            logger.warning(f"Path length exceeds Windows MAX_PATH limit:")
            logger.warning(f"  Folder: {pair.folder_path.name}")
            logger.warning(f"  Location: {pair.folder_path.parent}")
            logger.warning(f"  Current max path: {pair.max_path_length} chars")
            logger.warning(f"  Archive suffix adds: +{archive_suffix_length} chars ('{ARCHIVE_SUFFIX}')")
            logger.warning(f"  Total with archive: {effective_max} chars")
            logger.warning(f"  Windows limit: {MAX_PATH} chars")
            logger.warning(f"  Exceeds by: {excess} chars")
            
            # Show warning on console
            print("⚠️  WARNING: Path length exceeds Windows MAX_PATH limit")
            print(f"    Folder: {pair.folder_path.name}")
            print(f"    Location: {pair.folder_path.parent}")
            print(f"    Current max path: {pair.max_path_length} chars")
            print(f"    Archive suffix adds: +{archive_suffix_length} chars ('{ARCHIVE_SUFFIX}')")
            print(f"    Total with archive: {effective_max} chars")
            print(f"    Windows limit: {MAX_PATH} chars")
            print(f"    Exceeds by: {excess} chars")
            print()
            print(f"    Note: Long path support is enabled, archiving will proceed with")
            print(f"          extended-length path format (may not work on all systems).")
            print()
            
            # Ask user
            response = input("    Process this folder? (y/n): ").strip().lower()
            
            if response == 'y':
                logger.info(f"User chose to process folder with long path support: {pair.folder_path.name}")
                print(f"    ✓ Will process with long path support")
                pairs_to_process.append(pair)
                long_path_pairs.append((pair, effective_max, excess))
                print()
            else:
                logger.info(f"User chose to skip folder: {pair.folder_path.name}")
                print(f"    ⊘ Skipped")
                skipped_pairs.append(pair)
                print()
        else:
            pairs_to_process.append(pair)
    
    if not pairs_to_process:
        logger.info("No pairs to process")
        return 0
    
    # Initialize components
    sanitizer = FilenameSanitizer()
    archiver = SevenZipArchiver(args.seven_zip_path)
    verifier = ArchiveVerifier(args.seven_zip_path)
    
    # Process each pair
    success_count = 0
    failed_count = 0
    
    for i, pair in enumerate(pairs_to_process, 1):
        print(f"[{i}/{len(pairs_to_process)}] Processing: {pair.html_file.name}")
        print(f"    Size: {format_size(pair.total_size)}")
        
        # Sanitize name for archive and add suffix
        base_name = pair.base_name
        sanitized_name = sanitizer.sanitize(base_name)
        archive_name = f"{sanitized_name}_web_archive.7z"
        
        # Save archive in the same directory as the HTML file
        archive_path = pair.html_file.parent / archive_name
        
        print(f"    Archive: {archive_name}")
        print(f"    Location: {archive_path.parent}")
        
        if args.dry_run:
            print(f"    [DRY-RUN] Would create archive")
            success_count += 1
            print()
            continue
        
        # Create archive
        creation_result = archiver.create_archive(
            html_file=pair.html_file,
            folder=pair.folder_path,
            output_path=archive_path,
            compression_level=args.compression,
        )
        
        if not creation_result.success:
            print(f"    ❌ FAILED: {creation_result.error_message}")
            failed_count += 1
            print()
            continue
        
        compression_ratio = (1 - creation_result.compressed_size / creation_result.original_size) * 100
        print(f"    Compressed: {format_size(creation_result.compressed_size)} ({compression_ratio:.1f}% saved)")
        
        # Verify archive
        print(f"    Verifying archive...")
        verification_result = verifier.verify_archive(
            archive_path=archive_path,
            html_file=pair.html_file,
            folder=pair.folder_path,
            skip_crc=args.skip_verification,
        )
        
        if not verification_result.passed:
            print(f"    ❌ VERIFICATION FAILED: {verification_result.error_message}")
            print(f"       - Integrity test: {'✓' if verification_result.integrity_check else '✗'}")
            print(f"       - File count: {'✓' if verification_result.file_count_match else '✗'}")
            if not args.skip_verification:
                print(f"       - CRC check: {'✓' if verification_result.crc_check else '✗'}")
            failed_count += 1
            print()
            continue
        
        print(f"    ✓ Verification passed:")
        print(f"       - Integrity test: ✓")
        print(f"       - File count: ✓ ({verification_result.archived_files} files)")
        if not args.skip_verification:
            print(f"       - CRC check: ✓ (all files match)")
        
        # Delete source if requested
        if args.delete_source:
            print(f"    Deleting source files...")
            try:
                # Delete HTML file
                pair.html_file.unlink()
                # Delete folder
                shutil.rmtree(pair.folder_path)
                print(f"    ✓ Source files deleted")
            except Exception as e:
                print(f"    ⚠ Warning: Failed to delete source files: {e}")
        
        success_count += 1
        print()
    
    # Summary
    print("=" * 80)
    print("Summary:")
    print(f"  Successful: {success_count}")
    print(f"  Failed: {failed_count}")
    if skipped_pairs:
        print(f"  Skipped: {len(skipped_pairs)}")
    print(f"  Total: {len(scan_result.pairs)}")
    
    # Show problematic Unicode character warnings
    if problematic_chars_pairs:
        print()
        print("ℹ️  Folders with problematic Unicode characters (processed):")
        for pair in problematic_chars_pairs:
            print(f"  - {pair.folder_path.name}")
            print(f"    Details: {pair.problematic_chars_details}")
    
    # Show long path warnings in summary
    if long_path_pairs:
        print()
        print("⚠️  Long Path Warnings:")
        for pair, effective_max, excess in long_path_pairs:
            status = "✓ Processed" if pair in [p for p in pairs_to_process if p in [pp[0] for pp in long_path_pairs]] else "⊘ Skipped"
            print(f"  [{status}] {pair.folder_path.name}")
            print(f"           Path: {effective_max} chars (exceeds limit by {excess})")
    
    if skipped_pairs:
        print()
        print("Skipped folders:")
        for pair in skipped_pairs:
            print(f"  - {pair.folder_path.name}")
            print(f"    Location: {pair.folder_path.parent}")
    
    print("=" * 80)
    
    return 0 if failed_count == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
