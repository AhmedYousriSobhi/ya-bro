"""`broctl`: kubectl-style control CLI for the Ya-Bro agent (`broctl <noun> <verb>`, ADR-0024)."""

from __future__ import annotations

import argparse
import os

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


def _targets(args: argparse.Namespace) -> int:
    from ya_bro import targets

    try:
        if args.verb == "list":
            found = targets.load_all()
            for t in found:
                web, cli = ", ".join(t.origins) or "-", ", ".join(t.commands) or "-"
                print(f"{t.id}\tweb: {web}\tcli: {cli}")
            if not found:
                print("no targets: Ya-Bro sees no web page or command")
            return 0
        if args.verb == "allow":
            path = targets.save(targets.Target(args.id, tuple(args.origin), tuple(args.command)))
            print(f"allowed {args.id} ({path})")
            if args.origin:
                from ya_bro.token_server import DEFAULT_PORT

                print(
                    "its page must put the token in document.title; see docs/DEVELOPMENT.md "
                    f"(token endpoint http://127.0.0.1:{DEFAULT_PORT}/token)"
                )
            return 0
        print(f"revoked {args.id}" if targets.remove(args.id) else f"{args.id} was not allowed")
        return 0
    except targets.TargetError as e:
        print(e)
        return 1


def _gnome_demo(cmd: str, seconds: int, text: str = "", show: list[str] | None = None) -> int:
    import shutil
    import subprocess
    from pathlib import Path

    from ya_bro import targets, token_server

    py = shutil.which("python3", path="/usr/bin:/usr/local/bin")
    if not py or subprocess.run([py, "-c", "import gi"], capture_output=True).returncode:
        print("needs the system python3 with PyGObject (sudo apt install python3-gi)")
        return 1
    script = Path(__file__).parent / "platform" / "gnome_demo.py"
    args = [py, str(script), cmd, str(seconds)] + ([text] if text else [])
    env = None
    if show is not None:  # the step loop imports ya_bro, so the system python3 gets the source tree
        args = [py, "-m", "ya_bro.platform.gnome_show", *show]
        env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parent.parent)}
    server = None
    if targets.allowed_origins():
        try:
            server = token_server.TokenServer(token_server.new_token(), targets.allowed_origins)
            server.start()
        except OSError as e:
            print(f"token server not started ({e}); web targets stay out of scope")
    try:
        # The token goes over stdin, not argv or env, so `ps` and /proc/<pid>/environ never show it.
        proc = subprocess.run(
            args,
            env=env,
            input=(server.token if server else "") + "\n",
            text=True,
            check=False,
        )
        return proc.returncode
    except KeyboardInterrupt:
        return 130
    finally:
        if server:
            server.stop()


def _load(wait_seconds: int = 120) -> int:
    import time

    from ya_bro.platform import linux_setup as ls

    if ls.extension_loaded(ls.run):
        print("the Ya-Bro extension is already loaded")
        return 0
    copied = ls.copy_to_clipboard(ls.run, ls.HOTLOAD_SNIPPET)
    print("GNOME only finds new extensions at login. To load it now, in 3 steps:")
    print("  1. Press Alt+F2, type  lg  and press Enter (Looking Glass opens).")
    if copied:
        print("  2. Paste (Ctrl+V) at the bottom line and press Enter (it is in your clipboard).")
    else:
        print("  2. Paste this line at the bottom and press Enter:")
        print(f"     {ls.HOTLOAD_SNIPPET}")
    print("  3. Press Esc to close Looking Glass.")
    print(f"Waiting up to {wait_seconds} s for the extension to load...", flush=True)
    end = time.monotonic() + wait_seconds
    while time.monotonic() < end:
        if ls.extension_loaded(ls.run):
            print("loaded. Try: broctl point")
            return 0
        time.sleep(1)
    print("not loaded yet; run broctl doctor to see why")
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="broctl", description="Control the Ya-Bro sidekick")
    parser.add_argument("--version", action="version", version=f"broctl {__version__}")
    sub = parser.add_subparsers(dest="noun", metavar="<command>")
    sub.add_parser("version", help="print the version")
    sub.add_parser("doctor", help="check this machine (safe to paste in a bug report)")
    sub.add_parser("setup", help="first-run setup; asks before each persistent change")
    point = sub.add_parser("point", help="draw the Ya-Bro ring on your allowed app's window")
    point.add_argument("--seconds", type=int, default=30)
    point.add_argument("--text", default="Ya bro is here. Press Stop or Super+Shift+Esc.")
    scope = sub.add_parser("scope", help="inspect what Ya-Bro can see")
    scope.add_subparsers(dest="verb", required=True, metavar="<verb>").add_parser(
        "watch", help="print allowed windows entering and leaving scope"
    ).add_argument("--seconds", type=int, default=60)
    tgt = sub.add_parser(
        "targets", help="allow one tool (web page and/or command), not a whole app"
    )
    tverbs = tgt.add_subparsers(dest="verb", required=True, metavar="<verb>")
    tverbs.add_parser("list", help="show allowed targets")
    allow = tverbs.add_parser("allow", help="allow a target")
    allow.add_argument("id", help="short name, e.g. workbench")
    allow.add_argument(
        "--origin", action="append", default=[], help="web origin, e.g. http://127.0.0.1:8080"
    )
    allow.add_argument(
        "--command", action="append", default=[], help="CLI command name, e.g. benchctl"
    )
    tverbs.add_parser("revoke", help="stop allowing a target").add_argument("id")
    show = sub.add_parser("show", help="walk through a plan one step at a time (Show-me)")
    show.add_argument("plan", help="plan file (TOML), see docs/DEVELOPMENT.md")
    show.add_argument("--app", default="", help="app id (default: the focused allowed window)")
    sub.add_parser("load", help="load the extension now, without logging out")
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
    if args.noun == "load":
        return _load()
    if args.noun == "point":
        return _gnome_demo("point", args.seconds, args.text)
    if args.noun == "show":
        extra = ["--app", args.app] if args.app else []
        return _gnome_demo("show", 0, show=[str(args.plan), *extra])
    if args.noun == "scope":
        return _gnome_demo("watch", args.seconds)
    if args.noun == "apps":
        return _apps(args)
    if args.noun == "targets":
        return _targets(args)
    parser.print_help()
    return 0
