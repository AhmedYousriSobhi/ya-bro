"""An error loop in a real GTK3 app becomes a bubble you can click (#9: sources + offer bubble).

Run in headless-shell.sh with the system python3. The real `gnome_offers` watcher process listens to
AT-SPI; a GTK3 fixture raises two real error dialogs; the detector offers; the bubble is drawn on a
real frame; a real click on No is answered and the state file says so. Neither half alone proves
the two work together.
"""

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = Path(HERE).parent.parent
sys.path[:0] = [HERE]
from shellkit import App, Shell, find_pixels, pump, pump_until  # noqa: E402

BUTTON_BG = (0x3A, 0x3A, 0x52)
results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}".rstrip(), flush=True)


state_home = tempfile.mkdtemp()
os.environ["XDG_STATE_HOME"] = state_home  # never the maintainer's real state
config = Path(os.environ["XDG_CONFIG_HOME"]) / "ya-bro"
state_file = Path(state_home) / "ya-bro" / "struggle.json"
sys.path.insert(0, str(ROOT / "src"))
from ya_bro import struggle  # noqa: E402

det = struggle.Detector(time.time, state_file)
APP = "io.github.ahmedyousrisobhi.YaBroStruggleGtk3"
det.opt_in(APP)

sh = Shell()  # owns Core: "a step loop is running"
sh.start_input()
proc = subprocess.Popen(
    ["/usr/bin/python3", "-m", "ya_bro.platform.gnome_offers", "--seconds", "120"],
    env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
)  # fmt: skip
out = []
import threading  # noqa: E402

threading.Thread(target=lambda: [out.append(ln) for ln in proc.stdout], daemon=True).start()
check("the watcher starts", pump_until(lambda: any("watching" in ln for ln in out), 30), str(out))

sh.release_core()
fixture = App(os.path.join(HERE, "apps", "struggle_gtk3_fixture.py"))  # two error dialogs

r = sh.ratio


def button_pixels():
    return find_pixels(sh.grab(), BUTTON_BG, 6)


pts = []


def drawn():
    global pts
    pts = button_pixels()
    return len(pts) > 200


shown = pump_until(drawn, 40, step=0.5)
check("two real error dialogs make the bubble appear", shown, str(out[-4:]))
pump(0.7)
pts = button_pixels()
xs = sorted({x for x, _ in pts})
runs = []
for x in xs:
    if runs and x - runs[-1][1] <= 3:
        runs[-1][1] = x
    else:
        runs.append([x, x])
runs = [run for run in runs if run[1] - run[0] >= 10]  # drop stray matches in the desktop
check("three buttons", len(runs) == 3, str(runs))
if len(runs) == 3:
    y = sum(p[1] for p in pts) / len(pts) / r
    sh.click((runs[1][0] + runs[1][1]) / 2 / r, y)  # No
    ok = pump_until(lambda: any("struggle_answer" in ln for ln in out), 20)
    check("the answer is logged by the watcher", ok, str(out[-3:]))
    pump(1.5)
    saved = struggle.Detector(time.time, state_file).stats()
    check("the state file has the No", saved["no"] == 1 and saved["yes"] == 0, str(saved))
    check("the screen is clear again", pump_until(lambda: len(button_pixels()) < 50, 15, step=1.0))
fixture.proc.terminate()
proc.terminate()
try:
    proc.wait(10)
except subprocess.TimeoutExpired:
    proc.kill()
sys.exit(0 if all(results) else 1)
