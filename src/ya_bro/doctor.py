"""`broctl doctor` report and `broctl setup` consent flow (ADR-0017 §6, ADR-0014)."""

from __future__ import annotations

from collections.abc import Callable

from ya_bro.platform import desktop_apps
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


def choose_app(
    ask: Callable[[str], str],
    say: Callable[[str], None],
    apps: list[desktop_apps.DesktopApp] | None = None,
) -> str:
    """Search installed apps by name or id; pick by number or type an id. Empty = none."""
    apps = desktop_apps.available() if apps is None else apps
    while True:
        term = ask("Search apps by name (Enter = skip, or type an app id): ").strip()
        if not term:
            return ""
        needle = term.lower()
        hits = [a for a in apps if needle in a.name.lower() or needle in a.app_id.lower()]
        if not hits:
            if ls.valid_app_id(term) and "." in term:
                return term  # looks like an id the user knows; trust it
            say(f"no installed app matches {term!r}; try another word")
            continue
        shown = hits[:15]
        for n, a in enumerate(shown, 1):
            say(f"  {n:2}. {a.name}  [{a.wm_class or a.app_id}]")
        if len(hits) > len(shown):
            say(f"  ... {len(hits) - len(shown)} more, type more letters to narrow")
        pick = ask("Number to allow (Enter = search again): ").strip()
        if pick.isdigit() and 1 <= int(pick) <= len(shown):
            a = shown[int(pick) - 1]
            return a.wm_class or a.app_id  # the id the window actually presents


def setup(
    ask: Callable[[str], str] = input,
    runner: ls.Runner | None = None,
    say: Callable[[str], None] = print,
    apps: list[desktop_apps.DesktopApp] | None = None,
) -> int:
    """Each step needs its own explicit yes; anything else skips it."""
    runner = runner or ls.run
    say("Ya-Bro only works with the one app you name; every other app stays invisible to it.")
    app = choose_app(ask, say, apps)
    if not app:
        say("no app chosen: Ya-Bro will see nothing until you run setup again")
    for blurb, name, action in SETUP_STEPS:
        say(blurb)
        if ask(f"Do this ({name})? [y/N] ").strip().lower() in ("y", "yes"):
            say(action(runner))
        else:
            say(f"skipped: {name}")
    if app:
        say(ls.allow_app(runner, app))
    return 0
