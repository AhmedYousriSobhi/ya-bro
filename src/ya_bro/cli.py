"""`broctl`: kubectl-style control CLI for the Bro agent (`broctl <noun> <verb>`, ADR-0024)."""

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
        print("\n".join(apps) if apps else "no apps allowed: Bro sees nothing")
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
                print("no targets: Bro sees no web page or command")
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


def _pack(args: argparse.Namespace) -> int:
    from pathlib import Path

    from ya_bro import packs

    if args.verb == "check":
        try:
            p = packs.load(Path(args.dir))
        except packs.PackError as e:
            print(e)
            return 1
        print(f"{p.id} {p.version}: ok ({len(p.tasks)} tasks, trust {p.trust})")
        return 0
    found, problems = packs.load_all()
    for p in found:
        print(f"{p.id}\t{p.version}\t{p.license or 'no licence'}\t{len(p.tasks)} tasks\t{p.name}")
    for line in problems:
        print(f"skipped {line}")
    if not found:
        print("no packs found")
    return 0


HOOK_SCRIPT_REL = "shell/ya-bro.bash"


def _hook(args: argparse.Namespace) -> int:
    from pathlib import Path

    from ya_bro import terminal

    script = Path(__file__).resolve().parents[2] / HOOK_SCRIPT_REL
    rc = Path.home() / ".bashrc"
    if args.verb == "print":
        print(terminal.hook_block(script), end="")
        return 0
    if args.verb == "status":
        has = rc.exists() and terminal.BEGIN in rc.read_text()
        print(f"hook script: {script} ({'found' if script.is_file() else 'MISSING'})")
        print(f"{rc}: {'hook installed' if has else 'hook not installed'}")
        return 0
    if args.verb == "uninstall":
        print("removed from ~/.bashrc" if terminal.remove_block(rc) else "it was not installed")
        return 0
    print(f"This adds three lines to {rc} so new bash shells record, for the commands you allowed")
    print("with `broctl targets allow --command`, only their name, exit code and duration.")
    print("It never records arguments or output, and does nothing while Bro is not running.")
    if input("Add it? [y/N] ").strip().lower() != "y":
        print("not changed")
        return 1
    print("added; open a new terminal" if terminal.install_block(rc, script) else "already there")
    return 0


def _shell_watch(args: argparse.Namespace) -> int:
    import time

    from ya_bro import targets
    from ya_bro.shell_spool import ShellSpool

    commands = sorted({c for t in targets.load_all() for c in t.commands})
    if not commands:
        print("no allowed commands: run `broctl targets allow NAME --command COMMAND` first")
        return 1
    spool = ShellSpool()
    spool.open(commands)
    print(f"watching {', '.join(commands)} for {args.seconds} s (exit codes only)")
    try:
        end = time.monotonic() + args.seconds
        while time.monotonic() < end:
            for e in spool.poll():
                print(f"{e['argv0']} exit {e['exit']} in {e['ms']} ms ({e['tty']})", flush=True)
            time.sleep(0.2)
    except KeyboardInterrupt:
        pass
    finally:
        spool.close()
    return 0


def _struggle_gui(seconds: int) -> int | None:
    """Run the watch with the AT-SPI sources under the system python3; None when it has none."""
    import shutil
    import subprocess
    from pathlib import Path

    py = shutil.which("python3", path="/usr/bin:/usr/local/bin")
    if not py or subprocess.run([py, "-c", "import gi"], capture_output=True).returncode:
        return None
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parent.parent)}
    try:
        return subprocess.run(
            [py, "-m", "ya_bro.platform.gnome_struggle", "--seconds", str(seconds)],
            env=env,
            check=False,
        ).returncode
    except KeyboardInterrupt:
        return 130


