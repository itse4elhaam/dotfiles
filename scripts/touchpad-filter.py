#!/usr/bin/python3
"""Opt-in evdev -> uinput filter for the ELAN07AC:00 04F3:31EC touchpad.

It forwards every event unchanged, with two narrow corrections for faults that
the touchpad firmware itself reports (docs/touchpad-investigation/):

  bridge     A lone contact ends and a new lone contact starts within
             BRIDGE_WINDOW. The new contact continues the old tracking ID with
             BTN_TOUCH held, so libinput sees no lift, no new touch and no tap.
             Its real position is forwarded. To decide, the release of a lone
             contact is held for up to BRIDGE_WINDOW. The release of a contact
             that could still become a tap is never held.
  ghost hold A second contact that starts while the only other contact has been
             down for GHOST_PRIMARY_AGE and is GHOST_MIN_UNITS away is withheld
             for up to GHOST_HOLD. If it ends in that time it is dropped; if it
             persists, or anything suggests a real gesture, it is shown.

Coordinates are never invented or smoothed. Exiting for any reason closes the
grabbed descriptor, and the kernel then returns the touchpad to its normal
consumers. Runs only as touchpad-filter.service, which nothing starts at boot.
"""
import argparse
import errno
import fcntl
import json
import math
import os
from pathlib import Path
import select
import signal
import socket
import struct
import sys
import time
import uuid

# --- Correction thresholds -------------------------------------------------
BRIDGE_WINDOW = 0.060       # s: hold a lone release this long for a restart
BRIDGE_MIN_UNITS = 0        # restart distance needed to bridge (0: any)
TAP_GUARD_S = 0.200         # contacts younger than this (libinput's tap timeout is 180 ms)
TAP_MOVE_UNITS = 48         # ... that moved less than this (libinput: 1.3 mm, ~42 units) may tap
GHOST_PRIMARY_AGE = 0.200   # s the only other contact must have been down
GHOST_MIN_UNITS = 500       # distance of a held second contact from the first
GHOST_HOLD = 0.120          # s a second contact is withheld at most
REVEAL_SHORT = 0.020        # diagnostic: a shown ghost that ends this soon was probably a ghost
# Other diagnostic counts (never acted on): overlap_restarts is a shown contact ending while the
# only other contact started under BRIDGE_WINDOW earlier, whatever the first finger's age;
# late_second_starts is a second contact after GHOST_PRIMARY_AGE; bridge_skipped_tap_candidate is
# a restart that followed a possible tap, whose release is never held.

# --- Daemon timing ---------------------------------------------------------
WATCHDOG_S = 1.0            # the kernel kills the process if the loop stalls this long
POLL_S = 0.25
START_TIMEOUT = 10.0        # wait this long for an untouched pad before grabbing
STOP_WAIT = 2.0             # on stop, wait this long for an untouched pad before ungrabbing
REATTACH_TIMEOUT = 15.0     # follow a driver rebind for this long, else exit unfiltered
STATUS_HEARTBEAT = 5.0

EXPECTED_NAME = "ELAN07AC:00 04F3:31EC Touchpad"
EXPECTED_ID = (0x18, 0x04F3, 0x31EC)
FILTER_NAME = "ELAN07AC:00 04F3:31EC Touchpad (filtered)"
DEVICE = Path("/sys/bus/i2c/devices/i2c-ELAN07AC:00")
RUNTIME = Path("/run/touchpad-filter")
UINPUT = Path("/dev/uinput")
EXIT_REFUSED = 3

EV_SYN, EV_KEY, EV_ABS, EV_MSC = 0, 1, 3, 4
SYN_REPORT, SYN_DROPPED = 0, 3
ABS_X, ABS_Y = 0, 1
ABS_MT_SLOT, ABS_MT_POSITION_X, ABS_MT_POSITION_Y = 47, 53, 54
ABS_MT_TOOL_TYPE, ABS_MT_TRACKING_ID = 55, 57
MT_TOOL_FINGER = 0
BTN_LEFT, BTN_TOUCH = 272, 330
TOOL_KEYS = (325, 333, 334, 335, 328)     # FINGER, DOUBLETAP, TRIPLETAP, QUADTAP, QUINTTAP
TOUCH_KEYS = frozenset((BTN_TOUCH,) + TOOL_KEYS)
INPUT_EVENT = struct.Struct("@llHHi")
STAT_KEYS = ("frames", "held_releases", "bridged_drops", "suppressed_ghosts", "held_ghosts",
             "revealed_ghosts", "revealed_then_ended", "bridge_skipped_tap_candidate",
             "overlap_restarts", "second_starts", "late_second_starts", "unplaced_contacts", "resyncs")


