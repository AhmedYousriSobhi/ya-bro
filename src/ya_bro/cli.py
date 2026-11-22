"""Command-line entry point. The daemon arrives in a later issue."""

from __future__ import annotations

import argparse

from ya_bro import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ya-bro", description="Ya-Bro sidekick")
    parser.add_argument("--version", action="version", version=f"ya-bro {__version__}")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("doctor", help="check this machine (safe to paste in a bug report)")
    sub.add_parser("setup", help="first-run setup; asks before each persistent change")
    args = parser.parse_args(argv)
    if args.cmd == "doctor":
        from ya_bro import doctor

        report, code = doctor.doctor()
        print(report)
        return code
    if args.cmd == "setup":
        from ya_bro import doctor

        return doctor.setup()
    parser.print_help()
    return 0
