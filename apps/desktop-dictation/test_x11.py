#!/usr/bin/python3
"""Run GTK integration checks on a private Xvfb. Add --real-model to exercise T3."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time


def executable(path, source):
    path.write_text("#!/usr/bin/python3\n" + source)
    path.chmod(0o700)


def exercise(directory, real):
    os.environ.update(XDG_SESSION_TYPE="x11", GDK_BACKEND="x11", NO_AT_BRIDGE="1")
    os.environ["PATH"] = str(directory) + os.pathsep + os.environ["PATH"]
    audio = directory / "fixture.pcm"
    if real:
        samples = Path("/usr/share/sounds/alsa")
        subprocess.run(["sox", samples / "Front_Center.wav", samples / "Front_Left.wav",
                        samples / "Front_Center.wav", "-r", "16000", "-c", "1", "-b", "16",
                        "-e", "signed", "-t", "raw", audio], check=True)
    else:
        audio.write_bytes(b"\x00\x12" * 16000)
        worker = directory / "recognizer"
        executable(worker, """
import json, sys, time, os
from pathlib import Path
for line in sys.stdin.buffer:
    if line == b":finish\\n":
        time.sleep(.25)
        fixture = Path(os.environ["DICTATION_FIXTURE"]).with_suffix(".txt")
        print(json.dumps({"type":"final", "text":fixture.read_text() if fixture.exists() else "Finished words."}), flush=True)
    elif line != b":start\\n":
        print(json.dumps({"type":"partial", "text":"Live words"}), flush=True)
""")
        os.environ["T3_DICTATION_APPIMAGE"] = str(worker)
    os.environ["DICTATION_FIXTURE"] = str(audio)
    executable(directory / "parec", """
import os, sys, time
with open(os.environ["DICTATION_FIXTURE"], "rb") as audio:
    while True:
        sys.stdout.buffer.write(audio.read(1280) or bytes(1280))
        sys.stdout.flush()
        time.sleep(.04)
