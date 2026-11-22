"""Hot-load the extension through Looking Glass with injected keys (#57). Run inside headless-shell.sh
started WITHOUT the extension linked; the test links it after the shell is up (a late install)."""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "src"))
from shellkit import Gio, GLib, Shell, pump  # noqa: E402

from ya_bro.platform.linux_setup import EXT_UUID, HOTLOAD_SNIPPET  # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}".rstrip(), flush=True)


conn = Gio.bus_get_sync(Gio.BusType.SESSION, None)


def state():
    try:
        r = conn.call_sync(
            "org.gnome.Shell.Extensions",
            "/org/gnome/Shell/Extensions",
            "org.gnome.Shell.Extensions",
            "GetExtensionInfo",
            GLib.Variant("(s)", (EXT_UUID,)),
            None,
            0,
            3000,
            None,
        ).unpack()[0]
        return r.get("state")
    except GLib.Error as e:
        return e.message


sh = Shell.__new__(Shell)  # Shell() would wait for the extension, which is not loaded yet
sh.conn, sh.events = conn, []
_orig = Shell.call


def _call(self, iface, method, *a, **k):  # start_input calibrates through the extension
    if method == "GetMonitors":
        return [[[0, 0, 0, 1280, 800, 1.0, True]]]
    if method == "GetPointer":
        return [(400, 300)]
    return _orig(self, iface, method, *a, **k)


Shell.call = _call
sh.start_input()
Shell.call = _orig

root = os.path.join(HERE, "..", "..", "extension")
os.symlink(
    os.path.abspath(root),
    os.path.join(os.environ["XDG_DATA_HOME"], "gnome-shell/extensions", EXT_UUID),
)
os.system(f"gsettings set org.gnome.shell enabled-extensions \"['{EXT_UUID}']\"")
pump(2)
check(
    "late install: shell does not know the extension",
    state() is None,
    str(state()),
)
ALT, F2, RET = 0xFFE9, 0xFFBF, 0xFF0D


def typ(text):
    for ch in text:
        sh.tap(ord(ch))
        pump(0.03)


sh.key(ALT, True)
sh.tap(F2)
sh.key(ALT, False)
pump(1.0)
typ("lg")
sh.tap(RET)
pump(2.0)
typ(HOTLOAD_SNIPPET)
sh.tap(RET)
pump(3.0)
check("Looking Glass snippet loads the extension (ENABLED)", state() == 1.0, str(state()))
try:
    info = conn.call_sync(
        "io.github.ahmedyousrisobhi.YaBro.Shell",
        "/io/github/ahmedyousrisobhi/YaBro/Shell",
        "io.github.ahmedyousrisobhi.YaBro.Shell.Bridge1",
        "GetInfo",
        None,
        None,
        0,
        3000,
        None,
    )
    check("Bridge1 answers after the hot load", True, str(info.unpack()[0]["api"]))
except GLib.Error as e:
    check("Bridge1 answers after the hot load", "AccessDenied" in e.message, e.message[:80])
sys.exit(0 if all(results) else 1)
