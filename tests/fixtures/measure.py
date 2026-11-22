"""S1 measurements inside scripts/dev/headless-shell.sh. System python3.

Usage: measure.py OUT.json [--scale 1.5]
Writes raw numbers to OUT.json and prints a one-line summary per measurement.
"""

import json
import math
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gi.repository import Gio, GLib  # noqa: E402
from shellkit import (
    DEST,
    OVERLAY,
    PATH,
    App,
    Shell,
    atspi_widgets,  # noqa: E402
    find_pixels,
    pump,
    pump_until,
)

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURE = os.path.join(HERE, "apps", "toolkit_fixture.py")
RING = (245, 165, 36)
BUTTON_BG = (58, 58, 82)
SCALE = float(sys.argv[sys.argv.index("--scale") + 1]) if "--scale" in sys.argv else 1.0
OUT = sys.argv[1]
R = {"scale": SCALE}


def stats(vals):
    v = sorted(vals)
    if not v:
        return {"n": 0}
    return {
        "n": len(v),
        "median": round(statistics.median(v), 2),
        "p95": round(v[min(len(v) - 1, math.ceil(0.95 * len(v)) - 1)], 2),
        "max": round(v[-1], 2),
    }


def log(name, value):
    R[name] = value
    print(f"MEASURE {name}: {json.dumps(value)}", flush=True)


def set_scale(sh, scale):
    """Apply a monitor scale through Mutter DisplayConfig (needs scale-monitor-framebuffer, set by the harness)."""
    dc = ("org.gnome.Mutter.DisplayConfig", "/org/gnome/Mutter/DisplayConfig")
    state = sh.call(dc[0], "GetCurrentState", None, dc[0], dc[1])
    serial, monitors = state[0], state[1]
    connector, modes = monitors[0][0][0], monitors[0][1]
    mode = next(m for m in modes if m[1] == 1920 and m[2] == 1200)
    scales = sorted(mode[5], key=lambda s: abs(s - scale))
    chosen = scales[0]
    sh.call(
        dc[0],
        "ApplyMonitorsConfig",
        GLib.Variant(
            "(uua(iiduba(ssa{sv}))a{sv})",
            (
                serial,
                1,
                [
                    (
                        0,
                        0,
                        chosen,
                        0,
                        True,
                        [
                            (
                                connector[0] if isinstance(connector, tuple) else connector,
                                mode[0],
                                {},
                            )
                        ],
                    )
                ],
                {},
            ),
        ),
        dc[0],
        dc[1],
    )
    pump(3)
    return chosen


def wait_window(sh, pid, settle=2.0):
    w = {}

    def ok():
        for x in sh.windows():
            if x["pid"] == pid and x["frame"][2] > 0:
                w.update(x)
                return True
        return False

    pump_until(ok, 20)
    pump(settle)
    return next(x for x in sh.windows() if x["pid"] == pid and x["frame"][2] > 0)


def launch(sh, kind, args=(), gdk=None):
    env = {"GDK_BACKEND": gdk} if gdk else {}
    app = App(FIXTURE, [kind, *args], env)
    pump_until(lambda: app.events("ready"), 25)
    win = wait_window(sh, app.proc.pid)
    pump_until(lambda: app.events("bounds"), 10)
    return app, win


