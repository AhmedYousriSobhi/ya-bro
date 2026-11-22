"""Spike S8 step 2: a real browser tab as the scoped target. Run inside scripts/dev/headless-shell.sh.

Page A (allowed origin) fetches a token (only reachable same-origin with the X-Scope-Token header, so a page
on another origin is stopped by CORS) and puts it in its title. Page B (other origin) tries to read it
and is the tab we switch to. Uses Playwright's Chrome for Testing (not a snap) with a throwaway profile.
"""

import glob
import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib  # noqa: E402

PREFIX = "io.github.ahmedyousrisobhi.YaBro"
DEST = f"{PREFIX}.Shell"
PATH = "/io/github/ahmedyousrisobhi/YaBro/Shell"
BRIDGE = f"{DEST}.Bridge1"
TOKEN = "yb-" + secrets.token_hex(8)
results = []
log = {"issued": 0, "refused": 0, "preflight": 0, "pages": 0}


def check(name, ok, detail=""):
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}".rstrip(), flush=True)


def pump(seconds):
    end = time.time() + seconds
    ctx = GLib.MainContext.default()
    while time.time() < end:
        while ctx.iteration(False):
            pass
        time.sleep(0.02)


chrome = (
    glob.glob(os.path.expanduser("~/.cache/ms-playwright/chromium-*/chrome-linux*/chrome")) or [""]
)[-1]
if not chrome:
    print("SKIP  no non-snap Chrome for Testing found")
    sys.exit(0)

PAGE_A = """<!doctype html><title>loading</title><script>
fetch('/token',{headers:{'X-Scope-Token':'1'}}).then(r=>r.text()).then(t=>{document.title='workbench '+t});
</script>"""
PAGE_B = """<!doctype html><title>other site</title><script>
fetch('http://127.0.0.1:%d/token',{headers:{'X-Scope-Token':'1'}}).then(r=>r.text()).then(()=>{document.title='LEAKED'}).catch(()=>{document.title='other site (blocked)'});
</script>"""


class Handler(BaseHTTPRequestHandler):
    allowed_origin = ""
    page = ""

    def log_message(self, *a):
        pass

    def do_OPTIONS(self):  # preflight from another origin: refuse, no CORS headers
        log["preflight"] += 1
        self.send_response(403)
        self.end_headers()

    def do_GET(self):
        if self.path == "/token":
            origin = self.headers.get("Origin")
            if self.headers.get("X-Scope-Token") == "1" and origin in (
                None,
                type(self).allowed_origin,
            ):
                log["issued"] += 1
                body = TOKEN.encode()
            else:
                log["refused"] += 1
                self.send_response(403)
                self.end_headers()
                return
        else:
            log["pages"] += 1
            body = type(self).page.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html" if self.path != "/token" else "text/plain")
        self.end_headers()
        self.wfile.write(body)


def serve(page):
    handler = type("H", (Handler,), {"page": page})
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    handler.allowed_origin = f"http://127.0.0.1:{srv.server_port}"
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


srv_a = serve(PAGE_A)
port_a = srv_a.server_port
srv_b = serve("")
srv_b.RequestHandlerClass.page = PAGE_B % port_a

core = Gio.bus_get_sync(Gio.BusType.SESSION, None)
Gio.bus_own_name_on_connection(core, f"{PREFIX}.Core", Gio.BusNameOwnerFlags.NONE, None, None)
pump(1.0)


def call(method, params=None):
    return core.call_sync(
        DEST, PATH, BRIDGE, method, params, None, Gio.DBusCallFlags.NONE, 5000, None
    )


def windows():
    return call("ListWindows").unpack()[0]


def wait_for(pred, limit=15.0):
    start = time.monotonic()
    while time.monotonic() - start < limit:
        pump(0.01)
        if pred():
            return time.monotonic() - start
    return None


def cdp(path):
    method = "PUT" if path.startswith("/json/new") else "GET"
    req = urllib.request.Request(f"http://127.0.0.1:{dbg}{path}", method=method)
    with urllib.request.urlopen(req, timeout=5) as r:
        raw = r.read()
    try:
        return json.loads(raw or b"null")
    except ValueError:
        return raw.decode()  # /json/activate answers with plain text


profile = tempfile.mkdtemp(prefix="yb-chrome-")
with __import__("socket").socket() as _s:
    _s.bind(("127.0.0.1", 0))
    dbg = _s.getsockname()[1]  # a free port, not a guess that may hit another service
env = {k: v for k, v in os.environ.items() if k != "DISPLAY"}
proc = subprocess.Popen(
    [
        chrome,
        f"--user-data-dir={profile}",
        f"--remote-debugging-port={dbg}",
        "--ozone-platform=wayland",
        "--disable-gpu",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-sync",
        "--disable-background-networking",
        "--deny-permission-prompts",
        "--disable-extensions",
        "--no-proxy-server",
        "--no-sandbox",
        f"http://127.0.0.1:{port_a}/",
    ],
    env=env,
    stdout=subprocess.DEVNULL,
    stderr=open(os.path.join(profile, "chrome.err"), "w"),
)
try:

    def cdp_up():
        try:
            return cdp("/json/version") is not None
        except OSError:
            return False

    check(
        "Chrome for Testing started (CDP up)",
        wait_for(cdp_up, 40) is not None,
        os.path.basename(os.path.dirname(chrome)),
    )
    # Tokens are not pushed yet: the browser must be invisible even though its window exists.
    wait_for_page = wait_for(lambda: log["pages"] > 1, 90)
    pump(3.0)
    check(
        "browser window exists but is invisible without a token",
        windows() == [],
        str(len(windows())),
    )
    call("SetScopeTokens", GLib.Variant("(as)", ([TOKEN],)))
    t_in = wait_for(lambda: len(windows()) == 1, 15)
    check(
        "tab A (token in title) in scope",
        t_in is not None,
        f"{t_in}s app_id={[w['app_id'] for w in windows()]}",
    )
    check(
        "token issued to page A (same-origin, X-Scope-Token header)", log["issued"] >= 1, str(log)
    )

    tab_a = next(t for t in cdp("/json") if t["type"] == "page")
    tab_b = cdp(f"/json/new?http://127.0.0.1:{srv_b.server_port}/")  # activates the new tab
    t0 = time.monotonic()
    t_out = wait_for(lambda: len(windows()) == 0, 10)
    check("switch to tab B: window out of scope", t_out is not None, f"{t_out}s")
    pump(1.0)
    title_b = next((t["title"] for t in cdp("/json") if t["id"] == tab_b["id"]), "")
    check(
        "tab B could not read the token (CORS)",
        "LEAKED" not in title_b and log["preflight"] >= 1,
        f"title={title_b!r} {log}",
    )

    cdp(f"/json/activate/{tab_a['id']}")
    t_back = wait_for(lambda: len(windows()) == 1, 10)
    check("switch back to tab A: in scope again", t_back is not None, f"{t_back}s")
    call("SetScopeTokens", GLib.Variant("(as)", ([],)))
    check("tokens cleared: out of scope", wait_for(lambda: len(windows()) == 0, 5) is not None)
finally:
    print(
        "DEBUG chrome stderr:", open(os.path.join(profile, "chrome.err")).read()[-1500:], flush=True
    )
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
    shutil.rmtree(profile, ignore_errors=True)

sys.exit(0 if all(results) else 1)