class Model:
    """The input state the kernel stores for one device, with its duplicate filtering.

    `raw` mirrors the real touchpad (events already filtered by its kernel);
    `out` mirrors the uinput device, so each write can be checked against what
    libinput will actually receive.
    """

    def __init__(self, slots, mt_codes, keys=(), axes=()):
        self.mt_codes = tuple(sorted(code for code in mt_codes if code != ABS_MT_SLOT))
        self.slots = [{code: -1 if code == ABS_MT_TRACKING_ID else 0 for code in self.mt_codes}
                      for _ in range(slots)]
        self.slot = 0
        self.keys = {code: 0 for code in keys}
        self.axes = {code: 0 for code in axes}

    def copy(self):
        other = Model.__new__(Model)
        other.mt_codes = self.mt_codes
        other.slots = [dict(values) for values in self.slots]
        other.slot = self.slot
        other.keys = dict(self.keys)
        other.axes = dict(self.axes)
        return other

    def state(self):
        return ([sorted(values.items()) for values in self.slots], self.slot,
                sorted(self.keys.items()), sorted(self.axes.items()))

    def active(self):
        return {index for index, values in enumerate(self.slots) if values[ABS_MT_TRACKING_ID] >= 0}

    def position(self, slot):
        values = self.slots[slot]
        return values.get(ABS_MT_POSITION_X, 0), values.get(ABS_MT_POSITION_Y, 0)

    def apply(self, kind, code, value):
        """Store one event; True if the kernel would pass it on (it drops repeats)."""
        if kind == EV_ABS:
            if code == ABS_MT_SLOT:
                if 0 <= value < len(self.slots):
                    self.slot = value
                return False
            store = self.slots[self.slot] if code in self.mt_codes else self.axes
            if code not in store or store[code] == value:
                return False
            store[code] = value
            return True
        if kind == EV_KEY:
            if code not in self.keys or self.keys[code] == bool(value):
                return False
            self.keys[code] = int(bool(value))
            return True
        return True


class Contact:
    """A contact as the uinput device shows it; `source` is the raw slot feeding it."""

    def __init__(self, tracking_id, start, point, source):
        self.tracking_id = tracking_id
        self.start = start
        self.origin = point
        self.last = point
        self.reach = 0.0
        self.source = source

    def moved(self, point):
        self.last = point
        self.reach = max(self.reach, math.dist(point, self.origin))


def distance(first, second):
    return math.dist(first, second)


