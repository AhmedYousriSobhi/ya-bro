"""A GTK4 window with three text fields, for Do-it text entry (#27): an empty entry "Project name",
one that already holds the user's text ("Note"), and a password entry ("Secret"). System python3."""

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402


def field(box, widget, label):
    widget.update_property([Gtk.AccessibleProperty.LABEL], [label])
    box.append(widget)


def on_activate(app):
    win = Gtk.ApplicationWindow(application=app, default_width=420, default_height=240)
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    field(box, Gtk.Entry(), "Project name")
    note = Gtk.Entry(text="keep me")
    field(box, note, "Note")
    field(box, Gtk.PasswordEntry(), "Secret")
    win.set_child(box)
    win.present()


app = Gtk.Application(application_id="io.github.ahmedyousrisobhi.YaBroFixture")
app.connect("activate", on_activate)
app.run()
