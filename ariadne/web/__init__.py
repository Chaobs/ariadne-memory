"""
Ariadne Web UI — React + FastAPI modern graphical interface.

Replaces the legacy Tkinter GUI with a web-based interface that exposes
all CLI functionality through a REST API and serves a React SPA frontend.

Usage:
    # Start the web server
    ariadne web run

    # Or directly
    python -m ariadne.web
"""

from ariadne.web.api import create_app, run_server

__all__ = ["create_app", "run_server"]
