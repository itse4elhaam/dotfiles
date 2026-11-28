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
from glow import RecordingGlow
from gi.repository import GdkX11, Gio
from Xlib import X, XK, display, error
from Xlib.ext import xfixes, xinput, xtest


def paste_shortcut(wm_class):
    names = tuple(name.lower() for name in (wm_class or ()))
    if names and names[-1] in ("google-chrome", "chromium", "chromium-browser"):
        return ()
    if any(name in ("xterm", "uxterm", "rxvt", "urxvt", "urxvtc", "rxvt-unicode") for name in names):
        return ()
    terminals = ("terminal", "kitty", "alacritty", "ghostty", "wezterm", "tilix", "konsole", "terminator", "foot")
    if any(terminal in name for name in names for terminal in terminals):
        return (XK.XK_Control_L, XK.XK_Shift_L, XK.XK_v)
    return (XK.XK_Control_L, XK.XK_v)


class Recording:
    def __init__(self, app, target):
        self.app = app
        self.started = time.monotonic()
        self.released = None
        self.finished = False
        self.got_final = False
        self.last_partial = ""
        self.unsafe = not app.focus_inside(*target)
        self.target = target
        self.client = app.selection.client_id(self.target[0])
        self.clipboard_generation = app.clipboard_generation
        self.clipboard_owner = app.x.get_selection_owner(app.selection.atom)
        try:
            window = app.x.create_resource_object("window", target[0])
            wm_class = window.get_wm_class() if target[0] else None
            self.app_name = wm_class[-1] if wm_class else f"application {self.client[1]}"
            self.paste_keys = paste_shortcut(wm_class)
        except error.BadWindow:
            self.paste_keys = ()
            self.unsafe = True
        if not self.paste_keys or self.client in app.paused_clients:
            self.backup = None
        elif app.pending_backup is not None and self.clipboard_owner == app.selection.window:
            # Keep serving the first paste until its client reads it or it expires.
            self.backup = app.pending_backup
            self.clipboard_owner = app.selection.window if self.backup.values else X.NONE
        else:
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
                    self.post(self.app.audio_level, audioop.rms(data[:aligned], 2))
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
                if event["type"] == "progress":
                    self.post(self.app.engine_progress, event["text"])
                elif event["type"] == "partial":
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
        self.app.glow.stop()
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
        self.worker_path = Path(os.environ.get("DESKTOP_DICTATION_WORKER",
                                               Path(__file__).with_name("transcribe.py")))
        self.paused_clients = {}
        self.overlay = Overlay(self.copy_recovery, self.paused_clients, self.resume_client)
        self.glow = RecordingGlow()
        self.recording = None
        self.worker = None
        self.idle_since = time.monotonic()
        self.pending_backup = None
        self.expire_pending = None
        self.lock_generation = 0
        self.paste_press = None
        self.paste_serial = 0
        self.selection = TextSelection(self.x)
        self.clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        self.clipboard_generation = 0
        self.x.xfixes_query_version()
        self.x.xfixes_select_selection_input(
            self.selection.window, self.selection.atom,
            xfixes.XFixesSetSelectionOwnerNotifyMask | xfixes.XFixesSelectionWindowDestroyNotifyMask
            | xfixes.XFixesSelectionClientCloseNotifyMask)
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
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGUSR1, self.show_last)

    def show_last(self):
        if not self.locked and self.recording is None:
            active, _ = self.focus()
            window = GdkX11.X11Window.foreign_new_for_display(Gdk.Display.get_default(), active) if active else None
            self.overlay.present_at(window, animate=False)
            self.overlay.recall()
        return True

    def get_worker(self):
        if self.worker is None or self.worker.poll() is not None:
            if not self.worker_path.is_file():
                raise FileNotFoundError(self.worker_path)
            cpu_list = ",".join(map(str, sorted(os.sched_getaffinity(0))[:2]))
            self.worker = subprocess.Popen(
                ["taskset", "--cpu-list", cpu_list, "/usr/bin/python3", "-I", str(self.worker_path)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, start_new_session=True,
                env={**os.environ, "OMP_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "2"})
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
                self.lock_generation += 1
                if self.recording:
                    self.end("Cancelled")
                if self.expire_pending:
                    self.expire_pending()
                self.selection.replay = None
                self.overlay.clear_recoveries()
                self.stop_worker()

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
            self.overlay.reject_hold()
            return
        target = self.focus()
        active, _ = target
        window = GdkX11.X11Window.foreign_new_for_display(Gdk.Display.get_default(), active) if active else None
        self.overlay.present_at(window)
        try:
            self.watch_input(xinput.RawButtonPressMask | xinput.RawKeyPressMask)
            self.recording = Recording(self, target)
            recording = self.recording
            self.glow.track(window)
            GLib.timeout_add(90, lambda: self.recording is recording and self.tick())
        except OSError as exc:
            print(exc, file=sys.stderr)
            self.end("Could not start microphone or speech engine")

    def events(self, *_):
        while self.x.pending_events():
            event = self.x.next_event()
            # These events and the final grab are ordered on the same connection.
            if isinstance(event, xfixes.SelectionNotify):
                if event.owner.id not in (X.NONE, self.selection.window.id):
                    self.clipboard_generation += 1
                if (event.owner.id != self.selection.window.id and
                        self.x.get_selection_owner(self.selection.atom) != self.selection.window):
                    self.selection.guarded_reads.clear()
            elif event.type == X.SelectionRequest:
                self.selection.serve(event)
            elif event.type == X.SelectionClear:
                if self.x.get_selection_owner(self.selection.atom) != self.selection.window:
                    self.selection.text = ""
                    self.selection.saved = None
            elif event.type == X.KeyPress and event.detail in self.chord:
                self.modifiers_changed()
            elif event.type == X.KeyRelease and event.detail in self.chord:
                self.check_release()
            elif (self.paste_press is not None and getattr(event, "extension", None) == self.xi
                  and event.evtype == xinput.RawKeyPress
                  and self.paste_press == (event.sequence_number, struct.unpack_from("=I", event.data, 6)[0])):
                # XI2 raw time and detail start at wire bytes 12 and 16.
                self.selection.press_time = struct.unpack_from("=I", event.data, 2)[0]
                self.paste_press = None
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
            self.overlay.release_hold()
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
            if rec.unsafe and self.glow.target:
                self.glow.stop()
            elif self.glow.get_visible():
                self.glow.place()
            now = time.monotonic()
            if rec.released and now - rec.released > 30 + (rec.released - rec.started) / 2:
                self.failure("Speech engine timed out")
            elif not rec.released and now - rec.started > 300:
                rec.release()
                rec.unsafe = True
                self.overlay.finish()
                self.overlay.label.set_text("Five-minute limit · finishing…")
        return True

    def audio_level(self, rms):
        self.overlay.level(rms)
        rec = self.recording
        if rec.released is None and not rec.unsafe and self.glow.target:
            if not self.glow.get_visible() and self.focus() != rec.target:
                rec.unsafe = True
                self.glow.stop()
                return
            self.glow.level(self.overlay.levels[-1])

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

    def engine_progress(self, text):
        if not self.recording.cancelled and not self.recording.last_partial:
            self.overlay.label.set_text(text)

    def partial(self, text):
        if not self.recording.cancelled and text.strip():
            self.recording.last_partial = text.strip()
            self.overlay.label.set_text(text.strip())

    def end(self, message):
        self.glow.stop()
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

    def focus_inside(self, window_id, focus_id):
        if not window_id or focus_id in (X.NONE, X.PointerRoot):
            return False
        focused = self.x.create_resource_object("window", focus_id)
        try:
            for _ in range(32):
                if focused.id == window_id:
                    return True
                if focused == self.root:
                    break
                focused = focused.query_tree().parent
        except error.BadWindow:
            pass
        return False

    def modifiers_down(self):
        return self.root.query_pointer().mask & (X.ShiftMask | X.ControlMask | X.Mod1Mask | X.Mod4Mask | X.Mod5Mask)

    def recover(self, text, incomplete=False):
        client = self.recording.client
        self.end("")
        self.overlay.recover(text, incomplete, client)

    def copy_recovery(self, text):
        if self.expire_pending:
            self.expire_pending()
        if self.paused_clients or self.selection.confirmed:
            self.clipboard_generation += 1
            timestamp = GdkX11.x11_get_server_time(self.overlay.get_window())
            self.selection.copy(text, timestamp, self.paused_clients)
        else:
            self.clipboard.set_text(text, -1)

    def resume_client(self, client):
        self.paused_clients.pop(client, None)
        self.selection.guarded_reads.discard(client)

    def commit(self, text):
        if self.recording.cancelled:
            self.end("Cancelled")
            return
        if not text:
            self.end("No speech heard")
            return
        rec = self.recording
        client = rec.client
        if not rec.released:
            self.end("Speech engine stopped before release")
            return
        awaiting_modifier = (not rec.unsafe and time.monotonic() - rec.released < 2
                             and self.root.query_pointer().mask & (X.Mod1Mask | X.Mod4Mask))
        if self.pending_backup is not None or awaiting_modifier:
            if self.pending_backup is not None:
                self.overlay.status.set_text("Waiting for previous paste")
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
        read = False
        lock_generation = self.lock_generation
        def restore(late_client=None):
            nonlocal restored
            if serial == self.paste_serial and not restored:
                restored = True
                self.expire_pending = None
                self.paste_press = None
                self.pending_backup = None
                self.selection.put_back(rec.backup, late_client)
            return False
        def expire():
            if serial == self.paste_serial:
                self.selection.replay = None
            if serial == self.paste_serial and not restored:
                restore(client if not read else None)
                if not read:
                    # The original paste can still read. Only an explicit Resume
                    # permits another automatic delivery to this X11 client.
                    self.paused_clients[client] = rec.app_name
                    if self.lock_generation == lock_generation:
                        self.overlay.recover(text, client=client, show=self.recording is None)
            return False

        def on_read():
            nonlocal read
            read = True
            self.overlay.recover_confirmed(text, show=self.recording is None)
            # With an empty backup, dropping ownership now would also drop
            # a second conversion from the same GTK paste handler. Keep the
            # empty selection available until the delivery window closes.
            if rec.backup.values:
                GLib.idle_add(restore)
            else:
                self.selection.saved = {}
        self.x.grab_server()
        try:
            self.x.sync()
            safe = (client[0] == "process" and client not in self.paused_clients
                    and not self.x.pending_events()
                    and not rec.unsafe and rec.target == self.focus()
                    and self.focus_inside(*rec.target)
                    and client == self.selection.client_id(rec.target[0])
                    and rec.clipboard_generation == self.clipboard_generation
                    and rec.clipboard_owner == self.x.get_selection_owner(self.selection.atom)
                    and not self.modifiers_down())
            if safe and rec.paste_keys and rec.backup and rec.backup.ready and self.keyboard_available():
                window = self.x.create_resource_object("window", rec.target[0])
                keys = [self.x.keysym_to_keycode(sym) for sym in rec.paste_keys]
                if (paste_shortcut(window.get_wm_class()) == rec.paste_keys and all(keys)
                        and self.selection.claim(text, timestamp, client, rec.backup, on_read)):
                    self.expire_pending = expire
                    self.pending_backup = rec.backup
                    self.paste_serial = serial
                    for key in keys[:-1]:
                        xtest.fake_input(self.x, X.KeyPress, key)
                    # Isolate V in its own server clock tick. In particular, a
                    # GTK read that asks for fresh server time after dispatch
                    # must not accidentally acquire the V timestamp.
                    self.x.sync()
                    time.sleep(.002)
                    self.paste_press = (self.x.display.request_serial, keys[-1])
                    xtest.fake_input(self.x, X.KeyPress, keys[-1])
                    self.x.sync()
                    time.sleep(.002)
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
