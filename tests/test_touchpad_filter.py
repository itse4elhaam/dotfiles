import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from touchpad_captures import load_capture  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("touchpad_filter", REPO / "scripts/touchpad-filter.py")
tf = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tf)
FRAME = 0.007
KEYS = (272, 325, 328, 330, 333, 334, 335)
# The real device, from the capture's libinput record header.
CAPS = {"name": tf.EXPECTED_NAME, "id": (0x18, 0x04F3, 0x31EC, 0x100), "types": {0, 1, 3, 4},
        "keys": set(KEYS), "msc": {5}, "props": {0, 2},
        "abs": {0: (0, 0, 3689, 0, 0, 32), 1: (0, 0, 2410, 0, 0, 31), 47: (0, 0, 4, 0, 0, 0),
                53: (0, 0, 3689, 0, 0, 32), 54: (0, 0, 2410, 0, 0, 31), 55: (0, 0, 2, 0, 0, 0),
                57: (0, 0, 65535, 0, 0, 0)}}


class Kernel:
    """Per-frame contact positions -> the evdev frames hid-multitouch and input-mt would emit."""

    def __init__(self):
        self.model = tf.Model(5, (53, 54, 55, 57), KEYS, (0, 1))
        self.slot_keys = [None] * 5
        self.emitted_slot = 0
        self.next_id = 100
        self.scan = 0

    def frame(self, contacts, button=None):
        events = []
        used = set()

        def mt(slot, code, value):
            if self.model.slots[slot][code] == value:
                return
            if slot != self.emitted_slot:
                events.append((3, 47, slot))
                self.emitted_slot = slot
            self.model.slots[slot][code] = value
            events.append((3, code, value))
        if button is not None:
            events.append((1, 272, button))
            self.model.keys[272] = button
        for key, (x, y) in contacts.items():
            slot = next((index for index, held in enumerate(self.slot_keys)
                         if held == key and self.model.slots[index][57] >= 0), None)
            if slot is None:
                slot = next(index for index in range(5)
                            if self.model.slots[index][57] < 0 and index not in used)
                self.slot_keys[slot] = key
                mt(slot, 57, self.next_id)
                self.next_id += 1
            used.add(slot)
            mt(slot, 53, x)
            mt(slot, 54, y)
        for slot in range(5):
            if self.model.slots[slot][57] >= 0 and slot not in used:
                mt(slot, 57, -1)
                self.slot_keys[slot] = None
        active = sorted(self.model.active(), key=lambda slot: self.model.slots[slot][57])
        count = len(active)
        for code, value in [(330, int(count > 0))] + [(code, int(count == number)) for number, code in
                                                       enumerate(tf.TOOL_KEYS, 1)]:
            if self.model.keys[code] != value:
                self.model.keys[code] = value
                events.append((1, code, value))
        if active:
            for code, value in zip((0, 1), self.model.position(active[0])):
                if self.model.axes[code] != value:
                    self.model.axes[code] = value
                    events.append((3, code, value))
        self.model.slot = self.emitted_slot
        self.scan += 7000
        return events + [(4, 5, self.scan)]


def raw_frames(script):
    """script: [(time, {contact: (x, y)}), ...] -> [(time, events)]."""
    kernel = Kernel()
    return [(moment, kernel.frame(contacts)) for moment, contacts in script]


def stroke(key, start, xs, y, step=FRAME):
    return [(round(start + index * step, 6), {key: (x, y)}) for index, x in enumerate(xs)]


def lift(moment):
    return [(round(moment, 6), {})]


def merge(*scripts):
    """Combine contact scripts frame by frame (same timestamps share a frame)."""
    frames = {}
    for script in scripts:
        for moment, contacts in script:
            frames.setdefault(moment, {}).update(contacts)
    ordered = sorted(frames.items())
    # A contact absent from a later frame has lifted; keep each frame's set as given.
    return ordered


def run(frames, ghost_min_units=tf.GHOST_MIN_UNITS, until=None):
    core = tf.FilterCore(ghost_min_units=ghost_min_units)
    out = []
    for moment, events in frames:
        out += core.feed(moment, events)
    out += core.tick((until or frames[-1][0]) + 1.0)
    return core, out


class View:
    """What libinput receives from the uinput device: written frames after kernel duplicate filtering."""

    def __init__(self):
        self.model = tf.Model(5, (53, 54, 55, 57), KEYS, (0, 1))
        self.history = []

    def apply(self, frames):
        for moment, events in frames:
            for event in events:
                if (event[0], event[1]) == (3, 57):
                    old = self.model.slots[self.model.slot][57]
                    assert (event[2] == -1) != (old == -1) or event[2] == old, \
                        f"double tracking ID {old} -> {event[2]} at {moment}"
                self.model.apply(*event)
            count = len(self.model.active())
            for code, value in [(330, int(count > 0))] + [(code, int(count == number)) for number, code in
                                                           enumerate(tf.TOOL_KEYS, 1)]:
                assert self.model.keys[code] == value, (moment, code, self.model.keys[code], count)
            self.history.append((moment, {self.model.slots[slot][57]: self.model.position(slot)
                                          for slot in self.model.active()}))
        return self