def err(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def measure_coordinates(sh, label, kind, gdk=None):
    app, win = launch(sh, kind, gdk=gdk)
    try:
        frame, buf = win["frame"], win["buffer"]
        bounds = app.events("bounds")[0]["w"]
        ext = atspi_widgets(app.proc.pid)
        fw, fh = frame[2], frame[3]
        pts = [
            (x, y)
            for x in (160, 330, 500, 650)
            for y in (70, 130, 190, 250, 420, 500)
            if x < fw - 10 and y < fh - 10
        ]
        origins = []
        for lx, ly in pts:
            gx, gy = frame[0] + lx, frame[1] + ly
            t0 = time.monotonic()
            sh.move(5, 5)
            pump(0.05)
            sh.click(gx, gy)
            if pump_until(lambda t0=t0: app.events("click", t0), 1.5):
                c = app.events("click", t0)[-1]
                origins.append((gx - c["x"], gy - c["y"]))
        if origins:
            mo = (
                statistics.median(o[0] for o in origins),
                statistics.median(o[1] for o in origins),
            )
        else:
            mo = (float("nan"), float("nan"))
        out = {
            "window": {"frame": frame, "buffer": buf, "client": win["client"]},
            "click_samples": len(origins),
            "origin_truth": mo,
            "origin_err_frame": stats([err(o, frame[:2]) for o in origins]),
            "origin_err_buffer": stats([err(o, buf[:2]) for o in origins]),
        }
        # AT-SPI WINDOW extents vs the app's own bounds, and end-to-end prediction vs truth.
        e_ext, e_total_f, e_total_b = [], [], []
        for name, b in bounds.items():
            if name not in ext:
                continue
            ew = ext[name]["window"]
            e_ext.append(err(ew[:2], b[:2]))
            truth = (mo[0] + b[0], mo[1] + b[1])
            e_total_f.append(err((frame[0] + ew[0], frame[1] + ew[1]), truth))
            e_total_b.append(err((buf[0] + ew[0], buf[1] + ew[1]), truth))
        out["atspi_window_ext_vs_toolkit_bounds"] = stats(e_ext)
        out["end_to_end_err_frame_origin"] = stats(e_total_f)
        out["end_to_end_err_buffer_origin"] = stats(e_total_b)
        out["atspi_screen_extents_all_zero"] = (
            all(v["screen"][:2] == (0, 0) for v in ext.values()) if ext else None
        )
        out["atspi_widgets_found"] = len([k for k in ext if k.startswith("W")])
        best = (
            frame
            if out["origin_err_frame"].get("median", 1e9)
            <= out["origin_err_buffer"].get("median", 1e9)
            else buf
        )
        out["best_origin"] = "frame" if best is frame else "buffer"
        # Hit test: click the predicted centre (best origin + AT-SPI extents) and see which button fires.
        ok = 0
        names = sorted(k for k in ext if k.startswith("W"))
        for name in names:
            ew = ext[name]["window"]
            t0 = time.monotonic()
            sh.move(5, 5)
            pump(0.03)
            sh.click(best[0] + ew[0] + ew[2] / 2, best[1] + ew[1] + ew[3] / 2)
            pump_until(lambda t0=t0: app.events("button", t0), 0.8)
            ev = app.events("button", t0)
            ok += 1 if ev and ev[-1]["w"] == name else 0
        out["hit_test"] = {"hits": ok, "of": len(names)}
        log(f"coords[{label}]", out)
    finally:
        app.close()
        pump(0.5)


def ring_edges(pb, rect, factor, probe=6):
    """Which of the 4 ring edges are visible at the expected position (rect in logical px)?"""
    x, y, w, h = rect
    cx, cy = x + w / 2, y + h / 2
    W, H = pb.get_width(), pb.get_height()

    def near(px, py, horizontal):
        pxi, pyi = int(px * factor), int(py * factor)
        r = int(probe * factor)
        if horizontal:
            cols = range(max(0, pxi - 8), min(W, pxi + 9))
            rows = range(max(0, pyi - r), min(H, pyi + r + 1))
        else:
            cols = range(max(0, pxi - r), min(W, pxi + r + 1))
            rows = range(max(0, pyi - 8), min(H, pyi + 9))
        return find_pixels(pb, RING, 45, rows, cols)

    hits = {
        "top": near(cx, y, True),
        "bottom": near(cx, y + h, True),
        "left": near(x, cy, False),
        "right": near(x + w, cy, False),
    }
    return {k: len(v) for k, v in hits.items()}, hits


def edge_error(hits, rect, factor):
    """Pixel error (logical px) of detected ring edge centres against the expected edges."""
    x, y, w, h = rect
    errs = []
    for k, pts in hits.items():
        if not pts:
            continue
        if k in ("top", "bottom"):
            mean = sum(p[1] for p in pts) / len(pts) / factor
            errs.append(abs(mean - (y if k == "top" else y + h)))
        else:
            mean = sum(p[0] for p in pts) / len(pts) / factor
            errs.append(abs(mean - (x if k == "left" else x + w)))
    return errs


def monitor_factor(sh):
    m = sh.call(f"{DEST}.Bridge1", "GetMonitors")[0][0]
    return m, m[3], m[4]


def measure_overlay(sh):
    mon, lw, lh = monitor_factor(sh)
    log("monitor", {"logical": [lw, lh], "scale": mon[5], "layout_mode": sh.info()["layout_mode"]})
    app, win = launch(sh, "gtk4")
    pump(1)
    pb0 = sh.grab()
    factor = pb0.get_width() / lw
    log("frame_factor", factor)
    frame = win["frame"]
    bounds = app.events("bounds")[0]["w"]
    # Origin from clicks (same as the coordinate measurement).
    sh.move(5, 5)
    pump(0.05)
    t0 = time.monotonic()
    sh.click(frame[0] + 400, frame[1] + 250)
    pump_until(lambda t0=t0: app.events("click", t0), 1.5)
    c = app.events("click", t0)[-1]
    origin = (frame[0] + 400 - c["x"], frame[1] + 250 - c["y"])
    b5 = bounds["W05"]
    target = (round(origin[0] + b5[0]), round(origin[1] + b5[1]), round(b5[2]), round(b5[3]))
    b10 = bounds["W10"]
    t10 = (round(origin[0] + b10[0]), round(origin[1] + b10[1]))

    # Ring alignment.
    sh.show_step(
        target=("(iiii)", target),
        ring=("s", "confident"),
        text=("s", "Click here"),
        buttons=("as", ["next"]),
        bubble_at=("(ii)", (t10[0], t10[1] + 70)),
    )
    pump(0.6)
    pb = sh.grab()
    counts, hits = ring_edges(pb, target, factor)
    ee = edge_error(hits, target, factor)
    log(
        "ring_alignment",
        {"target": target, "edges_found": counts, "edge_err_logical_px": stats(ee)},
    )

    # Click-through: 500 clicks under the ring, 500 on the bubble background; avatar and button must not leak.
    focus_before = len([e for e in sh.events if e[1] == "FocusChanged"])
    ring_pt = (target[0] + target[2] / 2, target[1] + target[3] / 2)
    bub = (t10[0] + 3, t10[1] + 70 + 3)
    n_before = len(app.events("click"))
    t_start = time.monotonic()
    for i in range(500):
        sh.click(*ring_pt)
        sh.click(bub[0] + (i % 3), bub[1] + (i % 3))
        if i % 100 == 0:
            sh.ping()
    pump(1.0)
    reached = len(app.events("click")) - n_before
    focus_after = len([e for e in sh.events if e[1] == "FocusChanged"])
    still = next(x for x in sh.windows() if x["pid"] == app.proc.pid)["focused"]
    log(
        "click_through",
        {
            "sent": 1000,
            "reached_app": reached,
            "blocked": 1000 - reached,
            "seconds": round(time.monotonic() - t_start, 1),
            "focus_events": focus_after - focus_before,
            "app_still_focused": still,
        },
    )

    # Avatar click must produce UserEvent and not reach the app.
    n_before = len(app.events("click"))
    ev_before = len(sh.events)
    avatar_pt = (t10[0] - 40 + 16, t10[1] + 70 + 16)
    sh.click(*avatar_pt)
    pump(0.5)
    got = [e for e in sh.events[ev_before:] if e[1] == "UserEvent" and e[2][0] == "avatar_click"]
    log(
        "avatar_click",
        {"user_event": len(got), "leaked_to_app": len(app.events("click")) - n_before},
    )

    # Bubble button: find its pixels, click, expect UserEvent button:next and no leak.
    pb = sh.grab()
    bb = find_pixels(pb, BUTTON_BG, 6)
    if bb:
        bx = sum(p[0] for p in bb) / len(bb) / factor
        by = sum(p[1] for p in bb) / len(bb) / factor
        n_before = len(app.events("click"))
        ev_before = len(sh.events)
        sh.click(bx, by)
        pump(0.5)
        got = [
            e
            for e in sh.events[ev_before:]
            if e[1] == "UserEvent" and e[2][0].startswith("button:")
        ]
        log(
            "bubble_button_click",
            {
                "found_pixels": len(bb),
                "user_event": [g[2][0] for g in got],
                "leaked_to_app": len(app.events("click")) - n_before,
            },
        )
    else:
        log("bubble_button_click", {"found_pixels": 0})

    # Stop key latency: Super+Shift+Escape, 50 reps.
    lat, hidden_ok = [], 0
    for _ in range(50):
        sh.show_step(text=("s", "x"))
        pump(0.05)
        ev_before = len(sh.events)
        sh.key("super", True)
        sh.key("shift", True)
        t0 = time.monotonic()
        sh.key("escape", True)
        pump_until(
            lambda eb=ev_before: any(
                e[1] == "UserEvent" and e[2][0] == "stop_key" for e in sh.events[eb:]
            ),
            1.0,
            0.002,
        )
        evs = [e for e in sh.events[ev_before:] if e[1] == "UserEvent" and e[2][0] == "stop_key"]
        if evs:
            lat.append((evs[0][0] - t0) * 1000)
        sh.key("escape", False)
        sh.key("shift", False)
        sh.key("super", False)
        hidden_ok += 0 if sh.state()["visible"] else 1
        pump(0.1)
    log(
        "stop_key",
        {"sent": 50, "received": len(lat), "hidden": hidden_ok, "latency_ms": stats(lat)},
    )
    sh.hide()
    pump(0.5)  # a Super tap may have toggled the overview; make sure it is closed
    if sh.state()["overview"]:
        sh.tap("super")
        pump(1.0)

    # Pointer flight lands where asked (Bezier).
    sh.call(OVERLAY, "FlyPointer", GLib.Variant("((ii)u)", ((300, 500), 600)))
    pump(1.2)
    pb = sh.grab()
    dots = find_pixels(
        pb,
        RING,
        30,
        range(int(480 * factor), int(520 * factor)),
        range(int(280 * factor), int(320 * factor)),
    )
    log("pointer_flight_lands", {"orange_pixels_near_target": len(dots)})
    sh.hide()

    # Popover: does the popup appear in ListWindows, and does the ring draw above it?
    ext = atspi_widgets(app.proc.pid, prefix=("Menu",))
    menu_ext = ext.get("Menu", {}).get("window")
    wins_before = {w["id"] for w in sh.windows()}
    if menu_ext:
        sh.click(
            origin[0] + menu_ext[0] + menu_ext[2] / 2, origin[1] + menu_ext[1] + menu_ext[3] / 2
        )
        pump(1.0)
        wins_after = sh.windows()
        new = [w for w in wins_after if w["id"] not in wins_before]
        log(
            "popover_in_window_list",
            {
                "new_windows": [
                    {
                        "type": w["type"],
                        "frame": w["frame"],
                        "buffer": w["buffer"],
                        "transient_for": w["transient_for"],
                    }
                    for w in new
                ]
            },
        )
        pop = new[0]["frame"] if new else None
        if pop:
            # Ring whose left edge crosses the popover.
            rect = (pop[0] + 20, pop[1] + 6, 60, 40)
            sh.show_step(
                target=("(iiii)", rect), ring=("s", "confident"), text=("s", "over popover")
            )
            pump(0.6)
            pb = sh.grab()
            counts, _ = ring_edges(pb, rect, factor)
            log("ring_above_popover", {"rect": rect, "edges_found": counts})
            sh.hide()
        sh.tap("escape")
        pump(0.5)

    # Overview hides the ring; leaving it brings the ring back.
    sh.show_step(target=("(iiii)", target), ring=("s", "confident"), text=("s", "ov"))
    pump(0.4)
    sh.tap("super")
    pump(1.5)
    st = sh.state()
    counts_ov, _ = ring_edges(sh.grab(), target, factor)
    sh.tap("super")
    pump(1.5)
    counts_back, _ = ring_edges(sh.grab(), target, factor)
    log(
        "overview",
        {
            "state_overview": st["overview"],
            "edges_in_overview": counts_ov,
            "edges_after": counts_back,
        },
    )
    sh.hide()
    app.close()
    pump(0.5)

    for flag in ("--maximize", "--fullscreen"):
        a2, w2 = launch(sh, "gtk4", args=(flag,))
        pump(1)
        rect = (200, 300, 300, 150)
        sh.show_step(target=("(iiii)", rect), ring=("s", "confident"), text=("s", flag))
        pump(0.8)
        counts, hits = ring_edges(sh.grab(), rect, factor)
        log(
            f"ring_above{flag.replace('--', '_')}",
            {
                "frame": w2["frame"],
                "fullscreen": w2["fullscreen"],
                "edges_found": counts,
                "unredirect_disabled": sh.state()["unredirect_disabled"],
            },
        )
        sh.hide()
        a2.close()
        pump(0.5)


def measure_signals(sh):
    """Non-peer subscriber must receive no Ya-Bro signals while the core peer does."""
    other = Gio.DBusConnection.new_for_address_sync(
        os.environ["DBUS_SESSION_BUS_ADDRESS"],
        Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT
        | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
        None,
        None,
    )
    got = []
    other.signal_subscribe(
        DEST, None, None, PATH, None, Gio.DBusSignalFlags.NONE, lambda *a: got.append(a[4])
    )
    pump(0.3)
    core_before = len(sh.events)
    app = App(FIXTURE, ["gtk4"])
    pump_until(lambda: app.events("ready"), 20)
    pump(2.5)
    app.close()
    pump(1.0)
    log(
        "signal_unicast",
        {"core_received": len(sh.events) - core_before, "non_peer_match_rule_received": len(got)},
    )
    # BecomeMonitor from a non-peer: records residual same-uid exposure, not a pass/fail.
    mon = Gio.DBusConnection.new_for_address_sync(
        os.environ["DBUS_SESSION_BUS_ADDRESS"],
        Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT
        | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
        None,
        None,
    )
    seen = []

    def filt(_c, msg, incoming):
        if msg.get_member() in ("FocusChanged", "WindowsChanged", "GeometryChanged"):
            seen.append(msg.get_member())
        return msg

    mon.add_filter(filt)
    try:
        mon.call_sync(
            "org.freedesktop.DBus",
            "/org/freedesktop/DBus",
            "org.freedesktop.DBus.Monitoring",
            "BecomeMonitor",
            GLib.Variant("(asu)", ([f"sender='{DEST}'"], 0)),
            None,
            Gio.DBusCallFlags.NONE,
            3000,
            None,
        )
        app = App(FIXTURE, ["gtk4"])
        pump_until(lambda: app.events("ready"), 20)
        pump(2.5)
        app.close()
        pump(1)
        log(
            "become_monitor_sees_unicast",
            {"became_monitor": True, "ya_bro_signals_seen": len(seen)},
        )
    except GLib.Error as e:
        log("become_monitor_sees_unicast", {"became_monitor": False, "error": e.message[:120]})


def main():
    sh = Shell()
    if SCALE != 1.0:
        log("applied_scale", set_scale(sh, SCALE))
    sh.start_input()  # after the scale change: a reconfigured monitor invalidates earlier streams
    measure_signals(sh)
    for label, kind, gdk in (
        ("gtk4", "gtk4", None),
        ("adw", "adw", None),
        ("gtk3_wayland", "gtk3", "wayland"),
        ("gtk3_xwayland", "gtk3", "x11"),
    ):
        try:
            measure_coordinates(sh, label, kind, gdk)
        except Exception as e:  # keep going: a missing toolkit must not hide the other results
            log(f"coords[{label}]", {"error": f"{type(e).__name__}: {e}"})
    measure_overlay(sh)
    with open(OUT, "w") as f:
        json.dump(R, f, indent=2, default=str)


main()
