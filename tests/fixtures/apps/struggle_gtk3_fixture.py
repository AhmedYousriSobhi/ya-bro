"""GTK3 app that raises two error dialogs by itself, 3 s and 7 s after it starts (#9).

A GTK3 MessageDialog of type error is the one dialog GNOME's AT-SPI reports with the `alert` role
(GTK4's AlertDialog and libadwaita's are plain `dialog`). Run with system python3.
"""

import os

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402


def on_activate(app):
    win = Gtk.ApplicationWindow(application=app, title="Struggle GTK3 Fixture")
    win.set_default_size(300, 200)
    win.show_all()

    def alert():
        d = Gtk.MessageDialog(
            transient_for=win, modal=True, message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.CLOSE, text="It failed",
        )  # fmt: skip
        d.show()
        GLib.timeout_add(1500, lambda: d.destroy() or False)
        return False

    GLib.timeout_add(3000, alert)
    GLib.timeout_add(7000, alert)


app = Gtk.Application(
    application_id=os.environ.get("STRUGGLE_APP_ID", "io.github.ahmedyousrisobhi.YaBroStruggleGtk3")
)
app.connect("activate", on_activate)
app.run([])