class PassThroughTests(unittest.TestCase):
    """Healthy input must come out bit-identical, and without added delay where libinput times it."""

    def assert_identical(self, frames, out, delayed=()):
        self.assertEqual([events for _, events in out], [events for _, events in frames])
        for index, ((moment, _), (written, _)) in enumerate(zip(frames, out)):
            if index in delayed:
                self.assertAlmostEqual(written - moment, tf.BRIDGE_WINDOW, places=6)
            else:
                self.assertEqual(written, moment, f"frame {index} delayed")
        View().apply(out)

    def test_single_finger_move_is_identical_and_only_the_lift_waits_for_a_restart(self):
        frames = raw_frames(stroke("a", 0.0, range(1000, 2000, 20), 1200) + lift(0.35))
        core, out = run(frames)
        self.assert_identical(frames, out, delayed={len(frames) - 1})
        self.assertEqual(core.stats["held_releases"], 1)
        self.assertEqual(core.stats["bridged_drops"], 0)

    def test_an_intentional_tap_is_identical_with_no_delay(self):
        frames = raw_frames(stroke("a", 0.0, [1500] * 13, 1200) + lift(0.091))
        core, out = run(frames)
        self.assert_identical(frames, out)
        self.assertEqual(core.stats["held_releases"], 0)

    def test_a_double_tap_and_a_tap_and_drag_keep_both_touches(self):
        script = (stroke("a", 0.0, [1500] * 12, 1200) + lift(0.084)
                  + stroke("b", 0.140, [1510] * 10, 1205) + lift(0.210)
                  + stroke("c", 0.300, [1500] * 11, 1200) + lift(0.377)
                  + stroke("d", 0.440, range(1500, 2200, 25), 1200) + lift(0.64))
        frames = raw_frames(script)
        core, out = run(frames)
        self.assert_identical(frames, out, delayed={len(frames) - 1})
        self.assertEqual(core.stats["bridged_drops"], 0)
        tracking = {event[2] for _, events in out for event in events if event[:2] == (3, 57) and event[2] >= 0}
        self.assertEqual(len(tracking), 4)

    def test_simultaneous_two_finger_scroll_is_identical(self):
        script = merge(stroke("a", 0.0, [1400] * 40, 1000), stroke("b", 0.0, [2000] * 40, 1000))
        script = [(moment, {"a": (1400, 1000 + 8 * index), "b": (2000, 1000 + 8 * index)})
                  for index, (moment, _) in enumerate(script)] + lift(0.28)
        frames = raw_frames(script)
        core, out = run(frames)
        self.assert_identical(frames, out)
        self.assertEqual(core.stats["held_ghosts"], 0)

    def test_staggered_two_finger_scroll_under_200_ms_is_identical(self):
        script = [(round(index * FRAME, 6), {"a": (1400, 1000 + 8 * index)}) for index in range(14)]
        script += [(round(index * FRAME, 6), {"a": (1400, 1000 + 8 * index), "b": (2100, 1000 + 8 * index)})
                   for index in range(14, 60)]
        frames = raw_frames(script + lift(0.42))
        core, out = run(frames)
        self.assert_identical(frames, out)
        self.assertEqual(core.stats["held_ghosts"], 0)

    def test_late_second_finger_is_shown_within_the_hold_and_never_dropped(self):
        # The second finger lands 400 ms after the first, 700 units away, and stays:
        # the ghost rule holds it, so this case is delayed by design, never eaten.
        script = [(round(index * FRAME, 6), {"a": (1400 + 4 * index, 1000)}) for index in range(57)]
        script += [(round(index * FRAME, 6), {"a": (1400 + 4 * index, 1000), "b": (2100, 1000 + 6 * index)})
                   for index in range(57, 150)]
        frames = raw_frames(script + lift(1.05))
        core, out = run(frames)
        view = View().apply(out)
        landed = 57 * FRAME
        shown = next(moment for moment, contacts in view.history if len(contacts) == 2)
        self.assertLessEqual(shown - landed, tf.GHOST_HOLD + 1e-9)
        self.assertEqual(core.stats["revealed_ghosts"], 1)
        self.assertEqual(core.stats["suppressed_ghosts"], 0)
        # Positions shown are raw positions; after the reveal every frame is the raw frame.
        raw_by_time = dict(frames)
        after = [(moment, events) for moment, events in out if moment > shown]
        self.assertTrue(after)
        for moment, events in after[:-1]:
            self.assertEqual(events, raw_by_time[moment])
        # While held, finger a's motion is forwarded unchanged and nothing of b leaks.
        held = [(moment, events) for moment, events in out if landed <= moment < shown]
        self.assertTrue(held)
        for moment, events in held:
            raw_a_x = [event for event in raw_by_time[moment] if event[:2] == (3, 0)]
            self.assertEqual([event for event in events if event[:2] == (3, 0)], raw_a_x)
            self.assertNotIn(2100, [event[2] for event in events if event[:2] == (3, 53)])


