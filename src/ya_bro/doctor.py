"""`ya-bro doctor` report and `ya-bro setup` consent flow (ADR-0017 §6, ADR-0014)."""

from __future__ import annotations

from collections.abc import Callable

from ya_bro.platform import linux_setup as ls

MARK = {"ok": "ok  ", "warn": "WARN", "fail": "FAIL", "info": "info"}

SETUP_STEPS: list[tuple[str, str, Callable[[ls.Runner], str]]] = [
    (
        "Turn on GNOME toolkit accessibility (persistent setting) so Ya-Bro can read app UIs.",
        "enable accessibility",
        ls.enable_a11y,
    ),
    (
        "Install the Ya-Bro Shell extension. It sees window positions, app ids and the pointer; "
        "it cannot see screen pixels, typing or window contents.",
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
    for blurb, name, action in SETUP_STEPS:
        say(blurb)
        if ask(f"Do this ({name})? [y/N] ").strip().lower() in ("y", "yes"):
            say(action(runner))
        else:
            say(f"skipped: {name}")
    return 0
