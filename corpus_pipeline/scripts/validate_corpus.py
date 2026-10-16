#!/usr/bin/env python3
"""Validate a built corpus. Example: python scripts/validate_corpus.py --help."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from kazlegal_corpus.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["validate", *sys.argv[1:]]))
