"""GTK4 app for the struggle sources (#9): two menus, a dialog with Cancel/OK, an alert, an undoable
text view and a Help menu item. Prints what really happened as JSON lines (the ground truth the
test compares the AT-SPI observations against). Run with system python3."""

import json
import os

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, Gtk  # noqa: E402


def say(**kw):
    print(json.dumps(kw), flush=True)


def on_activate(app):
    win = Gtk.ApplicationWindow(application=app, title="Struggle Fixture")
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    for m in (box,):  # one margin on all sides
        m.set_margin_top(20)
        m.set_margin_start(20)
        m.set_margin_end(20)
        m.set_margin_bottom(20)

    file_menu = Gio.Menu()
    file_menu.append("Export", "win.export")
    file_menu.append("Open", "win.noop")
    edit_menu = Gio.Menu()
    edit_menu.append("Undo", "win.undo")
    edit_menu.append("Select", "win.noop")
    help_menu = Gio.Menu()
    help_menu.append("Manual", "win.help")
    bar = Gtk.Box(spacing=6)
    for label, model in (("File", file_menu), ("Edit", edit_menu), ("Help", help_menu)):
        bar.append(Gtk.MenuButton(label=label, menu_model=model))
    box.append(bar)

    text = Gtk.TextView()
    text.set_size_request(300, 120)
    buf = text.get_buffer()
    buf.set_enable_undo(True)
    box.append(text)
    alert = Gtk.Button(label="Alert")
    box.append(alert)

    def action(name, fn):
        a = Gio.SimpleAction.new(name, None)
        a.connect("activate", lambda *_: (say(e="action", name=name), fn()))
        win.add_action(a)

    def export():
        d = Gtk.Window(title="Export", transient_for=win, modal=True)
        d.set_default_size(260, 120)
        row = Gtk.Box(spacing=6, margin_top=20, margin_start=20, margin_end=20, margin_bottom=20)
        for label in ("Cancel", "OK"):
            b = Gtk.Button(label=label)
            b.connect("clicked", lambda _b, label=label: (say(e="dialog", button=label), d.close()))
            row.append(b)
        d.set_child(row)
        d.present()

    def raise_alert(*_):
        dlg = Gtk.AlertDialog(message="Something failed", detail="try again")
        dlg.set_buttons(["Dismiss"])
        dlg.choose(win, None, lambda *_: say(e="alert", button="Dismiss"))

    action("export", export)
    action("noop", lambda: None)
    action("undo", lambda: buf.undo())
    action("help", lambda: None)
    alert.connect("clicked", raise_alert)
    win.set_child(box)
    win.set_default_size(420, 320)
    win.present()


app = Gtk.Application(
    application_id=os.environ.get("STRUGGLE_APP_ID", "io.github.ahmedyousrisobhi.YaBroStruggle")
)
app.connect("activate", on_activate)
app.run([])
