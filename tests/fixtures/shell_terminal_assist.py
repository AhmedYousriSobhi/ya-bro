"""Terminal companion on a real frame (#115): the bubble beside a real VTE terminal shows the
command; Copy puts it on the clipboard (pasted back with Ctrl+Shift+V), Write it puts it at the
bash prompt without running it, Enter runs it and the plan moves on by itself.

Run in headless-shell.sh with YB_ALLOWED=["io.github.ahmedyousrisobhi.YaBroVte"]; YB_SHOTS=dir keeps
screenshots.
"""

import asyncio
import contextlib
import io
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, "..", "..", "src")]
import gi  # noqa: E402
import gi.events  # noqa: E402
from shellkit import Shell, find_pixels  # noqa: E402

from ya_bro import terminal  # noqa: E402
from ya_bro.platform.gnome_adapters import AtspiPerception, GnomeBridge  # noqa: E402
from ya_bro.platform.gnome_show import run_pack  # noqa: E402

APP = "io.github.ahmedyousrisobhi.YaBroVte"
HOOK = Path(HERE).resolve().parents[1] / "shell" / "ya-bro.bash"
BUTTON_BG = (0x3A, 0x3A, 0x52)  # .yabro-button in extension/stylesheet.css
SHOTS = os.environ.get("YB_SHOTS", "")
results = []
# The real-terminal guard is for the unit tests; this terminal is a private one in a private shell.
os.environ.pop("PYTEST_CURRENT_TEST", None)


def check(name, ok, detail=""):
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}".rstrip(), file=sys.__stdout__, flush=True)


async def until(pred, limit=15.0):
    end = asyncio.get_running_loop().time() + limit
    while asyncio.get_running_loop().time() < end:
        if await pred():
            return True
        await asyncio.sleep(0.2)
    return await pred()


def type_line(sh, text, enter=True):
    for ch in text:
        sh.tap(ord(ch))
    if enter:
        sh.tap(0xFF0D)


def buttons(sh):
    bx, by, bw, bh = sh.state()["bubble"]
    r = sh.ratio
    pb = sh.grab()
    pts = find_pixels(
        pb, BUTTON_BG, 6, rows=range(int(by * r), int((by + bh) * r)),
        cols=range(int(bx * r), min(pb.get_width(), int((bx + bw) * r))),
    )  # fmt: skip
    xs = sorted({x for x, _y in pts})
    runs = []
    for x in xs:
        if runs and x - runs[-1][1] <= 3:
            runs[-1][1] = x
        else:
            runs.append([x, x])
    y = sum(p[1] for p in pts) / len(pts) / r if pts else 0
    return [((a + b) / 2 / r, y) for a, b in runs]


def shot(sh, name):
    if SHOTS:
        os.makedirs(SHOTS, exist_ok=True)
        sh.grab().savev(os.path.join(SHOTS, name), "png", [], [])


async def main():
    work = Path(tempfile.mkdtemp(prefix="yb-assist-"))
    (work / "scripts").mkdir()
    fake = work / "scripts" / "benchctl"
    fake.write_text('#!/bin/sh\necho "benchctl-ran $1"\n')
    fake.chmod(0o755)
    rc = work / "rc"
    rc.write_text(f"PS1='YBP$ '\ncd {work}\n. {HOOK}\n")
    env = dict(os.environ, GTK_A11Y="atspi")
    env.pop("DISPLAY", None)
    term = subprocess.Popen(
        ["/usr/bin/python3", str(Path(HERE) / "apps" / "vte_fixture.py"), "--",
         "bash", "--noprofile", "--rcfile", str(rc), "-i"],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )  # fmt: skip
    sh = Shell()
    sh.start_input()
    perception = AtspiPerception(GnomeBridge(sh.conn))
    win = None
    for _ in range(60):
        win = next((w for w in sh.windows() if w["app_id"] == APP), None)
        if win:
            break
        await asyncio.sleep(0.5)
    check("the terminal window opened", win is not None)
    await asyncio.sleep(4)
    fx, fy, fw, fh = win["frame"]
    for _ in range(20):
        sh.click(fx + fw // 2, fy + fh // 2)
        await asyncio.sleep(0.4)
        if any(w["focused"] and w["app_id"] == APP for w in sh.windows()):
            break

    out = io.StringIO()

    async def shown():
        return bool(sh.state()["visible"]) and len(buttons(sh)) >= 4

    with contextlib.redirect_stdout(out):
        task = asyncio.create_task(run_pack("workbench", "start the cluster"))
        check("the bubble appears beside the terminal", await until(shown, 30))
        for _ in range(3):  # a fresh prompt, so the hook marks this terminal idle
            type_line(sh, "")
            await asyncio.sleep(1)
        row = buttons(sh)
        check("five buttons: Copy, Write it, Next, Why?, Stop", len(row) == 5, str(row))
        shot(sh, "1-bubble-beside-terminal.png")

        async def prompt_text():
            return await terminal.last_output(perception, APP)

        # Copy, then paste with Ctrl+Shift+V: the clipboard holds exactly the command
        sh.click(*row[0])
        await asyncio.sleep(1)
        sh.key("ctrl", True)
        sh.key("shift", True)
        sh.tap(ord("V"))
        sh.key("shift", False)
        sh.key("ctrl", False)

        async def pasted():
            return "./scripts/benchctl plan" in await prompt_text()

        check("Copy puts the command on the clipboard", await until(pasted, 10))
        shot(sh, "2-after-copy-and-paste.png")
        sh.key("ctrl", True)
        sh.tap(ord("u"))
        sh.key("ctrl", False)  # clear the line
        await asyncio.sleep(1)

        # Write it: the command lands at the prompt and does not run
        before = out.getvalue()
        sh.click(*buttons(sh)[1])

        async def written():
            t = await prompt_text()
            return t.rstrip().endswith("./scripts/benchctl plan")

        check("Write it puts the command at the prompt", await until(written, 10))
        check(
            "and it was not run",
            "command_ran" not in out.getvalue() and "benchctl-ran" not in await prompt_text(),
        )
        shot(sh, "3-after-write-it.png")
        del before

        # the user's own Enter runs it, and the plan moves on by itself
        sh.tap(0xFF0D)

        async def advanced():
            return "command_ran step=0" in out.getvalue()

        check(
            "Enter runs it and the step finishes by itself",
            await until(advanced, 15),
            out.getvalue()[-200:],
        )
        await asyncio.sleep(1.5)
        shot(sh, "4-next-step.png")
        task.cancel()
    term.terminate()


asyncio.run(main(), loop_factory=gi.events.GLibEventLoopPolicy().new_event_loop)
sys.exit(0 if all(results) else 1)
