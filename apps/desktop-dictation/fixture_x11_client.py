"""Separate application process for private clipboard integration tests."""
import json
import os
import sys

from Xlib import X, XK, Xatom, display


def gtk_entry():
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gdk, GLib, Gtk

    window, entry = Gtk.Window(), Gtk.Entry()
    window.add(entry)
    window.show_all()
    entry.grab_focus()
    entry.set_text("AB")
    entry.set_position(0)

    def report(message):
        Gdk.Display.get_default().sync()
        print(json.dumps([message, entry.get_text(), entry.get_position()]), flush=True)
        return False

    entry.connect_after("paste-clipboard", lambda *_: GLib.idle_add(report, "requested"))
    entry.connect("notify::cursor-position", lambda *_: report("cursor"))
    entry.connect("key-press-event", lambda _, event: report("snapshot") if event.keyval == Gdk.KEY_F12 else False)
    Gdk.Display.get_default().sync()
    print(window.get_window().get_xid(), flush=True)
    Gtk.main()


if __name__ == "__main__":
    if "--gtk-entry" in sys.argv:
        gtk_entry()
        sys.exit(0)
    x = display.Display()
    window = x.screen().root.create_window(0, 0, 8, 8, 0, 0, X.InputOnly, X.CopyFromParent)
    # A self-declared PID must never let this process impersonate the target.
    window.change_property(x.intern_atom("_NET_WM_PID"), Xatom.CARDINAL, 32, [os.getppid()])
    window.change_attributes(event_mask=X.KeyPressMask)
    window.map()
    x.sync()
    print(window.id, flush=True)
    for command in sys.stdin:
        target = "UTF8_STRING"
        timestamp = X.CurrentTime
        if command.strip() == "key-time":
            while True:
                event = x.next_event()
                if event.type == X.KeyPress and event.detail == x.keysym_to_keycode(XK.XK_v):
                    timestamp = event.time
                    break
        elif command.strip() == "image/png":
            target = "image/png"
        else:
            assert command.strip() == "read"
        window.convert_selection(x.intern_atom("CLIPBOARD"), x.intern_atom(target),
                                 x.intern_atom("DICTATION_TEST_PASTE"), timestamp)
        x.flush()
