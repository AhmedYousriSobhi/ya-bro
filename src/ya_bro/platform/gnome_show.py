"""`broctl show`: run the Show-me loop on GNOME. Runs under the system python3 (PyGObject).

    PYTHONPATH=<repo>/src python3 -m ya_bro.platform.gnome_show <plan.toml> [--app ID]

Reads an optional web-target token from stdin (one line, may be empty), like gnome_demo.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

import gi
import gi.events

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib  # noqa: E402

from ya_bro import brain as brains  # noqa: E402
from ya_bro import (  # noqa: E402
    config,
    keystore,
    packs,
    plans,
    privacy,
    shell_command,
    targets,
    terminal,
    token_server,
)
from ya_bro.command_watch import CommandWatch  # noqa: E402
from ya_bro.platform.docked_overlay import DockedOverlay  # noqa: E402
from ya_bro.platform.gnome_adapters import (  # noqa: E402
    BRIDGE,
    PREFIX,
    AtspiActuator,
    AtspiPerception,
    GnomeBridge,
    GnomeOverlay,
    _call,
)
from ya_bro.policy import LocalPolicy, ShowMePolicy  # noqa: E402
from ya_bro.shell_spool import ShellSpool  # noqa: E402
from ya_bro.steps import StepLoop, Timing  # noqa: E402
from ya_bro.terminal_write import TerminalWriter  # noqa: E402
from ya_bro.tone import Tone  # noqa: E402
from ya_bro.types import Plan, Rect, WindowInfo  # noqa: E402


async def run(
    plan_path: Path | None,
    app_override: str,
    token: str,
    goal: str = "",
    dry: bool = False,
    do_it: bool = False,
    docked: bool = False,
) -> int:
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    plan = None
    cascade = None
    app = app_override
    if plan_path is not None:
        try:
            plan, app, _ = plans.load(plan_path, app_override)
        except plans.PlanError as e:
            print(e)
            return 2
    Gio.bus_own_name_on_connection(bus, f"{PREFIX}.Core", Gio.BusNameOwnerFlags.NONE, None, None)
    await asyncio.sleep(0.5)  # let the extension notice the new owner
    if token:
        _call(bus, BRIDGE, "SetScopeTokens", GLib.Variant("(as)", ([token],)))
    bridge = GnomeBridge(bus)
    try:
        wins = bridge.raw_windows()
    except GLib.Error as e:
        print(f"cannot reach the Bro extension ({e.message}); run: broctl doctor")
        return 1
    if not app:
        focused = next((w for w in wins if w["focused"]), wins[0] if wins else None)
        app = focused["app_id"] if focused else ""
    if not app:
        print("no allowed window is open; open the app you allowed (broctl apps list)")
        return 1
    if plan is None and not goal:
        from ya_bro.platform.ask_window import AskWindow

        goal = await AskWindow().get() or ""
        if not goal:
            print("cancelled")
            return 0
    if plan is None:
        try:
            cascade, plan = await ask(goal, app, bridge)
        except brains.BrainError as e:
            print(e)
            return 1
        if dry:
            for n, s in enumerate(plan.steps, 1):
                aim = f" -> {s.target.role} {s.target.name!r}" if s.target else ""
                print(f"{n}. [R{int(s.risk)}] {s.narration}{aim}")
            return 0
    plan = plans.rebind(plan, app)
    overlay = DockedOverlay() if docked else GnomeOverlay(bus, bridge)

    def log(event: str, **fields) -> None:
        print(f"{event} " + " ".join(f"{k}={v}" for k, v in fields.items()), flush=True)

    cfg = config.load(app)
    replan = None
    if cascade is not None:

        async def replan(done, stuck):
            return await cascade.revise(app, done, stuck)

    perception = AtspiPerception(bridge, plan.extents_offset)
    if do_it and not cfg.do_it.allowed:
        print(f"Do-it is off for {app}: set `allowed = true` under [do_it] in its config first")
        return 2
    found_packs, _ = packs.load_all()
    loop = StepLoop(
        perception,
        overlay,
        bridge,
        LocalPolicy(do_it=do_it, packs=packs.resolve(found_packs, app_id=app, window_class=app))
        if do_it
        else ShowMePolicy(),
        Timing(done_hold=1.5),
        actuator=AtspiActuator(perception) if do_it else None,
        log=log,
        tone=Tone(cfg.humour, "ar" if cfg.language == "ar" else "en", cfg.less_chatty),
        replan=replan,
    )
    verb = "doing" if do_it else "showing"
    print(f"{verb} {len(plan.steps)} steps on {app}. Stop: bubble button or Super+Shift+Esc.")
    outcome = await loop.run(plan, app, preview=cascade is not None and cascade.from_model)
    print(f"finished: {outcome}")
    if cascade is not None:
        print(cascade.usage_line())
    return 0


class _NoPerception:
    """Pack-only mode reads nothing: the steps name no control to find."""

    async def find(self, app_id, role, name="", text=""):
        return []

    async def locate(self, ref):
        return None

    async def read_text(self, ref):
        return ""


class _NoBridge:
    """Pack-only mode has no app window to scope: the bubble is plain text in its own window."""

    _win = WindowInfo("0", "pack", "", Rect(0, 0, 1, 1), focused=True)

    async def windows(self):
        return [self._win]

    async def focused_window(self):
        return self._win


async def _hover(token: str = ""):
    """The bubble beside a terminal window the extension reports, else a plain window. The window is
    reported when its app is allowed, or, with a token, while a hooked shell shows it in the title
    (ADR-0029 §8). Returns (overlay, bridge, hovering, why not)."""
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        Gio.bus_own_name_on_connection(
            bus, f"{PREFIX}.Core", Gio.BusNameOwnerFlags.NONE, None, None
        )
        await asyncio.sleep(0.5)  # let the extension notice the new owner
        bridge = GnomeBridge(bus)
        if token:
            _call(bus, BRIDGE, "SetScopeTokens", GLib.Variant("(as)", ([token],)))
        for _ in range(8 if token else 1):
            if bridge.raw_windows():
                return GnomeOverlay(bus, bridge, corner="top-right"), bridge, True, ""
            await asyncio.sleep(0.5)
        why = (
            "the extension reports no terminal window. Either it is an older build than this "
            "checkout (run `broctl doctor`; after `broctl setup` log out and in), or this terminal "
            "never showed Bro's title token: it needs the hook (`broctl hook install`, then a new "
            "shell) and a window title that follows the shell (Ptyxis, GNOME Terminal and the like "
            "do; embedded terminals such as VS Code's or an Electron app's do not: allow that app "
            "with `broctl apps allow <id>`)"
        )
        kind = terminal.terminal_kind(dict(os.environ))
        if kind != "window":
            why = f"{kind}: {terminal.EMBEDDED_HINT}. Fix: {terminal.EMBEDDED_FIX}"
    except GLib.Error as e:
        why = f"the Bro extension is not reachable ({e.message}); see `broctl doctor`"
    return DockedOverlay(), _NoBridge(), False, why


async def run_pack(pack_id: str, goal: str, overlay: DockedOverlay | None = None) -> int:
    """`broctl ask --pack ID`: walk through a pack's task. Steps with a command show it as a snippet
    (Copy, Write it); the user presses Enter, and the plan moves on when the shell hook sees it
    finish. Reads no screen. With an allowed terminal window the bubble hovers beside it, else it
    is a plain window."""
    found, _problems = packs.load_all()
    pack = next((p for p in found if p.id == pack_id), None)
    if pack is None or not pack.tasks:
        print(f"no pack {pack_id!r} with tasks (see `broctl pack list`)")
        return 2
    if not goal:
        from ya_bro.platform.ask_window import AskWindow

        goal = await AskWindow(f"What do you want to do with {pack.name}?").get() or ""
        if not goal:
            print("cancelled")
            return 0
    try:
        plan = await plans.ScriptedBrain(list(pack.tasks.values())).plan(goal, pack_id)
    except plans.PlanError as e:
        print(f"{e}. Tasks in {pack_id}: {', '.join(sorted(pack.tasks))}")
        return 1
    folder = next((t.dir for t in targets.load_all() if t.id == pack_id and t.dir), "")
    plan = plans.with_folder_step(plan, pack.name, folder)
    cfg = config.load(pack_id)
    hovering = False
    # The hook records only the commands this plan shows, and only while this run lasts. Its title
    # token scopes the terminal to this run, so the terminal app itself need not be allowed.
    spool = ShellSpool()
    spool.open(sorted({shell_command.argv0(s.command) for s in plan.steps if s.command}))
    writer = TerminalWriter()
    keeper = None
    try:
        if overlay is None:
            token = token_server.new_token()
            spool.set_scope_token(token)
            keeper = asyncio.create_task(_keep_title(writer, token))
            overlay, bridge, hovering, why = await _hover(token)
        else:
            bridge, why = _NoBridge(), ""
        return await _walk(plan, pack, pack_id, cfg, overlay, bridge, hovering, spool, writer, why)
    finally:
        if keeper:
            keeper.cancel()
        spool.close()


async def _keep_title(writer: TerminalWriter, token: str) -> None:
    """The terminal is in scope only while its title carries the token, and Ptyxis resets a title
    that was set once, so core re-sets it every second for as long as the run lasts."""
    while True:
        await asyncio.to_thread(writer.set_title, token)
        await asyncio.sleep(1.0)


async def _walk(  # noqa: PLR0913
    plan: Plan, pack, pack_id: str, cfg, overlay, bridge, hovering: bool, spool, writer, why: str
) -> int:
    loop = StepLoop(
        _NoPerception(),
        overlay,
        bridge,
        ShowMePolicy(),
        Timing(done_hold=1.5),
        log=lambda event, **f: print(event, *(f"{k}={v}" for k, v in f.items()), flush=True),
        tone=Tone(cfg.humour, "ar" if cfg.language == "ar" else "en", cfg.less_chatty),
        writer=writer,
        commands=CommandWatch(spool),
    )
    where = "beside your terminal" if hovering else "in a window"
    print(f"{len(plan.steps)} steps for {pack.name}, shown {where}. Stop or Esc ends it.")
    if why:
        print(f"Not beside your terminal: {why}.")
    print(f"finished: {await loop.run(plan, pack_id)}")
    return 0


async def ask(goal: str, app: str, bridge: GnomeBridge) -> tuple[brains.FallbackBrain, Plan]:
    """Plan from plain words: a pack task if one matches, else Claude (ADR-0008 §4)."""
    found, _problems = packs.load_all()
    mine = packs.resolve(found, app_id=app, window_class=app)
    scripted = plans.ScriptedBrain([t for p in mine for t in p.tasks.values()]) if mine else None
    perception = AtspiPerception(bridge)

    async def observe(app_id: str) -> list[tuple[str, str]]:
        seen = []
        for role in OBSERVED_ROLES:
            seen += [(role, r.name) for r in await perception.find(app_id, role)]
        return seen

    cfg = config.load(app)
    key = brains.load_key(store=keystore.default_store())
    model = (
        brains.ClaudeBrain(
            key,
            observe,
            found,
            cfg.brain.model,
            base_url=os.environ.get("ANTHROPIC_BASE_URL", brains.API_URL),
            max_calls=cfg.brain.max_calls,
        )
        if key
        else None
    )
    if model is None and not privacy.load_consent().given:
        print("no API key and no consent yet: only pack tasks can answer (see `broctl setup`)")
    cascade = brains.FallbackBrain(scripted, model)
    return cascade, await cascade.plan(goal, app)


# What the model is told is on screen: the roles a person can act on, nothing else.
OBSERVED_ROLES = ("button", "toggle button", "menu item", "page tab", "check box", "radio button")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="broctl show")
    ap.add_argument("plan", type=Path, nargs="?")
    ap.add_argument("--app", default="")
    ap.add_argument(
        "--ask",
        default="",
        metavar="GOAL",
        help="plan from plain words (empty: open the ask window)",
    )
    ap.add_argument("--dry", action="store_true", help="with --ask: print the plan and stop")
    ap.add_argument("--do-it", action="store_true", help="press the controls itself (R0/R1)")
    ap.add_argument("--docked", action="store_true", help="bubble in a plain window, no ring")
    ap.add_argument("--pack", default="", help="walk through this pack's task in a plain window")
    args = ap.parse_args(argv)
    if args.pack:
        return asyncio.run(
            run_pack(args.pack, args.ask),
            loop_factory=gi.events.GLibEventLoopPolicy().new_event_loop,
        )
    if args.plan and args.ask:
        ap.error("give a plan file or --ask GOAL, not both")
    token = sys.stdin.readline().strip()
    return asyncio.run(
        run(args.plan, args.app, token, args.ask, args.dry, args.do_it, args.docked),
        loop_factory=gi.events.GLibEventLoopPolicy().new_event_loop,
    )


if __name__ == "__main__":
    sys.exit(main())
