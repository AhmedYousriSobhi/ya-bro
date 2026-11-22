"""GTK4 app for the Show-me loop: Create -> (wizard) Confirm -> label Done. Run with system python3."""

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402


def on_activate(app):
    win = Gtk.ApplicationWindow(application=app, title="Steps Fixture")
    stack = Gtk.Stack()
    create = Gtk.Button(label="Create")
    confirm = Gtk.Button(label="Confirm")
    done = Gtk.Label(label="Done")
    for name, widget in (("create", create), ("confirm", confirm), ("done", done)):
        widget.set_margin_top(60)
        widget.set_margin_start(60)
        widget.set_margin_end(60)
        widget.set_margin_bottom(60)
        stack.add_named(widget, name)
    create.connect("clicked", lambda *_: stack.set_visible_child_name("confirm"))
    confirm.connect("clicked", lambda *_: stack.set_visible_child_name("done"))
    win.set_child(stack)
    win.set_default_size(420, 320)
    win.present()


import os  # noqa: E402

app = Gtk.Application(
    application_id=os.environ.get("STEPS_APP_ID", "io.github.ahmedyousrisobhi.YaBroSteps")
)
app.connect("activate", on_activate)
app.run([])