def _struggle(args: argparse.Namespace) -> int:
    import asyncio
    import contextlib
    import time

    from ya_bro import packs, struggle, struggle_host, targets
    from ya_bro.shell_spool import ShellSpool

    det = struggle.Detector(time.time, struggle.default_state_path())
    verb = args.verb
    if verb == "status":
        watching = sorted(a for a in det._opted_in if det.is_watching(a))
        print(f"proactive mode: {'on' if det.enabled_globally else 'off'}")
        print(f"sensitivity: {det.sensitivity} of 4 (1 quiet, 4 eager)")
        print("watching: " + (", ".join(watching) or "nothing (it is off for every app)"))
        print("answers so far: " + ", ".join(f"{k} {v}" for k, v in det.stats().items()))
        return 0
    if verb in ("on", "off"):
        det.set_enabled(verb == "on")
        print(f"proactive mode {verb}")
        return 0
    if verb in ("enable", "disable"):
        try:
            (det.opt_in if verb == "enable" else det.opt_out)(args.app)
        except struggle.ContentError as e:
            print(e)
            return 1
        print(f"{verb}d {args.app}")
        return 0
    if verb == "sensitivity":
        try:
            det.set_sensitivity(args.step)
        except ValueError as e:
            print(e)
            return 1
        print(f"sensitivity {args.step} of 4")
        return 0
    found = targets.load_all()
    commands = struggle_host.command_apps(found)
    watched = [a for a in sorted(set(commands.values())) if det.is_watching(a)]
    gui = sorted(a for a in det._opted_in if det.is_watching(a) and a not in commands.values())
    if gui:  # menus, dialogs, alerts and undo come from AT-SPI, which needs the system python3
        code = _struggle_gui(args.seconds)
        if code is not None:
            return code
        print(f"no AT-SPI here, so only commands and idle are watched, not: {', '.join(gui)}")
    if not watched:
        print("watching nothing: `broctl struggle enable APP` for an allowed target first")
        return 1
    spool = ShellSpool()
    spool.open(sorted(c for c, a in commands.items() if a in watched))
    packs_found, _problems = packs.load_all()
    struggle_host.tune_from_packs(det, packs_found, commands, [])
    host = struggle_host.StruggleHost(
        det, commands, shell=spool, on_offer=lambda o: print(f"OFFER ({o.score:.1f}): {o.why}")
    )
    print(f"watching {', '.join(watched)} for {args.seconds} s; you are never interrupted here")

    async def go():
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(host.run(), args.seconds)

    try:
        asyncio.run(go())
    except KeyboardInterrupt:
        pass
    finally:
        spool.close()
    return 0


def _persona(args: argparse.Namespace) -> int:
    from ya_bro import persona

    if args.verb == "lint":
        problems = persona.lint()
        for p in problems:
            print(p)
        print("persona: ok" if not problems else f"persona: {len(problems)} problems")
        return 1 if problems else 0
    data = persona.load()
    if args.verb == "style":
        print(persona.style_guide(), end="")
        return 0
    if args.verb == "list":  # every line, grouped, for review (the Arabic needs a native reader)
        for moment, spec in data.moments.items():
            print(
                f"\n[{moment}] max humour {spec.max_humour}"
                + (", sensitive" if spec.sensitive else "")
            )
            for ln in data.lines[args.lang].get(moment, ()):
                print(f"  h{ln.humour}{' bro' if ln.bro else ''}: {ln.text}")
        return 0
    facts = dict(kv.split("=", 1) for kv in args.fact if "=" in kv)
    p = persona.Persona(humour=args.humour, locale=args.lang, less_chatty=args.less_chatty)
    try:
        print(p.say(args.moment, **facts))
    except persona.PersonaError as e:
        print(e)
        return 1
    return 0


def _eval_struggle(args: argparse.Namespace) -> int:
    from pathlib import Path

    from ya_bro import struggle_eval

    directory = (
        Path(args.dir) if args.dir else Path(__file__).resolve().parents[2] / "evals/struggle"
    )
    try:
        if args.sweep:
            for step in (1, 2, 3, 4):
                r = struggle_eval.run(directory, step)
                med = r.median_time_to_offer
                med_text = "n/a" if med is None else f"{med:.0f} s"
                print(
                    f"sensitivity {step}: precision {100 * r.precision:.0f}%, "
                    f"recall {100 * r.recall:.0f}%, offers {r.offers}, median {med_text}, "
                    f"false/h {r.false_offers_per_hour:.2f}"
                )
            return 0
        report = struggle_eval.run(directory, args.sensitivity)
    except (struggle_eval.EvalError, ValueError) as e:
        print(e)
        return 2
    print(report.text(verbose=args.verbose))
    return 0 if report.passes else 1


def _eval(args: argparse.Namespace) -> int:
    from pathlib import Path

    if args.verb == "struggle":
        return _eval_struggle(args)

    from ya_bro import pointing_eval

    directory = (
        Path(args.dir) if args.dir else Path(__file__).resolve().parents[2] / "evals/pointing"
    )
    try:
        report = pointing_eval.run(directory)
    except pointing_eval.EvalError as e:
        print(e)
        return 2
    print(report.text(verbose=args.verbose))
    return 0 if report.passes else 1


