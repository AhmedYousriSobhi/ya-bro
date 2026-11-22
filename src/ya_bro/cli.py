"""`broctl`: kubectl-style control CLI for the Ya-Bro agent (`broctl <noun> <verb>`, ADR-0024)."""

from __future__ import annotations

import argparse

from ya_bro import __version__


def _apps(args: argparse.Namespace) -> int:
    from ya_bro.platform import linux_setup as ls

    run = ls.run
    if args.verb == "list":
        apps = ls.get_allowed(run)
        if apps is None:
            print("extension not installed; run `broctl setup`")
            return 1
        print("\n".join(apps) if apps else "no apps allowed: Ya-Bro sees nothing")
        return 0
    if args.verb == "available":
        from ya_bro.platform import desktop_apps

        for app in desktop_apps.available():
            extra = f"  (window class: {app.wm_class})" if app.wm_class else ""
            print(f"{app.app_id}\t{app.name}{extra}")
        return 0
    if args.verb == "allow":
        print(ls.allow_app(run, args.app, replace=False))
    else:
        print(ls.revoke_app(run, args.app))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="broctl", description="Control the Ya-Bro sidekick")
    parser.add_argument("--version", action="version", version=f"broctl {__version__}")
    sub = parser.add_subparsers(dest="noun", metavar="<command>")
    sub.add_parser("version", help="print the version")
    sub.add_parser("doctor", help="check this machine (safe to paste in a bug report)")
    sub.add_parser("setup", help="first-run setup; asks before each persistent change")
    apps = sub.add_parser("apps", help="manage which apps Ya-Bro may see (default: none)")
    verbs = apps.add_subparsers(dest="verb", required=True, metavar="<verb>")
    verbs.add_parser("list", help="show allowed apps")
    verbs.add_parser("available", help="list installed app ids you could allow")
    for verb, text in (("allow", "allow an app id"), ("revoke", "stop allowing an app id")):
        verbs.add_parser(verb, help=text).add_argument("app", help="app id, e.g. org.gimp.GIMP")
    args = parser.parse_args(argv)

    if args.noun == "version":
        print(f"broctl {__version__}")
        return 0
    if args.noun == "doctor":
        from ya_bro import doctor

        report, code = doctor.doctor()
        print(report)
        return code
    if args.noun == "setup":
        from ya_bro import doctor

        return doctor.setup()
    if args.noun == "apps":
        return _apps(args)
    parser.print_help()
    return 0