class FilterCore:
    """Pure correction logic: raw frames in, uinput frames out, each with its write time.

    feed() takes one raw frame (without its SYN_REPORT) and the kernel time it
    was stamped with. tick() handles deadlines when no frame arrives. Both
    return [(write_time, events)]; every returned frame ends with SYN_REPORT
    when written. Frames are forwarded verbatim whenever no correction is
    active, so healthy input passes through unchanged.
    """

    def __init__(self, slots=5, mt_codes=(53, 54, 55, 57), keys=(BTN_LEFT,) + tuple(sorted(TOUCH_KEYS)),
                 axes=(ABS_X, ABS_Y), ghost_min_units=GHOST_MIN_UNITS):
        self.raw = Model(slots, mt_codes, keys, axes)
        self.out = Model(slots, mt_codes, keys, axes)
        self.ghost_min_units = ghost_min_units
        self.visible = {}      # out slot -> Contact
        self.feeds = {}        # raw slot -> out slot
        self.hidden = {}       # raw slot -> (start, deadline)
        self.ignored = set()   # raw slots whose contact predates a resync; never shown
        self.pending = None    # (out slot, held raw events, deadline)
        self.raw_start = {}    # raw slot -> start time (diagnostics)
        self.revealed_at = {}
        self.tap_end = None
        self.stats = dict.fromkeys(STAT_KEYS, 0)

    @classmethod
    def for_device(cls, caps, **options):
        mt_codes = [code for code in caps["abs"] if 47 <= code <= 0x3D]
        slots = caps["abs"][ABS_MT_SLOT][2] + 1
        axes = [code for code in caps["abs"] if code < 47]
        return cls(slots=slots, mt_codes=mt_codes, keys=sorted(caps["keys"]), axes=axes, **options)

    # --- public interface ---------------------------------------------------
    def deadline(self):
        times = [deadline for _, deadline in self.hidden.values()]
        if self.pending is not None:
            times.append(self.pending[2])
        return min(times) if times else None

    def seed(self, now, model):
        """Adopt the real pad's state (taken untouched) and copy its stored values to uinput."""
        self.raw = model.copy()
        self.ignored = set(self.raw.active())
        frame = self.emit(now, [], self.raw)
        return [frame] if frame[1] else []

    def resync(self, now, model):
        """After SYN_DROPPED: lift everything, then ignore contacts already down."""
        self.stats["resyncs"] += 1
        frames = self.release_all(now)
        self.raw = model.copy()
        self.ignored = set(self.raw.active())
        return frames

    def release_all(self, now):
        """Lift every contact the uinput device shows, e.g. before detaching or exiting."""
        self.pending = None
        self.hidden.clear()
        self.feeds.clear()
        self.visible.clear()
        self.ignored = set(self.raw.active())
        frame = self.emit(now, [], self.raw, sync=False)
        return [frame] if frame[1] else []

    def tick(self, now):
        frames = []
        if self.pending is not None and now >= self.pending[2]:
            frames += self.flush_pending(self.pending[2])
        due = [slot for slot, (_, deadline) in self.hidden.items() if now >= deadline]
        if due:
            when = max(self.hidden[slot][1] for slot in due)
            frames.append(self.reveal(when, self.raw, due))
        return frames

    def feed(self, now, events):
        frames = self.tick(now)
        self.stats["frames"] += 1
        nxt = self.raw.copy()
        started, ended, button = [], [], False
        for kind, code, value in events:
            if kind == EV_ABS and code == ABS_MT_TRACKING_ID:
                old = nxt.slots[nxt.slot][ABS_MT_TRACKING_ID]
                if old >= 0 and value != old:
                    ended.append(nxt.slot)
                if value >= 0 and value != old:
                    started.append(nxt.slot)
            elif kind == EV_KEY and code not in TOUCH_KEYS:
                button = True
            nxt.apply(kind, code, value)

        if self.pending is not None:
            bridged = self.try_bridge(now, events, nxt, started, ended, button)
            if bridged is not None:
                return frames + [bridged]
            frames += self.flush_pending(now)

        clean_before = self.clean() and self.out.state() == self.raw.state()
        prev, self.raw = self.raw, nxt
        decided = False
        pre = []

        for slot in ended:
            self.ignored.discard(slot)
            if slot in self.hidden:
                del self.hidden[slot]
                self.stats["suppressed_ghosts"] += 1
                decided = True
            revealed = self.revealed_at.pop(slot, None)
            if revealed is not None and now - revealed <= REVEAL_SHORT:
                self.stats["revealed_then_ended"] += 1

        if self.hidden and (button or any(slot in self.feeds for slot in ended)
                            or any(slot not in self.hidden for slot in started)):
            # A real gesture after all: show the held contact first, as it was
            # before this frame, then apply this frame on top.
            pre.append(self.reveal(now, prev, list(self.hidden)))
            decided = True

        lone_before = len(self.visible) == 1
        for slot in ended:
            out_slot = self.feeds.pop(slot, None)
            if out_slot is None:
                continue
            contact = self.visible[out_slot]
            survivors = nxt.active()
            if len(survivors) == 1 and not started:
                other = next(iter(survivors))
                if now - self.raw_start.get(other, now) <= BRIDGE_WINDOW:
                    self.stats["overlap_restarts"] += 1
            if lone_before and not survivors and not started and not button and not pre:
                if self.tap_candidate(contact, now):
                    self.tap_end = now
                else:
                    contact.source = None
                    self.pending = (out_slot, list(events), now + BRIDGE_WINDOW)
                    self.stats["held_releases"] += 1
                    return frames + pre
            del self.visible[out_slot]

        for slot in started:
            self.raw_start[slot] = now
            if len(started) == 1 and nxt.active() == {slot} and self.tap_end is not None:
                if now - self.tap_end <= BRIDGE_WINDOW:
                    self.stats["bridge_skipped_tap_candidate"] += 1
            self.tap_end = None
            if self.is_ghost(now, slot, nxt, started, button, pre):
                self.hidden[slot] = (now, now + GHOST_HOLD)
                self.stats["held_ghosts"] += 1
                decided = True
                continue
            if not self.place(now, slot, nxt):
                decided = True

        for contact in self.visible.values():
            if contact.source is not None:
                contact.moved(nxt.position(contact.source))

        if clean_before and not decided and self.clean():
            for event in events:
                self.out.apply(*event)
            return frames + pre + [(now, list(events))]
        return frames + pre + [self.emit(now, events, nxt)]

    # --- decisions ----------------------------------------------------------
    def clean(self):
        """No correction in force: every raw contact is shown as itself, in its own slot."""
        if self.pending is not None or self.hidden or self.ignored:
            return False
        return all(self.visible[out].tracking_id == self.raw.slots[raw][ABS_MT_TRACKING_ID] and raw == out
                   for raw, out in self.feeds.items())

    def tap_candidate(self, contact, now):
        return now - contact.start < TAP_GUARD_S and contact.reach < TAP_MOVE_UNITS

    def is_finger(self, model, slot):
        return model.slots[slot].get(ABS_MT_TOOL_TYPE, MT_TOOL_FINGER) == MT_TOOL_FINGER

    def is_ghost(self, now, slot, nxt, started, button, pre):
        if len(started) != 1 or self.hidden or pre or button or len(self.visible) != 1:
            return False
        primary = next(iter(self.visible.values()))
        if primary.source is None or nxt.active() != {primary.source, slot}:
            return False
        self.stats["second_starts"] += 1
        if now - primary.start < GHOST_PRIMARY_AGE:
            return False
        self.stats["late_second_starts"] += 1
        return (self.is_finger(nxt, slot)
                and distance(nxt.position(slot), nxt.position(primary.source)) >= self.ghost_min_units)

    def try_bridge(self, now, events, nxt, started, ended, button):
        out_slot, _, _ = self.pending
        if (len(started) != 1 or ended or button or nxt.active() != set(started)
                or not self.is_finger(nxt, started[0])):
            return None
        slot = started[0]
        contact = self.visible[out_slot]
        if distance(nxt.position(slot), contact.last) < BRIDGE_MIN_UNITS:
            return None
        self.pending = None
        self.raw = nxt
        self.raw_start[slot] = now
        self.feeds[slot] = out_slot
        contact.source = slot
        contact.moved(nxt.position(slot))
        self.stats["bridged_drops"] += 1
        return self.emit(now, events, nxt)

    def flush_pending(self, now):
        out_slot, held, _ = self.pending
        self.pending = None
        trial = self.out.copy()
        for event in held:
            trial.apply(*event)
        del self.visible[out_slot]
        if trial.state() == self.raw.state() and self.clean():
            self.out = trial
            return [(now, held)]
        return [self.emit(now, held, self.raw)]

    def place(self, now, slot, model):
        """Show a raw contact, in its own slot when that is free."""
        taken = set(self.visible)
        free = [index for index in range(len(self.out.slots))
                if index not in taken and self.out.slots[index][ABS_MT_TRACKING_ID] < 0]
        if not free:
            self.ignored.add(slot)
            self.stats["unplaced_contacts"] += 1
            return False
        out_slot = slot if slot in free else free[0]
        self.feeds[slot] = out_slot
        self.visible[out_slot] = Contact(model.slots[slot][ABS_MT_TRACKING_ID], now,
                                         model.position(slot), slot)
        return True

    def reveal(self, now, model, slots):
        """Show held second contacts with their positions in `model`."""
        for slot in slots:
            start, _ = self.hidden.pop(slot)
            if self.place(start, slot, model):
                self.stats["revealed_ghosts"] += 1
                self.revealed_at[slot] = now
        return self.emit(now, [], model)

    # --- output -------------------------------------------------------------
    def emit(self, now, events, target, sync=True):
        """Write what changes the uinput state into the wanted one, then the frame's other events.

        When no correction remains, idle slots, keys and pointer axes are also
        brought back to the raw values, so the next frames can pass verbatim.
        Stored values of a slot whose contact ends in this frame are synced
        later: libinput would read them as a last motion of the lifting touch.
        """
        final = sync and self.clean()
        out = self.out
        wanted = []
        for index, have in enumerate(out.slots):
            contact = self.visible.get(index)
            if contact is not None and contact.source is not None:
                want = dict(target.slots[contact.source])
                want[ABS_MT_TRACKING_ID] = contact.tracking_id
            elif contact is not None:
                want = dict(have)
            elif final and have[ABS_MT_TRACKING_ID] < 0:
                want = dict(target.slots[index])
            else:
                want = dict(have)
                want[ABS_MT_TRACKING_ID] = -1
            if (have[ABS_MT_TRACKING_ID] >= 0 and want[ABS_MT_TRACKING_ID] >= 0
                    and have[ABS_MT_TRACKING_ID] != want[ABS_MT_TRACKING_ID]):
                raise RuntimeError(f"slot {index} would change tracking ID within one frame")
            wanted.append(want)

        written = []
        slot = out.slot
        order = [ABS_MT_TRACKING_ID, ABS_MT_TOOL_TYPE, ABS_MT_POSITION_X, ABS_MT_POSITION_Y]
        for index, want in enumerate(wanted):
            have = out.slots[index]
            codes = [code for code in order if code in want] + [
                code for code in out.mt_codes if code not in order]
            changes = [(code, want[code]) for code in codes if want[code] != have[code]]
            if not changes:
                continue
            if slot != index:
                written.append((EV_ABS, ABS_MT_SLOT, index))
                slot = index
            written += [(EV_ABS, code, value) for code, value in changes]

        count = sum(want[ABS_MT_TRACKING_ID] >= 0 for want in wanted)
        if final:
            keys = {code: target.keys.get(code, 0) for code in TOUCH_KEYS if code in out.keys}
            axes = dict(target.axes)
        else:
            keys = {BTN_TOUCH: int(count > 0)}
            keys.update({code: int(count == number) for number, code in enumerate(TOOL_KEYS, 1)})
            keys = {code: value for code, value in keys.items() if code in out.keys}
            axes = dict(out.axes)
            shown = [(contact.start, contact.tracking_id, index) for index, contact in self.visible.items()
                     if wanted[index][ABS_MT_TRACKING_ID] >= 0]
            if shown:
                oldest = wanted[min(shown)[2]]
                axes.update({ABS_X: oldest.get(ABS_MT_POSITION_X, 0), ABS_Y: oldest.get(ABS_MT_POSITION_Y, 0)})
        written += [(EV_KEY, code, keys[code]) for code in (BTN_TOUCH,) + TOOL_KEYS
                    if code in keys and keys[code] != out.keys[code]]
        written += [(EV_ABS, code, value) for code, value in sorted(axes.items())
                    if code in out.axes and out.axes[code] != value]
        written += [event for event in events
                    if not (event[0] == EV_ABS and (event[1] == ABS_MT_SLOT or event[1] in out.mt_codes
                                                    or event[1] in out.axes))
                    and not (event[0] == EV_KEY and event[1] in TOUCH_KEYS)
                    and event[0] != EV_SYN]
        if final and slot != target.slot:
            written.append((EV_ABS, ABS_MT_SLOT, target.slot))
        for event in written:
            out.apply(*event)
        return now, written


