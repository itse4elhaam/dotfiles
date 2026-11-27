#!/usr/bin/python3
"""Hold a key to dictate into the focused X11 application."""
import audioop
import json
import os
import queue
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

from overlay import Gdk, GLib, Gtk, Overlay
from gi.repository import GdkX11
from Xlib import X, XK, display, error
from Xlib.ext import xinput, xtest


class Recording:
    def __init__(self, app, image):
        self.app = app
        self.started = time.monotonic()
        self.released = None
        self.finished = False
        self.unsafe = False
        self.target = app.focus()
        self.audio = queue.Queue(maxsize=7500)  # Five minutes at 40 ms per block.
        self.worker = self.mic = None
        try:
            self.mic = subprocess.Popen([
                "parec", "--raw", "--format=s16le", "--rate=16000", "--channels=1",
                "--latency-msec=40", "--process-time-msec=20",
            ], stdout=subprocess.PIPE)
            self.worker = subprocess.Popen(
                [image, str(Path(__file__).resolve().with_name("transcribe.cjs"))],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, start_new_session=True,
                env={**os.environ, "ELECTRON_RUN_AS_NODE": "1", "OMP_NUM_THREADS": "2"})
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
                self.post(self.app.end, "Microphone disconnected")
        except queue.Full:
            self.post(self.app.end, "Recording buffer full")
        finally:
            self.mic.stdout.close()
            self.mic.wait()
            try:
                self.audio.put_nowait(None)
            except queue.Full:
                pass

    def feed(self):
        try:
            with self.worker.stdin as pipe:
                while not self.finished:
                    data = self.audio.get()
                    if data is None:
                        break
                    pipe.write(data)
                    pipe.flush()
        except (BrokenPipeError, OSError):
            pass

    def read_result(self):
        final = None
        try:
            with self.worker.stdout as pipe:
                for line in pipe:
                    event = json.loads(line)
                    if event["type"] == "partial":
                        self.post(self.app.partial, event["text"])
                    elif event["type"] == "final":
                        final = event["text"]
        except (ValueError, KeyError):
            self.post(self.app.end, "Speech engine returned an invalid result")
        status = self.worker.wait()
        if status or final is None:
            self.post(self.app.end, "Speech engine unavailable · check service log")
        else:
            self.post(self.app.commit, final)

    def release(self):
        self.released = time.monotonic()
        self.mic.terminate()

    def close(self):
        self.finished = True
        if self.mic and self.mic.poll() is None:
            self.mic.terminate()
        if self.worker and self.worker.poll() is None:
            try:
                os.killpg(self.worker.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


class Dictation:
    def __init__(self):
        self.x = display.Display()
        self.root = self.x.screen().root
        self.active_atom = self.x.intern_atom("_NET_ACTIVE_WINDOW")
        self.key = os.environ.get("DICTATION_KEY", "F9")
        self.code = self.x.keysym_to_keycode(XK.string_to_keysym(self.key))
        if not self.code:
            raise ValueError("Unknown DICTATION_KEY: " + self.key)
        self.image = os.path.expanduser(os.environ.get(
            "T3_DICTATION_APPIMAGE", "~/Applications/T3-Code-Nightly-x86_64.AppImage"))
        self.overlay = Overlay()
        self.recording = None
        self.held = False
        self.escape = self.x.keysym_to_keycode(XK.XK_Escape)
        # Reserve only the chosen unmodified key, including lock-key variants.
        lock_masks = {0, X.LockMask}
        num = self.x.keysym_to_keycode(XK.XK_Num_Lock)
        for index, codes in enumerate(self.x.get_modifier_mapping()):
            if num in codes:
                lock_masks |= {mask | (1 << index) for mask in lock_masks}
        errors = []
        for mask in lock_masks:
            self.root.grab_key(self.code, mask, False, X.GrabModeAsync, X.GrabModeAsync,
                               onerror=lambda exc, _: errors.append(exc) or True)
        self.x.sync()
        if errors:
            raise RuntimeError(f"{self.key} is already reserved")
        self.x.xinput_query_version()
        self.xi = self.x.query_extension("XInputExtension").major_opcode
        self.release_pending = False
        GLib.io_add_watch(self.x.fileno(), GLib.IO_IN, self.events)
        GLib.timeout_add(60, self.tick)

    def watch_input(self, mask):
        self.root.xinput_select_events([(xinput.AllMasterDevices, mask)])
        self.x.flush()

    def focus(self):
        active = self.root.get_full_property(self.active_atom, X.AnyPropertyType)
        focused = self.x.get_input_focus().focus
        return (int(active.value[0]) if active and len(active.value) else 0,
                getattr(focused, "id", focused))

    def start(self):
        if self.recording:
            self.recording.unsafe = True
            return
        active, _ = self.focus()
        window = GdkX11.X11Window.foreign_new_for_display(Gdk.Display.get_default(), active) if active else None
        self.overlay.present_at(window)
        try:
            self.watch_input(xinput.RawButtonPressMask)
            self.recording = Recording(self, self.image)
        except OSError as exc:
            print(exc, file=sys.stderr)
            self.end("Could not start microphone or T3 speech engine")

    def events(self, *_):
        while self.x.pending_events():
            event = self.x.next_event()
            if event.type == X.KeyPress and event.detail == self.code:
                if not self.held:
                    self.held = True
                    self.start()
                self.release_pending = False
            elif event.type == X.KeyRelease and event.detail == self.code:
                self.release_pending = True
            elif self.recording:
                if event.type == X.KeyPress and event.detail == self.escape:
                    self.end("Cancelled")
                elif (event.type == X.KeyPress or
                      (getattr(event, "extension", None) == self.xi and
                       getattr(event, "evtype", None) in (xinput.RawButtonPress, xinput.RawKeyPress))):
                    self.recording.unsafe = True
        if self.release_pending:
            # X autorepeat may send a release/press pair for a key still held.
            self.release_pending = False
            if not self.x.query_keymap()[self.code // 8] & (1 << (self.code % 8)):
                self.held = False
                if self.recording and self.recording.released is None:
                    self.recording.release()
                    self.watch_input(xinput.RawButtonPressMask | xinput.RawKeyPressMask)
                    self.overlay.label.set_text("Finishing…")
        return True

    def tick(self):
        self.events()
        rec = self.recording
        if rec:
            if self.focus() != rec.target:
                rec.unsafe = True
            now = time.monotonic()
            if rec.released and now - rec.released > 30:
                self.end("Speech engine timed out")
            elif not rec.released and now - rec.started > 300:
                rec.release()
                rec.unsafe = True
                self.overlay.label.set_text("Five-minute limit · finishing…")
        return True

    def partial(self, text):
        if not self.recording.released:
            self.overlay.label.set_text(text.strip() or "Listening…")

    def end(self, message):
        rec, self.recording = self.recording, None
        if rec:
            rec.close()
        self.watch_input(0)
        self.overlay.message(message, 2200)

    def commit(self, text):
        if not text:
            self.end("No speech heard")
            return
        # GTK owns the selection. The transcript is also available for manual paste.
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(text, -1)
        Gdk.Display.get_default().sync()
        rec = self.recording
        self.events()
        self.x.grab_server()
        try:
            self.x.sync()
            if (self.x.pending_events() or self.recording is not rec or rec.unsafe or rec.target != self.focus()
                    or not rec.target[0] or rec.target[1] in (X.NONE, X.PointerRoot)
                    or self.root.query_pointer().mask & (X.ShiftMask | X.ControlMask | X.Mod1Mask | X.Mod4Mask)):
                message = "Focus changed · transcript copied"
            else:
                window = self.x.create_resource_object("window", rec.target[0])
                classes = " ".join(window.get_wm_class() or ()).lower()
                mods = [XK.XK_Control_L]
                if any(name in classes for name in ("terminal", "kitty", "alacritty", "ghostty", "wezterm", "tilix")):
                    mods.append(XK.XK_Shift_L)
                keys = [self.x.keysym_to_keycode(sym) for sym in [*mods, XK.XK_v]]
                for key in keys:
                    xtest.fake_input(self.x, X.KeyPress, key)
                for key in reversed(keys):
                    xtest.fake_input(self.x, X.KeyRelease, key)
                message = "Transcript ready"
        except error.XError:
            message = "Field closed · transcript copied"
        finally:
            self.x.ungrab_server()
            self.x.flush()
        self.end(message)


if __name__ == "__main__":
    if os.environ.get("XDG_SESSION_TYPE", "x11") != "x11":
        sys.exit("Desktop dictation requires an X11 session")
    app = Dictation()
    try:
        Gtk.main()
    finally:
        if app.recording:
            app.recording.close()
        app.x.close()
