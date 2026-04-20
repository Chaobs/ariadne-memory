#!/usr/bin/env python
"""Download third-party dependencies to vendor/packages."""

import subprocess
import sys
import os
from pathlib import Path

VENDOR_DIR = Path(__file__).parent
PACKAGES_DIR = VENDOR_DIR / "packages"

# Third-party packages to download (CLI + optional dependencies)
PACKAGES = [
    # CLI dependencies
    "typer[all]",
    "rich",

    # Optional dependencies
    "beautifulsoup4",
    "ebooklib",
    "Pillow",
    "markitdown[all]",
    "oletools",  # For .msg file support
]

def download_package(pkg: str) -> bool:
    """Download a package to vendor/packages."""
    output_dir = str(PACKAGES_DIR)

    cmd = [
        sys.executable, "-m", "pip", "download",
        "--no-deps",  # Don't download dependencies
        "-d", output_dir,
        pkg
    ]

    print(f"Downloading {pkg}...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        print(f"  OK: {pkg}")
        return True
    else:
        print(f"  FAIL: {pkg}: {result.stderr[:200]}")
        return False

def main():
    os.chdir(PACKAGES_DIR)

    print(f"Downloading packages to: {PACKAGES_DIR}")
    print(f"Python: {sys.version}")
    print()

    success = 0
    failed = []

    for pkg in PACKAGES:
        if download_package(pkg):
            success += 1
        else:
            failed.append(pkg)
        print()

    print(f"\n=== Summary ===")
    print(f"Success: {success}/{len(PACKAGES)}")

    if failed:
        print(f"Failed: {', '.join(failed)}")
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