def frames_of(events):
    """Split [time, type, code, value, ...] events into (time, [(type, code, value)]) frames."""
    frame = []
    for event in events:
        kind, code, value = event[1:4]
        if kind == EV_SYN and code == SYN_REPORT:
            yield event[0], frame
            frame = []
        elif kind == EV_SYN:
            continue
        else:
            frame.append((kind, code, value))


def replay(trace, ghost_min_units=GHOST_MIN_UNITS):
    """Run the core over a touchpad-watch trace; returns (stats, output frames)."""
    core = FilterCore(ghost_min_units=ghost_min_units)
    events = [event for event in trace.get("initial_events", []) + trace["events"]
              if len(event) < 5 or event[4] == "touchpad"]
    output = []
    last = None
    for moment, frame in frames_of(events):
        output += core.feed(moment, frame)
        last = moment
    if last is not None:
        output += core.tick(last + 1.0)
    return core.stats, output


# --- Device access ---------------------------------------------------------
def _ioc(direction, number, size, kind=ord("E")):
    return (direction << 30) | (size << 16) | (kind << 8) | number


EVIOCGID = _ioc(2, 0x02, 8)
EVIOCGRAB = _ioc(1, 0x90, 4)
EVIOCSCLOCKID = _ioc(1, 0xA0, 4)
UI_DEV_CREATE = _ioc(0, 1, 0, ord("U"))
UI_DEV_DESTROY = _ioc(0, 2, 0, ord("U"))
UI_DEV_SETUP = _ioc(1, 3, 92, ord("U"))       # struct uinput_setup
UI_ABS_SETUP = _ioc(1, 4, 28, ord("U"))       # struct uinput_abs_setup
UI_SET_EVBIT = _ioc(1, 100, 4, ord("U"))
UI_SET_KEYBIT = _ioc(1, 101, 4, ord("U"))
UI_SET_ABSBIT = _ioc(1, 103, 4, ord("U"))
UI_SET_MSCBIT = _ioc(1, 104, 4, ord("U"))
UI_SET_PROPBIT = _ioc(1, 110, 4, ord("U"))
KEY_BYTES, ABS_BYTES, MSC_BYTES, PROP_BYTES = 96, 8, 1, 4
INPUT_PROP_POINTER, INPUT_PROP_BUTTONPAD = 0, 2


