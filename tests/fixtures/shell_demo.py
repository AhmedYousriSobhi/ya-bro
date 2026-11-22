"""Runs gnome_demo.py watch/point against the allowed GTK4 fixture inside headless-shell.sh (#53)."""

import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DEMO = os.path.join(HERE, "..", "..", "src", "ya_bro", "platform", "gnome_demo.py")
results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}".rstrip(), flush=True)


def demo(*args, timeout=30):
    r = subprocess.run(
        ["/usr/bin/python3", DEMO, *args],
        input="\n",  # the token line broctl sends; empty here
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return r.returncode, r.stdout + r.stderr


rc, out = demo("watch", "2")
check("watch with no window says so", rc == 0 and "no allowed window" in out, out.strip()[:80])

fixture = subprocess.Popen(
    ["/usr/bin/python3", os.path.join(HERE, "apps", "gtk4_fixture.py")],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
time.sleep(4)
rc, out = demo("watch", "2")
check(
    "watch reports the allowed window", rc == 0 and "+ in scope: io.github" in out, out.strip()[:90]
)
rc, out = demo("point", "4", "hello from the bro")
check("point shows the overlay", "visible=True" in out, out.strip()[:120])
lines = [ln for ln in out.splitlines() if ln.startswith("overlay")]
check(
    "point ends hidden (last overlay line)",
    lines[-1] == "overlay hidden: visible=False",
    str(lines[-2:]),
)
check("point exits cleanly", rc == 0, f"rc={rc}")
check("point prints no warnings", "Warning" not in out and "Traceback" not in out, out[-80:])
fixture.terminate()
sys.exit(0 if all(results) else 1)
