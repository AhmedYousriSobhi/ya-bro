"""`broctl doctor` report and `broctl setup` consent flow (ADR-0017 §6, ADR-0014)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ya_bro import keystore, packs, targets
from ya_bro.platform import desktop_apps
from ya_bro.platform import linux_setup as ls

MARK = {"ok": "ok  ", "warn": "WARN", "fail": "FAIL", "info": "info"}

SETUP_STEPS: list[tuple[str, str, Callable[[ls.Runner], str]]] = [
    (
        "Turn on GNOME toolkit accessibility. This is a persistent, SYSTEM-WIDE setting: every "
        "app exposes its UI tree on the accessibility bus to any program that asks. GNOME has no "
        "per-app switch. Bro itself will read only the app you named.",
        "enable accessibility",
        ls.enable_a11y,
    ),
    (
        "Install the Bro Shell extension. It runs inside GNOME Shell, so it can technically "
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


def doctor(
    env: dict[str, str] | None = None,
    runner: ls.Runner | None = None,
    store: keystore.Backend | None = None,
) -> tuple[str, int]:
    checks = ls.run_all(env, runner or ls.run, store)
    return format_report(checks), 1 if any(c.status == "fail" for c in checks) else 0


PAGE = 15
_BROWSERS = ("firefox", "chrom", "brave", "epiphany", "vivaldi", "opera", "librewolf", "zen")


def _is_browser(app: desktop_apps.DesktopApp | str) -> bool:
    text = app.lower() if isinstance(app, str) else f"{app.app_id} {app.name}".lower()
    return any(b in text for b in _BROWSERS)


def choose_app(
    ask: Callable[[str], str],
    say: Callable[[str], None],
    apps: list[desktop_apps.DesktopApp] | None = None,
) -> str:
    """A numbered list of installed apps, a page at a time. Type letters to filter, a number to
    pick, Enter for the next page, q to skip. Returns the app id, or "" for none."""
    apps = desktop_apps.available() if apps is None else apps
    shown_from, hits = 0, apps
    while True:
        page = hits[shown_from : shown_from + PAGE]
        if not page:
            say("no installed app matches; try other letters, or q to skip")
        for n, a in enumerate(page, 1):
            say(f"  {n:2}. {a.name}  [{a.wm_class or a.app_id}]")
        more = len(hits) - shown_from - len(page)
        if more > 0:
            say(f"  ... {more} more (Enter shows the next page)")
        pick = ask("Number to allow, letters to filter, Enter = more, q = skip: ").strip()
        if pick.lower() in ("q", "quit", "skip"):
            return ""
        if not pick:
            shown_from = shown_from + PAGE if more > 0 else 0
            continue
        if pick.isdigit():
            if 1 <= int(pick) <= len(page):
                a = page[int(pick) - 1]
                chosen = a.wm_class or a.app_id  # the id the window actually presents
                if _is_browser(a) and not _browser_ok(ask, say, a.name):
                    continue
                return chosen
            say("that number is not on this page")
            continue
        needle = pick.lower()
        found = [a for a in apps if needle in a.name.lower() or needle in a.app_id.lower()]
        if not found and ls.valid_app_id(pick) and "." in pick:
            return pick  # looks like an id the user knows; trust it
        shown_from, hits = 0, found


def _browser_ok(ask: Callable[[str], str], say: Callable[[str], None], name: str) -> bool:
    say(
        f"{name} is a browser. Allowing it lets Bro see where EVERY {name} window is (never what "
        "is in it). For a web tool such as workbench, pick the tool instead: it is in scope only "
        "while its own tab is the active one."
    )
    return ask(f"Allow all of {name} anyway? [y/N] ").strip().lower() in ("y", "yes")


@dataclass(frozen=True)
class Tool:
    """A tool a pack knows by its command name(s): scoped as a target (ADR-0025), not an app."""

    id: str
    name: str
    commands: tuple[str, ...]


def tool_packs() -> list[Tool]:
    found, _problems = packs.load_all()
    out = []
    for p in found:
        names = sorted({Path(a).name for a in p.match.get("argv0", ())})
        if names:
            out.append(Tool(p.id, p.name, tuple(names)))
    return out


def choose_access(
    ask: Callable[[str], str],
    say: Callable[[str], None],
    apps: list[desktop_apps.DesktopApp] | None,
    tools: list[Tool],
) -> tuple[str, list[str]]:
    """What Bro may see: tools (command and web page, scoped) and/or one installed app.
    Returns (app id or "", ids of the tools allowed)."""
    say("What should Bro be able to see? Only what you pick; everything else stays invisible.")
    options: list[Tool | None] = [*tools, None]
    for n, t in enumerate(options, 1):
        if t is None:
            say(f"  {n}. An installed app (Calculator, GIMP, a browser, ...)")
        else:
            say(f"  {n}. {t.name}: a tool (command {', '.join(t.commands)}, and its web page)")
    reply = ask("Pick numbers, e.g. 1 or 1,2 (Enter = nothing yet): ").replace(",", " ").split()
    picked = {int(x) for x in reply if x.isdigit() and 1 <= int(x) <= len(options)}
    app, allowed = "", []
    for n in sorted(picked):
        t = options[n - 1]
        if t is None:
            app = choose_app(ask, say, apps)
        elif _allow_tool(ask, say, t):
            allowed.append(t.id)
    return app, allowed


def _allow_tool(ask: Callable[[str], str], say: Callable[[str], None], tool: Tool) -> bool:
    web = ask(
        f"{tool.name}'s web page address, if any (Enter = none, e.g. http://127.0.0.1:8080): "
    ).strip()
    folder = ask(
        f"The folder where {tool.name}'s commands run (e.g. ~/projects/{tool.id}; Enter = none): "
    ).strip()
    try:
        path = targets.save(targets.Target(tool.id, (web,) if web else (), tool.commands, folder))
    except targets.TargetError as e:
        say(f"not saved: {e}")
        return False
    where = f"its page at {web} (only while that tab is active)" if web else "no web page"
    home = f", run from {folder}" if folder else ""
    say(f"{tool.name} allowed: command {', '.join(tool.commands)}{home}, {where}. Saved in {path}.")
    say("  (the hook records only those command names; run `broctl hook install` if you have not)")
    return True


def setup(
    ask: Callable[[str], str] = input,
    runner: ls.Runner | None = None,
    say: Callable[[str], None] = print,
    apps: list[desktop_apps.DesktopApp] | None = None,
    tools: list[Tool] | None = None,
    assume_yes: bool = False,
) -> int:
    """The privacy answers default to no (they decide what is sent). The two steps Bro cannot work
    without default to yes, and `assume_yes` takes them without asking."""
    runner = runner or ls.run
    from ya_bro import privacy

    if not privacy.load_consent().given:
        privacy.save_consent(privacy.ask_consent(ask, say))
    app, tool_ids = choose_access(ask, say, apps, tool_packs() if tools is None else tools)
    if not app and not tool_ids:
        say("nothing chosen: Bro will see nothing until you run `broctl setup` again")
    for blurb, name, action in SETUP_STEPS:
        say(blurb)
        reply = "y" if assume_yes else ask(f"Do this ({name})? [Y/n] ").strip().lower()
        if reply in ("", "y", "yes"):
            say(action(runner))
        else:
            say(f"skipped: {name}")
    if app:
        say(ls.allow_app(runner, app))
    say(
        "Next: log out and back in once (GNOME loads the extension at login), then `broctl doctor`."
    )
    return 0
