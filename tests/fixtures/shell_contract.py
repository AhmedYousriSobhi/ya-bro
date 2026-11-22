"""Contract checks for the Ya-Bro Shell extension, run inside scripts/dev/headless-shell.sh.

System python3 (needs PyGObject). Prints one line per check and exits non-zero on any failure.
"""

import os
import subprocess
import sys
import time

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib  # noqa: E402

PREFIX = "io.github.ahmedyousrisobhi.YaBro"
DEST = f"{PREFIX}.Shell"
PATH = "/io/github/ahmedyousrisobhi/YaBro/Shell"
BRIDGE = f"{DEST}.Bridge1"
OVERLAY = f"{DEST}.Overlay1"
HERE = os.path.dirname(os.path.abspath(__file__))

results = []


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


def call(conn, iface, method, params=None, sig=None, timeout=5000):
    return conn.call_sync(
        DEST,
        PATH,
        iface,
        method,
        params,
        GLib.VariantType(sig) if sig else None,
        Gio.DBusCallFlags.NONE,
        timeout,
        None,
    )


def get_prop(conn, name):
    return call(conn, OVERLAY, "GetState").unpack()[0][name]


def error_of(fn):
    try:
        fn()
        return None
    except GLib.Error as e:
        return e.message


core = Gio.bus_get_sync(Gio.BusType.SESSION, None)
other = Gio.DBusConnection.new_for_address_sync(
    os.environ["DBUS_SESSION_BUS_ADDRESS"],
    Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
    None,
    None,
)

for _ in range(60):
    if core.call_sync(
        "org.freedesktop.DBus",
        "/org/freedesktop/DBus",
        "org.freedesktop.DBus",
        "NameHasOwner",
        GLib.Variant("(s)", (DEST,)),
        None,
        Gio.DBusCallFlags.NONE,
        2000,
        None,
    ).unpack()[0]:
        break
    pump(0.5)

# 1. Non-peer is denied before core owns its name; extension is on the bus.
err = error_of(lambda: call(other, BRIDGE, "GetInfo"))
check("non-peer GetInfo denied", err is not None and "AccessDenied" in err, err or "")

# 2. Become core.
Gio.bus_own_name_on_connection(core, f"{PREFIX}.Core", Gio.BusNameOwnerFlags.NONE, None, None)
pump(1.0)
info = call(core, BRIDGE, "GetInfo").unpack()[0]
check(
    "core GetInfo",
    info.get("api") == 1,
    str({k: info[k] for k in ("api", "shell_version", "layout_mode")}),
)
err = error_of(lambda: call(other, BRIDGE, "ListWindows"))
check("non-peer ListWindows still denied", err is not None and "AccessDenied" in err)
err = error_of(lambda: call(other, OVERLAY, "ShowStep", GLib.Variant("(a{sv})", ({},))))
check("non-peer ShowStep denied", err is not None and "AccessDenied" in err)

