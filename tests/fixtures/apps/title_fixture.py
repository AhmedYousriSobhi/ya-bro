"""GTK4 window whose title is set from stdin lines (spike #47: stands in for a browser tab)."""

import sys

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk  # noqa: E402


def on_activate(app: Gtk.Application) -> None:
    win = Gtk.ApplicationWindow(application=app, title="plain")
    win.set_default_size(300, 120)
    win.present()

    def on_stdin(fd, _cond):
        line = fd.readline()
        if not line:
            app.quit()
            return False
        win.set_title(line.rstrip("\n"))
        return True

    GLib.io_add_watch(sys.stdin, GLib.IO_IN | GLib.IO_HUP, on_stdin)


app = Gtk.Application(application_id="io.github.ahmedyousrisobhi.YaBroTitle")
app.connect("activate", on_activate)
app.run([])
