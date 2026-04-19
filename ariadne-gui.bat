@echo off
REM Ariadne GUI Entry Point
REM
REM This script launches the Ariadne GUI interface.
REM Usage: Run this script directly, or double-click it.

cd /d "%~dp0"
python -m ariadne.cli gui