""")
    from dictate import Dictation, Gdk, Gtk, paste_shortcut
    from Xlib import X, XK, Xatom, display
    x = display.Display()
    window, box = Gtk.Window(), Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    first, second = Gtk.Entry(), Gtk.Entry()
    box.add(first)
    box.add(second)
    window.add(box)
    window.show_all()
    first.grab_focus()
    Gdk.Display.get_default().sync()
    xid = window.get_window().get_xid()
    x.screen().root.change_property(x.intern_atom("_NET_ACTIVE_WINDOW"), Xatom.WINDOW, 32, [xid])
    x.create_resource_object("window", xid).set_input_focus(X.RevertToParent, X.CurrentTime)
    x.sync()
    app = Dictation()

    def until(test, timeout=4):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            while Gtk.events_pending():
                Gtk.main_iteration_do(False)
            if test():
                return
            time.sleep(.005)
        raise AssertionError(f"Timed out, overlay reads {app.overlay.label.get_text()!r}")

    def keys(*sequence):
        subprocess.run(["xdotool", *sequence], check=True)

    def hold(a, b):
        keys("keydown", a, "keydown", b)
        until(lambda: app.recording is not None)
        until(lambda: app.overlay.label.get_text() != "Speak now…", 12)
        assert max(app.overlay.levels) > 0

    app.clipboard.set_text("Original text", -1)
    until(lambda: app.clipboard_generation > 0)
    start = time.monotonic()
    hold("Super_L", "Alt_L")
    print(f"First partial at {time.monotonic() - start:.2f}s: {app.overlay.label.get_text()}", flush=True)
    keys("click", "4")
    release = time.monotonic()
    keys("keyup", "Super_L")
    until(lambda: app.recording.released is not None)
    assert not first.get_text()
    keys("keyup", "Alt_L")
    until(lambda: bool(first.get_text()), 12)
    text = first.get_text()
    print(f"Inserted after {time.monotonic() - release:.2f}s: {text}", flush=True)
    until(lambda: app.selection.saved is not None)
    assert app.clipboard.wait_for_text() == "Original text"
    if real:
        assert "front" in text.lower()
        # A short second utterance can end before the first native partial.
        second.grab_focus()
        keys("keydown", "Alt_L", "keydown", "Super_L")
        until(lambda: app.recording is not None)
        until(lambda: time.monotonic() - app.recording.started > 1.35)
        release = time.monotonic()
        keys("keyup", "Alt_L", "keyup", "Super_L")
        until(lambda: bool(second.get_text()), 12)
        print(f"Short hold inserted after {time.monotonic() - release:.2f}s: {second.get_text()}", flush=True)
        assert "front" in second.get_text().lower()
        app.stop_worker()
        return
    assert text == "Finished words."
    assert paste_shortcut(("gnome-terminal-server", "Gnome-terminal")) == (XK.XK_Control_L, XK.XK_Shift_L, XK.XK_v)
    target = x.create_resource_object("window", xid)
    original_class = target.get_wm_class()
    serial = app.paste_serial
    for wm_class in (("terminal", "XTerm"), ("uxterm", "UXTerm"), ("urxvt", "URxvt")):
        target.set_wm_class(*wm_class)
        x.sync()
        hold("Alt_L", "Super_L")
        keys("keyup", "Alt_L", "keyup", "Super_L")
        until(lambda: app.overlay.recovery == text)
        assert app.paste_serial == serial and first.get_text() == text
        assert app.clipboard.wait_for_text() == "Original text"
        app.overlay.dismiss_recovery()
    target.set_wm_class(*original_class)
    x.sync()
    app.clipboard.set_text("Existing clipboard", -1)
    hold("Alt_L", "Super_L")
    keys("keyup", "Alt_L", "keyup", "Super_L", "key", "Tab")
    until(lambda: app.overlay.recovery is not None)
    assert second.is_focus() and not second.get_text() and first.get_text() == text
    assert app.clipboard.wait_for_text() == "Existing clipboard"
    app.overlay.copy_recovery()
    assert app.clipboard.wait_for_text() == text
    app.clipboard.set_text("Late Tab sentinel", -1)
    # Input after the early event drain but before the final server grab.
    hold("Super_L", "Alt_L")
    grab = app.x.grab_server
    def tab_then_grab():
        keys("key", "Tab")
        grab()
    app.x.grab_server = tab_then_grab
    keys("keyup", "Super_L", "keyup", "Alt_L")
    until(lambda: app.overlay.recovery is not None)
    app.x.grab_server = grab
    assert app.clipboard.wait_for_text() == "Late Tab sentinel" and first.get_text() == text and not second.get_text()
    app.overlay.dismiss_recovery()

    # GTK reuses its owner window for a fresh copy just before the final guard.
    hold("Super_L", "Alt_L")
    previous_owner = app.x.get_selection_owner(app.selection.atom)
    def copy_then_grab():
        app.clipboard.set_text("Newer clipboard", -1)
        Gdk.Display.get_default().sync()
        assert app.x.get_selection_owner(app.selection.atom) == previous_owner
        grab()
    app.x.grab_server = copy_then_grab
    keys("keyup", "Super_L", "keyup", "Alt_L")
    until(lambda: app.overlay.recovery is not None)
    app.x.grab_server = grab
    assert app.clipboard.wait_for_text() == "Newer clipboard"
    assert first.get_text() == text and not second.get_text()
    app.overlay.dismiss_recovery()

    # XI 2.1 must report input while another client has grabbed the keyboard.
    hold("Alt_L", "Super_L")
    keys("keyup", "Alt_L", "keyup", "Super_L")
    until(lambda: app.recording.released)
    grabbed = x.create_resource_object("window", xid)
    assert grabbed.grab_keyboard(False, X.GrabModeAsync, X.GrabModeAsync, X.CurrentTime) == X.GrabSuccess
    keys("key", "Tab")
    second.grab_focus()
    x.ungrab_keyboard(X.CurrentTime)
    x.sync()
    until(lambda: app.overlay.recovery is not None)
    assert not second.get_text() and first.get_text() == text
    app.overlay.dismiss_recovery()
    # Even without intervening input, a grab can divert the synthetic paste.
    popup = x.screen().root.create_window(0, 0, 8, 8, 0, 0, X.InputOnly, X.CopyFromParent)
    popup.map()
    x.sync()
    hold("Alt_L", "Super_L")
    keys("keyup", "Alt_L", "keyup", "Super_L")
    until(lambda: app.recording.released)
    assert popup.grab_keyboard(False, X.GrabModeAsync, X.GrabModeAsync, X.CurrentTime) == X.GrabSuccess
    try:
        until(lambda: app.overlay.recovery is not None)
        assert app.clipboard.wait_for_text() == "Newer clipboard" and not second.get_text()
    finally:
        x.ungrab_keyboard(X.CurrentTime)
        popup.destroy()
        x.sync()
    app.overlay.dismiss_recovery()

    # Both fields belong to one X client. A late reader from the first
    # field must never consume the second transcript when the first expires.
    first.grab_focus()
    delayed = []
    def defer_paste(entry):
        entry.stop_emission_by_name("paste-clipboard")
        delayed.append(entry)
    ignored = first.connect("paste-clipboard", defer_paste)
    generation = app.clipboard_generation
    app.clipboard.set_text("Original before two holds", -1)
    until(lambda: app.clipboard_generation > generation)
    audio.with_suffix(".txt").write_text("Ignored transcript")
    hold("Super_L", "Alt_L")
    keys("keyup", "Alt_L", "keyup", "Super_L")
    until(lambda: bool(delayed))
    first.disconnect(ignored)
    # Clipboard requests on an unrelated X connection still see the user's
    # clipboard, even before the first target consumes its paste.
    outsider = x.screen().root.create_window(0, 0, 1, 1, 0, 0, X.InputOnly, X.CopyFromParent)
    prop = x.intern_atom("DICTATION_TEST_PASTE")
    utf8 = x.intern_atom("UTF8_STRING")
    outsider.convert_selection(app.selection.atom, utf8, prop, X.CurrentTime)
    x.flush()
    until(lambda: outsider.get_full_property(prop, utf8) is not None)
    assert outsider.get_full_property(prop, utf8).value == b"Original before two holds"
    outsider.destroy()
    second.grab_focus()
    audio.with_suffix(".txt").write_text("Second transcript")
    hold("Super_L", "Alt_L")
    keys("keyup", "Alt_L", "keyup", "Super_L")
    until(lambda: app.pending_backup is None and app.overlay.recovery == "Second transcript")
    assert app.overlay.resume.is_visible()
    # A hold started *after* expiry also uses Copy, even when another field
    # in the same client still has a deferred paste request.
    audio.with_suffix(".txt").write_text("Third transcript")
    hold("Alt_L", "Super_L")
    keys("keyup", "Super_L", "keyup", "Alt_L")
    until(lambda: app.overlay.recovery == "Third transcript")
    first.set_text("")
    delayed.pop().emit("paste-clipboard")
    until(lambda: not app.selection.expired_reads)
    assert not first.get_text() and not second.get_text()
    assert app.clipboard.wait_for_text() == "Original before two holds"
    app.overlay.dismiss_recovery()
    assert app.overlay.recovery == "Second transcript"
    app.overlay.copy_recovery()
    assert app.clipboard.wait_for_text() == "Second transcript"
    assert app.overlay.recovery == "Ignored transcript"
    app.overlay.resume.clicked()
    assert not app.paused_clients
    app.overlay.dismiss_recovery()
    app.clipboard.set_text("Discard before empty fixture", -1)
    app.clipboard.clear()
    until(lambda: not app.x.get_selection_owner(app.selection.atom))
    # A field can accept Ctrl+V and defer reading the selection until the next hold.
    first.set_text("")
    first.grab_focus()
    handler = first.connect("paste-clipboard", defer_paste)
    audio.with_suffix(".txt").write_text("First delayed transcript")
    hold("Super_L", "Alt_L")
    keys("keyup", "Super_L", "keyup", "Alt_L")
    until(lambda: bool(delayed))
    first.disconnect(handler)
    second.grab_focus()
    audio.with_suffix(".txt").write_text("Second delayed transcript")
    hold("Super_L", "Alt_L")
    keys("keyup", "Alt_L", "keyup", "Super_L")
    until(lambda: app.recording is not None and app.recording.got_final)
    assert not second.get_text()
    delayed.pop().emit("paste-clipboard")
    until(lambda: second.get_text() == "Second delayed transcript" and app.pending_backup is None)
    assert first.get_text() == "First delayed transcript"
    assert not app.clipboard.wait_for_text()
    second.set_text("")
    hold("Alt_L", "Super_L")
    app.worker.kill()
    until(lambda: app.overlay.recovery == "Live words")
    assert not second.get_text()
    keys("keyup", "Alt_L", "keyup", "Super_L")
    until(lambda: not app.held)
    hold("Alt_L", "Super_L")
    warm_worker = app.worker
    keys("key", "Escape", "keyup", "Super_L", "keyup", "Alt_L")
    until(lambda: app.recording is None)
    assert not second.get_text() and app.overlay.label.get_text() == "Cancelled"
    assert app.worker is warm_worker and warm_worker.poll() is None
    app.stop_worker()


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as tmp:
        r, w = os.pipe()
        server = subprocess.Popen(["Xvfb", "-displayfd", str(w), "-screen", "0", "960x640x24",
                                   "-nolisten", "tcp"], pass_fds=[w])
        os.close(w)
        try:
            with os.fdopen(r) as display_number:
                number = display_number.readline().strip()
            assert number.isdigit()
            os.environ["DISPLAY"] = ":" + number
            exercise(Path(tmp), "--real-model" in sys.argv[1:])
        finally:
            server.terminate()
            server.wait()
