"""Helpers for the S1 measurements: D-Bus calls, input injection (Mutter RemoteDesktop), frame grabs.

Runs inside scripts/dev/headless-shell.sh with system python3. Test-only code: the extension itself
has no injection or capture methods (ADR-0023 §11.4).
"""

import json
import os
import subprocess
import tempfile
import threading
import time

import gi

gi.require_version("Gio", "2.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf, Gio, GLib  # noqa: E402

PREFIX = "io.github.ahmedyousrisobhi.YaBro"
DEST = f"{PREFIX}.Shell"
PATH = "/io/github/ahmedyousrisobhi/YaBro/Shell"
BRIDGE = f"{DEST}.Bridge1"
OVERLAY = f"{DEST}.Overlay1"
RD = "org.gnome.Mutter.RemoteDesktop"
SC = "org.gnome.Mutter.ScreenCast"
BTN_LEFT = 0x110
KEY = {
    "super": 0xFFEB,
    "shift": 0xFFE1,
    "escape": 0xFF1B,
    "ctrl": 0xFFE3,
    "alt": 0xFFE9,
    "f11": 0xFFC8,
}


def pump(seconds):
    end = time.time() + seconds
    ctx = GLib.MainContext.default()
    while time.time() < end:
        while ctx.iteration(False):
            pass
        time.sleep(0.005)


def pump_until(cond, timeout, step=0.01):
    end = time.time() + timeout
    while time.time() < end:
        pump(step)
        if cond():
            return True
    return cond()


class Shell:
    """Core-role client of the extension, plus injector and grabber."""

    def __init__(self):
        self.conn = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        Gio.bus_own_name_on_connection(
            self.conn, f"{PREFIX}.Core", Gio.BusNameOwnerFlags.NONE, None, None
        )
        self.events = []  # (monotonic, signal name, params)
        for iface in (BRIDGE, OVERLAY):
            self.conn.signal_subscribe(
                DEST, iface, None, PATH, None, Gio.DBusSignalFlags.NONE, self._on_signal
            )
        pump_until(lambda: self._has_owner(DEST), 30)
        pump(1.0)

    def _on_signal(self, _c, _s, _p, _i, name, params, *_):
        self.events.append((time.monotonic(), name, params.unpack()))

    def _has_owner(self, name):
        return self.conn.call_sync(
            "org.freedesktop.DBus",
            "/org/freedesktop/DBus",
            "org.freedesktop.DBus",
            "NameHasOwner",
            GLib.Variant("(s)", (name,)),
            None,
            0,
            2000,
            None,
        ).unpack()[0]

    def call(self, iface, method, args=None, dest=DEST, path=PATH, timeout=8000):
        return self.conn.call_sync(
            dest, path, iface, method, args, None, Gio.DBusCallFlags.NONE, timeout, None
        ).unpack()

    # -- extension API
    def windows(self):
        return self.call(BRIDGE, "ListWindows")[0]

    def info(self):
        return self.call(BRIDGE, "GetInfo")[0]

    def state(self):
        return self.call(OVERLAY, "GetState")[0]

    def show_step(self, **kw):
        v = {k: GLib.Variant(s, val) for k, (s, val) in kw.items()}
        return self.call(OVERLAY, "ShowStep", GLib.Variant("(a{sv})", (v,)))[0]

    def hide(self):
        self.call(OVERLAY, "Hide")

    def ping(self):
        self.call(OVERLAY, "Ping", GLib.Variant("(u)", (1,)))

    def pointer(self):
        return self.call(BRIDGE, "GetPointer")[0]

    # -- Mutter RemoteDesktop + ScreenCast (test-only injection and frame source)
    def start_input(self, connector=None):
        if connector is None:  # headless shells use Meta-0; a devkit shell names its own monitor
            dc = "org.gnome.Mutter.DisplayConfig"
            state = self.call(dc, "GetCurrentState", None, dc, "/org/gnome/Mutter/DisplayConfig")
            connector = state[1][0][0][0]
        self.rd = self.call(RD, "CreateSession", None, RD, "/org/gnome/Mutter/RemoteDesktop")[0]
        sid = self.conn.call_sync(
            RD,
            self.rd,
            "org.freedesktop.DBus.Properties",
            "Get",
            GLib.Variant("(ss)", (RD + ".Session", "SessionId")),
            None,
            0,
            5000,
            None,
        ).unpack()[0]
        sc = self.call(
            SC,
            "CreateSession",
            GLib.Variant("(a{sv})", ({"remote-desktop-session-id": GLib.Variant("s", sid)},)),
            SC,
            "/org/gnome/Mutter/ScreenCast",
        )[0]
        self.stream = self.call(
            SC + ".Session", "RecordMonitor", GLib.Variant("(sa{sv})", (connector, {})), SC, sc
        )[0]
        self.node = {}

        def on_added(_c, _s, path, _i, name, params, *_):
            if name == "PipeWireStreamAdded":
                self.node["n"] = params.unpack()[0]

        self.conn.signal_subscribe(
            None, SC + ".Stream", None, None, None, Gio.DBusSignalFlags.NONE, on_added
        )
        self.call(RD + ".Session", "Start", None, RD, self.rd)
        pump_until(lambda: "n" in self.node, 10)
        # Injected coordinates are in stream pixels; calibrate against the shell's own pointer so the
        # harness works at any monitor scale instead of assuming 1:1.
        self.ratio = 1.0
        self._rd("NotifyPointerMotionAbsolute", GLib.Variant("(sdd)", (self.stream, 400.0, 300.0)))
        pump(0.2)
        # Stream space is physical pixels: logical * monitor scale. Use the exact scale, and only use
        # the measured value (integer-rounded) as a sanity check.
        scale = self.call(BRIDGE, "GetMonitors")[0][0][5]
        try:
            px = self.pointer()[0]
        except GLib.Error:  # GetPointer is refused while no allowed app is focused (#43)
            px = 0
        if px > 0 and abs(400.0 / px - scale) > 0.05:
            raise RuntimeError(
                f"pointer calibration disagrees: measured {400.0 / px:.3f}, scale {scale}"
            )
        self.ratio = scale

    def _rd(self, method, args):
        self.call(RD + ".Session", method, args, RD, self.rd)

    def move(self, x, y):
        r = self.ratio  # stream pixels per logical pixel (the monitor scale)
        self._rd(
            "NotifyPointerMotionAbsolute",
            GLib.Variant("(sdd)", (self.stream, float(x) * r, float(y) * r)),
        )

    def click(self, x=None, y=None):
        if x is not None:
            self.move(x, y)
        self._rd("NotifyPointerButton", GLib.Variant("(ib)", (BTN_LEFT, True)))
        self._rd("NotifyPointerButton", GLib.Variant("(ib)", (BTN_LEFT, False)))

    def key(self, sym, down):
        self._rd(
            "NotifyKeyboardKeysym",
            GLib.Variant("(ub)", (KEY[sym] if isinstance(sym, str) else sym, down)),
        )

    def tap(self, sym):
        self.key(sym, True)
        self.key(sym, False)

    def grab(self):
        """One frame of the monitor as a GdkPixbuf.

        A static screen produces no new frames, so ask for 3 buffers briefly and fall back to 1.
        """
        f = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        f.close()
        for n, limit in ((3, 6), (1, 15)):
            try:
                subprocess.run(
                    [
                        "gst-launch-1.0",
                        "-q",
                        "pipewiresrc",
                        f"path={self.node['n']}",
                        f"num-buffers={n}",
                        "!",
                        "videoconvert",
                        "!",
                        "pngenc",
                        "snapshot=true",
                        "!",
                        "filesink",
                        f"location={f.name}",
                    ],
                    check=True,
                    capture_output=True,
                    timeout=limit,
                )
                break
            except subprocess.TimeoutExpired:
                if n == 1:
                    raise
        pb = GdkPixbuf.Pixbuf.new_from_file(f.name)
        os.unlink(f.name)
        return pb


class App:
    """A fixture app process with its JSONL stdout collected on a thread."""

    def __init__(self, script, args=(), env=None):
        e = dict(os.environ, GTK_A11Y="atspi", **(env or {}))
        if e.get("GDK_BACKEND") == "x11":
            # Only ever the harness's private Xwayland; never fall back to a DISPLAY from the caller.
            if not os.environ.get("YB_XDISPLAY"):
                raise RuntimeError(
                    "x11 requested but no private Xwayland display (run with YB_X11=1)"
                )
            e["DISPLAY"] = os.environ["YB_XDISPLAY"]
            e["XAUTHORITY"] = os.environ.get("YB_XAUTH", "")
        else:
            e.pop("DISPLAY", None)
        self.proc = subprocess.Popen(
            ["/usr/bin/python3", script, *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            env=e,
        )
        self.lines = []
        self._t = threading.Thread(target=self._read, daemon=True)
        self._t.start()

    def _read(self):
        for ln in self.proc.stdout:
            try:
                self.lines.append((time.monotonic(), json.loads(ln)))
            except ValueError:
                pass

    def events(self, kind=None, since=0):
        return [e for t, e in self.lines if t >= since and (kind is None or e.get("e") == kind)]

    def close(self):
        self.proc.terminate()
        try:
            self.proc.wait(5)
        except subprocess.TimeoutExpired:
            self.proc.kill()


def find_pixels(pb, rgb, tol=40, rows=None, cols=None):
    """Return pixel coordinates (x, y) whose colour is within tol of rgb, in the given rows/cols."""
    w, h, n, stride = pb.get_width(), pb.get_height(), pb.get_n_channels(), pb.get_rowstride()
    px = pb.get_pixels()
    out = []
    ys = rows if rows is not None else range(h)
    xs = list(cols) if cols is not None else list(range(w))
    for y in ys:
        base = y * stride
        for x in xs:
            i = base + x * n
            if (
                abs(px[i] - rgb[0]) <= tol
                and abs(px[i + 1] - rgb[1]) <= tol
                and abs(px[i + 2] - rgb[2]) <= tol
            ):
                out.append((x, y))
    return out


def atspi_widgets(pid, prefix=("W", "P"), timeout=20):
    """{name: {'window': (x,y,w,h), 'screen': (x,y,w,h)}} for buttons of the app with this pid."""
    gi.require_version("Atspi", "2.0")
    from gi.repository import Atspi

    def walk(node, out, depth=0):
        if depth > 14 or node is None:
            return
        try:
            name = node.get_name() or ""
            if name.startswith(prefix) and node.get_role_name() in (
                "button",
                "push button",
                "toggle button",
                "menu button",
            ):
                ext_w = node.get_extents(Atspi.CoordType.WINDOW)
                ext_s = node.get_extents(Atspi.CoordType.SCREEN)
                out[name] = {
                    "window": (ext_w.x, ext_w.y, ext_w.width, ext_w.height),
                    "screen": (ext_s.x, ext_s.y, ext_s.width, ext_s.height),
                }
            for i in range(node.get_child_count()):
                walk(node.get_child_at_index(i), out, depth + 1)
        except GLib.Error:
            pass

    end = time.time() + timeout
    out = {}
    while time.time() < end:
        desktop = Atspi.get_desktop(0)
        out = {}
        for i in range(desktop.get_child_count()):
            app = desktop.get_child_at_index(i)
            try:
                if app and app.get_process_id() == pid:
                    walk(app, out)
            except GLib.Error:
                pass
        if len([k for k in out if k.startswith("W")]) >= 20:
            break
        time.sleep(0.5)
    return out