def EVIOCGNAME(size):
    return _ioc(2, 0x06, size)


def EVIOCGPROP(size):
    return _ioc(2, 0x09, size)


def EVIOCGMTSLOTS(size):
    return _ioc(2, 0x0A, size)


def EVIOCGKEY(size):
    return _ioc(2, 0x18, size)


def EVIOCGBIT(kind, size):
    return _ioc(2, 0x20 + kind, size)


def EVIOCGABS(code):
    return _ioc(2, 0x40 + code, 24)


def UI_GET_SYSNAME(size):
    return _ioc(2, 44, size, ord("U"))


def bits(data):
    return {index * 8 + bit for index, byte in enumerate(data) for bit in range(8) if byte >> bit & 1}


class IdentityError(Exception):
    """The node is not exactly this ELAN touchpad; it must not be grabbed."""


def read_caps(fd, ioctl):
    def query(request, size):
        buffer = bytearray(size)
        ioctl(fd, request, buffer, True)
        return bytes(buffer)
    caps = {"name": query(EVIOCGNAME(256), 256).split(b"\0", 1)[0].decode(errors="replace"),
            "id": struct.unpack("4H", query(EVIOCGID, 8)),
            "types": bits(query(EVIOCGBIT(0, 4), 4)),
            "props": bits(query(EVIOCGPROP(PROP_BYTES), PROP_BYTES))}
    caps["keys"] = bits(query(EVIOCGBIT(EV_KEY, KEY_BYTES), KEY_BYTES)) if EV_KEY in caps["types"] else set()
    caps["msc"] = bits(query(EVIOCGBIT(EV_MSC, MSC_BYTES), MSC_BYTES)) if EV_MSC in caps["types"] else set()
    codes = bits(query(EVIOCGBIT(EV_ABS, ABS_BYTES), ABS_BYTES)) if EV_ABS in caps["types"] else set()
    caps["abs"] = {code: struct.unpack("6i", query(EVIOCGABS(code), 24)) for code in sorted(codes)}
    return caps


def check_identity(caps):
    problems = []
    if caps["name"] != EXPECTED_NAME:
        problems.append(f"name {caps['name']!r}")
    if tuple(caps["id"][:3]) != EXPECTED_ID:
        problems.append("id bus %04x vendor %04x product %04x" % tuple(caps["id"][:3]))
    if caps["types"] - {EV_SYN, EV_KEY, EV_ABS, EV_MSC}:
        problems.append(f"unexpected event types {sorted(caps['types'])}")
    missing = ({ABS_X, ABS_Y, ABS_MT_SLOT, ABS_MT_POSITION_X, ABS_MT_POSITION_Y, ABS_MT_TRACKING_ID}
               - set(caps["abs"]))
    missing |= {BTN_TOUCH, TOOL_KEYS[0]} - caps["keys"]
    if missing:
        problems.append(f"missing codes {sorted(missing)}")
    if INPUT_PROP_BUTTONPAD not in caps["props"]:
        problems.append("not a buttonpad")
    if not problems:
        slots = caps["abs"][ABS_MT_SLOT][2] + 1
        resolutions = (caps["abs"][ABS_MT_POSITION_X][5], caps["abs"][ABS_MT_POSITION_Y][5])
        if not 2 <= slots <= 16 or min(resolutions) <= 0:
            problems.append(f"{slots} slots, resolution {resolutions}")
    if problems:
        raise IdentityError("refusing a device that is not the expected touchpad: " + "; ".join(problems))


def same_layout(first, second):
    """Capabilities and axis ranges equal (current axis values may differ)."""
    def layout(caps):
        return (caps["name"], tuple(caps["id"]), caps["types"], caps["props"], caps["keys"], caps["msc"],
                {code: info[1:] for code, info in caps["abs"].items()})
    return layout(first) == layout(second)


