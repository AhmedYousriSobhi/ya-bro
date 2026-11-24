"""A bare VTE terminal (GTK3, libvte 2.91) running the command after `--`. System python3.

The same widget Ptyxis and GNOME Terminal draw with, without Ptyxis' spawn agent (which needs a
systemd user bus the isolated test session does not have). Usage: vte_fixture.py -- CMD [ARGS...]
"""

import sys

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
gi.require_version("Vte", "2.91")
from gi.repository import Gdk, GLib, Gtk, Vte  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else ["bash"]


def on_activate(app):
    win = Gtk.ApplicationWindow(application=app, default_width=760, default_height=420)
    term = Vte.Terminal()
    term.spawn_async(
        Vte.PtyFlags.DEFAULT, None, argv, None, GLib.SpawnFlags.DEFAULT, None, None, -1, None, None
    )
    term.connect("child-exited", lambda *_: app.quit())
    # A terminal app shows OSC 2 in its window title; the bare widget only reports it.
    term.connect("window-title-changed", lambda t: win.set_title(t.get_window_title() or ""))

    # Ptyxis binds Ctrl+Shift+V to paste; the bare widget does not, so the tests ask for it here.
    def on_key(_w, ev):
        want = Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK
        if ev.keyval in (Gdk.KEY_V, Gdk.KEY_v) and (ev.state & want) == want:
            term.paste_clipboard()
            return True
        return False

    term.connect("key-press-event", on_key)
    win.add(term)
    win.show_all()


app = Gtk.Application(application_id="io.github.ahmedyousrisobhi.YaBroVte")
app.connect("activate", on_activate)
sys.exit(app.run([sys.argv[0]]))
