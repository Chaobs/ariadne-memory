@echo off
REM Ariadne Web UI Entry Point
REM
REM This script launches the Ariadne Web UI (React + FastAPI).
REM Opens http://127.0.0.1:8770 in your default browser.
REM Usage: Run this script directly, or double-click it.
REM Options:
REM   ariadne-web.bat          — Start on default port 8770
REM   ariadne-web.bat 8080     — Start on custom port

cd /d "%~dp0"
if "%1"=="" (
    python -m ariadne.cli web run
) else (
    python -m ariadne.cli web run --port %1
)
