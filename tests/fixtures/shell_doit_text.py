"""Do-it text entry on a real GTK4 app (#27): the bro fills an empty field through AT-SPI's
EditableText, never overwrites the user's text and never touches a password field.
Run in headless-shell.sh with the system python3."""

import asyncio
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, "..", "..", "src")]
import gi.events  # noqa: E402
from shellkit import Shell  # noqa: E402

from ya_bro.platform.gnome_adapters import AtspiActuator, AtspiPerception, GnomeBridge  # noqa: E402
from ya_bro.types import ElementRef, Step  # noqa: E402

APP = "io.github.ahmedyousrisobhi.YaBroFixture"
results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}".rstrip(), flush=True)


async def main():
    env = dict(os.environ, GTK_A11Y="atspi")
    env.pop("DISPLAY", None)
    app = subprocess.Popen(
        ["/usr/bin/python3", os.path.join(HERE, "apps", "text_fixture.py")],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )  # fmt: skip
    sh = Shell()
    for _ in range(40):
        if any(w["app_id"] == APP for w in sh.windows()):
            break
        await asyncio.sleep(0.5)
    await asyncio.sleep(2)
    perception = AtspiPerception(GnomeBridge(sh.conn))
    actuator = AtspiActuator(perception)

    async def read(role, name):
        refs = await perception.find(APP, role, name)
        return await perception.read_text(refs[0]) if len(refs) == 1 else None

    def step(role, name, text):
        return Step("x", "n", ElementRef(APP, role, name), text=text)

    ok = await actuator.act(step("text", "Project name", "Project X"))
    check("an empty field is filled", ok and await read("text", "Project name") == "Project X")
    again = await actuator.act(step("text", "Project name", "Other"))
    check(
        "a field that already has text is not overwritten",
        again is False and await read("text", "Project name") == "Project X",
    )
    mine = await actuator.act(step("text", "Note", "replaced"))
    check(
        "the user's own text is kept",
        mine is False and await read("text", "Note") == "keep me",
    )
    pw = await actuator.act(step("password text", "Secret", "abc"))
    check("a password field is never typed into", pw is False)
    missing = await actuator.act(step("text", "No such field", "abc"))
    check("a missing field is not typed into", missing is False)
    app.terminate()


asyncio.run(main(), loop_factory=gi.events.GLibEventLoopPolicy().new_event_loop)
sys.exit(0 if all(results) else 1)