class Touchpad:
    """The real touchpad's evdev node, opened read-only and checked before anything else."""

    def __init__(self, path, ioctl=fcntl.ioctl, opener=os.open):
        self.ioctl = ioctl
        self.path = str(path)
        self.fd = opener(self.path, os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC)
        self.grabbed = False
        try:
            self.caps = read_caps(self.fd, ioctl)
            check_identity(self.caps)
            ioctl(self.fd, EVIOCSCLOCKID, struct.pack("i", time.CLOCK_MONOTONIC))
        except BaseException:
            os.close(self.fd)
            raise

    def fileno(self):
        return self.fd

    def read(self):
        return os.read(self.fd, INPUT_EVENT.size * 256)

    def drain(self):
        try:
            while self.read():
                pass
        except BlockingIOError:
            pass

    def grab(self, on):
        self.ioctl(self.fd, EVIOCGRAB, 1 if on else 0)
        self.grabbed = on

    def state(self):
        """The kernel's current slot values, keys and axes for this device."""
        caps = self.caps
        slots = caps["abs"][ABS_MT_SLOT][2] + 1
        model = Model(slots, [code for code in caps["abs"] if 47 <= code <= 0x3D], sorted(caps["keys"]),
                      [code for code in caps["abs"] if code < 47])
        for code in model.mt_codes:
            buffer = bytearray(struct.pack("I", code) + bytes(4 * slots))
            self.ioctl(self.fd, EVIOCGMTSLOTS(len(buffer)), buffer, True)
            for index, value in enumerate(struct.unpack(f"{slots}i", bytes(buffer[4:]))):
                model.slots[index][code] = value
        info = bytearray(24)
        self.ioctl(self.fd, EVIOCGABS(ABS_MT_SLOT), info, True)
        model.slot = struct.unpack("6i", bytes(info))[0]
        for code in model.axes:
            info = bytearray(24)
            self.ioctl(self.fd, EVIOCGABS(code), info, True)
            model.axes[code] = struct.unpack("6i", bytes(info))[0]
        keys = bytearray(KEY_BYTES)
        self.ioctl(self.fd, EVIOCGKEY(KEY_BYTES), keys, True)
        down = bits(keys)
        for code in model.keys:
            model.keys[code] = int(code in down)
        return model

    def close(self):
        if self.fd is not None:
            os.close(self.fd)    # closing also ends the grab
            self.fd = None


class UInput:
    """The virtual twin: same capabilities, axis ranges and ids, a distinct name, fuzz 0."""

    def __init__(self, caps, name=FILTER_NAME, path=UINPUT, ioctl=fcntl.ioctl, opener=os.open):
        self.ioctl = ioctl
        self.fd = opener(str(path), os.O_WRONLY | os.O_NONBLOCK | os.O_CLOEXEC)
        self.created = False
        try:
            for kind in sorted(caps["types"] - {EV_SYN}):
                ioctl(self.fd, UI_SET_EVBIT, kind)
            for code in sorted(caps["keys"]):
                ioctl(self.fd, UI_SET_KEYBIT, code)
            for code in sorted(caps["msc"]):
                ioctl(self.fd, UI_SET_MSCBIT, code)
            for code in sorted(caps["props"]):
                ioctl(self.fd, UI_SET_PROPBIT, code)
            for code, (_, minimum, maximum, _, flat, resolution) in sorted(caps["abs"].items()):
                ioctl(self.fd, UI_SET_ABSBIT, code)
                ioctl(self.fd, UI_ABS_SETUP, struct.pack("HH6i", code, 0, 0, minimum, maximum, 0, flat, resolution))
            bus, vendor, product, version = caps["id"]
            ioctl(self.fd, UI_DEV_SETUP, struct.pack("4H80sI", bus, vendor, product, version,
                                                     name.encode()[:79], 0))
            ioctl(self.fd, UI_DEV_CREATE)
            self.created = True
            sysname = bytearray(64)
            try:
                ioctl(self.fd, UI_GET_SYSNAME(64), sysname, True)
                self.sysname = bytes(sysname).split(b"\0", 1)[0].decode()
            except OSError:
                self.sysname = None
        except BaseException:
            os.close(self.fd)
            raise

    def write(self, events):
        data = b"".join(INPUT_EVENT.pack(0, 0, kind, code, value) for kind, code, value in events)
        data += INPUT_EVENT.pack(0, 0, EV_SYN, SYN_REPORT, 0)
        view = memoryview(data)
        while view:
            view = view[os.write(self.fd, view):]

    def close(self):
        if self.fd is None:
            return
        try:
            if self.created:
                self.ioctl(self.fd, UI_DEV_DESTROY)
        finally:
            os.close(self.fd)
            self.fd = None


class Backend:
    """Finds and opens the real devices. Tests substitute fakes for the ioctl and open calls."""

    def __init__(self, device=DEVICE, uinput=UINPUT, ioctl=fcntl.ioctl, opener=os.open):
        self.device, self.uinput, self.ioctl, self.opener = device, uinput, ioctl, opener

    def find(self):
        """The touchpad's event node under the ELAN I2C device, never a virtual one."""
        for name_path in sorted(self.device.glob("*/input/input*/name")):
            try:
                if name_path.read_text().strip() != EXPECTED_NAME:
                    continue
                for node in sorted(name_path.parent.glob("event*")):
                    return Path("/dev/input") / node.name, name_path.parent.parent.parent.name
            except OSError:
                continue
        return None

    def open_touchpad(self, path):
        return Touchpad(path, self.ioctl, self.opener)

    def open_uinput(self, caps):
        return UInput(caps, path=self.uinput, ioctl=self.ioctl, opener=self.opener)


