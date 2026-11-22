"""`ya-bro doctor` report and `ya-bro setup` consent flow (ADR-0017 §6, ADR-0014)."""

from __future__ import annotations

from collections.abc import Callable

from ya_bro.platform import linux_setup as ls

MARK = {"ok": "ok  ", "warn": "WARN", "fail": "FAIL", "info": "info"}

SETUP_STEPS: list[tuple[str, str, Callable[[ls.Runner], str]]] = [
    (
        "Turn on GNOME toolkit accessibility. This is a persistent, SYSTEM-WIDE setting: every "
        "app exposes its UI tree on the accessibility bus to any program that asks. GNOME has no "
        "per-app switch. Ya-Bro itself will read only the app you named.",
        "enable accessibility",
        ls.enable_a11y,
    ),
    (
        "Install the Ya-Bro Shell extension. It runs inside GNOME Shell, so it can technically "
        "see every window; by design it reports only the app you named (default-deny: no app "
        "named means nothing is reported). It never sees screen pixels, typing or contents.",
        "install extension",
        ls.install_extension,
    ),
]


def format_report(checks: list[ls.Check]) -> str:
    lines = []
    for c in checks:
        lines.append(f"[{MARK[c.status]}] {c.name}: {c.detail}")
        if c.fix:
            lines.append(f"       fix: {c.fix}")
    return "\n".join(lines)


def doctor(env: dict[str, str] | None = None, runner: ls.Runner | None = None) -> tuple[str, int]:
    checks = ls.run_all(env, runner or ls.run)
    return format_report(checks), 1 if any(c.status == "fail" for c in checks) else 0


def setup(
    ask: Callable[[str], str] = input,
    runner: ls.Runner | None = None,
    say: Callable[[str], None] = print,
) -> int:
    """Each step needs its own explicit yes; anything else skips it."""
    runner = runner or ls.run
    say("Ya-Bro only works with the one app you name; every other app stays invisible to it.")
    app = ask("App id to allow (e.g. org.gimp.GIMP; empty = none yet): ").strip()
    if not app:
        say("no app chosen: Ya-Bro will see nothing until you run setup again")
    for blurb, name, action in SETUP_STEPS:
        say(blurb)
        if ask(f"Do this ({name})? [y/N] ").strip().lower() in ("y", "yes"):
            say(action(runner))
            if app and action is ls.install_extension:
                say(ls.allow_app(runner, app))
        else:
            say(f"skipped: {name}")
    return 0