# 3. A real window shows up, with geometry and without a title.
fixture = subprocess.Popen(
    ["/usr/bin/python3", os.path.join(HERE, "apps", "gtk4_fixture.py")],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
win = None
for _ in range(40):
    pump(0.25)
    wins = call(core, BRIDGE, "ListWindows").unpack()[0]
    win = next((w for w in wins if w["pid"] == fixture.pid and w["frame"][2] > 0), None)
    if win:
        break
check("fixture window listed", win is not None)
if win:
    check(
        "window has frame and app_id and no title",
        win["frame"][2] > 0 and "title" not in win and bool(win["app_id"]),
        f"frame={win['frame']} buffer={win['buffer']} app_id={win['app_id']}",
    )
    title = call(core, BRIDGE, "GetWindowTitle", GLib.Variant("(tu)", (win["id"], 0))).unpack()[0]
    check("GetWindowTitle returns a string (focus gating not yet asserted)", isinstance(title, str))


# 3b. Per-app scoping (#43): default-deny. With an empty allowlist nothing is listed or readable.
def set_allowed(value):
    subprocess.run(
        [
            "gsettings",
            "--schemadir",
            os.path.join(HERE, "..", "..", "extension", "schemas"),
            "set",
            "org.gnome.shell.extensions.ya-bro",
            "allowed-apps",
            value,
        ],
        check=True,
    )
    pump(0.5)


if win:
    set_allowed("[]")
    wins = call(core, BRIDGE, "ListWindows").unpack()[0]
    check("empty allowlist: no windows listed", not any(w["pid"] == fixture.pid for w in wins))
    title = call(core, BRIDGE, "GetWindowTitle", GLib.Variant("(tu)", (win["id"], 0))).unpack()[0]
    check("empty allowlist: title refused", title == "")
    err = error_of(lambda: call(core, BRIDGE, "GetPointer"))
    check("empty allowlist: pointer refused", err is not None)
    set_allowed('["io.github.ahmedyousrisobhi.YaBroFixture"]')
    wins = call(core, BRIDGE, "ListWindows").unpack()[0]
    check("allowed app listed again", any(w["pid"] == fixture.pid for w in wins))

# 3c. Token scope (spike #47): a window whose app is NOT allowed enters scope only while its title
# carries a token that core pushed, and leaves the moment the title changes.
TOKEN = "yb-" + "a1b2c3d4e5f6a7b8"
changes = []
core.signal_subscribe(
    None,
    BRIDGE,
    "WindowsChanged",
    PATH,
    None,
    Gio.DBusSignalFlags.NONE,
    lambda *a: changes.append((time.monotonic(), a[5].unpack())),
)
tab = subprocess.Popen(
    ["/usr/bin/python3", os.path.join(HERE, "apps", "title_fixture.py")],
    stdin=subprocess.PIPE,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    text=True,
)


def listed():
    wins = call(core, BRIDGE, "ListWindows").unpack()[0]
    return next((w for w in wins if w["pid"] == tab.pid), None)


def wait_for(pred, limit=5.0):
    start = time.monotonic()
    while time.monotonic() - start < limit:
        pump(0.01)
        if pred():
            return time.monotonic() - start
    return None


def set_title(text):
    tab.stdin.write(text + "\n")
    tab.stdin.flush()


pump(2.0)
check("token scope: unlisted without token", listed() is None)
err = error_of(lambda: call(other, BRIDGE, "SetScopeTokens", GLib.Variant("(as)", ([TOKEN],))))
check("token scope: non-core cannot set tokens", err is not None and "AccessDenied" in err)
call(core, BRIDGE, "SetScopeTokens", GLib.Variant("(as)", (["short", TOKEN],)))
set_title("page " + TOKEN)
t_in = wait_for(lambda: listed() is not None)
check("token scope: listed once title has the token", t_in is not None, f"{t_in}s")
n = len(changes)
t0 = time.monotonic()
set_title("other tab")
t_out = wait_for(lambda: listed() is None)
check("token scope: dropped after title changes", t_out is not None, f"{t_out}s")
pump(0.3)
sig_out = next((t - t0 for t, v in changes[n:] if v[1]), None)
check("token scope: WindowsChanged removal emitted", sig_out is not None, f"{sig_out}s")
set_title("again " + TOKEN)
wait_for(lambda: listed() is not None)
call(core, BRIDGE, "SetScopeTokens", GLib.Variant("(as)", ([],)))
check("token scope: cleared tokens drop it", listed() is None)
call(core, BRIDGE, "SetScopeTokens", GLib.Variant("(as)", (["short"],)))
set_title("page short")
pump(0.3)
check("token scope: short token ignored", listed() is None)
tab.stdin.close()
tab.wait(timeout=5)

mons = call(core, BRIDGE, "GetMonitors").unpack()[0]
check("monitors", len(mons) == 1 and mons[0][3:5] == (1280, 800) and mons[0][6], str(mons))

# 4. Overlay lifecycle.
check("overlay hidden initially", get_prop(core, "visible") is False)
target = tuple(win["frame"]) if win else (100, 100, 200, 100)
args = {
    "target": GLib.Variant("(iiii)", target),
    "ring": GLib.Variant("s", "confident"),
    "text": GLib.Variant("s", "x" * 500),
    "buttons": GLib.Variant("as", ["next", "bogus", "stop"]),
    "dir": GLib.Variant("s", "ltr"),
}
serial = call(core, OVERLAY, "ShowStep", GLib.Variant("(a{sv})", (args,))).unpack()[0]
check("ShowStep returns serial and shows", serial >= 1 and get_prop(core, "visible") is True)
call(core, OVERLAY, "Hide")
check(
    "Hide hides, idempotent",
    get_prop(core, "visible") is False and call(core, OVERLAY, "Hide") is not None,
)

# 5. Rate limit: > 60 draw calls in one second get LimitsExceeded.
errs = 0
for _ in range(80):
    if error_of(
        lambda: call(core, OVERLAY, "FlyPointer", GLib.Variant("((ii)u)", ((10, 10), 100)))
    ):
        errs += 1
check("draw rate limit (60/s)", errs > 0, f"limited={errs}/80")
pump(1.2)
call(core, OVERLAY, "Hide")

# 6. Dead-man: no Ping for > 6 s hides the overlay.
call(core, OVERLAY, "ShowStep", GLib.Variant("(a{sv})", ({"text": GLib.Variant("s", "hi")},)))
check("shown before dead-man wait", get_prop(core, "visible") is True)
t0 = time.time()
while get_prop(core, "visible") and time.time() - t0 < 12:
    pump(0.2)
elapsed = time.time() - t0
check(
    "dead-man hides within 8 s",
    get_prop(core, "visible") is False and elapsed <= 8,
    f"{elapsed:.1f}s",
)

# 7. Ping keeps it alive.
call(core, OVERLAY, "ShowStep", GLib.Variant("(a{sv})", ({"text": GLib.Variant("s", "hi")},)))
for _ in range(5):
    pump(2.0)
    call(core, OVERLAY, "Ping", GLib.Variant("(u)", (1,)))
check("Ping keeps overlay visible (10 s)", get_prop(core, "visible") is True)

# 7b. Disable/enable cycles: extension must keep working and report no errors.
EXT = "org.gnome.Shell.Extensions"
UUID = os.environ["YB_UUID"]


def ext(method, *a, sig="(s)"):
    return core.call_sync(
        "org.gnome.Shell.Extensions",
        "/org/gnome/Shell/Extensions",
        EXT,
        method,
        GLib.Variant(sig, a),
        None,
        Gio.DBusCallFlags.NONE,
        5000,
        None,
    ).unpack()


cycles_ok = True
for _ in range(20):
    ext("DisableExtension", UUID)
    pump(0.3)
    ext("EnableExtension", UUID)
    pump(0.5)
    try:
        cycles_ok &= call(core, BRIDGE, "GetInfo").unpack()[0].get("api") == 1
    except GLib.Error:
        cycles_ok = False
errors = ext("GetExtensionErrors", UUID)[0]
check("20 disable/enable cycles: still serving, no errors", cycles_ok and not errors, str(errors))

# 8. Core name lost -> hidden within 2 s.
core.close_sync(None)
pump(0.1)
probe = Gio.DBusConnection.new_for_address_sync(
    os.environ["DBUS_SESSION_BUS_ADDRESS"],
    Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
    None,
    None,
)
Gio.bus_own_name_on_connection(probe, f"{PREFIX}.Perceiver", Gio.BusNameOwnerFlags.NONE, None, None)
pump(0.5)
check("non-peer cannot GetState", error_of(lambda: call(other, OVERLAY, "GetState")) is not None)
t0 = time.time()
vis = True
while time.time() - t0 < 6:
    pump(0.2)
    vis = get_prop(probe, "visible")
    if not vis:
        break
check("core killed -> overlay hidden", vis is False, f"{time.time() - t0:.1f}s")

fixture.terminate()
sys.exit(0 if all(results) else 1)
