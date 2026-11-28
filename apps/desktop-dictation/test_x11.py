#!/usr/bin/python3
"""Run GTK integration checks on a private Xvfb. Add --real-model to exercise T3."""
import os
from pathlib import Path
import signal
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
    run = app.overlay.label.get_layout().get_iter().get_run_readonly()
    assert run.item.analysis.font.describe().get_family() == "Inter"
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
    assert app.overlay.recovery == text
    app.overlay.dismiss_recovery()
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
    if "--chrome" in sys.argv:
        page = directory / "editor.html"
        page.write_text("""<title>Dictation fixture</title>
            <input autofocus oninput="document.title=this.value">
            <div contenteditable oninput="document.title=this.innerText"></div>""")
        sentence = "Hello, T3! Let's send 42 words (OK?)."
        audio.with_suffix(".txt").write_text(sentence)
        chrome = subprocess.Popen(["google-chrome", "--ozone-platform=x11",
            "--user-data-dir=" + str(directory / "chrome-profile"), "--no-first-run",
            "--no-default-browser-check", "--disable-background-networking", "--disable-sync",
            "--disable-extensions", "--disable-gpu", "--password-store=basic",
            "--app=" + page.as_uri()], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            def field():
                return subprocess.run(["xdotool", "search", "--onlyvisible", "--name", "Dictation fixture"],
                                      capture_output=True, text=True).stdout.strip()
            until(field, 20)
            browser = x.create_resource_object("window", int(field().splitlines()[0]))
            x.screen().root.change_property(app.active_atom, Xatom.WINDOW, 32, [browser.id])
            browser.set_input_focus(X.RevertToParent, X.CurrentTime)
            x.sync()
            def title():
                prop = browser.get_full_property(x.intern_atom("_NET_WM_NAME"), X.AnyPropertyType)
                return prop.value.decode() if prop else ""
            owner = x.get_selection_owner(app.selection.atom)
            original_serial = app.paste_serial
            for element in ("input", "contenteditable"):
                if element == "contenteditable":
                    keys("key", "Tab", "key", "Caps_Lock")
                    sentence = "Second field: Caps Lock works, too!"
                    audio.with_suffix(".txt").write_text(sentence)
                hold("Super_L", "Alt_L")
                keys("keyup", "Alt_L", "keyup", "Super_L")
                until(lambda: app.recording is None)
                until(lambda: sentence == title(), 8)
                assert x.get_selection_owner(app.selection.atom) == owner
                assert app.clipboard.wait_for_text() == "Original text"
                print(browser.get_wm_class(), element, title(), flush=True)
            # Exercise the installed T3 class and a layout with directly
            # representable Unicode on the same private Chromium renderer.
            keys("key", "Caps_Lock", "key", "ctrl+a")
            browser.set_wm_class("com.t3tools.t3code", "com.t3tools.T3Code")
            x.sync()
            subprocess.run(["setxkbmap", "de"], check=True)
            sentence = "Grüße aus Köln!"
            audio.with_suffix(".txt").write_text(sentence)
            hold("Alt_L", "Super_L")
            keys("keyup", "Super_L", "keyup", "Alt_L")
            until(lambda: title() == sentence, 8)
            print(browser.get_wm_class(), "German layout", title(), flush=True)
            for unsupported in ("Prefix then newline\n", "Prefix then tab\t", "Prefix then emoji 🐈", "x" * 257):
                audio.with_suffix(".txt").write_text(unsupported)
                hold("Super_L", "Alt_L")
                keys("keyup", "Super_L", "keyup", "Alt_L")
                until(lambda: app.overlay.recovery == unsupported)
                assert title() == sentence
                assert app.paste_serial == original_serial
                assert x.get_selection_owner(app.selection.atom) == owner
        finally:
            chrome.terminate()
            chrome.wait(timeout=10)
            app.stop_worker()
        return
    target = x.create_resource_object("window", xid)
    # A stable active-window property can disagree with actual keyboard focus.
    recipient = x.create_resource_object("window", int(other.stdout.readline()))
    root = x.screen().root
    root.change_property(app.active_atom, Xatom.WINDOW, 32, [recipient.id])
    x.sync()
    before_paste = app.paste_serial
    hold("Super_L", "Alt_L")
    assert not app.glow.get_visible()
    keys("keyup", "Alt_L", "keyup", "Super_L")
    until(lambda: app.overlay.recovery == text)
    assert first.get_text() == text and not second.get_text()
    assert app.paste_serial == before_paste and app.clipboard.wait_for_text() == "Original text"
    app.overlay.dismiss_recovery()
    root.change_property(app.active_atom, Xatom.WINDOW, 32, [xid])
    x.sync()
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
    assert app.x.get_selection_owner(app.selection.atom) == app.selection.window
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
        delayed.append((entry, Gtk.get_current_event_time()))

    handler = first.connect("paste-clipboard", defer_paste)
    hold("Alt_L", "Super_L")
    keys("keyup", "Alt_L", "keyup", "Super_L")
    until(lambda: bool(delayed))
    first.disconnect(handler)
    _, key_time = delayed.pop()
    assert key_time != X.CurrentTime
    def other_read(expected, command="read"):
        recipient.delete_property(prop)
        x.sync()
        other.stdin.write(command + "\n")
        other.stdin.flush()
        until(lambda: recipient.get_full_property(prop, utf8) is not None)
        assert recipient.get_full_property(prop, utf8).value == expected

    other_read(b"Newer clipboard")
    assert app.pending_backup is not None
    def secondary_read(expected, timestamp):
        reader.delete_property(prop)
        reader.convert_selection(app.selection.atom, utf8, prop, timestamp)
        x.flush()
        until(lambda: reader.get_full_property(prop, utf8) is not None)
        value = reader.get_full_property(prop, utf8).value
        assert value == expected
        return value

    secondary_read(text.encode(), key_time)
    until(lambda: app.pending_backup is None)
    assert app.clipboard.wait_for_text() == "Newer clipboard"

    assert app.overlay.recovery == text
    app.overlay.dismiss_recovery()

    # arboard-style readers use CurrentTime even inside the V handler.
    # Exercise the value the field would actually insert, including recovery.
    generation = app.clipboard_generation
    app.clipboard.set_text("CurrentTime sentinel", -1)
    until(lambda: app.clipboard_generation > generation)
    handler = first.connect("paste-clipboard", defer_paste)
    hold("Alt_L", "Super_L")
    keys("keyup", "Alt_L", "keyup", "Super_L")
    until(lambda: bool(delayed))
    first.disconnect(handler)
    entry, _ = delayed.pop()
    entry.set_text(entry.get_text() + secondary_read(b"", X.CurrentTime).decode())
    until(lambda: app.pending_backup is None and app.overlay.recovery == text)
    assert entry.get_text() == text
    app.overlay.copy_recovery()
    secondary_read(b"", X.CurrentTime)
    secondary_read(b"", X.CurrentTime)
    other_read(text.encode())
    assert app.overlay.resume.get_mapped() and not app.overlay.copy_button.get_visible()
    app.overlay.resume.clicked()
    assert not app.overlay.get_visible()
    secondary_read(text.encode(), X.CurrentTime)

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
    # The same GTK process reads outside the shortcut handler. It must
    # neither see either clipboard value nor acknowledge A's shortcut.
    ordinary = []
    app.clipboard.request_text(lambda _, value, _data: ordinary.append(value), None)
    until(lambda: bool(ordinary))
    assert not ordinary[0] and app.pending_backup is not None
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
    secondary_read(b"", X.CurrentTime)
    secondary_read(b"", X.CurrentTime)
    entry, key_time = delayed.pop()
    entry.set_text(entry.get_text() + secondary_read(b"", key_time).decode())
    app.overlay.resume.clicked()
    assert not first.get_text() and not second.get_text()
    keys("key", "ctrl+v")
    until(lambda: second.get_text() == "Second transcript")
    second.set_text("")
    assert app.overlay.recovery == "Ignored transcript"
    assert not app.overlay.resume.get_visible() and not app.paused_clients
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
    delayed.pop()[0].emit("paste-clipboard")
    until(lambda: first.get_text() == "Copied during pending paste")
    other_read(b"")
    assert app.pending_backup is not None
    other_read(b"Other client transcript", "key-time")
    until(lambda: app.pending_backup is None)
    assert app.clipboard.wait_for_text() == "Copied during pending paste"
    assert app.overlay.recovery == "Other client transcript"
    app.overlay.dismiss_recovery()
    x.screen().root.change_property(app.active_atom, Xatom.WINDOW, 32, [xid])
    x.create_resource_object("window", xid).set_input_focus(X.RevertToParent, X.CurrentTime)
    xres = app.selection.xres
    app.selection.xres = None
    try:
        assert app.selection.client_id(reader.id) != app.selection.client_id(xid)
        assert app.selection.client_id(reader.id) == ("connection", x.display.info.resource_id_base)
    finally:
        app.selection.xres = xres
    x.sync()
    until(lambda: app.overlay.recovery is not None)
    app.overlay.resume.clicked()
    assert not app.paused_clients
    app.overlay.dismiss_recovery()

    # Without a verified focused process a second connection might otherwise
    # paste the previous clipboard, so send no shortcut at all.
    app.selection.xres = None
    try:
        serial = app.paste_serial
        hold("Alt_L", "Super_L")
        keys("keyup", "Super_L", "keyup", "Alt_L")
        until(lambda: app.overlay.recovery == "Other client transcript")
        assert app.paste_serial == serial and app.pending_backup is None
        app.overlay.dismiss_recovery()
    finally:
        app.selection.xres = xres

    # An empty selection and an intervening owner cannot tell us whether
    # the first shortcut was consumed. Copy must guard either recovery card.
    for intervening_copy in (False, True):
        app.clipboard.set_text("Clipboard before A", -1)
        if not intervening_copy:
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
        if intervening_copy:
            assert app.pending_backup is not None
            app.clipboard.set_text("External copy", -1)
            Gdk.Display.get_default().sync()
            owner = app.x.get_selection_owner(app.selection.atom)
            assert owner and owner != app.selection.window
        until(lambda: app.overlay.recovery == "Recovered B" and app.recording is None)
        if intervening_copy:
            assert app.x.get_selection_owner(app.selection.atom) == owner
            other_read(b"External copy")
        app.overlay.copy_recovery()
        assert not app.clipboard.wait_for_text()
        assert not app.clipboard.wait_for_text()
        other_read(b"Recovered B")
        # Wait for the GTK field's own deferred conversion before releasing the guard.
        conversions = []
        serve = app.selection.serve
        def observe_paste(request):
            serve(request)
            if request.target in app.selection.formats:
                conversions.append(request.target)
        app.selection.serve = observe_paste
        try:
            delayed.pop()[0].emit("paste-clipboard")
            until(lambda: bool(conversions))
        finally:
            app.selection.serve = serve
        assert not first.get_text()
        app.overlay.resume.clicked()
        keys("key", "ctrl+v")
        until(lambda: second.get_text() == "Recovered B")
        assert not first.get_text()
        second.set_text("")
        assert not app.overlay.resume.get_visible()
        app.overlay.dismiss_recovery()

    app.clipboard.set_text("Restored compound text", -1)
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
    delayed.pop()[0].emit("paste-clipboard")
    until(lambda: app.pending_backup is None and app.overlay.recovery == "Second delayed transcript")
    assert not first.get_text() and not second.get_text()
    compound = Gdk.Atom.intern("COMPOUND_TEXT", False)
    def compound_read():
        data = app.clipboard.wait_for_contents(compound)
        return data.get_data_type().name(), data.get_format(), bytes(data.get_data() or b"")
    assert compound_read() == ("COMPOUND_TEXT", 8, b"")
    assert compound_read() == ("COMPOUND_TEXT", 8, b"")
    app.overlay.resume.clicked()
    assert compound_read() == ("COMPOUND_TEXT", 8, b"Restored compound text")
    reader.destroy()
    while app.overlay.recovery is not None:
        app.overlay.dismiss_recovery()

    # Consecutive GTK pastes retain only the latest acknowledged card.
    for entry, transcript in ((first, "Direct A"), (second, "Direct B")):
        entry.grab_focus()
        audio.with_suffix(".txt").write_text(transcript)
        hold("Alt_L", "Super_L")
        keys("keyup", "Super_L", "keyup", "Alt_L")
        until(lambda: entry.get_text() == transcript and app.pending_backup is None)
    assert app.overlay.pending == [("Direct B", False, None)]
    assert app.overlay.status.get_text() == "Sent to app"
    until(lambda: not app.overlay.get_visible(), 6)
    os.kill(os.getpid(), signal.SIGUSR1)
    until(lambda: app.overlay.get_visible() and app.overlay.recovery == "Direct B")
    assert window.get_focus() is second
    app.overlay.dismiss_recovery()
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

    app.clipboard.set_text("Temporary value", -1)
    app.clipboard.clear()
    until(lambda: not app.x.get_selection_owner(app.selection.atom))
    early_reads = []
    def read_before_default(_entry):
        early_reads.append(app.clipboard.wait_for_text())
        idle = []
        from gi.repository import GLib
        GLib.idle_add(lambda: idle.append(True))
        until(lambda: bool(idle))
    handler = second.connect("paste-clipboard", read_before_default)
    audio.with_suffix(".txt").write_text("Empty clipboard start")
    hold("Super_L", "Alt_L")
    keys("keyup", "Alt_L", "keyup", "Super_L")
    until(lambda: second.get_text() == "Empty clipboard start")
    assert early_reads == ["Empty clipboard start"]
    second.disconnect(handler)
    until(lambda: app.pending_backup is None)
    assert not app.x.get_selection_owner(app.selection.atom)
    second.set_text("")
    app.overlay.dismiss_recovery()

    # An ordinary read *inside* GTK's key handler and the entry's default
    # paste can have identical wire fields, including requestor and time.
    fields = []
    serve = app.selection.serve
    def observe(request):
        if request.target in app.selection.formats:
            fields.append((request.requestor.id, request.selection, request.target,
                           request.property, request.time))
        serve(request)
    app.selection.serve = observe
    generation = app.clipboard_generation
    app.clipboard.set_text("Before GTK handler", -1)
    until(lambda: app.clipboard_generation > generation)
    observed = []
    def inspect_before_paste(entry):
        observed.append(app.clipboard.wait_for_text())
        # Ensure the later reads really do run after the idle restoration.
        until(lambda: app.pending_backup is None)
        plain = Gdk.Atom.intern("STRING", False)
        observed.append(bytes(app.clipboard.wait_for_contents(plain).get_data()).decode())
    handler = second.connect("paste-clipboard", inspect_before_paste)
    audio.with_suffix(".txt").write_text("Intended field text")
    hold("Alt_L", "Super_L")
    keys("keyup", "Super_L", "keyup", "Alt_L")
    until(lambda: second.get_text() == "Intended field text")
    second.disconnect(handler)
    gesture = fields[-3:]
    assert observed == ["Intended field text"] * 2
    assert gesture[0] == gesture[2] and gesture[0][-1] != X.CurrentTime, gesture
    assert gesture[1][-1] == gesture[0][-1] and gesture[1][2] != gesture[0][2], gesture
    assert app.overlay.recovery == "Intended field text"
    assert app.clipboard.wait_for_text() == "Before GTK handler"
    other_read(b"Before GTK handler")
    # A newer acknowledged paste must not revive A, even when replayed by
    # the same process on another connection.
    reader = x.screen().root.create_window(0, 0, 1, 1, 0, 0, X.InputOnly, X.CopyFromParent)
    audio.with_suffix(".txt").write_text("Later transcript")
    second.set_text("")
    hold("Alt_L", "Super_L")
    keys("keyup", "Super_L", "keyup", "Alt_L")
    until(lambda: second.get_text() == "Later transcript")
    secondary_read(b"", gesture[0][-1])
    assert app.clipboard.wait_for_text() == "Before GTK handler"
    # Lock while the latest conversion still has replayable text.
    from gi.repository import GLib
    current_time = app.selection.replay[0]
    app.lock_changed(None, None, "ActiveChanged", GLib.Variant("(b)", (True,)))
    assert app.selection.replay is None and not app.overlay.pending
    app.show_last()
    assert not app.overlay.get_visible() and app.overlay.confirmed_card is None
    secondary_read(b"", current_time)
    other_read(b"Before GTK handler")
    app.lock_changed(None, None, "ActiveChanged", GLib.Variant("(b)", (False,)))

    # A wrapped server timestamp is indistinguishable from an old request.
    # Simulate just the repeated XI2 timestamp on the dispatched shortcut.
    handler = second.connect("paste-clipboard", defer_paste)
    audio.with_suffix(".txt").write_text("Wrapped event")
    hold("Alt_L", "Super_L")
    keys("keyup", "Super_L", "keyup", "Alt_L")
    until(lambda: bool(delayed))
    second.disconnect(handler)
    entry, _ = delayed.pop()
    app.selection.press_time = gesture[0][-1]
    entry.set_text(secondary_read(b"", gesture[0][-1]).decode())
    assert app.pending_backup is not None
    until(lambda: app.overlay.recovery == "Wrapped event")
    assert not entry.get_text()
    other_read(b"Before GTK handler")
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
