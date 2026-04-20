#!/usr/bin/env python
"""Extract all whl files in vendor/packages for direct import."""

import os
import sys
import zipfile
from pathlib import Path

PACKAGES_DIR = Path(__file__).parent / "packages"

def extract_wheel(whl_path: Path, extract_dir: Path) -> bool:
    """Extract a wheel file to the packages directory."""
    try:
        with zipfile.ZipFile(whl_path, 'r') as zf:
            zf.extractall(extract_dir)
        return True
    except Exception as e:
        print(f"  Failed to extract {whl_path.name}: {e}")
        return False

def main():
    whl_files = list(PACKAGES_DIR.glob("*.whl"))
    print(f"Found {len(whl_files)} wheel files to extract")
    print()

    success = 0
    failed = []

    for whl in sorted(whl_files):
        pkg_name = whl.stem.split('-')[0]
        print(f"Extracting {whl.name}...")
        if extract_wheel(whl, PACKAGES_DIR):
            print(f"  OK: {pkg_name}")
            success += 1
        else:
            print(f"  FAIL: {pkg_name}")
            failed.append(whl.name)

    print()
    print(f"=== Summary ===")
    print(f"Success: {success}/{len(whl_files)}")

    if failed:
        print(f"Failed: {', '.join(failed)}")
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