class BridgeTests(unittest.TestCase):
    def dead_band_script(self, gap=0.014, restart_x=1975):
        script = stroke("a", 0.0, range(1000, 1560, 10), 1200)
        end = script[-1][0] + FRAME
        script += lift(end)
        script += stroke("b", round(end + gap, 6), range(restart_x, 2600, 10), 1210)
        return script + lift(script[-1][0] + FRAME)

    def test_a_drop_across_the_band_continues_the_same_touch_at_the_real_position(self):
        frames = raw_frames(self.dead_band_script())
        core, out = run(frames)
        view = View().apply(out)
        self.assertEqual(core.stats["bridged_drops"], 1)
        mid = [contacts for moment, contacts in view.history][:-1]
        self.assertTrue(all(len(contacts) == 1 for contacts in mid), "the touch lifted mid-stroke")
        self.assertEqual({tid for contacts in mid for tid in contacts}, {100})
        positions = [next(iter(contacts.values())) for contacts in mid]
        self.assertIn((1975, 1210), positions)
        self.assertNotIn(tuple(range(1560, 1975)), positions)
        lifts = [event for _, events in out for event in events if event == (3, 57, -1)]
        self.assertEqual(len(lifts), 1)

    def test_a_restart_after_the_window_is_a_new_touch(self):
        frames = raw_frames(self.dead_band_script(gap=0.080))
        core, out = run(frames)
        self.assertEqual(core.stats["bridged_drops"], 0)
        self.assertEqual([events for _, events in out], [events for _, events in frames])

    def test_bridged_restart_in_another_slot_keeps_the_original_slot(self):
        frames = [(0.0, [(3, 57, 100), (3, 53, 1500), (3, 54, 1200), (1, 330, 1), (1, 325, 1),
                         (3, 0, 1500), (3, 1, 1200), (4, 5, 0)])]
        frames += [(round(0.007 * index, 6), [(3, 53, 1500 + 10 * index), (3, 0, 1500 + 10 * index),
                                              (4, 5, 7000 * index)]) for index in range(1, 40)]
        frames += [(0.287, [(3, 57, -1), (1, 330, 0), (1, 325, 0), (4, 5, 280000)]),
                   (0.301, [(3, 47, 1), (3, 57, 101), (3, 53, 2300), (3, 54, 1210), (1, 330, 1), (1, 325, 1),
                            (3, 0, 2300), (3, 1, 1210), (4, 5, 294000)]),
                   (0.308, [(3, 53, 2310), (3, 0, 2310), (4, 5, 301000)]),
                   (0.315, [(3, 57, -1), (1, 330, 0), (1, 325, 0), (4, 5, 308000)])]
        # A new touch in slot 0 exactly where slot 0's last contact ended: the kernel
        # omits X and Y because they equal its stored values. The virtual slot 0
        # last showed 2310, so the filter must supply them.
        frames += [(0.6, [(3, 47, 0), (3, 57, 102), (1, 330, 1), (1, 325, 1), (3, 0, 1890), (3, 1, 1200),
                          (4, 5, 0)]),
                   (0.607, [(3, 53, 1895), (3, 0, 1895), (4, 5, 7000)]),
                   (0.614, [(3, 53, 1900), (3, 0, 1900), (4, 5, 14000)]),
                   (0.621, [(3, 57, -1), (1, 330, 0), (1, 325, 0), (4, 5, 21000)])]
        core, out = run(frames)
        view = View().apply(out)
        self.assertEqual(core.stats["bridged_drops"], 1)
        bridged = [contacts for _, contacts in view.history if contacts.get(100) == (2310, 1210)]
        self.assertTrue(bridged)
        self.assertNotIn(101, {tid for _, contacts in view.history for tid in contacts})
        self.assertEqual([contacts for moment, contacts in view.history if 0.6 <= moment < 0.62],
                         [{102: (1890, 1200)}, {102: (1895, 1200)}, {102: (1900, 1200)}])
        # Back in sync, so later frames pass verbatim again.
        self.assertEqual(core.out.state(), core.raw.state())
        self.assertEqual(out[-2][1], frames[-2][1])

    def test_a_tap_followed_by_a_fast_far_touch_is_not_merged(self):
        script = stroke("a", 0.0, [1500] * 10, 1200) + lift(0.070)
        script += stroke("b", 0.090, range(2200, 2400, 20), 1200) + lift(0.160)
        frames = raw_frames(script)
        core, out = run(frames)
        self.assertEqual(core.stats["bridged_drops"], 0)
        self.assertEqual(core.stats["bridge_skipped_tap_candidate"], 1)
        self.assertEqual([events for _, events in out], [events for _, events in frames])
        self.assertEqual([moment for moment, _ in out][:-1], [moment for moment, _ in frames][:-1])

    def test_a_physical_click_at_the_restart_is_never_bridged(self):
        script = self.dead_band_script()
        kernel = Kernel()
        frames = []
        restart = next(index for index, (_, contacts) in enumerate(script) if "b" in contacts)
        for index, (moment, contacts) in enumerate(script):
            frames.append((moment, kernel.frame(contacts, button=1 if index == restart else None)))
        core, out = run(frames)
        self.assertEqual(core.stats["bridged_drops"], 0)

    def test_two_drops_in_one_stroke_are_both_bridged(self):
        script = stroke("a", 0.0, range(1000, 1500, 10), 1200)
        script += lift(0.350) + stroke("b", 0.364, range(1700, 2200, 10), 1200)
        script += lift(0.714) + stroke("c", 0.728, range(2400, 2900, 10), 1200) + lift(1.078)
        core, out = run(raw_frames(script))
        self.assertEqual(core.stats["bridged_drops"], 2)
        self.assertEqual(len({tid for _, contacts in View().apply(out).history for tid in contacts}), 1)


