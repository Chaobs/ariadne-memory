#!/bin/bash
# =============================================================================
# Ariadne Web UI Launcher (Linux / macOS)
# =============================================================================
#
# This script launches the Ariadne Web UI (React + FastAPI).
# Opens http://127.0.0.1:8770 in your default browser.
#
# Usage:
#   ./ariadne-web.sh           — Start on default port 8770
#   ./ariadne-web.sh 8080      — Start on custom port
#   ./ariadne-web.sh --dev     — Start in development mode (Vite dev server)
#
# Requirements:
#   - Python 3.9+
#   - ariadne[web] installed: pip install ariadne[web]
#     Or run from source: export PYTHONPATH="${PWD}:${PYTHONPATH}"
#
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Default port
PORT=""
DEV_MODE=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dev|-d)
            DEV_MODE="1"
            shift
            ;;
        --port|-p)
            PORT="--port $2"
            shift 2
            ;;
        --help|-h)
            echo "Ariadne Web UI Launcher"
            echo ""
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  (none)           Start Web UI on default port 8770"
            echo "  <port>           Start Web UI on custom port"
            echo "  --dev, -d        Start in development mode (Vite dev server)"
            echo "  --port <port>, -p <port>"
            echo "                   Specify port (can also use: $0 <port>"
            echo "  --help, -h       Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                # Start on port 8770"
            echo "  $0 8080           # Start on port 8080"
            echo "  $0 --port 9000    # Start on port 9000"
            echo "  $0 --dev          # Start React dev server"
            exit 0
            ;;
        *)
            # Assume it's a port number
            if [[ "$1" =~ ^[0-9]+$ ]]; then
                PORT="--port $1"
            else
                echo "Unknown option: $1"
                echo "Use --help for usage information"
                exit 1
            fi
            shift
            ;;
    esac
done

# Detect Python command
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "Error: Python not found. Please install Python 3.9+."
    exit 1
fi

# Check if ariadne is installed (can import)
if ! $PYTHON_CMD -c "import ariadne" 2>/dev/null; then
    echo "Warning: 'ariadne' package not found in Python path."
    echo "If running from source, set PYTHONPATH:"
    echo "  export PYTHONPATH=\"${SCRIPT_DIR}:\${PYTHONPATH}\""
    echo ""
fi

# Check web optional dependencies
if ! $PYTHON_CMD -c "import fastapi" 2>/dev/null; then
    echo "Warning: 'fastapi' not installed. Install with:"
    echo "  pip install 'ariadne[web]'"
    echo ""
fi

if [ -n "$DEV_MODE" ]; then
    # Development mode: start both frontend dev server and backend
    echo "Starting Ariadne Web UI in DEVELOPMENT mode..."
    echo ""

    FRONTEND_DIR="$SCRIPT_DIR/ariadne/web/frontend"

    if [ ! -d "$FRONTEND_DIR" ]; then
        echo "Error: Frontend directory not found at $FRONTEND_DIR"
        exit 1
    fi

    if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
        echo "Installing frontend dependencies..."
        (cd "$FRONTEND_DIR" && npm install)
    fi

    echo "Starting Vite dev server (http://localhost:5173)..."
    echo "Starting FastAPI backend (http://localhost:8770)..."
    echo ""
    echo "Open http://localhost:5173 in your browser"
    echo ""

    # Start backend in background
    $PYTHON_CMD -m ariadne.cli web run $PORT &
    BACKEND_PID=$!

    # Wait a moment for backend to start
    sleep 2

    # Start frontend dev server
    cd "$FRONTEND_DIR"
    npm run dev &
    FRONTEND_PID=$!

    # Wait for either to exit
    trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT

    echo "Press Ctrl+C to stop all services"
    wait

else
    # Normal mode: just start the web UI via CLI
    echo "Starting Ariadne Web UI..."
    echo ""

    $PYTHON_CMD -m ariadne.cli web run $PORT

fi
