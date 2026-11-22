"""Tiny GTK4 app with known widgets for AT-SPI tests (ADR-0016). Run with system python3."""

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402


def on_activate(app: Gtk.Application) -> None:
    win = Gtk.ApplicationWindow(application=app, title="Ya-Bro Fixture")
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    box.append(Gtk.Button(label="Fixture Button"))
    box.append(Gtk.Entry(placeholder_text="Fixture Entry"))
    win.set_child(box)
    win.present()


app = Gtk.Application(application_id="io.github.ahmedyousrisobhi.YaBroFixture")
app.connect("activate", on_activate)
app.run([])
