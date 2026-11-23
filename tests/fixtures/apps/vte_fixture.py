"""A bare VTE terminal (GTK3, libvte 2.91) running the command after `--`. System python3.

The same widget Ptyxis and GNOME Terminal draw with, without Ptyxis' spawn agent (which needs a
systemd user bus the isolated test session does not have). Usage: vte_fixture.py -- CMD [ARGS...]
"""

import sys

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Vte", "2.91")
from gi.repository import GLib, Gtk, Vte  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else ["bash"]


def on_activate(app):
    win = Gtk.ApplicationWindow(application=app, default_width=760, default_height=420)
    term = Vte.Terminal()
    term.spawn_async(
        Vte.PtyFlags.DEFAULT, None, argv, None, GLib.SpawnFlags.DEFAULT, None, None, -1, None, None
    )
    term.connect("child-exited", lambda *_: app.quit())
    win.add(term)
    win.show_all()


app = Gtk.Application(application_id="io.github.ahmedyousrisobhi.YaBroVte")
app.connect("activate", on_activate)
sys.exit(app.run([sys.argv[0]]))
