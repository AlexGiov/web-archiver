# Web Archiver

**Intelligent tool for archiving saved web pages (HTML + resource folders)**

Automatically detect, archive, and verify saved web pages with their associated resource folders. Supports all major browser save formats with comprehensive verification.

## ✨ Features

- **Smart Detection**: Auto-detects HTML + folder pairs from all browsers (Chrome, Firefox, IE, Edge)
- **3-Level Verification**: Integrity + file count + CRC32 checksum validation
- **7zip Compression**: High compression ratios (30-70% space saved)
- **Windows Long Path Support**: Handles paths > 260 characters automatically
- **Unicode Safe**: Normalizes problematic characters (curly quotes, etc.)
- **Interactive Warnings**: Path length and Unicode character detection with skip option
- **Safe Deletion**: Only deletes originals after successful verification
- **Comprehensive Logging**: Detailed timestamped logs for audit trail
- **Dry-Run Mode**: Preview operations before execution
- **Batch Processing**: Process entire directory trees

## 📋 Requirements

- **Python**: 3.11+
- **7-Zip**: Required for archiving ([download](https://www.7-zip.org/download.html))
  - Default path: `7z` (from PATH)
  - Custom path: `--7z-path "/path/to/7z"`

## 🚀 Installation

```bash
# Clone repository
git clone https://github.com/yourusername/web-archiver.git
cd web-archiver

# Install dependencies
pip install -r requirements.txt

# Or install as package
pip install -e .
```

## 🎯 Quick Start

### Analyze (Scan Only)

```bash
# Scan directory for web page pairs
python web_archive_analyzer.py "/path/to/saved/pages"

# Scan with depth limit
python web_archive_analyzer.py "D:/Downloads" --max-depth 1

# Save results to JSON
python web_archive_analyzer.py "D:/Downloads" --json results.json
```

### Archive & Verify

```bash
# Dry-run (preview only)
python web_archive_zipper.py "D:/Downloads" --dry-run

# Create archives (keep originals)
python web_archive_zipper.py "D:/Downloads"

# Create archives and delete originals (after verification)
python web_archive_zipper.py "D:/Downloads" --delete-source

# Custom compression level (0-9)
python web_archive_zipper.py "D:/Downloads" --compression 9
```

## 📖 Usage Examples

### Example 1: Clean Up Downloads Folder

```bash
# 1. Scan first to see what will be archived
python web_archive_analyzer.py "C:/Users/Me/Downloads"

# Output:
# Valid HTML + Folder Pairs:
# 1. article.htm
#    HTML: 45.23 KB
#    Folder: article_files (127 files, 2.34 MB)
#    Pattern: _files
#    Total: 2.39 MB

# 2. Archive with dry-run
python web_archive_zipper.py "C:/Users/Me/Downloads" --dry-run

# 3. Actually archive
python web_archive_zipper.py "C:/Users/Me/Downloads"

# 4. Delete originals after verification
python web_archive_zipper.py "C:/Users/Me/Downloads" --delete-source
```

### Example 2: Batch Archive Research Papers

```bash
# Archive all saved papers, keeping originals
python web_archive_zipper.py "D:/Research/Papers" --compression 9

# Verification happens automatically:
# ✓ Integrity test
# ✓ File count (127 files)
# ✓ CRC check (all files match)
```

### Example 3: Handle Long Paths

When paths exceed Windows MAX_PATH limit (260 chars):

```
⚠️  WARNING: Path length exceeds Windows MAX_PATH limit
    Folder: very_long_folder_name_files
    Current max path: 252 chars
    Archive suffix adds: +15 chars ('_web_archive.7z')
    Total with archive: 267 chars
    Windows limit: 260 chars
    Exceeds by: 7 chars

    Note: Long path support is enabled, archiving will proceed with
          extended-length path format (may not work on all systems).

    Process this folder? (y/n): y
```

### Example 4: UNC Network Paths

```bash
# Archive from network share
python web_archive_zipper.py "\\\\server\\share\\webpages"
```

## 🔍 Browser Patterns Detected

| Browser | Pattern | Example |
|---------|---------|---------|
| Chrome/Edge | `_files` | `page.htm` + `page_files/` |
| Chrome Alt | `_file` | `page.htm` + `page_file/` |
| Internet Explorer | `.files` | `page.htm` + `page.files/` |
| Generic | `Files` | `page.htm` + `pageFiles/` |

## ✅ Verification Levels

Every archive undergoes **3-level verification**:

### 1. Integrity Test
7zip tests archive integrity (`7z t archive.7z`)
- Ensures archive is not corrupted
- Validates all compressed data

### 2. File Count Match
Compares number of files:
- Original folder: Count via filesystem
- Archive: Count via 7zip listing
- **Must match exactly**

### 3. CRC32 Checksum
Validates every file:
- Calculates CRC32 for each file in original folder
- Compares with CRC32 from 7zip archive
- **All must match** (with Unicode normalization)

## 🛡️ Safety Features

1. **Long Path Detection**: Warns about Windows 260-char limit
2. **Unicode Warning**: Detects problematic characters (curly quotes)
3. **Interactive Prompts**: User confirms before processing risky items
4. **Verification Before Deletion**: Only deletes after ALL checks pass
5. **Detailed Logging**: Full audit trail in `logs/web_archiver_YYYYMMDD_HHMMSS.log`
6. **Dry-Run Mode**: Preview without making changes

## 📊 Output Example

```
[1/3] Processing: article.htm
    Size: 2.39 MB
    Archive: article_web_archive.7z
    Location: D:\Downloads
    Compressed: 847.23 KB (64.5% saved)
    Verifying archive...
    ✓ Verification passed:
       - Integrity test: ✓
       - File count: ✓ (127 files)
       - CRC check: ✓ (all files match)

================================================================================
Summary:
  Successful: 3
  Failed: 0
  Skipped: 0
  Total: 3
================================================================================
```

## 🔧 Advanced Usage

### Python API - Analyzer

```python
from pathlib import Path
from web_archiver.core import WebArchiveScanner

# Scan directory
scanner = WebArchiveScanner()
result = scanner.scan(Path("D:/Downloads"), max_depth=1)

# Process results
for pair in result.pairs:
    print(f"HTML: {pair.html_file}")
    print(f"Folder: {pair.folder_path} ({pair.file_count} files)")
    print(f"Total size: {pair.total_size} bytes")
```

### Python API - Archiver

```python
from pathlib import Path
from web_archiver.core import SevenZipArchiver, ArchiveVerifier

# Create archive
archiver = SevenZipArchiver()
result = archiver.create_archive(
    html_file=Path("article.htm"),
    folder=Path("article_files"),
    output_path=Path("article_web_archive.7z"),
    compression_level=5
)

# Verify
verifier = ArchiveVerifier()
verification = verifier.verify_archive(
    archive_path=Path("article_web_archive.7z"),
    html_file=Path("article.htm"),
    folder=Path("article_files"),
    skip_crc=False
)

print(f"Verification passed: {verification.passed}")
```

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=web_archiver --cov-report=html

# Specific test
pytest tests/test_scanner.py -v
```

## 📁 Archive Naming

Archives are saved with pattern:
```
<original_name>_web_archive.7z
```

Examples:
- `article.htm` + `article_files/` → `article_web_archive.7z`
- `report.html` + `report.files/` → `report_web_archive.7z`

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Write tests for new features
4. Submit Pull Request

## 📝 License

MIT License - see [LICENSE](LICENSE) file

## 🙏 Acknowledgments

- Built for preserving web content archives
- Handles real-world edge cases (long paths, Unicode issues)
- Battle-tested on production data

## 📧 Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/web-archiver/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/web-archiver/discussions)

---

**Made with ❤️ for web content preservation**
