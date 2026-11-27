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


def exercise(directory, real, other):
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
    until(app.glow.get_mapped)
    from Xlib.ext import shape
    Gdk.Display.get_default().sync()
    light = x.create_resource_object("window", app.glow.get_window().get_xid())
    assert not light.shape_get_rectangles(shape.SK.Input).rectangles
    _, _, glow_w, glow_h, _ = app.glow.bounds
    rim = light.shape_get_rectangles(shape.SK.Bounding).rectangles
    assert rim and not any(r.x <= glow_w // 2 < r.x + r.width and
                           r.y <= glow_h // 2 < r.y + r.height for r in rim), (app.glow.bounds, rim)
    assert app.focus() == app.recording.target
    if not real:
        window.move(40, 35)
        window.resize(320, 140)
        until(lambda: app.glow.bounds[:4] == (40, 35, 320, 140))
        assert app.focus() == app.recording.target
    print(f"First partial at {time.monotonic() - start:.2f}s: {app.overlay.label.get_text()}", flush=True)
    keys("click", "4")
    release = time.monotonic()
    keys("keyup", "Super_L")
    until(lambda: app.recording.released is not None)
    assert not app.glow.get_visible()
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
    native_owner = app.x.get_selection_owner(app.selection.atom)
    app.overlay.copy_recovery()
    assert app.x.get_selection_owner(app.selection.atom) == native_owner
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

    # Like Zed/arboard, the focused GTK window and its selection reader
    # belong to one process but use different X connections.
    first.grab_focus()
    reader = x.screen().root.create_window(0, 0, 1, 1, 0, 0, X.InputOnly, X.CopyFromParent)
    prop = x.intern_atom("DICTATION_TEST_PASTE")
    utf8 = x.intern_atom("UTF8_STRING")
    delayed = []
    def defer_paste(entry):
        entry.stop_emission_by_name("paste-clipboard")
        delayed.append(entry)

    handler = first.connect("paste-clipboard", defer_paste)
    hold("Alt_L", "Super_L")
    keys("keyup", "Alt_L", "keyup", "Super_L")
    until(lambda: bool(delayed))
    first.disconnect(handler)
    delayed.pop()
    recipient = x.create_resource_object("window", int(other.stdout.readline()))
    def other_read(expected):
        recipient.delete_property(prop)
        x.sync()
        other.stdin.write("read\n")
        other.stdin.flush()
        until(lambda: recipient.get_full_property(prop, utf8) is not None)
        assert recipient.get_full_property(prop, utf8).value == expected

    other_read(b"Newer clipboard")
    assert app.pending_backup is not None
    def secondary_read(expected):
        reader.delete_property(prop)
        reader.convert_selection(app.selection.atom, utf8, prop, X.CurrentTime)
        x.flush()
        until(lambda: reader.get_full_property(prop, utf8) is not None)
        assert reader.get_full_property(prop, utf8).value == expected

    secondary_read(text.encode())
    until(lambda: app.pending_backup is None)
    assert app.clipboard.wait_for_text() == "Newer clipboard"

    # Both fields belong to one X client. A late reader from the first
    # field must never consume the second transcript when the first expires.
    first.grab_focus()
    ignored = first.connect("paste-clipboard", defer_paste)
    generation = app.clipboard_generation
    app.clipboard.set_text("Original before two holds", -1)
    until(lambda: app.clipboard_generation > generation)
    audio.with_suffix(".txt").write_text("Ignored transcript")
    hold("Super_L", "Alt_L")
    keys("keyup", "Alt_L", "keyup", "Super_L")
    until(lambda: bool(delayed))
    first.disconnect(ignored)
    other_read(b"Original before two holds")
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
    app.overlay.dismiss_recovery()
    assert app.overlay.recovery == "Second transcript"
    app.overlay.copy_recovery()
    other_read(b"Second transcript")
    delayed.pop()
    secondary_read(b"")
    until(lambda: not app.selection.outstanding)
    assert not first.get_text() and not second.get_text()
    keys("key", "ctrl+v")
    until(lambda: second.get_text() == "Second transcript")
    second.set_text("")
    assert app.overlay.recovery == "Ignored transcript"
    app.overlay.resume.clicked()
    assert not app.paused_clients
    app.overlay.dismiss_recovery()
    # A fresh copy before expiry belongs to the external owner. When a later
    # paste targets another X client, the paused client can still read its copy.
    first.grab_focus()
    handler = first.connect("paste-clipboard", defer_paste)
    hold("Super_L", "Alt_L")
    keys("keyup", "Super_L", "keyup", "Alt_L")
    until(lambda: bool(delayed))
    first.disconnect(handler)
    generation = app.clipboard_generation
    app.clipboard.set_text("Copied during pending paste", -1)
    until(lambda: app.clipboard_generation > generation)
    assert app.pending_backup is not None
    until(lambda: app.pending_backup is None and app.overlay.resume.is_visible())

    x.screen().root.change_property(app.active_atom, Xatom.WINDOW, 32, [recipient.id])
    recipient.set_input_focus(X.RevertToParent, X.CurrentTime)
    x.sync()
    audio.with_suffix(".txt").write_text("Other client transcript")
    hold("Alt_L", "Super_L")
    keys("keyup", "Alt_L", "keyup", "Super_L")
    until(lambda: app.pending_backup is not None)
    delayed.pop().emit("paste-clipboard")
    until(lambda: first.get_text() == "Copied during pending paste")
    other_read(b"Other client transcript")
    until(lambda: app.pending_backup is None)
    assert app.clipboard.wait_for_text() == "Copied during pending paste"
    x.screen().root.change_property(app.active_atom, Xatom.WINDOW, 32, [xid])
    x.create_resource_object("window", xid).set_input_focus(X.RevertToParent, X.CurrentTime)
    xres = app.selection.xres
    app.selection.xres = None
    try:
        assert app.selection.client_id(reader.id) != app.selection.client_id(xid)
        assert app.selection.client_id(reader.id) == ("connection", x.display.info.resource_id_base)
    finally:
        app.selection.xres = xres
    reader.destroy()
    x.sync()
    until(lambda: app.overlay.recovery is not None)
    app.overlay.resume.clicked()
    assert not app.paused_clients
    app.overlay.dismiss_recovery()

    # An empty selection and an intervening owner cannot tell us whether
    # the first shortcut was consumed. Copy must guard either recovery card.
    for intervening_copy in (False, True):
        app.clipboard.set_text("Discard", -1)
        app.clipboard.clear()
        until(lambda: not app.x.get_selection_owner(app.selection.atom))
        first.set_text("")
        first.grab_focus()
        handler = first.connect("paste-clipboard", defer_paste)
        hold("Super_L", "Alt_L")
        keys("keyup", "Alt_L", "keyup", "Super_L")
        until(lambda: bool(delayed))
        first.disconnect(handler)
        second.grab_focus()
        audio.with_suffix(".txt").write_text("Recovered B")
        hold("Super_L", "Alt_L")
        keys("keyup", "Alt_L", "keyup", "Super_L")
        until(lambda: app.overlay.recovery == "Recovered B" and app.recording is None)
        if intervening_copy:
            app.clipboard.set_text("External copy", -1)
            until(lambda: app.x.get_selection_owner(app.selection.atom))
        app.overlay.copy_recovery()
        delayed.pop().emit("paste-clipboard")
        until(lambda: not app.selection.outstanding)
        assert not first.get_text()
        keys("key", "ctrl+v")
        until(lambda: second.get_text() == "Recovered B")
        second.set_text("")
        app.overlay.resume.clicked()
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
    app.overlay.dismiss_recovery()

    # A hold refused during finalization stays visibly mic-off until release,
    # including after recovery or the normal no-speech dismissal timer.
    for result in ("Earlier hold transcript", ""):
        audio.with_suffix(".txt").write_text(result)
        hold("Alt_L", "Super_L")
        previous = app.recording
        keys("keyup", "Super_L")
        until(lambda: previous.released is not None)
        keys("keydown", "Super_L")
        notice = app.overlay.hold_notice
        until(notice.get_mapped)
        assert app.recording is previous and app.overlay.label.get_text() == "Live words"
        assert "release and press again" in notice.get_text()
        until(lambda: app.recording is None)
        if result:
            assert app.overlay.recovery == result and app.overlay.actions.get_mapped()
        else:
            deadline = time.monotonic() + 2.4
            until(lambda: time.monotonic() >= deadline)
        assert app.overlay.label.get_text() == (result or "No speech heard")
        assert app.held and notice.get_mapped() and app.recording is None
        assert window.get_focus() is second and app.focus() == previous.target
        keys("keyup", "Super_L", "keyup", "Alt_L")
        until(lambda: not app.held)
        assert not notice.get_visible()
        if result:
            assert app.overlay.recovery == result and app.overlay.get_visible()
            app.overlay.dismiss_recovery()
        else:
            assert not app.overlay.get_visible()
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
            with subprocess.Popen([sys.executable, Path(__file__).with_name("fixture_x11_client.py")],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True) as other:
                exercise(Path(tmp), "--real-model" in sys.argv[1:], other)
        finally:
            server.terminate()
            server.wait()
