#!/usr/bin/python3
"""Hold a key to dictate into the focused X11 application."""
import audioop
import base64
import json
import os
import queue
import signal
import struct
import subprocess
import sys
import threading
import time
from pathlib import Path

from selection import ClipboardBackup, TextSelection
from overlay import Gdk, GLib, Gtk, Overlay
from gi.repository import GdkX11, Gio
from Xlib import X, XK, display, error
from Xlib.ext import xinput, xtest


class Recording:
    def __init__(self, app):
        self.app = app
        self.started = time.monotonic()
        self.released = None
        self.finished = False
        self.got_final = False
        self.last_partial = ""
        self.unsafe = False
        self.target = app.focus()
        self.clipboard_generation = app.clipboard_generation
        self.clipboard_owner = app.x.get_selection_owner(app.selection.atom)
        self.backup = ClipboardBackup(app.clipboard, app.x, self.clipboard_owner)
        self.cancelled = False
        self.audio = queue.Queue(maxsize=7500)  # Five minutes at 40 ms per block.
        self.worker = self.mic = None
        try:
            self.mic = subprocess.Popen([
                "parec", "--raw", "--format=s16le", "--rate=16000", "--channels=1",
                "--latency-msec=40", "--process-time-msec=20",
            ], stdout=subprocess.PIPE)
            self.worker = app.get_worker()
        except OSError:
            self.close()
            raise
        for target in (self.capture, self.feed, self.read_result):
            threading.Thread(target=target, daemon=True).start()

    def post(self, callback, *args):
        def deliver():
            if self.app.recording is self:
                callback(*args)
            return False
        GLib.idle_add(deliver)

    def capture(self):
        carry = b""
        try:
            while data := self.mic.stdout.read(1280):
                data = carry + data
                aligned = len(data) & ~1
                self.audio.put_nowait(data[:aligned])
                if aligned:
                    self.post(self.app.overlay.level, audioop.rms(data[:aligned], 2))
                carry = data[aligned:]
            if self.released is None:
                self.post(self.app.failure, "Microphone disconnected")
        except queue.Full:
            self.post(self.app.failure, "Recording buffer full")
        finally:
            self.mic.stdout.close()
            self.mic.wait()
            try:
                self.audio.put_nowait(None)
            except queue.Full:
                pass

    def feed(self):
        try:
            pipe = self.worker.stdin
            pipe.write(b":start\n")
            while not self.finished:
                data = self.audio.get()
                if data is None:
                    pipe.write(b":finish\n")
                    pipe.flush()
                    break
                pipe.write(base64.b64encode(data) + b"\n")
                pipe.flush()
        except (BrokenPipeError, OSError):
            pass

    def read_result(self):
        try:
            for line in self.worker.stdout:
                event = json.loads(line)
                if event["type"] == "partial":
                    self.post(self.app.partial, event["text"])
                elif event["type"] == "final":
                    self.got_final = True
                    self.post(self.app.commit, event["text"])
                    return
        except (ValueError, KeyError, OSError):
            pass
        self.post(self.app.failure, "Speech engine unavailable · check service log")

    def release(self):
        self.released = time.monotonic()
        self.mic.terminate()

    def close(self):
        self.finished = True
        if self.mic and self.mic.poll() is None:
            self.mic.terminate()
            self.mic.wait()
        if self.worker and not self.got_final:
            self.app.stop_worker()


