#!/usr/bin/env python3
"""
Ariadne MCP Server - Command-line launcher.

Usage:
    python -m ariadne.tools.mcp_server                    # Stdio mode (default)
    python -m ariadne.tools.mcp_server --host 0.0.0.0      # HTTP mode
    python -m ariadne.tools.mcp_server --config config.json  # With config file
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ariadne.mcp import create_server

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Ariadne MCP Server - Model Context Protocol integration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Start in stdio mode (for Claude Desktop, etc.)
    python -m ariadne.tools.mcp_server

    # Start in HTTP mode
    python -m ariadne.tools.mcp_server --transport http --port 8765

    # With custom data paths
    python -m ariadne.tools.mcp_server --vectors ./my_vectors --graph ./my_graph.db

    # With config file
    python -m ariadne.tools.mcp_server --config config.json
        """,
    )

    parser.add_argument(
        "--vectors",
        default="./data/vectors",
        help="Vector store path (default: ./data/vectors)",
    )
    parser.add_argument(
        "--graph",
        default="./data/graph.db",
        help="Graph database path (default: ./data/graph.db)",
    )
    parser.add_argument(
        "--config",
        help="Config file path",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
        help="Transport mode (default: stdio)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Port to bind to (default: 8765)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log level (default: INFO)",
    )

    args = parser.parse_args()

    # Create server
    server = create_server(
        vector_store_path=args.vectors,
        graph_db_path=args.graph,
        config_path=args.config,
    )

    # Run with selected transport
    if args.transport == "stdio":
        print("Starting Ariadne MCP Server in stdio mode...", file=sys.stderr)
        print("Press Ctrl+C to stop.", file=sys.stderr)
        server.run_stdio()
    else:
        print(f"Starting Ariadne MCP Server on {args.host}:{args.port}...", file=sys.stderr)
        server.run(host=args.host, port=args.port)
