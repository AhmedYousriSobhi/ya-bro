"""Command-line entry point. `ya-bro doctor` and the daemon arrive in later issues (#17)."""

from __future__ import annotations

import argparse

from ya_bro import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ya-bro", description="Ya-Bro sidekick")
    parser.add_argument("--version", action="version", version=f"ya-bro {__version__}")
    parser.parse_args(argv)
    parser.print_help()
    return 0
