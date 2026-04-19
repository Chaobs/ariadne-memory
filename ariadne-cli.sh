#!/bin/bash
# Ariadne CLI Entry Point (Unix/Linux/macOS)
#
# This script launches the Ariadne CLI interface.
# Usage: Run this script directly, or ./ariadne-cli from terminal.

cd "$(dirname "$0")"
python -m ariadne.cli "$@"
