"""Stand-in for core on GNOME (#53): `watch` prints scope changes, `point` draws the ring.

Runs under the system python3 (needs PyGObject), as `python3 gnome_demo.py <watch|point> [seconds]`.
Self-contained on purpose: no ya_bro imports, so `broctl` itself stays dependency-free.
"""

import sys

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib  # noqa: E402

PREFIX = "io.github.ahmedyousrisobhi.YaBro"
DEST = f"{PREFIX}.Shell"
PATH = "/io/github/ahmedyousrisobhi/YaBro/Shell"
BRIDGE = f"{DEST}.Bridge1"
OVERLAY = f"{DEST}.Overlay1"


class Demo:
    def __init__(self):
        self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        self.loop = GLib.MainLoop()
        self.serial = 0
        self.followed = None
        self.shown = None
        self.done = False
        self.hinted = False
        # broctl sends the web-target token on stdin (not argv or env); empty line without one.
        self.token = sys.stdin.readline().strip()

    def push_token(self):
        self.call(BRIDGE, "SetScopeTokens", GLib.Variant("(as)", ([self.token],)))
        return False

    def call(self, iface, method, params=None):
        return self.bus.call_sync(
            DEST, PATH, iface, method, params, None, Gio.DBusCallFlags.NONE, 3000, None
        )

    def become_core(self):
        if self._has_owner():
            sys.exit("another core already runs; stop it first")
        Gio.bus_own_name_on_connection(
            self.bus, f"{PREFIX}.Core", Gio.BusNameOwnerFlags.NONE, None, None
        )
        if self.token:
            GLib.timeout_add(100, self.push_token)
        GLib.timeout_add(500, self.loop.quit)  # let the extension notice the new owner
        self.loop.run()

    def _has_owner(self):
        return self.bus.call_sync(
            "org.freedesktop.DBus",
            "/org/freedesktop/DBus",
            "org.freedesktop.DBus",
            "NameHasOwner",
            GLib.Variant("(s)", (f"{PREFIX}.Core",)),
            None,
            Gio.DBusCallFlags.NONE,
            2000,
            None,
        ).unpack()[0]

    def windows(self):
        try:
            return self.call(BRIDGE, "ListWindows").unpack()[0]
        except GLib.Error as e:
            sys.exit(f"cannot reach the Ya-Bro extension ({e.message}); run: broctl doctor")

    def visible(self):
        return self.call(OVERLAY, "GetState").unpack()[0]["visible"]

    def finish(self, *_):
        if self.done:
            return
        self.done = True
        try:
            self.call(OVERLAY, "Hide")
            if self.shown is not None:
                print(f"overlay hidden: visible={self.visible()}", flush=True)
        except GLib.Error:
            pass
        self.loop.quit()

    def watch(self, seconds):
        seen = {}

        def tick():
            now = {w["id"]: w for w in self.windows()}
            for wid, w in now.items():
                if wid not in seen:
                    frame = tuple(w["frame"])
                    print(
                        f"+ in scope: {w['app_id']} focused={w['focused']} frame={frame}",
                        flush=True,
                    )
            for wid, w in seen.items():
                if wid not in now:
                    print(f"- left scope: {w['app_id']}", flush=True)
            seen.clear()
            seen.update(now)
            return True

        if not self.windows():
            print(
                "no allowed window is open yet (open the app you allowed); watching...", flush=True
            )
        tick()
        GLib.timeout_add(200, tick)
        self.run_for(seconds)

    def point(self, seconds, text):
        def tick():
            if self.done:
                return False
            wins = self.windows()
            # Only the focused allowed window: a ring on a window you cannot see (maximised behind
            # another one) would cover the whole screen for no reason.
            win = next((w for w in wins if w["focused"]), None)
            if win is None:
                if self.shown is not None:
                    self.call(OVERLAY, "Hide")
                    self.shown = None
                if wins and not self.hinted:
                    print(f"click the {wins[0]['app_id']} window to see the ring", flush=True)
                    self.hinted = True
                return True
            key = (win["id"], tuple(win["frame"]))
            if key != self.shown:
                x, y, w, h = win["frame"]
                args = {
                    "target": GLib.Variant("(iiii)", (x, y, w, h)),
                    "ring": GLib.Variant("s", "confident"),
                    "text": GLib.Variant("s", text),
                    "buttons": GLib.Variant("as", ["stop"]),
                    "follow_window": GLib.Variant("t", win["id"]),
                }
                self.call(OVERLAY, "ShowStep", GLib.Variant("(a{sv})", (args,)))
                self.shown = key
                print(f"overlay on {win['app_id']}: visible={self.visible()}", flush=True)
            return True

        def ping():
            if self.done:
                return False
            self.serial += 1
            self.call(OVERLAY, "Ping", GLib.Variant("(u)", (self.serial,)))
            return True

        def on_event(_c, _s, _p, _i, _sig, params):
            kind = params.unpack()[0]
            if kind in ("stop_key", "button:stop"):
                print("stopped", flush=True)
                self.finish()

        self.bus.signal_subscribe(
            DEST, OVERLAY, "UserEvent", PATH, None, Gio.DBusSignalFlags.NONE, on_event
        )
        if not self.windows():
            print("no allowed window is open; open the app you allowed", flush=True)
        tick()
        ping()
        GLib.timeout_add(250, tick)
        GLib.timeout_add(2000, ping)  # the extension hides everything after ~6 s of silence
        self.run_for(seconds)

    def run_for(self, seconds):
        GLib.timeout_add_seconds(seconds, self.finish)
        try:
            gi.require_version("GLibUnix", "2.0")
            from gi.repository import GLibUnix

            GLibUnix.signal_add(GLib.PRIORITY_DEFAULT, 2, self.finish)  # Ctrl+C
        except (ValueError, ImportError):
            GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, 2, self.finish)
        self.loop.run()
        self.finish()


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "watch"
    seconds = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    text = sys.argv[3] if len(sys.argv) > 3 else "Ya bro is here. Press Stop or Super+Shift+Esc."
    demo = Demo()
    demo.become_core()
    if cmd == "watch":
        demo.watch(seconds)
    elif cmd == "point":
        demo.point(seconds, text)
    else:
        sys.exit(f"unknown command {cmd!r}")


if __name__ == "__main__":
    main()