class GhostTests(unittest.TestCase):
    def primary(self, frames=120):
        return [(round(index * FRAME, 6), {"a": (1000 + 5 * index, 1200)}) for index in range(frames)]

    def with_ghost(self, script, start, frames, x=1800, y=1200):
        for index in range(start, start + frames):
            script[index][1]["g"] = (x, y)
        return script

    def test_a_short_ghost_is_dropped_and_the_finger_passes_unchanged(self):
        script = self.with_ghost(self.primary(), 60, 5)
        frames = raw_frames(script + lift(120 * FRAME))
        core, out = run(frames)
        view = View().apply(out)
        self.assertEqual(core.stats["suppressed_ghosts"], 1)
        self.assertTrue(all(len(contacts) <= 1 for _, contacts in view.history))
        self.assertEqual([contacts for _, contacts in view.history][:-1],
                         [{100: (1000 + 5 * index, 1200)} for index in range(120)])
        self.assertEqual(core.out.state(), core.raw.state())

    def test_a_ghost_closer_than_the_floor_passes_verbatim(self):
        script = self.with_ghost(self.primary(), 60, 5, x=1000 + 5 * 60 + 285)
        frames = raw_frames(script + lift(120 * FRAME))
        core, out = run(frames)
        self.assertEqual(core.stats["held_ghosts"], 0)
        self.assertEqual([events for _, events in out], [events for _, events in frames])
        core, _ = run(frames, ghost_min_units=200)
        self.assertEqual(core.stats["suppressed_ghosts"], 1)

    def test_when_the_first_finger_lifts_during_a_hold_the_second_is_shown_first(self):
        script = self.primary(60)
        script += [(round(60 * FRAME, 6), {"a": (1300, 1200), "g": (2100, 1200)})]
        script += [(round(index * FRAME, 6), {"g": (2100 + 5 * (index - 61), 1200)}) for index in range(61, 120)]
        frames = raw_frames(script + lift(120 * FRAME))
        core, out = run(frames)
        view = View().apply(out)
        counts = [len(contacts) for _, contacts in view.history]
        first_two = counts.index(2)
        self.assertNotIn(0, counts[:first_two + 2], "a lift showed before the second finger")
        self.assertEqual(counts[first_two + 1], 1)
        self.assertEqual(out[first_two][0], out[first_two + 1][0])
        self.assertEqual(core.stats["suppressed_ghosts"], 0)

    def test_a_click_or_third_finger_during_a_hold_shows_the_held_finger_first(self):
        script = self.with_ghost(self.primary(), 60, 30)
        kernel = Kernel()
        frames = [(moment, kernel.frame(contacts, button=1 if index == 63 else None))
                  for index, (moment, contacts) in enumerate(script)]
        core, out = run(frames)
        view = View().apply(out)
        click = next(index for index, (_, events) in enumerate(out) if (1, 272, 1) in events)
        self.assertEqual(len(view.history[click][1]), 2)
        self.assertEqual(len(view.history[click - 1][1]), 2)
        self.assertEqual(core.stats["revealed_ghosts"], 1)
        script = self.with_ghost(self.primary(), 60, 30)
        for index in range(63, 90):
            script[index][1]["c"] = (2600, 1500)
        core, out = run(raw_frames(script))
        self.assertEqual(core.stats["revealed_ghosts"], 1)
        self.assertEqual(max(len(contacts) for _, contacts in View().apply(out).history), 3)


class CaptureReplayTests(unittest.TestCase):
    """Replays the labelled captures. Counts are pinned so a logic change shows up here."""
    EXPECTED = {  # capture: (bridged, suppressed at 500 units, suppressed at 200 units)
        "A": (32, 0, 2), "B": (14, 0, 1), "C": (16, 1, 1), "D": (18, 0, 0)}

    def test_captures_bridge_the_drops_and_never_break_the_output_stream(self):
        for name, (bridged, ghosts_500, ghosts_200) in self.EXPECTED.items():
            with self.subTest(capture=name):
                trace = load_capture(name)
                for floor, ghosts in ((500, ghosts_500), (200, ghosts_200)):
                    stats, out = tf.replay(trace, floor)
                    View().apply(out)
                    self.assertEqual((stats["bridged_drops"], stats["suppressed_ghosts"]), (bridged, ghosts))