class Dictation:
    def __init__(self):
        self.x = display.Display()
        self.root = self.x.screen().root
        self.active_atom = self.x.intern_atom("_NET_ACTIVE_WINDOW")
        def keycode(name):
            return self.x.keysym_to_keycode(XK.string_to_keysym(name))
        self.alt = keycode("Alt_L")
        self.supers = {keycode("Super_L"), keycode("Super_R")} - {0}
        self.chord = self.supers | {self.alt}
        self.other_modifiers = {keycode(name) for name in
                                ("Alt_R", "Shift_L", "Shift_R", "Control_L", "Control_R",
                                 "ISO_Level3_Shift", "Meta_L", "Meta_R")} - self.chord - {0}
        self.image = os.path.expanduser(os.environ.get(
            "T3_DICTATION_APPIMAGE", "~/Applications/T3-Code-Nightly-x86_64.AppImage"))
        self.overlay = Overlay()
        self.recording = None
        self.worker = None
        self.idle_since = time.monotonic()
        self.pending_restore = None
        self.paste_serial = 0
        self.selection = TextSelection(self.x)
        self.clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        self.clipboard_generation = 0
        self.clipboard.connect("owner-change", self.clipboard_changed)
        self.locked = False
        saver = Gio.DBusProxy.new_for_bus_sync(
            Gio.BusType.SESSION, Gio.DBusProxyFlags.DO_NOT_AUTO_START, None,
            "org.gnome.ScreenSaver", "/org/gnome/ScreenSaver", "org.gnome.ScreenSaver", None)
        self.saver = saver
        saver.connect("g-signal", self.lock_changed)
        if saver.get_name_owner():
            self.locked, = saver.call_sync("GetActive", None, Gio.DBusCallFlags.NONE, 1000, None).unpack()
        self.held = False
        self.escape = self.x.keysym_to_keycode(XK.XK_Escape)
        # Accept either press order and lock-key variants.
        lock_masks = {0, X.LockMask}
        num = self.x.keysym_to_keycode(XK.XK_Num_Lock)
        for index, codes in enumerate(self.x.get_modifier_mapping()):
            if num in codes:
                lock_masks |= {mask | (1 << index) for mask in lock_masks}
        errors = []
        grabs = [(self.alt, X.Mod4Mask), *((code, X.Mod1Mask) for code in self.supers)]
        for code, modifier in grabs:
            for mask in lock_masks:
                self.root.grab_key(code, modifier | mask, False, X.GrabModeAsync, X.GrabModeAsync,
                                   onerror=lambda exc, _: errors.append(exc) or True)
        self.x.sync()
        if errors:
            raise RuntimeError("Super + Left Alt is already reserved")
        self.xi = self.x.query_extension("XInputExtension").major_opcode
        version = xinput.XIQueryVersion(display=self.x.display, opcode=self.xi, major_version=2, minor_version=1)
        if (version.major_version, version.minor_version) < (2, 1):
            raise RuntimeError("Desktop dictation needs XInput 2.1 for focus protection")
        GLib.io_add_watch(self.x.fileno(), GLib.IO_IN, self.events)
        self.keymap = Gdk.Keymap.get_for_display(Gdk.Display.get_default())
        self.keymap.connect("state-changed", self.modifiers_changed)
        GLib.timeout_add_seconds(5, self.maintenance)

    def get_worker(self):
        if self.worker is None or self.worker.poll() is not None:
            if not os.access(self.image, os.X_OK):
                raise FileNotFoundError(self.image)
            cpu_list = ",".join(map(str, sorted(os.sched_getaffinity(0))[:2]))
            self.worker = subprocess.Popen(
                ["taskset", "--cpu-list", cpu_list, self.image,
                 str(Path(__file__).resolve().with_name("transcribe.cjs"))],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, start_new_session=True,
                env={**os.environ, "ELECTRON_RUN_AS_NODE": "1", "OMP_NUM_THREADS": "2"})
        return self.worker

    def stop_worker(self):
        worker, self.worker = self.worker, None
        if worker and worker.poll() is None:
            try:
                os.killpg(worker.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            worker.wait()

    def lock_changed(self, proxy, sender, name, params):
        if name == "ActiveChanged":
            self.locked, = params.unpack()
            if self.locked:
                if self.recording:
                    self.end("Cancelled")
                self.overlay.dismiss_recovery()
                self.stop_worker()

    def clipboard_changed(self, clipboard, event):
        owner = event.owner
        if owner and owner.get_xid() != self.selection.window.id:
            self.clipboard_generation += 1

    def watch_input(self, mask):
        self.root.xinput_select_events([(xinput.AllMasterDevices, mask)])
        self.x.flush()

    def focus(self):
        active = self.root.get_full_property(self.active_atom, X.AnyPropertyType)
        focused = self.x.get_input_focus().focus
        return (int(active.value[0]) if active and len(active.value) else 0,
                getattr(focused, "id", focused))

    def start(self):
        if self.locked:
            return
        if self.recording:
            self.overlay.label.set_text("Finishing previous recording · hold again when ready")
            return
        if self.pending_restore:
            self.pending_restore()
        active, _ = self.focus()
        window = GdkX11.X11Window.foreign_new_for_display(Gdk.Display.get_default(), active) if active else None
        self.overlay.present_at(window)
        try:
            self.watch_input(xinput.RawButtonPressMask | xinput.RawKeyPressMask)
            self.recording = Recording(self)
            recording = self.recording
            GLib.timeout_add(90, lambda: self.recording is recording and self.tick())
        except OSError as exc:
            print(exc, file=sys.stderr)
            self.end("Could not start microphone or T3 speech engine")

    def events(self, *_):
        while self.x.pending_events():
            event = self.x.next_event()
            if event.type == X.SelectionRequest:
                self.selection.serve(event)
            elif event.type == X.SelectionClear:
                if self.x.get_selection_owner(self.selection.atom) != self.selection.window:
                    self.selection.text = ""
                    self.selection.saved = None
            elif event.type == X.KeyPress and event.detail in self.chord:
                self.modifiers_changed()
            elif event.type == X.KeyRelease and event.detail in self.chord:
                self.check_release()
            elif self.recording:
                if event.type == X.KeyPress and event.detail == self.escape:
                    self.cancel()
                elif event.type == X.KeyPress:
                    self.recording.unsafe = True
                elif getattr(event, "extension", None) == self.xi:
                    if event.evtype == xinput.RawButtonPress:
                        if struct.unpack_from("=I", event.data, 6)[0] not in (4, 5, 6, 7):
                            self.recording.unsafe = True
                    elif event.evtype == xinput.RawKeyPress:
                        # XI2 raw detail is a CARD32 at byte 16 of the wire event.
                        code = struct.unpack_from("=I", event.data, 6)[0]
                        if code == self.escape and self.held:
                            self.cancel()
                        elif code not in self.chord:
                            self.recording.unsafe = True
        return True

    def chord_down(self, keys=None):
        if keys is None:
            keys = self.x.query_keymap()
        def down(code):
            return keys[code // 8] & (1 << (code % 8))
        return down(self.alt) and any(down(code) for code in self.supers)

    def check_release(self, keys=None):
        if self.held and not self.chord_down(keys):
            self.held = False
            if self.recording and self.recording.released is None:
                self.recording.release()
                self.overlay.finish()

    def maintenance(self):
        self.events()
        if not self.recording and self.worker and time.monotonic() - self.idle_since >= 900:
            self.stop_worker()
        return True

    def modifiers_changed(self, *_):
        # GDK receives XKB modifier changes even during Mutter's Super grab.
        # Idle dictation therefore needs neither keystroke monitoring nor polling.
        keys = self.x.query_keymap()
        if (not self.held and self.chord_down(keys) and
                not any(keys[c // 8] & (1 << (c % 8)) for c in self.other_modifiers)):
            self.held = True
            self.start()
        self.check_release(keys)

    def tick(self):
        self.events()
        rec = self.recording
        if rec:
            if self.focus() != rec.target:
                rec.unsafe = True
            now = time.monotonic()
            if rec.released and now - rec.released > 30 + (rec.released - rec.started) / 2:
                self.failure("Speech engine timed out")
            elif not rec.released and now - rec.started > 300:
                rec.release()
                rec.unsafe = True
                self.overlay.label.set_text("Five-minute limit · finishing…")
        return True

    def cancel(self):
        rec = self.recording
        rec.cancelled = True
        if not rec.released:
            rec.release()
        self.overlay.message("Cancelled", 550)

    def failure(self, message):
        if self.recording.cancelled:
            self.end("Cancelled")
        elif self.recording.last_partial:
            self.recover(self.recording.last_partial, incomplete=True)
        else:
            self.end(message)

    def partial(self, text):
        if not self.recording.cancelled and text.strip():
            self.recording.last_partial = text.strip()
            self.overlay.label.set_text(text.strip())

    def end(self, message):
        self.idle_since = time.monotonic()
        rec, self.recording = self.recording, None
        if rec:
            rec.close()
        self.watch_input(0)
        self.overlay.message(message, 2200)

    def keyboard_available(self):
        # Called under our server grab. No client can acquire a new keyboard
        # grab between this probe and the queued paste events.
        status = self.root.grab_keyboard(False, X.GrabModeAsync, X.GrabModeAsync, X.CurrentTime)
        if status != X.GrabSuccess:
            return False
        self.x.ungrab_keyboard(X.CurrentTime)
        return True

    def modifiers_down(self):
        return self.root.query_pointer().mask & (X.ShiftMask | X.ControlMask | X.Mod1Mask | X.Mod4Mask | X.Mod5Mask)

    def recover(self, text, incomplete=False):
        self.end("")
        self.overlay.recover(text, incomplete)

    def commit(self, text):
        if self.recording.cancelled:
            self.end("Cancelled")
            return
        if not text:
            self.end("No speech heard")
            return
        rec = self.recording
        if not rec.released:
            self.end("Speech engine stopped before release")
            return
        if (not rec.unsafe and rec.released and time.monotonic() - rec.released < 2
                and self.root.query_pointer().mask & (X.Mod1Mask | X.Mod4Mask)):
            def after_release():
                if self.recording is rec:
                    self.commit(text)
                return False
            GLib.timeout_add(35, after_release)
            return
        self.events()
        if self.recording is not rec:
            return
        timestamp = GdkX11.x11_get_server_time(self.overlay.get_window())
        pasted = False
        serial = self.paste_serial + 1
        restored = False
        def restore():
            nonlocal restored
            if serial == self.paste_serial and not restored:
                restored = True
                self.pending_restore = None
                self.selection.put_back(rec.backup)
            return False
        def expire():
            if serial == self.paste_serial and not restored:
                restore()
                if self.recording is None and self.overlay.serial == completion_serial:
                    self.overlay.recover(text)
            return False

        def on_read(requestor):
            mask = self.x.display.info.resource_id_mask
            if requestor & ~mask == rec.target[0] & ~mask:
                GLib.idle_add(restore)
        self.x.grab_server()
        try:
            self.x.sync()
            safe = (rec.backup.ready and not self.x.pending_events() and not rec.unsafe and rec.target == self.focus()
                    and rec.target[0] and rec.target[1] not in (X.NONE, X.PointerRoot)
                    and rec.clipboard_generation == self.clipboard_generation
                    and rec.clipboard_owner == self.x.get_selection_owner(self.selection.atom)
                    and not self.modifiers_down())
            if safe and self.keyboard_available():
                window = self.x.create_resource_object("window", rec.target[0])
                classes = " ".join(window.get_wm_class() or ()).lower()
                mods = [XK.XK_Control_L]
                if any(name in classes for name in ("terminal", "kitty", "alacritty", "ghostty", "wezterm", "tilix", "konsole", "terminator", "foot")):
                    mods.append(XK.XK_Shift_L)
                keys = [self.x.keysym_to_keycode(sym) for sym in [*mods, XK.XK_v]]
                if self.selection.claim(text, timestamp, on_read):
                    self.pending_restore = restore
                    self.paste_serial = serial
                    for key in keys:
                        xtest.fake_input(self.x, X.KeyPress, key)
                    for key in reversed(keys):
                        xtest.fake_input(self.x, X.KeyRelease, key)
                    pasted = True
        except error.XError:
            pass
        finally:
            self.x.ungrab_server()
            self.x.flush()
        if pasted:
            self.end("Transcript ready")
            self.overlay.sent(text)
            completion_serial = self.overlay.serial
            GLib.timeout_add(1800, expire)
        else:
            self.recover(text)


if __name__ == "__main__":
    if os.environ.get("XDG_SESSION_TYPE", "x11") != "x11":
        sys.exit("Desktop dictation requires an X11 session")
    app = Dictation()
    try:
        Gtk.main()
    finally:
        if app.recording:
            app.recording.close()
        app.stop_worker()
        app.x.close()
