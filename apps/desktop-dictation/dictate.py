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


PASTE_TIMEOUT_MS = 1800


def paste_shortcut(wm_class):
    names = tuple(name.lower() for name in (wm_class or ()))
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
        if not self.paste_keys or app.hold_blocked(self.client):
            self.backup = None
        elif app.pending_backup is not None and self.clipboard_owner == app.selection.window:
            # Keep serving the first paste until its client reads it or it expires.
            self.backup = app.pending_backup
            self.clipboard_owner = app.selection.window if self.backup.values else X.NONE
        else:
            # A restored selection already has a complete byte-for-byte
            # snapshot. Avoid converting it again through our own reader.
            saved = app.selection.saved if self.clipboard_owner == app.selection.window else None
            self.backup = ClipboardBackup(app.clipboard, app.x, self.clipboard_owner, saved)
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
        self.controls = {keycode("Control_L"), keycode("Control_R")}
        self.shifts = {keycode("Shift_L"), keycode("Shift_R")}
        self.paste_modifiers = set()
        self.paste_shift_states = set()
        self.finish_manual_paste = None
        self.chord = self.supers | {self.alt}
        self.other_modifiers = {keycode(name) for name in
                                ("Alt_R", "Shift_L", "Shift_R", "Control_L", "Control_R",
                                 "ISO_Level3_Shift", "Meta_L", "Meta_R")} - self.chord - {0}
        self.worker_path = Path(os.environ.get("DESKTOP_DICTATION_WORKER",
                                               Path(__file__).with_name("transcribe.py")))
        self.paused_clients = {}
        self.navigation_guards = {}  # client -> last hold when navigation was observed
        self.overlay = Overlay(self.copy_recovery, self.paused_clients, self.resume_client)
        self.glow = RecordingGlow(self.x)
        self.recording = None
        self.worker = None
        self.idle_since = time.monotonic()
        self.pending_backup = None
        self.paste_target = None
        self.expire_pending = None
        self.lock_generation = 0
        self.paste_press = None
        self.hold_serial = 0
        self.pending_read = None
        self.paste_serial = 0
        self.event_idle = None
        self.replay_deadline = 0
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
        self.lock_masks = lock_masks
        self.resume_grabs = {}
        self.v_key = keycode("v")
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
            self.worker = subprocess.Popen(
                ["/usr/bin/python3", "-I", str(self.worker_path)],
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
                self.interrupt_paste()
                self.release_resume_shortcuts()
                self.overlay.clear_recoveries()
                self.stop_worker()

    def watch_input(self, mask):
        self.root.xinput_select_events([(xinput.AllMasterDevices, mask)])
        self.x.flush()

    def interrupt_paste(self):
        if self.expire_pending:
            self.expire_pending()
        else:
            self.retire_replay()

    def expire_overdue_paste(self):
        if self.paste_target is None or time.monotonic() < self.replay_deadline:
            return False
        self.interrupt_paste()
        return True

    def retire_replay(self):
        self.selection.replay = None
        if self.paste_target is not None:
            _, focus_id = self.paste_target
            self.paste_target = None
            self.root.change_attributes(event_mask=0)
            self.x.create_resource_object("window", focus_id).change_attributes(
                event_mask=0, onerror=lambda exc, _: isinstance(exc, error.BadWindow))
            if self.recording is None:
                self.watch_input(0)
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
        self.hold_serial += 1
        if not self.expire_pending or self.pending_read == "tagged":
            self.interrupt_paste()
        target = self.focus()
        active, _ = target
        window = GdkX11.X11Window.foreign_new_for_display(Gdk.Display.get_default(), active) if active else None
        self.overlay.present_at(window)
        try:
            self.watch_input(xinput.RawButtonPressMask | xinput.RawKeyPressMask | xinput.RawKeyReleaseMask)
            self.recording = Recording(self, target)
            recording = self.recording
            self.glow.track(window)
            GLib.timeout_add(90, lambda: self.recording is recording and self.tick())
        except OSError as exc:
            print(exc, file=sys.stderr)
            self.end("Could not start microphone or speech engine")

    def paste_key(self, event, code):
        # Only observed during the outstanding offer. Keep modifier state,
        # never the typed characters. The synthetic shortcut precedes dispatch.
        if event.evtype == xinput.RawKeyRelease:
            self.paste_modifiers.discard(code)
            return False
        if code in self.chord:
            self.paste_modifiers.add(code)
            return False
        if self.pending_read not in ("untagged", "typing", "navigation") or self.paste_modifiers & self.chord:
            self.interrupt_paste()
        elif code in self.controls | self.shifts:
            self.paste_modifiers.add(code)
            if self.pending_read != "navigation":
                self.pending_read = "typing"
        else:
            symbol = self.x.keycode_to_keysym(code, 0)
            control = bool(self.paste_modifiers & self.controls)
            shifted = bool(self.paste_modifiers & self.shifts)
            if symbol == XK.XK_v and control and shifted in self.paste_shift_states:
                return True
            printable = (0x20 <= symbol <= 0x7e or 0xa0 <= symbol <= 0xff
                         or 0x01000100 <= symbol <= 0x0110ffff)
            deletion = symbol in (XK.XK_BackSpace, XK.XK_Delete, XK.XK_KP_Delete) and not shifted
            if deletion or (printable and (not control or (symbol == XK.XK_a and not shifted))):
                if self.pending_read != "navigation":
                    self.pending_read = "typing"
            elif (XK.XK_Home <= symbol <= XK.XK_End
                  or symbol in (XK.XK_Tab, XK.XK_Return, XK.XK_KP_Enter, XK.XK_Escape)):
                # Navigation may redirect a native paste within the same X window.
                self.pending_read = "navigation"
                self.navigation_hold = self.hold_serial
            else:
                self.interrupt_paste()
        return False

    def events(self, *_):
        deferred_requests = []
        manual_paste = False
        grabbed_v = None
        offer_focus = self.paste_target[1] if self.expire_pending and self.paste_target else None
        batch_recipient = None
        if self.selection.replay:
            batch_recipient = self.selection.gestures[self.selection.replay[0]]
        remaining = self.x.pending_events()
        while remaining:
            remaining -= 1
            event = self.x.next_event()
            if (self.paste_target and self.selection.press_time is not None
                    and getattr(event, "extension", None) == self.xi):
                detail = struct.unpack_from("=I", event.data, 6)[0]
                if event.evtype in (xinput.RawKeyPress, xinput.RawKeyRelease):
                    if self.paste_key(event, detail):
                        # A queued read from this editor could predate the V.
                        # An identified clipboard manager reads independently.
                        if any(self.selection.could_be_recipient(req) for req in deferred_requests):
                            self.interrupt_paste()
                        else:
                            manual_paste = True
                elif event.evtype == xinput.RawButtonPress and detail not in (4, 5, 6, 7):
                    self.interrupt_paste()
            if self.paste_target and (
                    (event.type == X.FocusOut and event.mode == X.NotifyNormal
                     and event.window.id == self.paste_target[1])
                    or (event.type == X.PropertyNotify and event.atom == self.active_atom)):
                self.interrupt_paste()
            # These events and the final grab are ordered on the same connection.
            if isinstance(event, xfixes.SelectionNotify):
                empty_restore = (event.owner.id == X.NONE
                                 and event.sequence_number == self.selection.empty_restore_serial)
                if empty_restore:
                    self.selection.empty_restore_serial = None
                if event.owner.id not in (X.NONE, self.selection.window.id):
                    self.clipboard_generation += 1
                if (event.owner.id != self.selection.window.id and
                        self.x.get_selection_owner(self.selection.atom) != self.selection.window):
                    self.interrupt_paste()
                    self.selection.guarded_reads.clear()
                    # Restoring an originally empty clipboard relinquishes
                    # ownership as part of the same paste. A different owner
                    # taking over ends our reason to intercept manual V.
                    if not empty_restore:
                        self.release_resume_shortcuts()
            elif event.type == X.SelectionRequest:
                if not deferred_requests:
                    # The focus round trip brings preceding input and focus
                    # events into this snapshot. Do it once per batch for
                    # first reads, replay and target negotiation alike.
                    if self.paste_target and self.focus() != self.paste_target:
                        self.interrupt_paste()
                    remaining = self.x.pending_events()
                deferred_requests.append(event)
            elif event.type == X.SelectionClear:
                if self.x.get_selection_owner(self.selection.atom) != self.selection.window:
                    self.selection.text = ""
                    self.selection.saved = None
            elif (event.type == X.KeyPress and event.detail == self.v_key and not event.send_event
                  and event.window != self.root):
                if event.window.id in self.resume_grabs and event.window.id != offer_focus:
                    self.replay_resume_shortcut(event, deferred_requests)
                else:
                    # Chrome must see the ownership change before receiving V.
                    grabbed_v = event
            elif event.type == X.KeyPress and event.detail in self.chord:
                self.modifiers_changed()
            elif event.type == X.KeyRelease and event.detail in self.chord:
                self.check_release()
            elif (self.paste_press is not None and getattr(event, "extension", None) == self.xi
                  and event.evtype == xinput.RawKeyPress
                  and self.paste_press == (event.sequence_number, struct.unpack_from("=I", event.data, 6)[0])):
                # XI2 raw time and detail start at wire bytes 12 and 16.
                self.selection.dispatch(struct.unpack_from("=I", event.data, 2)[0])
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
        if manual_paste and self.finish_manual_paste:
            if self.focus() != self.paste_target:
                self.interrupt_paste()
            elif not self.expire_overdue_paste():
                self.finish_manual_paste()
                batch_recipient = None
        if grabbed_v is not None:
            # Focus can leave the original window while the key is frozen.
            # Discard that press rather than replay it into another client.
            unresolved = self.expire_pending is not None
            if unresolved:
                self.interrupt_paste()
            mode = X.AsyncKeyboard
            self.x.grab_server()
            try:
                if not unresolved and not self.locked and self.x.get_input_focus().focus == grabbed_v.window:
                    mode = X.ReplayKeyboard
            finally:
                self.x.allow_events(mode, grabbed_v.time)
                self.x.ungrab_server()
                self.x.flush()
        if deferred_requests:
            # A cancellation can release an empty clipboard while draining.
            owns_selection = self.x.get_selection_owner(self.selection.atom) == self.selection.window
            if not owns_selection:
                self.interrupt_paste()
            for request in deferred_requests:
                client = self.selection.client_id(request.requestor.id)
                if request.selection == self.selection.atom:
                    # An old conversion arrived before a fresh dispatch. Keep
                    # the ordinary pause until the user explicitly resumes.
                    readers = tuple(self.navigation_guards) if client[0] != "process" else (client,)
                    for reader in readers:
                        if self.navigation_guards.pop(reader, None) is not None:
                            self.overlay.late_read(reader, show=self.recording is None)
                if (request.selection == self.selection.atom and self.pending_read in ("typing", "navigation")
                        and (client == self.selection.recipient or client[0] != "process")):
                    # Typing could have moved the caret before a delayed
                    # conversion. Refuse it and its possible fallback reads.
                    self.interrupt_paste()
                # A busy event loop or an X server round trip can outlast the
                # timer. Check the absolute cutoff before each wire reply.
                if self.expire_overdue_paste():
                    owns_selection = self.x.get_selection_owner(self.selection.atom) == self.selection.window
                if not owns_selection:
                    self.selection.notify(request, X.NONE)
                elif batch_recipient is not None and self.paste_target is None:
                    # Even a previously acknowledged tagged offer may have
                    # ended in this batch. Never substitute its saved clipboard
                    # for a conversion queued against that offer.
                    self.selection.serve(request, client=client, interrupted_client=batch_recipient)
                else:
                    self.selection.serve(request, client=client)
        # Round trips can buffer more events in python-xlib without another
        # fd wakeup. Yield to GLib before taking a fresh finite snapshot.
        if self.x.pending_events() and self.event_idle is None:
            self.event_idle = GLib.idle_add(self.buffered_events)
        return True

    def buffered_events(self):
        self.event_idle = None
        self.events()
        return False

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

    def modifiers_changed(self, keymap=None):
        # GDK receives XKB modifier changes even during Mutter's Super grab.
        # Idle dictation therefore needs neither keystroke monitoring nor polling.
        keys = self.x.query_keymap()
        if keymap is not None and not self.held and self.expire_pending and self.chord_down(keys):
            # GDK can announce the chord before our X connection has processed
            # the Enter that preceded it. The keymap round trip buffered both.
            self.events()
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
        if self.paste_target is None:
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

    def hold_blocked(self, client):
        if client not in self.paused_clients:
            return False
        navigation_hold = self.navigation_guards.get(client)
        return navigation_hold is None or self.hold_serial <= navigation_hold

    def paste_blocked_reason(self, rec):
        # Called after syncing inside the server grab, immediately before dispatch.
        if self.hold_blocked(rec.client):
            # The card shows the live pause state until the user resumes.
            return "Ready to copy"
        if rec.client[0] != "process":
            return "Couldn’t identify the app"
        if not rec.paste_keys:
            return "Use Copy in this app"
        if (rec.unsafe or rec.target != self.focus() or not self.focus_inside(*rec.target)
                or rec.client != self.selection.client_id(rec.target[0])):
            return "Focus or input changed"
        if (rec.clipboard_generation != self.clipboard_generation
                or rec.clipboard_owner != self.x.get_selection_owner(self.selection.atom)):
            return "Clipboard changed"
        if self.x.pending_events():
            return "Desktop changed during dictation"
        if self.modifiers_down():
            return "Modifier key held"
        if not rec.backup or not rec.backup.ready:
            return "Couldn’t back up clipboard"
        if not self.keyboard_available():
            return "Keyboard in use"
        return None

    def recover(self, text, incomplete=False, reason=None):
        client = self.recording.client
        self.end("")
        self.overlay.recover(text, incomplete, client, reason=reason)

    def copy_recovery(self, text):
        self.interrupt_paste()
        if self.paused_clients or self.selection.gestures:
            self.clipboard_generation += 1
            timestamp = GdkX11.x11_get_server_time(self.overlay.get_window())
            self.selection.copy(text, timestamp, self.paused_clients)
        else:
            self.clipboard.set_text(text, -1)

    def probe_chrome_paste_grabs(self, window):
        # Probe every native shortcut before touching CLIPBOARD. XUngrabKey
        # releases only this client's reservations, including partial successes.
        # The surrounding server grab excludes competitors until we reinstall
        # these grabs after dispatching our own XTest V.
        masks = [X.ControlMask | shift | lock for shift in (0, X.ShiftMask)
                 for lock in self.lock_masks]
        caught = error.CatchError()
        for mask in masks:
            window.grab_key(self.v_key, mask, False, X.GrabModeAsync, X.GrabModeSync, onerror=caught)
        for mask in masks:
            window.ungrab_key(self.v_key, mask, onerror=caught)
        self.x.sync()
        return [] if caught.get_error() else masks

    def watch_resume_shortcut(self, rec):
        # After navigation, keep only a passive grab on this app window.
        window = self.x.create_resource_object("window", rec.target[0])
        masks = {X.ControlMask | (X.ShiftMask if shift else 0) | lock
                 for shift in self.paste_shift_states for lock in self.lock_masks}
        for mask in masks:
            window.grab_key(self.v_key, mask, False, X.GrabModeAsync, X.GrabModeSync,
                            onerror=lambda exc, _: isinstance(exc, (error.BadAccess, error.BadWindow)))
        self.resume_grabs[window.id] = rec.client, rec.target, masks

    def replay_resume_shortcut(self, event, queued):
        # Replay the physical V to its native handler even if Resume raced
        # the frozen grab, or an older conversion prevents releasing the guard.
        try:
            grab = self.resume_grabs.get(event.window.id)
            if not grab or self.locked:
                return
            client, target, _ = grab
            if (self.focus() == target and self.selection.client_id(event.window.id) == client
                    and not any(self.selection.could_be_recipient(req, client) for req in queued)):
                self.resume_client(client)
                self.overlay.client_resumed(client)
        finally:
            self.x.allow_events(X.ReplayKeyboard, event.time)
            self.x.flush()

    def release_resume_shortcuts(self, client=None):
        if not self.resume_grabs:
            return
        for xid, (owner, _, masks) in list(self.resume_grabs.items()):
            if client is None or owner == client:
                window = self.x.create_resource_object("window", xid)
                for mask in masks:
                    window.ungrab_key(self.v_key, mask, onerror=lambda exc, _: isinstance(exc, error.BadWindow))
                del self.resume_grabs[xid]
        self.x.flush()

    def resume_client(self, client):
        self.release_resume_shortcuts(client)
        self.navigation_guards.pop(client, None)
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
        lock_generation = self.lock_generation
        hold_serial = self.hold_serial
        paste_grabs = []

        def restore(late_client=None, keep_replay=False):
            nonlocal restored
            restored = True
            self.expire_pending = None
            self.finish_manual_paste = None
            self.paste_modifiers.clear()
            self.paste_press = None
            self.pending_backup = None
            self.pending_read = None
            if not keep_replay:
                self.retire_replay()
            self.selection.put_back(rec.backup, late_client)
            for modifiers in paste_grabs:
                focus_window.ungrab_key(self.v_key, modifiers,
                                       onerror=lambda exc, _: isinstance(exc, error.BadWindow))
            self.x.flush()

        # A new hold permits one bounded offer. Guard the restored clipboard
        # again unless the user deliberately pastes or resumes.
        renewed_hold = hold_serial if client in self.navigation_guards else None

        def confirm(keep_replay=False, guard_hold=renewed_hold):
            late_client = client if guard_hold is not None else None
            restore(late_client=late_client, keep_replay=keep_replay and late_client is None)
            if late_client is not None:
                self.paused_clients[client] = rec.app_name
                self.navigation_guards[client] = guard_hold
                self.watch_resume_shortcut(rec)
            if self.lock_generation == lock_generation:
                self.overlay.recover_confirmed(text, show=self.recording is None, client=late_client)

        def interrupt():
            if self.pending_read == "tagged":
                # Empty backups can keep a delivered GTK offer alive for a
                # second conversion. A redirect ends that gesture successfully.
                confirm()
                return False
            navigated = self.pending_read == "navigation"
            restore(client)
            if navigated:
                self.watch_resume_shortcut(rec)
            # A conversion need not be the paste that changes the field.
            self.paused_clients[client] = rec.app_name
            if self.lock_generation == lock_generation:
                self.overlay.recover(text, client=client, show=self.recording is None)
            return False

        def settle(deadline=False):
            nonlocal settle_timer
            if serial != self.paste_serial:
                return False
            if restored:
                if deadline:
                    self.retire_replay()
                return False
            if not deadline:
                settle_timer = None
            # A timer can run while raw input is buffered on the X connection.
            self.x.sync()
            self.events()
            self.expire_overdue_paste()
            if restored or (not deadline and settle_timer is not None):
                return False
            # An untagged recipient still negotiating at the hard deadline
            # could otherwise paste the restored clipboard on its next read.
            if (self.pending_read is None or self.focus() != rec.target
                    or self.x.get_selection_owner(self.selection.atom) != self.selection.window
                    or (deadline and self.pending_read != "tagged")):
                return interrupt()
            if self.pending_read == "navigation":
                confirm(guard_hold=self.navigation_hold)
                return False
            confirm(keep_replay=(self.pending_read != "typing" and bool(rec.backup.values)
                                 and not deadline and hold_serial == self.hold_serial))
            return False

        settle_timer = None
        def on_read(untagged):
            nonlocal settle_timer
            self.pending_read = "untagged" if untagged else "tagged"
            if untagged:
                # Clients may negotiate several formats in one native paste.
                # Serialize subsequent holds until their reads have settled.
                if settle_timer is not None:
                    GLib.source_remove(settle_timer)
                settle_timer = GLib.timeout_add(350, settle)
                return
            # With an empty backup, dropping ownership now would also drop
            # a second conversion from the same GTK paste handler. Keep the
            # empty selection available until the delivery window closes.
            if rec.backup.values:
                GLib.idle_add(settle)
            else:
                self.selection.saved = {}
        reason = None
        self.x.grab_server()
        try:
            self.x.sync()
            reason = self.paste_blocked_reason(rec)
            if reason is None:
                window = self.x.create_resource_object("window", rec.target[0])
                keys = [self.x.keysym_to_keycode(sym) for sym in rec.paste_keys]
                wm_class = window.get_wm_class() or ()
                chrome = any(name.lower() in ("google-chrome", "google-chrome-beta", "google-chrome-unstable",
                                              "chromium", "chromium-browser") for name in wm_class)
                focus_window = self.x.create_resource_object("window", rec.target[1])
                if chrome:
                    paste_grabs = self.probe_chrome_paste_grabs(focus_window)
                    if not paste_grabs:
                        reason = "Paste shortcut in use"
                if (reason is None and paste_shortcut(wm_class) == rec.paste_keys and all(keys)
                        and self.selection.claim(text, timestamp, client, rec.backup, on_read)):
                    if client in self.navigation_guards:
                        self.resume_client(client)
                    self.pending_read = None
                    self.paste_modifiers.clear()
                    self.paste_shift_states = {XK.XK_Shift_L in rec.paste_keys}
                    # Chrome also accepts Ctrl+Shift+V for plain-text paste.
                    if chrome:
                        self.paste_shift_states.add(True)
                    self.finish_manual_paste = lambda: confirm(guard_hold=None)
                    self.expire_pending = interrupt
                    self.paste_target = rec.target
                    self.root.change_attributes(event_mask=X.PropertyChangeMask)
                    focus_window.change_attributes(event_mask=X.FocusChangeMask)
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
                    self.replay_deadline = time.monotonic() + PASTE_TIMEOUT_MS / 1000
                    xtest.fake_input(self.x, X.KeyPress, keys[-1])
                    self.x.sync()
                    time.sleep(.002)
                    for key in reversed(keys):
                        xtest.fake_input(self.x, X.KeyRelease, key)
                    # Hold the next manual V until Chrome sees the restored clipboard.
                    for mask in paste_grabs:
                        focus_window.grab_key(self.v_key, mask, False, X.GrabModeAsync, X.GrabModeSync)
                    pasted = True
        except error.XError:
            pass
        finally:
            self.x.ungrab_server()
            self.x.flush()
        if pasted:
            self.end("Transcript ready")
            self.overlay.sent(text)
            remaining_ms = int((self.replay_deadline - time.monotonic()) * 1000) + 1
            GLib.timeout_add(max(1, remaining_ms), settle, True)
            self.events()  # XSync may already have buffered the raw shortcut events.
        else:
            self.recover(text, reason=reason)


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