class FakeIoctl:
    """Answers the evdev and uinput ioctls from a capability table, and records every call."""

    def __init__(self, caps, model=None):
        self.caps = caps
        self.model = model
        self.calls = []

    @staticmethod
    def bits(codes, size):
        data = bytearray(size)
        for code in codes:
            data[code // 8] |= 1 << code % 8
        return data

    def __call__(self, fd, request, arg=0, mutate=False):
        kind, number, size = request >> 8 & 0xFF, request & 0xFF, request >> 16 & 0x3FFF
        self.calls.append((request, arg if isinstance(arg, int) else bytes(arg)))
        data = None
        if kind == ord("E"):
            caps = self.caps
            if number == 0x06:
                data = caps["name"].encode()
            elif number == 0x02:
                data = struct.pack("4H", *caps["id"])
            elif number == 0x09:
                data = self.bits(caps["props"], size)
            elif 0x20 <= number < 0x40:
                table = {0: caps["types"], 1: caps["keys"], 3: set(caps["abs"]), 4: caps["msc"]}
                data = self.bits(table.get(number - 0x20, set()), size)
            elif 0x40 <= number < 0x80:
                info = list(caps["abs"][number - 0x40])
                data = struct.pack("6i", *info)
            elif number == 0x0A:
                code = struct.unpack_from("I", arg)[0]
                slots = (size - 4) // 4
                values = [self.model.slots[index][code] if self.model else (-1 if code == 57 else 0)
                          for index in range(slots)]
                data = struct.pack("I", code) + struct.pack(f"{slots}i", *values)
            elif number == 0x18:
                data = self.bits([code for code, down in (self.model.keys.items() if self.model else []) if down],
                                 size)
        elif kind == ord("U") and number == 44:
            data = b"input999"
        if data is not None and mutate:
            arg[:len(data)] = data
        return 0


class DeviceTests(unittest.TestCase):
    def opener(self, log):
        def open_fake(path, flags, mode=0o777):
            log.append((str(path), flags))
            return os.open(os.devnull, os.O_RDWR | os.O_CLOEXEC)
        return open_fake

    def test_identity_mismatch_refuses_before_any_grab(self):
        for change in ({"name": "ELAN07AC:00 04F3:31EC Mouse"}, {"id": (0x18, 0x04F3, 0x31ED, 0x100)},
                       {"id": (0x03, 0x04F3, 0x31EC, 0x100)}, {"props": {0}}):
            with self.subTest(change=change):
                ioctl, opened = FakeIoctl(dict(CAPS, **change)), []
                with self.assertRaises(tf.IdentityError):
                    tf.Touchpad("/dev/input/event5", ioctl, self.opener(opened))
                self.assertNotIn(tf.EVIOCGRAB, [request for request, _ in ioctl.calls])
                self.assertTrue(opened[0][1] & os.O_CLOEXEC and not opened[0][1] & (os.O_WRONLY | os.O_RDWR))

    def test_the_virtual_device_mirrors_the_touchpad_with_a_distinct_name(self):
        ioctl, opened = FakeIoctl(CAPS), []
        pad = tf.Touchpad("/dev/input/event5", ioctl, self.opener(opened))
        device = tf.UInput(pad.caps, path="/dev/uinput", ioctl=ioctl, opener=self.opener(opened))
        self.assertTrue(opened[1][1] & os.O_CLOEXEC)
        calls = ioctl.calls
        setup = next(arg for request, arg in calls if request == tf.UI_DEV_SETUP)
        bus, vendor, product, version, name, _ = struct.unpack("4H80sI", setup)
        self.assertEqual((bus, vendor, product, version), CAPS["id"])
        self.assertEqual(name.rstrip(b"\0").decode(), tf.FILTER_NAME)
        axes = {struct.unpack("HH6i", arg)[0]: struct.unpack("HH6i", arg)[2:] for request, arg in calls
                if request == tf.UI_ABS_SETUP}
        self.assertEqual(axes, {code: (0, minimum, maximum, 0, flat, resolution)
                                for code, (_, minimum, maximum, _, flat, resolution) in CAPS["abs"].items()})
        self.assertEqual({arg for request, arg in calls if request == tf.UI_SET_KEYBIT}, set(KEYS))
        self.assertEqual({arg for request, arg in calls if request == tf.UI_SET_PROPBIT}, {0, 2})
        self.assertEqual({arg for request, arg in calls if request == tf.UI_SET_MSCBIT}, {5})
        self.assertEqual({arg for request, arg in calls if request == tf.UI_SET_EVBIT}, {1, 3, 4})
        self.assertEqual([request for request, _ in calls][-2:], [tf.UI_DEV_CREATE, tf.UI_GET_SYSNAME(64)])
        device.close()
        self.assertEqual(calls[-1][0], tf.UI_DEV_DESTROY)
        pad.close()

    def test_discovery_finds_only_the_touchpad_node_of_the_i2c_device(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for hid, number, name, event in (("0018:04F3:31EC.002C", 142, "ELAN07AC:00 04F3:31EC Touchpad", 5),
                                             ("0018:04F3:31EC.002C", 141, "ELAN07AC:00 04F3:31EC Mouse", 4)):
                node = root / hid / "input" / f"input{number}"
                (node / f"event{event}").mkdir(parents=True)
                (node / "name").write_text(name + "\n")
            self.assertEqual(tf.Backend(device=root).find(), (Path("/dev/input/event5"), "0018:04F3:31EC.002C"))
            self.assertIsNone(tf.Backend(device=root / "missing").find())

    def test_state_query_reads_slots_keys_and_axes(self):
        model = tf.Model(5, (53, 54, 55, 57), KEYS, (0, 1))
        model.slots[2][57], model.slots[2][53] = 7, 1234
        model.keys[330] = 1
        ioctl = FakeIoctl(CAPS, model)
        pad = tf.Touchpad("/dev/input/event5", ioctl, self.opener([]))
        state = pad.state()
        self.assertEqual(state.active(), {2})
        self.assertEqual(state.slots[2][53], 1234)
        self.assertTrue(tf.touched(state))
        pad.close()


class FakePad:
    def __init__(self, sock, hid, log, stall=False, touched_reads=0):
        self.sock, self.hid, self.log, self.stall = sock, hid, log, stall
        self.touched_reads = touched_reads
        self.caps = CAPS
        self.path = "/dev/input/event5"
        self.grabbed = False

    def fileno(self):
        return self.sock.fileno()

    def read(self):
        data = self.sock.recv(24 * 256)
        if data and self.stall:
            time.sleep(3)
        return data

    def drain(self):
        try:
            while self.sock.recv(4096):
                pass
        except BlockingIOError:
            pass

    def grab(self, on):
        self.grabbed = on
        self.log(f"grab {int(on)} {self.hid}")

    def state(self):
        model = tf.Model(5, (53, 54, 55, 57), KEYS, (0, 1))
        if self.grabbed and self.touched_reads:
            self.touched_reads -= 1
            model.slots[0][57] = 5
        return model

    def close(self):
        self.log(f"close {self.hid}")
        self.sock.close()


class FakeUInput:
    def __init__(self, sock, log):
        self.sock, self.log, self.sysname = sock, log, "input999"

    def write(self, events):
        self.log("frame " + json.dumps(events))

    def close(self):
        self.log("destroy")
        self.sock.close()


class FakeBackend:
    device = Path("/sys/fake")

    def __init__(self, pads, log, uinput_sock):
        self.pads, self.log, self.uinput_sock = list(pads), log, uinput_sock
        self.current = None

    def find(self):
        if self.current is None and self.pads:
            self.current = self.pads.pop(0)
        return (Path(self.current.path), self.current.hid) if self.current else None

    def open_touchpad(self, path):
        pad, self.current = self.current, None
        return pad

    def open_uinput(self, caps):
        return FakeUInput(self.uinput_sock, self.log)


class ServiceProcessTests(unittest.TestCase):
    """Run the real service loop in a child process with fake devices."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.log_path = self.root / "log"
        self.pid = None
        self.addCleanup(self.reap)

    def reap(self):
        if self.pid:
            try:
                os.kill(self.pid, signal.SIGKILL)
                os.waitpid(self.pid, 0)
            except (ProcessLookupError, ChildProcessError):
                pass

    def start(self, pads=1, settings=None, **pad_options):
        sockets = [socket.socketpair() for _ in range(pads + 1)]
        pid = os.fork()
        if pid == 0:
            try:
                for name, value in (settings or {}).items():
                    setattr(tf, name, value)
                handle = open(self.log_path, "a", buffering=1)

                def log(line):
                    handle.write(line + "\n")
                for ours, _ in sockets:
                    ours.close()
                for _, theirs in sockets:
                    theirs.setblocking(False)
                fakes = [FakePad(sockets[index][1], f"0018:04F3:31EC.{0x2C + index:04X}", log, **pad_options)
                         for index in range(pads)]
                service = tf.Service(FakeBackend(fakes, log, sockets[-1][1]), runtime=self.root,
                                     notifier=tf.Notifier(""))
                code = service.run()
            except BaseException as error:  # noqa: BLE001 - the child must never return into unittest
                with open(self.log_path, "a") as handle:
                    handle.write(f"error {type(error).__name__} {error}\n")
                code = 1
            os._exit(code)
        self.pid = pid
        for ours, theirs in sockets:
            theirs.close()
            self.addCleanup(ours.close)
        return [ours for ours, _ in sockets]

    def status(self):
        try:
            return json.loads((self.root / "status.json").read_text())
        except (OSError, ValueError):
            return {}

    def wait_for(self, predicate, timeout=5.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return True
            time.sleep(0.02)
        self.fail(f"timed out; status {self.status()} log {self.lines()}")

    def lines(self):
        return self.log_path.read_text().splitlines() if self.log_path.exists() else []

    def send(self, sock, events):
        now = time.monotonic()
        sock.sendall(b"".join(tf.INPUT_EVENT.pack(int(now), int(now % 1 * 1e6), *event)
                              for event in events + [(0, 0, 0)]))

    def touch(self, sock, tracking_id=1, x=1500):
        self.send(sock, [(3, 57, tracking_id), (3, 53, x), (3, 54, 1200), (1, 330, 1), (1, 325, 1)])

    def exit_status(self, timeout=5.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            pid, status = os.waitpid(self.pid, os.WNOHANG)
            if pid:
                self.pid = None
                return status
            time.sleep(0.01)
        self.fail("child did not exit")

    def test_sigkill_closes_the_grabbed_descriptor_so_the_kernel_releases_the_grab(self):
        pad, uinput = self.start()
        self.wait_for(lambda: self.status().get("state") == "active")
        self.touch(pad)
        self.wait_for(lambda: any(line.startswith("frame") and "57, 1" in line for line in self.lines()))
        os.kill(self.pid, signal.SIGKILL)
        self.assertTrue(os.WIFSIGNALED(self.exit_status()))
        # EOF only once every copy of the child's descriptor is closed: nothing kept the grab alive.
        pad.settimeout(2)
        uinput.settimeout(2)
        self.assertEqual(pad.recv(1), b"")
        self.assertEqual(uinput.recv(1), b"")

    def test_a_stalled_loop_is_killed_by_the_watchdog_within_about_a_second(self):
        pad, _ = self.start(stall=True)
        self.wait_for(lambda: self.status().get("state") == "active")
        started = time.monotonic()
        self.touch(pad)
        status = self.exit_status()
        elapsed = time.monotonic() - started
        self.assertTrue(os.WIFSIGNALED(status) and os.WTERMSIG(status) == signal.SIGALRM, status)
        self.assertLess(elapsed, 1.6)
        pad.settimeout(2)
        self.assertEqual(pad.recv(1), b"")

    def test_stop_lifts_the_virtual_touch_then_ungrabs_and_destroys(self):
        pad, _ = self.start()
        self.wait_for(lambda: self.status().get("state") == "active")
        self.touch(pad)
        self.wait_for(lambda: any("57, 1" in line for line in self.lines()))
        os.kill(self.pid, signal.SIGTERM)
        time.sleep(0.3)
        self.send(pad, [(3, 57, -1), (1, 330, 0), (1, 325, 0)])
        status = self.exit_status()
        self.assertEqual(os.WEXITSTATUS(status), 0)
        lines = self.lines()
        tail = lines[lines.index("grab 1 0018:04F3:31EC.002C"):]
        self.assertIn("destroy", tail)
        self.assertLess(tail.index("destroy"), tail.index("grab 0 0018:04F3:31EC.002C"))
        self.assertEqual(self.status()["state"], "stopped")

    def test_grabs_only_an_untouched_pad(self):
        pad, _ = self.start(touched_reads=2)
        self.wait_for(lambda: self.status().get("state") == "active")
        grabs = [line for line in self.lines() if line.startswith("grab")]
        self.assertEqual(grabs[:5], ["grab 1 0018:04F3:31EC.002C", "grab 0 0018:04F3:31EC.002C",
                                     "grab 1 0018:04F3:31EC.002C", "grab 0 0018:04F3:31EC.002C",
                                     "grab 1 0018:04F3:31EC.002C"])
        os.kill(self.pid, signal.SIGTERM)
        self.exit_status()

    def test_follows_a_driver_rebind_and_lifts_the_touch_in_between(self):
        first, second, _ = self.start(pads=2)
        self.wait_for(lambda: self.status().get("state") == "active")
        self.touch(first)
        self.wait_for(lambda: any("57, 1" in line for line in self.lines()))
        first.close()
        self.wait_for(lambda: self.status().get("hid") == "0018:04F3:31EC.002D"
                      and self.status().get("state") == "active")
        lines = self.lines()
        detach = lines.index("close 0018:04F3:31EC.002C")
        self.assertTrue(any("[3, 57, -1]" in line for line in lines[:detach]))
        self.touch(second, tracking_id=1)
        self.wait_for(lambda: sum("[3, 57, 1]" in line for line in self.lines()) == 2)
        os.kill(self.pid, signal.SIGTERM)
        self.send(second, [(3, 57, -1), (1, 330, 0), (1, 325, 0)])
        self.assertEqual(os.WEXITSTATUS(self.exit_status()), 0)

    def test_exits_unfiltered_when_the_touchpad_does_not_come_back(self):
        first, _ = self.start(settings={"REATTACH_TIMEOUT": 0.5})
        self.wait_for(lambda: self.status().get("state") == "active")
        first.close()
        self.assertEqual(os.WEXITSTATUS(self.exit_status()), 0)
        self.assertEqual(self.status()["state"], "device-gone")
        self.assertIn("destroy", self.lines())


class RefusalTests(unittest.TestCase):
    def test_the_service_refuses_a_mismatched_device_without_grabbing_or_creating_uinput(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            node = root / "sysfs/0018:04F3:31EC.002C/input/input142"
            (node / "event5").mkdir(parents=True)
            (node / "name").write_text(tf.EXPECTED_NAME + "\n")
            ioctl, opened = FakeIoctl(dict(CAPS, id=(0x18, 0x04F3, 0x3100, 0x100))), []
            backend = tf.Backend(device=root / "sysfs", uinput=root / "uinput", ioctl=ioctl,
                                 opener=DeviceTests.opener(None, opened))
            service = tf.Service(backend, runtime=root, notifier=tf.Notifier(""))
            service.arm = lambda: None
            with contextlib.redirect_stderr(io.StringIO()) as stderr:
                self.assertEqual(service.serve(), tf.EXIT_REFUSED)
            self.assertIn("refusing", stderr.getvalue())
            self.assertEqual([path for path, _ in opened], ["/dev/input/event5"])
            self.assertNotIn(tf.EVIOCGRAB, [request for request, _ in ioctl.calls])
            status = json.loads((root / "status.json").read_text())
            self.assertEqual(status["state"], "refused")
            self.assertIn("product 3100", status["error"])


class CoreEdgeTests(unittest.TestCase):
    def test_resync_lifts_everything_and_ignores_contacts_already_down(self):
        core = tf.FilterCore()
        kernel = Kernel()
        for moment, contacts in stroke("a", 0.0, range(1000, 1100, 10), 1200):
            core.feed(moment, kernel.frame(contacts))
        frames = core.resync(0.1, kernel.model)
        self.assertIn((3, 57, -1), frames[0][1])
        self.assertEqual(core.ignored, {0})
        self.assertEqual(core.feed(0.107, kernel.frame({"a": (1110, 1200)}))[-1][1], [(4, 5, kernel.scan)])

    def test_replay_cli_prints_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            trace = Path(directory) / "trace.json"
            frames = raw_frames(BridgeTests.dead_band_script(None))
            trace.write_text(json.dumps({"events": [[moment, *event] for moment, events in frames
                                                    for event in events + [(0, 0, 0)]]}))
            result = subprocess.run([sys.executable, "-I", str(REPO / "scripts/touchpad-filter.py"),
                                     "--replay", str(trace)], capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["bridged_drops"], 1)

    def test_run_mode_refuses_without_root(self):
        result = subprocess.run([sys.executable, "-I", str(REPO / "scripts/touchpad-filter.py"), "--run"],
                                capture_output=True, text=True, timeout=20)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("touchpad-filter.service", result.stderr)


class ControlScriptTests(unittest.TestCase):
    """scripts/touchpad-filter with stub sudo, systemctl, xinput and notify-send (no real sudo on PATH)."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        for tool in ("bash", "flock", "cat", "grep", "rm", "touch"):
            (self.bin / tool).symlink_to(subprocess.run(["which", tool], capture_output=True, text=True,
                                                        check=True).stdout.strip())
        self.calls = self.root / "calls"
        self.stub("sudo", 'echo "sudo $*" >> "$CALLS"\n'
                          'if [[ -n ${SUDO_FAILS:-} ]]; then echo "$SUDO_FAILS" >&2; exit 1; fi\n'
                          'case $3 in start) touch "$ACTIVE" ;; stop) rm -f "$ACTIVE" ;; esac\n')
        self.stub("systemctl", 'if [[ -e $ACTIVE ]]; then [[ $2 == --quiet ]] || echo active; exit 0; fi\n'
                               '[[ $2 == --quiet ]] || echo inactive; exit 3\n')
        self.stub("notify-send", 'echo "notify-send $*" >> "$CALLS"\n')
        self.stub("xinput", 'echo "${XINPUT_NAMES:-}"\n')
        self.status = self.root / "status.json"
        self.status.write_text(json.dumps({"state": "active", "virtual": "input999",
                                           "stats": {"bridged_drops": 4, "suppressed_ghosts": 1}}))
        self.env = {"PATH": str(self.bin), "HOME": str(self.root), "XDG_RUNTIME_DIR": str(self.root),
                    "CALLS": str(self.calls), "ACTIVE": str(self.root / "active"), "DISPLAY": ":99",
                    "TOUCHPAD_FILTER_STATUS": str(self.status)}

    def stub(self, name, body):
        path = self.bin / name
        path.write_text("#!/bin/bash\n" + body)
        path.chmod(0o755)

    def control(self, *args, **extra):
        return subprocess.run(["bash", str(REPO / "scripts/touchpad-filter"), *args],
                              env=dict(self.env, **extra), capture_output=True, text=True, timeout=20)

    def logged(self):
        return self.calls.read_text().splitlines() if self.calls.exists() else []

    def test_on_and_off_run_exactly_the_two_allowed_commands(self):
        result = self.control("on")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("bridged 4 drops, suppressed 1 ghosts", result.stdout)
        result = self.control("off")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("unfiltered", result.stdout)
        self.assertEqual(self.logged(), ["sudo -n /usr/bin/systemctl start touchpad-filter.service",
                                         "sudo -n /usr/bin/systemctl stop touchpad-filter.service"])

    def test_toggle_flips_state_and_notifies_for_the_shortcut(self):
        self.control("toggle", "--notify")
        self.control("toggle", "--notify")
        calls = self.logged()
        self.assertEqual([call for call in calls if call.startswith("sudo")],
                         ["sudo -n /usr/bin/systemctl start touchpad-filter.service",
                          "sudo -n /usr/bin/systemctl stop touchpad-filter.service"])
        notices = [call for call in calls if call.startswith("notify-send")]
        self.assertEqual(len(notices), 2)
        self.assertIn("On.", notices[0])
        self.assertIn("Off.", notices[1])

    def test_on_when_already_on_does_nothing(self):
        (self.root / "active").touch()
        result = self.control("on")
        self.assertIn("Already on", result.stdout)
        self.assertEqual(self.logged(), [])

    def test_missing_install_is_explained(self):
        result = self.control("on", "--notify", SUDO_FAILS="sudo: a password is required")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Not installed: run sudo /home/elhaam/dotfiles/scripts/install-touchpad-filter",
                      result.stdout)
        self.assertTrue(any("-u critical" in call for call in self.logged()))

    def test_a_refused_start_says_the_pad_is_unfiltered(self):
        self.status.write_text(json.dumps({"state": "refused", "error": "refusing a device that is not ..."}))
        result = self.control("on", SUDO_FAILS="Job for touchpad-filter.service failed.")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Did not start; the touchpad is unfiltered", result.stdout)
        self.assertIn("refusing a device", result.stdout)

    def test_status_reports_service_counts_and_the_x11_device(self):
        (self.root / "active").touch()
        result = self.control("status", XINPUT_NAMES=tf.FILTER_NAME)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [
            "touchpad-filter.service: active",
            "State active: bridged 4 drops, suppressed 1 ghosts, virtual device input999.",
            f'X11 lists "{tf.FILTER_NAME}".'])

    def test_bad_arguments_are_rejected(self):
        for args in ((), ("enable",), ("on", "--quiet"), ("on", "--notify", "x")):
            with self.subTest(args=args):
                self.assertEqual(self.control(*args).returncode, 2)
        self.assertEqual(self.logged(), [])


class UnitFileTests(unittest.TestCase):
    def test_unit_is_opt_in_sandboxed_and_never_restarts(self):
        unit = (REPO / "scripts/touchpad-filter.service").read_text()
        self.assertNotRegex(unit, r"(?m)^\[Install\]")
        for line in ("Restart=no", "WatchdogSec=2s", "Type=notify", "CapabilityBoundingSet=",
                     "DevicePolicy=closed", "DeviceAllow=char-input r", "DeviceAllow=/dev/uinput rw",
                     "ProtectSystem=strict", "PrivateNetwork=yes", "NoNewPrivileges=yes",
                     "ExecStart=/usr/bin/python3 -I /usr/local/libexec/touchpad-filter.py --run"):
            self.assertIn(line + "\n", unit)
        installer = (REPO / "scripts/install-touchpad-filter").read_text()
        self.assertNotRegex(installer, r"systemctl (enable|start|restart)")
        self.assertIn("NOPASSWD: %s start touchpad-filter.service, %s stop touchpad-filter.service", installer)


if __name__ == "__main__":
    unittest.main()
