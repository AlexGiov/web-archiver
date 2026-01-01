"""
Web Archive Tools - Clean Architecture.

Tools for managing saved web pages (HTML + assets folder).
Follows SOLID principles and Zen of Python.

Public API:
    - WebArchiveScanner: Scan for HTML+folder pairs
    - WebArchivePair: Immutable pair representation
"""

from .domain.models import WebArchivePair, ScanResult
from .core.scanner import WebArchiveScanner

__all__ = [
    'WebArchivePair',
    'ScanResult',
    'WebArchiveScanner',
]

__version__ = '1.0.0'
