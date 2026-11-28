#!/usr/bin/python3
"""Exercise desktop dictation on a private Xvfb with GTK or optional Chrome."""
import json
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
        # Exercise the worker with an empty home and just its own runtime and models.
        installed = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "desktop-dictation"
        fixture_home = directory / "home"
        data_home = fixture_home / ".local/share"
        app_data = data_home / "desktop-dictation"
        app_data.mkdir(parents=True)
        for asset in (installed / "models", *installed.glob("engine-*")):
            (app_data / asset.name).symlink_to(asset)
        os.environ.update(HOME=str(fixture_home), XDG_DATA_HOME=str(data_home),
                          XDG_CONFIG_HOME=str(fixture_home / ".config"))
        os.environ.pop("DESKTOP_DICTATION_WORKER", None)
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
        os.environ["DESKTOP_DICTATION_WORKER"] = str(worker)
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
        until(lambda: bool(app.recording.last_partial), 15)
        assert max(app.overlay.levels) > 0

    app.clipboard.set_text("Original text", -1)
    until(lambda: app.clipboard_generation > 0)
    start = time.monotonic()
    hold("Super_L", "Alt_L")
    until(app.glow.get_mapped)
    run = app.overlay.label.get_layout().get_iter().get_run_readonly()
    assert app.overlay.wave.get_visible()
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
    assert not app.overlay.wave.get_visible()
    assert app.overlay.label.get_ellipsize().value_nick == "end"
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
        if "--chrome" not in sys.argv:
            app.stop_worker()
            return
    else:
        assert text == "Finished words."
    assert paste_shortcut(("gnome-terminal-server", "Gnome-terminal")) == (XK.XK_Control_L, XK.XK_Shift_L, XK.XK_v)
    if "--chrome" in sys.argv:
        page = directory / "editor.html"
        page.write_text("""<meta charset="utf-8"><title>Dictation fixture</title>
            <input id="first" autofocus><textarea id="second"></textarea>
            <div id="editor" contenteditable></div><input id="next">
            <script>
            function ready() {
              if (document.hasFocus() && document.activeElement.id === "first")
                document.title = "Dictation fixture ready";
              else requestAnimationFrame(ready);
            }
            ready();
            const edits = [];
            document.oninput = event => {
              const field = event.target;
              edits.push([field.id, event.inputType, field.value ?? field.innerText]);
              document.title = JSON.stringify(edits);
              field.nextElementSibling.focus();
            };
            </script>""")
        chrome = subprocess.Popen(["google-chrome", "--ozone-platform=x11",
            "--user-data-dir=" + str(directory / "chrome-profile"), "--no-first-run",
            "--no-default-browser-check", "--disable-background-networking", "--disable-sync",
            "--disable-extensions", "--disable-gpu", "--password-store=basic",
            page.as_uri()], env=dict(os.environ,
                DBUS_SESSION_BUS_ADDRESS="unix:path=" + str(directory / "no-session-bus"),
                GTK_USE_PORTAL="0"), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
                # Read the fixture's edit log in one X request as Chrome updates it.
                prop = browser.get_full_property(x.intern_atom("_NET_WM_NAME"), X.AnyPropertyType, sizehint=1024)
                return prop.value.decode() if prop else ""
            until(lambda: title().startswith("Dictation fixture ready"))
            expected = []
            for name, direction in (("first", "Center"), ("second", "Left"), ("editor", "Right")):
                serial = app.paste_serial
                sentence = f"One complete sentence for {name}."
                if real:
                    subprocess.run(["sox", samples / f"Front_{direction}.wav", "-r", "16000", "-c", "1",
                                    "-b", "16", "-e", "signed", "-t", "raw", audio], check=True)
                else:
                    audio.with_suffix(".txt").write_text(sentence)
                hold("Super_L", "Alt_L")
                if real:
                    until(lambda: time.monotonic() - app.recording.started >= 2)
                keys("keyup", "Alt_L", "keyup", "Super_L")
                until(lambda: app.recording is None, 12)
                if real:
                    until(lambda: app.overlay.recovery and direction.lower() in app.overlay.recovery.lower())
                    sentence = app.overlay.recovery
                expected.append([name, "insertFromPaste", sentence])
                def correct_edits():
                    current = title()
                    return current.startswith("[") and json.JSONDecoder().raw_decode(current)[0] == expected
                try:
                    until(correct_edits)
                except AssertionError as exc:
                    raise AssertionError(
                        f"{name} expected {expected!r}, browser title {title()!r}, "
                        f"status {app.overlay.status.get_text()!r}, "
                        f"paste serial {serial} → {app.paste_serial}") from exc
                assert app.paste_serial == serial + 1
                assert app.clipboard.wait_for_text() == "Original text"
                print(name, "native paste", sentence, flush=True)
            until(lambda: app.pending_backup is None)
            assert app.clipboard.wait_for_text() == "Original text"
        finally:
            chrome.terminate()
            chrome.wait(timeout=10)
            app.stop_worker()
        return
    from gi.repository import GdkPixbuf
    pixels = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, 400, 300)
    pixels.fill(0x317baa93)
    pixels.new_subpixbuf(3, 5, 127, 189).fill(0xed081234)
    generation = app.clipboard_generation
    app.clipboard.set_image(pixels)
    until(lambda: app.clipboard_generation > generation)
    first.set_text("")
    serial = app.paste_serial
    hold("Super_L", "Alt_L")
    backup = app.recording.backup
    until(lambda: backup.ready)
    assert set(backup.values) == {x.intern_atom("image/png")}
    keys("keyup", "Alt_L", "keyup", "Super_L")
    until(lambda: first.get_text() == text and app.pending_backup is None)
    assert app.paste_serial == serial + 1
    restored = app.clipboard.wait_for_image()
    assert (restored.get_width(), restored.get_height()) == (400, 300)
    assert restored.get_pixels() == pixels.get_pixels()
    app.overlay.dismiss_recovery()
    # A PNG plus independently authored project data is a compound offer.
    # Exercise both successful and refused conversions from a widget owner.
    from selection import ClipboardBackup
    owner = Gtk.Invisible()
    owner.realize()
    clip = Gdk.SELECTION_CLIPBOARD
    png = Gdk.Atom.intern("image/png", False)
    project = Gdk.Atom.intern("application/x-test-project", False)
    Gtk.selection_add_target(owner, clip, png, 1)
    Gtk.selection_add_target(owner, clip, project, 2)
    project_data = b"layers and editable shapes"
    refuse_project = False
    requested = []

    def offer_project(widget, data, info, timestamp):
        requested.append(info)
        if info == 1:
            data.set(png, 8, backup.values[x.intern_atom("image/png")][2])
        elif not refuse_project:
            data.set(project, 8, project_data)

    owner.connect("selection-get", offer_project)
    generation = app.clipboard_generation
    assert Gtk.selection_owner_set(owner, clip, Gdk.CURRENT_TIME)
    until(lambda: app.clipboard_generation > generation)
    original_owner = x.get_selection_owner(app.selection.atom)
    mixed = ClipboardBackup(app.clipboard, x, original_owner)
    until(lambda: mixed.ready)
    assert mixed.values[x.intern_atom("image/png")] == backup.values[x.intern_atom("image/png")]
    assert mixed.values[x.intern_atom(project.name())][2] == project_data
    refuse_project = True
    requested.clear()
    serial = app.paste_serial
    hold("Super_L", "Alt_L")
    until(lambda: 2 in requested)
    keys("keyup", "Alt_L", "keyup", "Super_L")
    until(lambda: app.recording is None and app.overlay.recovery == text)
    assert x.get_selection_owner(app.selection.atom) == original_owner and app.paste_serial == serial
    refuse_project = False
    assert bytes(app.clipboard.wait_for_contents(project).get_data()) == project_data
    app.overlay.dismiss_recovery()
    # An oversized offer must keep its original owner and Copy recovery.
    original = "x" * (8 * 1024 * 1024 + 1)
    generation = app.clipboard_generation
    app.clipboard.set_text(original, -1)
    until(lambda: app.clipboard_generation > generation)
    original_owner = x.get_selection_owner(app.selection.atom)
    serial = app.paste_serial
    hold("Super_L", "Alt_L")
    keys("keyup", "Alt_L", "keyup", "Super_L")
    until(lambda: app.recording is None and app.overlay.recovery == text)
    assert x.get_selection_owner(app.selection.atom) == original_owner
    assert app.paste_serial == serial and app.clipboard.wait_for_text() == original
    app.overlay.dismiss_recovery()
    generation = app.clipboard_generation
    app.clipboard.set_text("Original text", -1)
    until(lambda: app.clipboard_generation > generation)
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
        assert app.overlay.status.get_text() == "Use Copy in this app"
        assert app.paste_serial == serial and first.get_text() == text
        assert app.clipboard.wait_for_text() == "Original text"
        app.overlay.dismiss_recovery()
    target.set_wm_class(*original_class)
    x.sync()
    # A backup can be too large or still pending at release. Explain why
    # the original clipboard and both fields were preserved.
    hold("Alt_L", "Super_L")
    until(lambda: app.recording.backup.ready)
    app.recording.backup.ready = False
    keys("keyup", "Alt_L", "keyup", "Super_L")
    until(lambda: app.overlay.recovery == text)
    assert app.overlay.status.get_text() == "Couldn’t back up clipboard"
    assert app.paste_serial == serial and app.clipboard.wait_for_text() == "Original text"
    app.overlay.dismiss_recovery()

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

    def native_paste_refused(entry):
        # GTK tries UTF8_STRING, COMPOUND_TEXT, then STRING. Wait until the
        # terminal response is on the wire before allowing Copy or Resume.
        serve = app.selection.serve
        targets = []
        def observe(request):
            serve(request)
            targets.append(request.target)
        app.selection.serve = observe
        try:
            entry.emit("paste-clipboard")
            until(lambda: Xatom.STRING in targets)
            assert utf8 in targets and x.intern_atom("COMPOUND_TEXT") in targets
        finally:
            app.selection.serve = serve

    handler = first.connect("paste-clipboard", defer_paste)
    hold("Alt_L", "Super_L")
    keys("keyup", "Alt_L", "keyup", "Super_L")
    until(lambda: bool(delayed))
    first.disconnect(handler)
    _, key_time = delayed.pop()
    assert key_time != X.CurrentTime
    def other_read(expected, command="read", target=utf8):
        recipient.delete_property(prop)
        x.sync()
        other.stdin.write(command + "\n")
        other.stdin.flush()
        until(lambda: recipient.get_full_property(prop, target) is not None)
        assert recipient.get_full_property(prop, target).value == expected

    other_read(b"Newer clipboard")
    assert app.pending_backup is not None
    def secondary_read(expected, timestamp, target=utf8):
        reader.delete_property(prop)
        reader.convert_selection(app.selection.atom, target, prop, timestamp)
        x.flush()
        def notified():
            while x.pending_events():
                event = x.next_event()
                if event.type == X.SelectionNotify and event.requestor == reader:
                    assert (event.selection, event.target, event.time) == (app.selection.atom, target, timestamp)
                    assert event.property == (X.NONE if expected is None else prop)
                    return True
        until(notified)
        result = reader.get_full_property(prop, X.AnyPropertyType)
        value = None if result is None else result.value
        if result is not None and target == app.selection.targets:
            assert result.property_type == Xatom.ATOM and result.format == 32
            value = list(value)
        elif result is not None:
            assert result.property_type == target
        assert value == expected, (value, expected)
        return value

    def retired_read(timestamp, queued_input=None):
        while x.pending_events():
            x.next_event()
        reader.delete_property(prop)
        reader.convert_selection(app.selection.atom, utf8, prop, timestamp)
        x.sync()
        if queued_input:
            queued_input()
        def answered():
            while x.pending_events():
                event = x.next_event()
                if event.type == X.SelectionNotify and event.requestor == reader:
                    return True
            return False
        until(answered)
        data = reader.get_full_property(prop, utf8)
        assert data is None or data.value == b"", data.value

    secondary_read(text.encode(), key_time)
    until(lambda: app.pending_backup is None)
    assert app.clipboard.wait_for_text() == "Newer clipboard"

    secondary_read(text.encode(), key_time)
    keys("key", "Tab")
    until(lambda: window.get_focus() is second)
    retired_read(key_time)
    assert not app.paused_clients
    assert app.clipboard.wait_for_text() == "Newer clipboard"
    first.grab_focus()
    assert app.overlay.recovery == text
    app.overlay.dismiss_recovery()

    # A transient switch can leave the snapshot identical when the old
    # timestamp is presented. Exercise both X focus and the WM active window.
    for redirect in ("focus", "active window", "expiry"):
        handler = first.connect("paste-clipboard", defer_paste)
        hold("Alt_L", "Super_L")
        keys("keyup", "Super_L", "keyup", "Alt_L")
        until(lambda: bool(delayed))
        first.disconnect(handler)
        _, stamp = delayed.pop()
        secondary_read(text.encode(), stamp)
        until(lambda: app.pending_backup is None)
        if redirect == "focus":
            recipient.set_input_focus(X.RevertToParent, X.CurrentTime)
            x.create_resource_object("window", xid).set_input_focus(X.RevertToParent, X.CurrentTime)
        elif redirect == "active window":
            for active in (recipient.id, xid):
                x.screen().root.change_property(app.active_atom, Xatom.WINDOW, 32, [active])
        else:
            until(lambda: app.selection.replay is None)
        x.sync()
        retired_read(stamp)
        assert not app.paused_clients and app.overlay.recovery == text
        assert not app.root.get_attributes().your_event_mask
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
    entry, current_gesture = delayed.pop()
    offered = [app.selection.targets, app.selection.timestamp, *app.selection.formats]
    entry.set_text(secondary_read(text.encode(), X.CurrentTime).decode())
    first_read = time.monotonic()
    until(lambda: time.monotonic() >= first_read + .20)
    secondary_read(offered, X.CurrentTime, app.selection.targets)
    # Chrome's final read can follow the first payload's 350 ms quiet timer.
    until(lambda: time.monotonic() >= first_read + .40)
    assert app.pending_backup is not None
    secondary_read(text.encode(), X.CurrentTime)
    until(lambda: app.pending_backup is None and app.overlay.recovery == text)
    assert entry.get_text() == text and not app.paused_clients
    secondary_read(text.encode(), current_gesture)
    xres = app.selection.xres
    app.selection.xres = None
    try:
        secondary_read(None, current_gesture)
    finally:
        app.selection.xres = xres
    secondary_read(b"CurrentTime sentinel", X.CurrentTime)
    # The server already queued the conversion when the pointer redirected
    # the gesture. Both events await dispatch on the selection connection.
    retired_read(current_gesture, lambda: keys("click", "1"))
    first.grab_focus()
    assert not app.paused_clients
    app.overlay.dismiss_recovery()

    # A key after dispatch but before the application's first read can
    # change the field. Keep the transcript for recovery in this case.
    handler = first.connect("paste-clipboard", defer_paste)
    hold("Alt_L", "Super_L")
    keys("keyup", "Alt_L", "keyup", "Super_L")
    until(lambda: bool(delayed))
    first.disconnect(handler)
    delayed.pop()
    keys("key", "Right")
    until(lambda: app.overlay.resume.is_visible() and app.pending_backup is None)
    app.overlay.dismiss_recovery()
    assert not app.overlay.get_visible()
    os.kill(os.getpid(), signal.SIGUSR1)  # Last Dictation launcher
    until(lambda: app.overlay.resume.get_mapped())
    assert app.overlay.status.get_text() == "Auto-paste paused"
    assert next(iter(app.paused_clients.values())) in app.overlay.label.get_text()
    assert not app.overlay.copy_button.get_visible()
    secondary_read(None, X.CurrentTime)
    app.show_last()
    assert len(app.overlay.pending) == 1
    app.overlay.resume.clicked()
    secondary_read(b"CurrentTime sentinel", X.CurrentTime)
    assert not app.paused_clients and not app.overlay.get_visible()

    # The first CurrentTime conversion can precede GTK's actual insertion.
    # Tab changes the focused entry without changing the X11 target window.
    for clipboard_kind in ("text", "no owner", "image", "empty text"):
        app.clipboard.set_text("Newer clipboard", -1)
        if clipboard_kind == "image":
            app.clipboard.set_image(pixels)
        elif clipboard_kind == "empty text":
            app.clipboard.set_text("", -1)
        elif clipboard_kind == "no owner":
            app.clipboard.clear()
            until(lambda: not app.x.get_selection_owner(app.selection.atom))
        first.grab_focus()
        handler = first.connect("paste-clipboard", defer_paste)
        cards_before = len(app.overlay.pending)
        hold("Super_L", "Alt_L")
        keys("keyup", "Alt_L", "keyup", "Super_L")
        until(lambda: bool(delayed))
        first.disconnect(handler)
        delayed.pop()
        secondary_read(text.encode(), X.CurrentTime)
        assert app.pending_backup is not None
        assert not app.overlay.status.get_text().startswith("Sent")
        keys("key", "Tab")
        until(lambda: second.has_focus() and app.pending_backup is None)
        keep = "KEEP THIS SELECTION"
        second.set_text(keep)
        second.select_region(0, -1)
        if clipboard_kind == "no owner":
            second.emit("paste-clipboard")
            # The X server answers GTK directly when there is no owner.
            until_time = time.monotonic() + .15
            until(lambda: time.monotonic() >= until_time)
        else:
            native_paste_refused(second)
        assert second.get_text() == keep and second.get_selection_bounds() == (0, len(keep))
        assert app.overlay.status.get_text().startswith("Auto-paste paused")
        assert app.overlay.resume.is_visible() and app.overlay.recovery == text
        assert len(app.overlay.pending) == cards_before + 1
        if clipboard_kind == "no owner":
            assert not app.x.get_selection_owner(app.selection.atom)
        elif clipboard_kind == "image":
            png_atom = x.intern_atom("image/png")
            secondary_read(None, X.CurrentTime, app.selection.targets)
            secondary_read(None, X.CurrentTime, png_atom)
            assert not app.clipboard.wait_is_image_available()
            assert app.clipboard.wait_for_image() is None
            other_read(backup.values[png_atom][2], "image/png", png_atom)
        else:
            other_read(b"Newer clipboard" if clipboard_kind == "text" else b"")
        if clipboard_kind in ("image", "empty text"):
            app.overlay.resume.clicked()
            if clipboard_kind == "image":
                assert app.clipboard.wait_for_image().get_pixels() == pixels.get_pixels()
            else:
                secondary_read(b"", X.CurrentTime)
            app.overlay.copy_recovery()
        else:
            app.overlay.copy_recovery()
            other_read(text.encode())
            secondary_read(None, X.CurrentTime)
            app.overlay.resume.clicked()
        keys("key", "ctrl+v")
        until(lambda: second.get_text() == text)
        second.set_text("")
        assert not app.paused_clients and len(app.overlay.pending) == cards_before

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
    # TARGETS alone must still expire to Copy/Resume recovery.
    secondary_read(offered, X.CurrentTime, app.selection.targets)
    assert app.selection.replay is None
    # The same GTK process reads outside the shortcut handler. It must
    # neither see either clipboard value nor acknowledge A's shortcut.
    ordinary = []
    app.clipboard.request_text(lambda _, value, _data: ordinary.append(value), None)
    until(lambda: bool(ordinary))
    assert ordinary == [None] and app.pending_backup is not None
    other_read(b"Original before two holds")
    until(lambda: app.pending_backup is None and app.overlay.resume.is_visible())
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
    secondary_read(None, X.CurrentTime)
    secondary_read(None, X.CurrentTime)
    entry, key_time = delayed.pop()
    secondary_read(None, key_time)
    app.overlay.resume.clicked()
    secondary_read(None, key_time)
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
        assert app.clipboard.wait_for_text() is None
        assert app.clipboard.wait_for_text() is None
        other_read(b"Recovered B")
        entry, expired_time = delayed.pop()
        native_paste_refused(entry)
        assert not first.get_text()
        app.overlay.resume.clicked()
        secondary_read(None, expired_time)
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
        if data is None:
            return None
        return data.get_data_type().name(), data.get_format(), bytes(data.get_data() or b"")
    assert compound_read() is None
    assert compound_read() is None
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
    assert len(app.overlay.pending) == 1 and app.overlay.recovery == "Direct B"
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
    # Typing after the text actually lands must leave the next hold usable,
    # including when there was no previous clipboard owner to restore.
    keys("key", "x")
    until(lambda: second.get_text() == "Empty clipboard startx" and app.pending_backup is None)
    assert not app.paused_clients and not app.overlay.resume.get_visible()
    serial = app.paste_serial
    audio.with_suffix(".txt").write_text("Again")
    hold("Alt_L", "Super_L")
    keys("keyup", "Super_L", "keyup", "Alt_L")
    until(lambda: second.get_text() == "Empty clipboard startxAgain")
    until(lambda: app.pending_backup is None)
    assert app.paste_serial == serial + 1 and not app.paused_clients
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
    # The GTK default paste still carries the original event time after a
    # nested event loop moved the caret inside the same entry.
    second.set_text("AB")
    second.set_position(0)
    before_default = []
    def move_before_default(entry):
        preflight = app.clipboard.wait_for_text()
        until(lambda: app.pending_backup is None)
        keys("key", "Right")
        until(lambda: entry.get_position() == 1)
        before_default.append((preflight, len(fields), Gtk.get_current_event_time()))
    handler = second.connect("paste-clipboard", move_before_default)
    hold("Alt_L", "Super_L")
    keys("keyup", "Super_L", "keyup", "Alt_L")
    until(lambda: before_default and len(fields) > before_default[0][1])
    second.disconnect(handler)
    preflight, _, timestamp = before_default[0]
    assert preflight == "Intended field text" and fields[-1][-1] == timestamp != X.CurrentTime
    # Let GTK process SelectionNotify and finish its asynchronous insertion.
    delivered = time.monotonic() + .15
    until(lambda: time.monotonic() >= delivered)
    assert (second.get_text(), second.get_position()) == ("AB", 1)
    assert not app.paused_clients
    # A newer acknowledged paste must not revive A, even when replayed by
    # the same process on another connection.
    reader = x.screen().root.create_window(0, 0, 1, 1, 0, 0, X.InputOnly, X.CopyFromParent)
    audio.with_suffix(".txt").write_text("Later transcript")
    second.set_text("")
    hold("Alt_L", "Super_L")
    keys("keyup", "Super_L", "keyup", "Alt_L")
    until(lambda: second.get_text() == "Later transcript")
    secondary_read(None, gesture[0][-1])
    assert app.clipboard.wait_for_text() == "Before GTK handler"
    # Lock while the latest conversion still has replayable text.
    from gi.repository import GLib
    current_time = app.selection.replay[0]
    app.lock_changed(None, None, "ActiveChanged", GLib.Variant("(b)", (True,)))
    assert app.selection.replay is None and not app.overlay.pending
    app.show_last()
    assert not app.overlay.get_visible() and app.overlay.confirmed_card is None
    secondary_read(None, current_time)
    other_read(b"Before GTK handler")
    app.lock_changed(None, None, "ActiveChanged", GLib.Variant("(b)", (False,)))

    # A wrapped server timestamp is indistinguishable from an old request.
    # Simulate just the repeated XI2 timestamp on the dispatched shortcut.
    from unittest.mock import patch
    handler = second.connect("paste-clipboard", defer_paste)
    audio.with_suffix(".txt").write_text("Wrapped event")
    dispatch = app.selection.dispatch
    with patch.object(app.selection, "dispatch", lambda _: dispatch(gesture[0][-1])):
        hold("Alt_L", "Super_L")
        keys("keyup", "Super_L", "keyup", "Alt_L")
        until(lambda: bool(delayed) and app.selection.press_time == gesture[0][-1])
    second.disconnect(handler)
    entry, _ = delayed.pop()
    secondary_read(None, X.CurrentTime)
    secondary_read(None, gesture[0][-1])
    assert app.pending_backup is not None
    until(lambda: app.overlay.recovery == "Wrapped event")
    assert entry.get_text() == "Later transcript"
    other_read(b"Before GTK handler")

    # When the timestamp table is full, a fresh hold goes to recovery and
    # old timestamps still guard a later explicit Copy.
    app.overlay.resume.clicked()
    serial = app.paste_serial
    with patch("selection.MAX_GESTURES", len(app.selection.gestures)):
        audio.with_suffix(".txt").write_text("At capacity")
        hold("Alt_L", "Super_L")
        keys("keyup", "Super_L", "keyup", "Alt_L")
        until(lambda: app.overlay.recovery == "At capacity")
        assert app.paste_serial == serial
        app.overlay.copy_recovery()
        secondary_read(None, gesture[0][-1])
        secondary_read(b"At capacity", X.CurrentTime)
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
