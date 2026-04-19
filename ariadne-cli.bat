@echo off
REM Ariadne CLI Entry Point
REM
REM This script launches the Ariadne CLI interface.
REM Usage: Run this script directly, or double-click it.

cd /d "%~dp0"
python -m ariadne.cli %*
