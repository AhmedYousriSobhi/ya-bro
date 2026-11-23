"""Plain words to a plan on the real Calculator, through a stand-in model (#5). Run in headless-shell.sh.

The model is a local HTTP server with a canned answer; everything else is real: the isolated shell,
GNOME Calculator, the AT-SPI walk that tells the brain what is on screen, the consent gate, the sent
list, the request over a real socket, and the plan landing on real controls.
"""

import asyncio
import json
import os
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, "..", "..", "src")]
cfg = tempfile.mkdtemp()
os.environ.update(XDG_CONFIG_HOME=cfg, XDG_STATE_HOME=cfg + "/state", XDG_CACHE_HOME=cfg + "/cache")

from shellkit import Shell  # noqa: E402

from ya_bro import privacy  # noqa: E402
from ya_bro.platform import gnome_show  # noqa: E402
from ya_bro.platform.gnome_adapters import AtspiPerception, GnomeBridge  # noqa: E402

APP = "org.gnome.Calculator"
requests = []
results = []
PLAN = {
    "steps": [
        {
            "intent": "press 7",
            "narration": "Press 7.",
            "risk": 0,
            "target": {"role": "button", "name": "7"},
        },
        {
            "intent": "press times",
            "narration": "Press ×.",
            "risk": 0,
            "target": {"role": "button", "name": "×"},
        },
    ]
}


class Model(BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers["content-length"])
        requests.append(json.loads(self.rfile.read(n)))
        out = json.dumps(
            {"content": [{"type": "tool_use", "name": "propose_plan", "input": PLAN}]}
        ).encode()
        self.send_response(200)
        self.send_header("content-length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *a):
        pass


def check(name, ok, detail=""):
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}".rstrip(), flush=True)


async def main():
    server = HTTPServer(("127.0.0.1", 0), Model)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test-0123456789abcdef"
    os.environ["ANTHROPIC_BASE_URL"] = f"http://127.0.0.1:{server.server_port}"
    env = dict(os.environ, GTK_A11Y="atspi")
    env.pop("DISPLAY", None)
    calc = subprocess.Popen(
        ["gnome-calculator"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    sh = Shell()
    sh.start_input()
    bridge = GnomeBridge(sh.conn)
    await asyncio.sleep(9)
    win = next(w for w in sh.windows() if w["app_id"] == APP)
    fx, fy, fw, _fh = win["frame"]
    for _ in range(20):
        sh.click(fx + fw // 2, fy + 150)  # focus via the empty display area
        await asyncio.sleep(0.5)
        if any(w["focused"] for w in sh.windows()):
            break
    try:
        # No consent yet: the model is not asked.
        try:
            await gnome_show.ask("what is seven times six", APP, bridge)
            check("without consent nothing is planned", False)
        except Exception as e:
            check("without consent the model is not asked", not requests, str(e))
        privacy.save_consent(privacy.Consent(privacy.CONSENT_VERSION, True, False))

        plan = await gnome_show.ask("what is seven times six", APP, bridge)
        check("a plan comes back from the model", len(plan.steps) == 2 and len(requests) == 1)
        content = requests[0]["messages"][0]["content"] if requests else ""
        check("the model was told what is really on screen", "button: 7" in content, content[:80])
        check("including the times key", "button: ×" in content)
        check("nothing of another app", "button: Activities" not in content)
        check(
            "the ledger lists the request by kind and size",
            [r["kind"] for r in privacy.read_sent()] == ["question", "elements", "pack"],
            str([r["kind"] for r in privacy.read_sent()]),
        )
        check("the ledger holds no words", "seven" not in privacy.sent_path().read_text())

        perception = AtspiPerception(bridge)
        for s in plan.steps:
            refs = await perception.find(APP, s.target.role, s.target.name)
            rect = await perception.locate(refs[0]) if refs else None
            check(f"the model's target {s.target.name!r} is a real control", rect is not None)

        before = len(requests)
        mult = await gnome_show.ask("multiply 7 by 6", APP, bridge)
        check(
            "a pack task answers without asking the model",
            len(requests) == before and len(mult.steps) > 2,
        )
    finally:
        calc.terminate()
        server.shutdown()


asyncio.run(
    main(), loop_factory=__import__("gi.events").events.GLibEventLoopPolicy().new_event_loop
)
sys.exit(0 if all(results) else 1)
