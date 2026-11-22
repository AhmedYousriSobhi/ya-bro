"""Measurement fixture: 20 buttons + a popover, GTK4 / libadwaita / GTK3. System python3.

Prints JSONL events on stdout so the harness has ground truth from the app itself:
  {"e":"motion","w":"W07","x":12.5,"y":9.0}   pointer, in that widget's local coordinates
  {"e":"click","x":..,"y":..}                 any button press reaching the window
  {"e":"button","w":"W07"}                    a button activated
Usage: toolkit_fixture.py {gtk4|adw|gtk3} [--maximize] [--fullscreen]
"""

import json
import sys

import gi

KIND = sys.argv[1] if len(sys.argv) > 1 else "gtk4"
FLAGS = set(sys.argv[2:])
if KIND == "gtk3":
    gi.require_version("Gtk", "3.0")
else:
    gi.require_version("Gtk", "4.0")
    if KIND == "adw":
        gi.require_version("Adw", "1")
from gi.repository import GLib, Gtk  # noqa: E402

COLS, ROWS = 4, 5


def emit(**kw):
    print(json.dumps(kw), flush=True)


def build_gtk4():
    grid = Gtk.Grid(
        column_spacing=24, row_spacing=16, margin_top=24, margin_start=24, margin_end=24
    )
    names = []
    for i in range(COLS * ROWS):
        name = f"W{i:02d}"
        btn = Gtk.Button(label=name)
        btn.set_size_request(110, 36)
        btn.connect("clicked", lambda _b, n=name: emit(e="button", w=n))
        mc = Gtk.EventControllerMotion()
        mc.connect("motion", lambda _c, x, y, n=name: emit(e="motion", w=n, x=x, y=y))
        btn.add_controller(mc)
        grid.attach(btn, i % COLS, i // COLS, 1, 1)
        names.append(name)
    pop = Gtk.Popover()
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    for j in range(5):
        pname = f"P{j}"
        pb = Gtk.Button(label=pname)
        pb.set_size_request(120, 30)
        mc = Gtk.EventControllerMotion()
        mc.connect("motion", lambda _c, x, y, n=pname: emit(e="motion", w=n, x=x, y=y))
        pb.add_controller(mc)
        box.append(pb)
    pop.set_child(box)
    menu = Gtk.MenuButton(label="Menu", popover=pop)
    menu.set_size_request(110, 36)
    grid.attach(menu, 0, ROWS, 2, 1)
    return grid


def on_activate(app):
    content = build_gtk4()
    if KIND == "adw":
        from gi.repository import Adw

        win = Adw.ApplicationWindow(application=app, title="Fixture")
        tv = Adw.ToolbarView()
        tv.add_top_bar(Adw.HeaderBar())
        tv.set_content(content)
        win.set_content(tv)
    else:
        win = Gtk.ApplicationWindow(application=app, title="Fixture")
        win.set_child(content)
    win.set_default_size(700, 560)
    click = Gtk.GestureClick()
    click.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
    click.connect("pressed", lambda _g, _n, x, y: emit(e="click", x=x, y=y))
    win.add_controller(click)
    if "--maximize" in FLAGS:
        win.maximize()
    if "--fullscreen" in FLAGS:
        win.fullscreen()
    win.present()

    def report_bounds():
        out = {}
        stack = [content]
        while stack:
            wd = stack.pop()
            if isinstance(wd, Gtk.Button) and (wd.get_label() or "").startswith("W"):
                ok, r = wd.compute_bounds(win)
                if ok:
                    out[wd.get_label()] = [r.get_x(), r.get_y(), r.get_width(), r.get_height()]
            c = wd.get_first_child()
            while c:
                stack.append(c)
                c = c.get_next_sibling()
        emit(e="bounds", w=out)
        return False

    GLib.timeout_add(1500, report_bounds)
    emit(e="ready", kind=KIND)


def run_gtk3():
    from gi.repository import Gdk

    win = Gtk.Window(title="Fixture")
    win.set_default_size(700, 560)
    grid = Gtk.Grid(
        column_spacing=24, row_spacing=16, margin_top=24, margin_start=24, margin_end=24
    )
    for i in range(COLS * ROWS):
        name = f"W{i:02d}"
        btn = Gtk.Button(label=name)
        btn.set_size_request(110, 36)
        btn.add_events(Gdk.EventMask.POINTER_MOTION_MASK)
        btn.connect(
            "motion-notify-event", lambda _w, ev, n=name: emit(e="motion", w=n, x=ev.x, y=ev.y)
        )
        btn.connect("clicked", lambda _b, n=name: emit(e="button", w=n))
        grid.attach(btn, i % COLS, i // COLS, 1, 1)
    pop = Gtk.Popover()
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, margin=6)
    for j in range(5):
        pname = f"P{j}"
        pb = Gtk.Button(label=pname)
        pb.set_size_request(120, 30)
        pb.add_events(Gdk.EventMask.POINTER_MOTION_MASK)
        pb.connect(
            "motion-notify-event", lambda _w, ev, n=pname: emit(e="motion", w=n, x=ev.x, y=ev.y)
        )
        box.pack_start(pb, False, False, 0)
    box.show_all()
    pop.add(box)
    menu = Gtk.MenuButton(label="Menu", popover=pop)
    menu.set_size_request(110, 36)
    grid.attach(menu, 0, ROWS, 2, 1)
    win.add(grid)
    win.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
    win.connect("button-press-event", lambda _w, ev: emit(e="click", x=ev.x, y=ev.y) or False)
    win.connect("destroy", Gtk.main_quit)
    win.show_all()

    def report_bounds3():
        out = {}
        for wd in grid.get_children():
            lab = wd.get_label() if isinstance(wd, Gtk.Button) else ""
            if lab and lab.startswith("W"):
                x, y = wd.translate_coordinates(win, 0, 0)
                a = wd.get_allocation()
                out[lab] = [x, y, a.width, a.height]
        emit(e="bounds", w=out)
        return False

    GLib.timeout_add(1500, report_bounds3)
    if "--maximize" in FLAGS:
        win.maximize()
    if "--fullscreen" in FLAGS:
        win.fullscreen()
    emit(e="ready", kind=KIND)
    Gtk.main()


if KIND == "gtk3":
    run_gtk3()
else:
    app = Gtk.Application(application_id="io.github.ahmedyousrisobhi.YaBroToolkit")
    app.connect("activate", on_activate)
    app.run([])