def _consent(args: argparse.Namespace) -> int:
    from ya_bro import privacy

    if args.verb == "revoke":
        privacy.save_consent(privacy.Consent(privacy.CONSENT_VERSION))
        print("sending is off; nothing leaves this machine")
        return 0
    print(privacy.describe_consent(privacy.load_consent()))
    return 0


def _sent(args: argparse.Namespace) -> int:
    from ya_bro import privacy

    print(privacy.format_sent(privacy.read_sent()))
    return 0


def _forget(args: argparse.Namespace) -> int:
    from ya_bro import privacy

    plan = privacy.forget_plan(args.everything)
    print("This deletes:")
    for what, _ in plan:
        print(f"  - {what}")
    if not args.everything:
        print("Your allowed apps, targets and settings stay (add --everything to remove them too).")
    if not args.yes and input("Delete it? [y/N] ").strip().lower() != "y":
        print("nothing deleted")
        return 1
    for what, act in plan:
        print(f"{'removed' if act() else 'nothing to remove'}: {what}")
    return 0


def _panic(args: argparse.Namespace) -> int:
    from ya_bro import privacy

    killed, notes = privacy.panic()
    print(f"stopped {len(killed)} Bro process{'' if len(killed) == 1 else 'es'}")
    for n in notes:
        print(n)
    print("the overlay clears by itself within a few seconds; allowed apps are unchanged")
    return 0


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
        print("the Bro extension is already loaded")
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
    parser = argparse.ArgumentParser(prog="broctl", description="Control the Bro sidekick")
    parser.add_argument("--version", action="version", version=f"broctl {__version__}")
    sub = parser.add_subparsers(dest="noun", metavar="<command>")
    sub.add_parser("version", help="print the version")
    sub.add_parser("doctor", help="check this machine (safe to paste in a bug report)")
    sub.add_parser("setup", help="first-run setup; asks before each persistent change")
    point = sub.add_parser("point", help="draw the Bro ring on your allowed app's window")
    point.add_argument("--seconds", type=int, default=30)
    point.add_argument("--text", default="Ya bro is here. Press Stop or Super+Shift+Esc.")
    scope = sub.add_parser("scope", help="inspect what Bro can see")
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
    ask = sub.add_parser("ask", help="say what you want to do; Bro plans it and walks you through")
    ask.add_argument("goal", help="in your own words, e.g. 'multiply 7 by 6'")
    ask.add_argument("--app", default="", help="app id (default: the focused allowed window)")
    ask.add_argument("--dry", action="store_true", help="print the plan and stop")
    show = sub.add_parser("show", help="walk through a plan one step at a time (Show-me)")
    show.add_argument("plan", help="plan file (TOML), see docs/DEVELOPMENT.md")
    show.add_argument("--app", default="", help="app id (default: the focused allowed window)")
    sub.add_parser("load", help="load the extension now, without logging out")
    apps = sub.add_parser("apps", help="manage which apps Bro may see (default: none)")
    verbs = apps.add_subparsers(dest="verb", required=True, metavar="<verb>")
    verbs.add_parser("list", help="show allowed apps")
    verbs.add_parser("available", help="list installed app ids you could allow")
    for verb, text in (("allow", "allow an app id"), ("revoke", "stop allowing an app id")):
        verbs.add_parser(verb, help=text).add_argument("app", help="app id, e.g. org.gimp.GIMP")
    pk = sub.add_parser("pack", help="app knowledge packs (ADR-0012)")
    pverbs = pk.add_subparsers(dest="verb", required=True, metavar="<verb>")
    pverbs.add_parser("list", help="show packs found (shipped and yours)")
    pverbs.add_parser("check", help="validate a pack directory").add_argument("dir")
    ev = sub.add_parser("eval", help="score Bro against labelled sets (ADR-0016)")
    everbs = ev.add_subparsers(dest="verb", required=True, metavar="<verb>")
    pt = everbs.add_parser("pointing", help="pointing accuracy on evals/pointing (exit 1 below)")
    pt.add_argument("--dir", default="", help="snapshot folder (default: evals/pointing)")
    pt.add_argument("-v", "--verbose", action="store_true", help="list every miss")
    sr = everbs.add_parser("struggle", help="replay evals/struggle through the detector")
    sr.add_argument("--dir", default="", help="scenario folder (default: evals/struggle)")
    sr.add_argument("-v", "--verbose", action="store_true", help="list every miss")
    sr.add_argument("--sensitivity", type=int, default=2, help="1 (quiet) to 4 (eager)")
    sr.add_argument("--sweep", action="store_true", help="precision and recall at every step")
    hk = sub.add_parser("hook", help="the bash hook that sees allowed commands finish (ADR-0021)")
    hverbs = hk.add_subparsers(dest="verb", required=True, metavar="<verb>")
    for verb, text in (
        ("print", "show what install would add to ~/.bashrc"),
        ("install", "add the hook to ~/.bashrc (asks first)"),
        ("uninstall", "remove it again"),
        ("status", "is it installed?"),
    ):
        hverbs.add_parser(verb, help=text)
    shw = sub.add_parser("shell", help="what the shell hook reports")
    shw.add_subparsers(dest="verb", required=True, metavar="<verb>").add_parser(
        "watch", help="print allowed commands as they finish"
    ).add_argument("--seconds", type=int, default=60)
    st = sub.add_parser("struggle", help='the "you stuck, bro?" offers (off for every app)')
    sv = st.add_subparsers(dest="verb", required=True, metavar="<verb>")
    sv.add_parser("status", help="what is on, how eager, what you answered")
    sv.add_parser("on", help="turn proactive mode on")
    sv.add_parser("off", help="turn proactive mode off")
    sv.add_parser("enable", help="watch one app or target for struggle").add_argument("app")
    sv.add_parser("disable", help="stop watching it").add_argument("app")
    sv.add_parser("sensitivity", help="1 (quiet) to 4 (eager)").add_argument("step", type=int)
    sv.add_parser("watch", help="print offers as they would appear").add_argument(
        "--seconds", type=int, default=300
    )
    co = sub.add_parser("consent", help="what you agreed to send (ADR-0014)")
    cv = co.add_subparsers(dest="verb", required=True, metavar="<verb>")
    cv.add_parser("show", help="your answer to the first-run screen")
    cv.add_parser("revoke", help="turn sending off")
    sub.add_parser("sent", help="every request that left this machine: kind and size, no content")
    fg = sub.add_parser("forget", help="delete logs, offers and the sent list")
    fg.add_argument("--everything", action="store_true", help="also allowed apps, targets, hook")
    fg.add_argument("--yes", action="store_true", help="do not ask")
    sub.add_parser("panic", help="stop every Bro process now (works with the core wedged)")
    pe = sub.add_parser("persona", help="what the bro says (ADR-0013): preview, review, lint")
    pv = pe.add_subparsers(dest="verb", required=True, metavar="<verb>")
    say = pv.add_parser("say", help="print one line for a moment")
    say.add_argument("moment", help="e.g. mismatch, offer_stuck, task_done")
    say.add_argument("--humour", type=int, default=1, help="0 (plain) to 3 (full bro)")
    say.add_argument("--lang", choices=("en", "ar"), default="en")
    say.add_argument("--less-chatty", action="store_true")
    say.add_argument("--fact", action="append", default=[], help="name=value, e.g. want=7")
    lst = pv.add_parser("list", help="print every line, for review")
    lst.add_argument("--lang", choices=("en", "ar"), default="en")
    pv.add_parser("lint", help="check the persona data (exit 1 on a problem)")
    pv.add_parser("style", help="print the tone guide that goes in the Brain's prompt")
    args = parser.parse_args(argv)

    if args.noun == "persona":
        return _persona(args)
    if args.noun in ("consent", "sent", "forget", "panic"):
        return {"consent": _consent, "sent": _sent, "forget": _forget, "panic": _panic}[args.noun](
            args
        )
    if args.noun == "struggle":
        return _struggle(args)
    if args.noun == "hook":
        return _hook(args)
    if args.noun == "shell":
        return _shell_watch(args)
    if args.noun == "eval":
        return _eval(args)
    if args.noun == "pack":
        return _pack(args)
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
    if args.noun == "ask":
        extra = ["--app", args.app] if args.app else []
        return _gnome_demo("show", 0, show=["--ask", args.goal, *extra, *(["--dry"] * args.dry)])
    if args.noun == "scope":
        return _gnome_demo("watch", args.seconds)
    if args.noun == "apps":
        return _apps(args)
    if args.noun == "targets":
        return _targets(args)
    parser.print_help()
    return 0
