#!/bin/bash
# Ariadne GUI Entry Point (Unix/Linux/macOS)
#
# This script launches the Ariadne GUI interface.
# Usage: Run this script directly, or ./ariadne-gui from terminal.

cd "$(dirname "$0")"
python -m ariadne.cli gui
