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
import json, sys, time
for line in sys.stdin.buffer:
    if line == b":finish\\n":
        time.sleep(.25)
        print(json.dumps({"type":"final", "text":"Finished words."}), flush=True)
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
    from dictate import Dictation, Gdk, Gtk
    from Xlib import X, Xatom, display
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
        until(lambda: app.overlay.label.get_text() != "Listening…", 12)
        assert max(app.overlay.levels) > 0

    start = time.monotonic()
    hold("Super_L", "Alt_L")
    print(f"First partial at {time.monotonic() - start:.2f}s: {app.overlay.label.get_text()}", flush=True)
    release = time.monotonic()
    keys("keyup", "Super_L")
    until(lambda: app.recording.released is not None)
    assert not first.get_text()
    keys("keyup", "Alt_L")
    until(lambda: bool(first.get_text()), 12)
    text = first.get_text()
    print(f"Inserted after {time.monotonic() - release:.2f}s: {text}", flush=True)
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
    app.clipboard.set_text("Existing clipboard", -1)
    hold("Alt_L", "Super_L")
    keys("keyup", "Alt_L", "keyup", "Super_L", "key", "Tab")
    until(lambda: app.overlay.recovery is not None)
    assert second.is_focus() and not second.get_text() and first.get_text() == text
    assert app.clipboard.wait_for_text() == "Existing clipboard"
    app.overlay.copy_recovery()
    assert app.clipboard.wait_for_text() == text
    hold("Alt_L", "Super_L")
    app.worker.kill()
    until(lambda: app.overlay.recovery == "Live words")
    assert not second.get_text()
    keys("keyup", "Alt_L", "keyup", "Super_L")
    until(lambda: not app.held)
    hold("Alt_L", "Super_L")
    keys("key", "Escape", "keyup", "Super_L", "keyup", "Alt_L")
    until(lambda: app.recording is None)
    assert not second.get_text() and app.overlay.label.get_text() == "Cancelled"


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
