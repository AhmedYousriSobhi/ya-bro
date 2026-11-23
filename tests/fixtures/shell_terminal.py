"""A real VTE terminal (the widget Ptyxis uses), a real bash with the hook, typed commands, read back (#21).

Run in headless-shell.sh with YB_ALLOWED=["io.github.ahmedyousrisobhi.YaBroVte"]. A stand-in `benchctl` prints the
workbench error format to stderr. Checks: the spool sees exit codes and nothing else, the terminal
text is readable over AT-SPI only for the allowed app and comes back redacted, and a pack explains
the error.
"""

import asyncio
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, "..", "..", "src")]
import gi  # noqa: E402
import gi.events  # noqa: E402
from shellkit import Shell  # noqa: E402

from ya_bro import packs, terminal  # noqa: E402
from ya_bro.platform.gnome_adapters import AtspiPerception, GnomeBridge  # noqa: E402
from ya_bro.shell_spool import ShellSpool  # noqa: E402

APP = "io.github.ahmedyousrisobhi.YaBroVte"
HOOK = Path(HERE).resolve().parents[1] / "shell" / "ya-bro.bash"
results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}".rstrip(), flush=True)


async def until(pred, limit=15.0):
    end = asyncio.get_running_loop().time() + limit
    while asyncio.get_running_loop().time() < end:
        if pred():
            return True
        await asyncio.sleep(0.2)
    return pred()


def type_line(sh, text):
    for ch in text:
        sh.tap(ord(ch))
    sh.tap(0xFF0D)  # Return


async def main():
    work = Path(tempfile.mkdtemp(prefix="yb-term-"))
    (work / "bin").mkdir()
    fake = work / "bin" / "benchctl"
    fake.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = start ]; then\n'
        '  echo "WB-REFUSED-MEMORY: not enough memory, token=hunter2value | fix: benchctl plan" >&2\n'
        "  exit 1\nfi\n"
        'echo "ok $1"\n'
    )
    fake.chmod(0o755)
    rc = work / "rc"
    rc.write_text(f"PS1='YBP$ '\nexport PATH={work}/bin:$PATH\n. {HOOK}\n")

    runtime = Path(os.environ["XDG_RUNTIME_DIR"]) / "ya-bro"
    spool = ShellSpool(runtime)
    spool.open(["benchctl"])

    env = dict(os.environ, GTK_A11Y="atspi")
    env.pop("DISPLAY", None)
    fixture = Path(HERE) / "apps" / "vte_fixture.py"
    term = subprocess.Popen(
        ["/usr/bin/python3", str(fixture), "--", "bash", "--noprofile", "--rcfile", str(rc), "-i"],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    sh = Shell()
    sh.start_input()
    bridge = GnomeBridge(sh.conn)
    win = None
    for _ in range(60):
        win = next((w for w in sh.windows() if w["app_id"] == APP), None)
        if win:
            break
        await asyncio.sleep(0.5)
    check("the VTE window opened", win is not None)
    if win is None:
        term.terminate()
        return
    await asyncio.sleep(4)
    fx, fy, fw, fh = win["frame"]
    for _ in range(20):
        sh.click(fx + fw // 2, fy + fh // 2)
        await asyncio.sleep(0.4)
        if any(w["focused"] and w["app_id"] == APP for w in sh.windows()):
            break

    perception = AtspiPerception(bridge)
    type_line(sh, "")  # the first key after a window opens is spent on activating it
    await asyncio.sleep(1)
    type_line(sh, "ls /")
    await asyncio.sleep(1)
    type_line(sh, "benchctl start --token hunter2arg")
    check("the failing command is seen with its exit code", await until(lambda: bool(spool.poll())))
    type_line(sh, "benchctl plan")
    events = []
    await until(lambda: events.extend(spool.poll()) or bool(events), 10)
    check("the next command is seen too, exit 0", [e["exit"] for e in events] == [0], str(events))
    raw = spool.spool_path.read_text()
    check(
        "a command that is not allowed really ran in the terminal",
        "bin" in await terminal.last_output(perception, APP),
    )
    check(
        "the spool holds no arguments, no output and no other command",
        "hunter2" not in raw and "ls" not in raw and "WB-" not in raw,
        raw[:200],
    )

    text = await terminal.last_output(perception, APP)
    check("terminal text is readable over AT-SPI", "benchctl plan" in text, repr(text[-160:]))
    check("and secrets in it come back redacted", "hunter2value" not in text, repr(text[-200:]))
    found, _ = packs.load_all([packs.SHIPPED])
    got = terminal.explain(found, "benchctl", text)
    check(
        "the workbench pack explains the error the terminal showed",
        got is not None
        and got[0].code == "WB-REFUSED-MEMORY"
        and got[1].suggest == "benchctl plan",
        str(got),
    )
    check(
        "another app's terminal text is out of reach",
        await terminal.last_output(perception, "org.gnome.Console") == "",
    )
    term.terminate()
    spool.close()


asyncio.run(main(), loop_factory=gi.events.GLibEventLoopPolicy().new_event_loop)
sys.exit(0 if all(results) else 1)
