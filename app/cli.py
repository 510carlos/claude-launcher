"""CLI entry point for claude-launcher."""
from __future__ import annotations

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="claude-launcher",
        description="Start Claude Code sessions on your dev machines from your phone.",
    )
    sub = parser.add_subparsers(dest="command")

    # --- start (default) ---
    start = sub.add_parser("start", help="Start the launcher server")
    start.add_argument("--host", default="0.0.0.0", help="Bind address (default: 0.0.0.0)")
    start.add_argument("--port", "-p", type=int, default=8765, help="Port (default: 8765)")
    start.add_argument("--reload", action="store_true", help="Auto-reload on code changes (dev mode)")

    # --- version ---
    sub.add_parser("version", help="Print version and exit")

    args = parser.parse_args()

    if args.command == "version":
        from importlib.metadata import version
        print(f"claude-launcher {version('claude-launcher')}")
        return

    # Default to "start" when no subcommand is given
    if args.command is None:
        args.host = "0.0.0.0"
        args.port = 8765
        args.reload = False

    import uvicorn
    uvicorn.run("app.main:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