# --- Service ---------------------------------------------------------------
class Notifier:
    """sd_notify without libsystemd; silent when not run by systemd."""

    def __init__(self, address=None):
        address = address if address is not None else os.environ.get("NOTIFY_SOCKET")
        self.socket = None
        self.last = float("-inf")
        if address:
            self.address = "\0" + address[1:] if address.startswith("@") else address
            self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM | socket.SOCK_CLOEXEC)

    def send(self, message):
        if self.socket is not None:
            try:
                self.socket.sendto(message.encode(), self.address)
            except OSError:
                pass

    def watchdog(self, now):
        if now - self.last >= 0.25:
            self.last = now
            self.send("WATCHDOG=1")


class Status:
    """/run/touchpad-filter/status.json: state and cumulative counts, world-readable."""

    def __init__(self, directory, instance):
        self.path = directory / "status.json"
        self.instance = instance
        self.record = {}
        self.written = float("-inf")

    def write(self, state, stats=None, force=True, **extra):
        now = time.monotonic()
        record = {"state": state, "pid": os.getpid(), "instance": self.instance, "name": FILTER_NAME,
                  "stats": dict(stats or self.record.get("stats") or {}),
                  "thresholds": {"bridge_window_s": BRIDGE_WINDOW, "bridge_min_units": BRIDGE_MIN_UNITS,
                                 "ghost_primary_age_s": GHOST_PRIMARY_AGE, "ghost_min_units": GHOST_MIN_UNITS,
                                 "ghost_hold_s": GHOST_HOLD, "tap_guard_s": TAP_GUARD_S,
                                 "tap_move_units": TAP_MOVE_UNITS}}
        record.update({key: value for key, value in self.record.items()
                       if key not in record and key not in ("mono", "wall", "error")})
        record.update(extra)
        changed = {key: value for key, value in record.items() if key not in ("mono", "wall")} != {
            key: value for key, value in self.record.items() if key not in ("mono", "wall")}
        if not force and not (changed and now - self.written >= 1.0) and now - self.written < STATUS_HEARTBEAT:
            return
        record.update(mono=now, wall=time.time())
        self.record = record
        self.written = now
        temporary = self.path.with_name(self.path.name + ".tmp")
        try:
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_CLOEXEC, 0o644)
            try:
                os.fchmod(fd, 0o644)
                os.write(fd, json.dumps(record).encode())
            finally:
                os.close(fd)
            os.replace(temporary, self.path)
        except OSError:
            pass


class Stop(Exception):
    pass


class Service:
    """The daemon. Every wait re-arms a kernel interval timer: if the loop stalls
    for WATCHDOG_S, SIGALRM (default action: terminate) ends the process, and the
    kernel releases the grab and destroys the uinput device."""

    def __init__(self, backend, runtime=RUNTIME, notifier=None, clock=time.monotonic):
        self.backend = backend
        self.runtime = runtime
        self.notifier = notifier or Notifier()
        self.clock = clock
        self.stopping = False
        self.status = Status(runtime, uuid.uuid4().hex)
        self.pad = None
        self.uinput = None
        self.core = None
        self.layout = None

    def arm(self):
        signal.setitimer(signal.ITIMER_REAL, WATCHDOG_S)
        self.notifier.watchdog(self.clock())

    def request_stop(self, *_):
        self.stopping = True

    def run(self):
        signal.signal(signal.SIGALRM, signal.SIG_DFL)
        signal.signal(signal.SIGTERM, self.request_stop)
        signal.signal(signal.SIGINT, self.request_stop)
        self.arm()
        try:
            return self.serve()
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)

    def serve(self):
        found = self.backend.find()
        if found is None:
            return self.refuse("ELAN touchpad event node not found under " + str(self.backend.device))
        try:
            self.pad = self.backend.open_touchpad(found[0])
        except (IdentityError, OSError) as error:
            return self.refuse(str(error))
        try:
            self.uinput = self.backend.open_uinput(self.pad.caps)
            self.layout = self.pad.caps
            self.status.record.update(device=str(found[0]), hid=found[1], virtual=self.uinput.sysname)
            ready = False
            while True:
                try:
                    self.attach(START_TIMEOUT if not ready else REATTACH_TIMEOUT)
                except Stop:
                    self.status.write("stopped", self.core.stats if self.core else None)
                    return 0
                if not ready:
                    self.notifier.send("READY=1\nSTATUS=filtering " + FILTER_NAME)
                    ready = True
                self.status.write("active", self.core.stats)
                if self.pump() == "stop":
                    self.shutdown()
                    return 0
                self.write(self.core.release_all(self.clock()))
                self.pad.close()
                self.pad = None
                self.status.write("reattaching", self.core.stats)
                if not self.reattach():
                    self.status.write("device-gone", self.core.stats,
                                      error="touchpad did not come back; it is unfiltered")
                    return 0
        except Exception as error:
            self.status.write("failed", self.core.stats if self.core else None,
                              error=f"{type(error).__name__}: {error}")
            raise
        finally:
            self.notifier.send("STOPPING=1")
            if self.uinput is not None:
                try:
                    if self.core is not None:
                        self.write(self.core.release_all(self.clock()))
                except Exception:
                    pass
                self.uinput.close()
            if self.pad is not None:
                self.pad.close()

    def refuse(self, message):
        print(message, file=sys.stderr, flush=True)
        self.status.write("refused", error=message)
        self.notifier.send("STATUS=" + message)
        return EXIT_REFUSED

    def write(self, frames):
        for _, events in frames:
            self.uinput.write(events)

    def wait(self, seconds):
        deadline = self.clock() + seconds
        while self.clock() < deadline:
            if self.stopping:
                raise Stop
            self.arm()
            time.sleep(min(0.05, max(0.0, deadline - self.clock())))

    def attach(self, timeout):
        """Grab only while untouched, so libinput never misses a lift of a touch it saw begin."""
        self.status.write("waiting-untouched", self.core.stats if self.core else None)
        deadline = self.clock() + timeout
        while True:
            if self.stopping:
                raise Stop
            self.arm()
            self.pad.drain()
            if not touched(self.pad.state()):
                self.pad.grab(True)
                self.pad.drain()
                state = self.pad.state()
                if not touched(state):
                    break
                self.pad.grab(False)
            if self.clock() > deadline:
                raise TimeoutError("the touchpad stayed touched; not grabbing it")
            self.wait(0.1)
        previous = self.core
        self.core = FilterCore.for_device(self.pad.caps)
        if previous is not None:
            # Same layout (checked): keep the model of what the uinput device stores.
            self.core.out = previous.out
            self.core.stats.update(previous.stats)
        self.write(self.core.seed(self.clock(), state))

    def pump(self):
        pending = bytearray()
        frame = []
        dropping = False
        stop_deadline = None
        while True:
            self.arm()
            now = self.clock()
            if self.stopping:
                core = self.core
                idle = not core.raw.active() and core.pending is None and not core.hidden
                if stop_deadline is None:
                    stop_deadline = now + STOP_WAIT
                if idle or now >= stop_deadline:
                    return "stop"
            timeout = POLL_S
            deadline = self.core.deadline()
            if deadline is not None:
                timeout = min(timeout, max(0.0, deadline - now))
            readable, _, _ = select.select([self.pad.fileno()], [], [], timeout)
            if readable:
                try:
                    data = self.pad.read()
                except BlockingIOError:
                    data = None
                except OSError as error:
                    if error.errno in (errno.ENODEV, errno.EIO, errno.ENXIO):
                        return "detached"
                    raise
                if data == b"":
                    return "detached"
                if data:
                    pending.extend(data)
                    complete = len(pending) // INPUT_EVENT.size * INPUT_EVENT.size
                    for second, micro, kind, code, value in INPUT_EVENT.iter_unpack(bytes(pending[:complete])):
                        moment = second + micro / 1e6
                        if kind == EV_SYN and code == SYN_DROPPED:
                            dropping = True
                            frame = []
                        elif kind == EV_SYN and code == SYN_REPORT:
                            if dropping:
                                dropping = False
                                self.write(self.core.resync(moment, self.pad.state()))
                            else:
                                self.write(self.core.feed(moment, frame))
                            frame = []
                        elif not dropping and kind != EV_SYN:
                            frame.append((kind, code, value))
                    del pending[:complete]
            self.write(self.core.tick(self.clock()))
            self.status.write("active", self.core.stats, force=False)

    def shutdown(self):
        self.write(self.core.release_all(self.clock()))
        self.uinput.close()
        self.uinput = None
        self.pad.grab(False)
        self.pad.close()
        self.pad = None
        self.status.write("stopped", self.core.stats)

    def reattach(self):
        """Follow a driver rebind (F12 recalibration): same device, new node."""
        deadline = self.clock() + REATTACH_TIMEOUT
        while self.clock() < deadline:
            try:
                self.wait(0.2)
            except Stop:
                return False
            found = self.backend.find()
            if found is None:
                continue
            try:
                pad = self.backend.open_touchpad(found[0])
            except IdentityError as error:
                print(error, file=sys.stderr, flush=True)
                return False
            except OSError:
                continue
            if not same_layout(self.layout, pad.caps):
                pad.close()
                print("touchpad came back with a different layout; exiting", file=sys.stderr, flush=True)
                return False
            self.pad = pad
            self.status.record.update(device=str(found[0]), hid=found[1])
            try:
                self.attach(REATTACH_TIMEOUT)
            except Stop:
                return False
            except TimeoutError:
                return False
            return True
        return False


def touched(model):
    return bool(model.active()) or bool(model.keys.get(BTN_TOUCH)) or bool(model.keys.get(BTN_LEFT))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--run", action="store_true", help="run the filter (root; via touchpad-filter.service)")
    mode.add_argument("--replay", type=Path, nargs="+", metavar="TRACE",
                      help="replay touchpad-watch traces through the corrections and print counts")
    parser.add_argument("--ghost-min-units", type=int, default=GHOST_MIN_UNITS)
    args = parser.parse_args()
    if args.replay:
        for path in args.replay:
            stats, _ = replay(json.loads(path.read_text()), args.ghost_min_units)
            print(json.dumps(dict(stats, trace=str(path), ghost_min_units=args.ghost_min_units)))
        return 0
    if os.geteuid() != 0:
        raise SystemExit("Run through touchpad-filter.service (scripts/touchpad-filter on).")
    return Service(Backend()).run()


if __name__ == "__main__":
    sys.exit(main())
