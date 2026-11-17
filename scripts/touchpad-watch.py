#!/usr/bin/python3
"""Record this ELAN touchpad and replay candidate faults; never reset automatically."""
import argparse
from collections import deque
import json
import math
import fcntl
import os
from pathlib import Path
import selectors
import struct
import subprocess
import time

DEVICE = Path("/sys/bus/i2c/devices/i2c-ELAN07AC:00")
NAMES = {"ELAN07AC:00 04F3:31EC Touchpad": "touchpad",
         "ELAN07AC:00 04F3:31EC Mouse": "mouse"}
HID_NAME = "ELAN07AC:00 04F3:31EC"
INPUT_EVENT = struct.Struct("@llHHi")
HIDIOCGRAWINFO = 0x80084803        # _IOR('H', 0x03, struct hidraw_devinfo)
HIDIOCGRAWNAME = 0x81004804        # _IOC(_IOC_READ, 'H', 0x04, 256)
HID_CAPACITY = 9000                # about 60 s of reports at the pad's ~140 Hz
CATEGORY_LIMIT = 20                # files kept per category
STORE_BUDGET = 64 * 1024 * 1024    # all saved recordings together
HID_CLOCK = ("CLOCK_MONOTONIC when touchpad-watch read the report; a few ms later "
             "than the kernel timestamp on the matching evdev frame")


def emit(record):
    print(json.dumps(record), flush=True)


def recording_time(path):
    try:
        return int(path.stem.rsplit("-", 1)[1])
    except (IndexError, ValueError):
        return 0


def prune_recordings(directory, keep):
    """Cap each category at CATEGORY_LIMIT files and the store at STORE_BUDGET bytes."""
    for category in ("candidate", "strip", "manual"):
        for old in sorted(directory.glob(f"touchpad-{category}-*.json"), key=recording_time)[:-CATEGORY_LIMIT]:
            if old != keep:
                old.unlink()
    files = []
    for path in directory.glob("touchpad-*.json"):
        try:
            files.append((path, path.stat().st_size))
        except OSError:
            continue
    total = sum(size for _, size in files)
    # Automatic captures go before user-marked incidents; oldest first within each.
    for path, size in sorted(files, key=lambda item: ("-manual-" in item[0].name, recording_time(item[0]))):
        if total <= STORE_BUDGET:
            break
        if path != keep:
            path.unlink()
            total -= size


class Recorder:
    def __init__(self, axes, directory):
        self.axes = axes
        self.directory = directory
        self.events = deque()
        self.seed_slots = {}
        self.seed_slot = 0
        self.seed_identity = None
        self.capacity_drop = float("-inf")
        self.hid = deque()
        self.hid_descriptors = {}
        self.hid_capacity_drop = float("-inf")

    def feed_hid(self, timestamp, identity, report):
        self.hid.append([timestamp, identity, report])
        while self.hid and (timestamp - self.hid[0][0] > 60 or len(self.hid) > HID_CAPACITY):
            if len(self.hid) > HID_CAPACITY:
                self.hid_capacity_drop = self.hid[0][0]
            self.hid.popleft()

    def discard_oldest(self):
        event = self.events.popleft()
        _, kind, code, value = event[:4]
        if len(event) >= 5 and event[4] != "touchpad":
            return
        identity = event[5] if len(event) >= 6 else None
        if identity != self.seed_identity or (kind, code) == (0, 3):
            self.seed_slots.clear()
            self.seed_slot = 0
            self.seed_identity = identity
        if kind == 3 and code == 47:
            self.seed_slot = value
        elif kind == 3 and code in (53, 54, 55, 57):
            self.seed_slots.setdefault(self.seed_slot, {})[code] = value

    def initial_events(self, timestamp):
        events = []
        for slot, values in sorted(self.seed_slots.items()):
            events.append([timestamp, 3, 47, slot])
            for code, value in sorted(values.items()):
                events.append([timestamp, 3, code, value])
        if events:
            events.extend([[timestamp, 3, 47, self.seed_slot], [timestamp, 0, 0, 0]])
        if self.seed_identity is not None:
            events = [event + ["touchpad", self.seed_identity] for event in events]
        return events

    def feed(self, event):
        self.events.append(event)
        while self.events and (event[0] - self.events[0][0] > 60 or len(self.events) > 50000):
            if len(self.events) > 50000:
                self.capacity_drop = self.events[0][0]
            self.discard_oldest()

    def save(self, timestamp, reason, detail=None):
        self.directory.mkdir(parents=True, exist_ok=True)
        while self.events and self.events[0][0] < timestamp - 60:
            self.discard_oldest()
        category = {"candidate_only": "candidate", "strip_candidate": "strip"}.get(reason, "manual")
        path = self.directory / f"touchpad-{category}-{time.time_ns()}.json"
        reports = [report for report in self.hid if timestamp - 60 <= report[0] <= timestamp]
        record = {"axes": self.axes, "reason": reason,
                  "window_start": self.events[0][0] if self.events else timestamp,
                  "truncated": self.capacity_drop >= timestamp - 60,
                  "initial_events": self.initial_events(timestamp - 60),
                  "markers": [timestamp], "events": [
            event for event in self.events if timestamp - 60 <= event[0] <= timestamp
        ], "hid": {"clock": HID_CLOCK, "capacity": HID_CAPACITY,
                   "truncated": self.hid_capacity_drop >= timestamp - 60,
                   "descriptors": {identity: descriptor for identity, descriptor in self.hid_descriptors.items()
                                   if any(report[1] == identity for report in reports)},
                   "reports": reports}}
        if detail is not None:
            record["detail"] = detail
        path.write_text(json.dumps(record, separators=(",", ":")))
        prune_recordings(self.directory, path)
        return {"event": "recording_saved", "path": str(path), "reason": reason}


class Detector:
    def __init__(self, axes):
        self.axes = axes
        self.slots = {}
        self.slot = 0
        self.dropped = False
        self.jumps = []
        self.last_request = float("-inf")
        self.requests = []
        self.last_frame = None
        self.suppress_until = float("-inf")
        self.new_contact = False
        self.identity = None

    def feed(self, event):
        timestamp, kind, code, value = event[:4]
        if len(event) >= 5 and event[4] != "touchpad":
            return []
        decisions = []
        if len(event) >= 6 and event[5] != self.identity:
            self.identity = event[5]
            self.slots.clear()
            self.slot = 0
            self.jumps.clear()
            self.dropped = False
            self.last_frame = None
            self.new_contact = False
            self.suppress_until = timestamp + 3
            decisions.append({"event": "device_changed", "time": timestamp,
                              "identity": self.identity})
        if any(self.axes[axis]["resolution"] <= 0 for axis in ("x", "y")):
            return decisions
        if (kind, code) == (0, 3):
            self.slots.clear()
            self.jumps.clear()
            self.dropped = True
            return decisions + [{"event": "events_lost", "time": timestamp}]
        if self.dropped:
            if (kind, code) == (0, 0):
                self.dropped = False
            return decisions
        if kind == 3 and code == 47:
            self.slot = value
        state = self.slots.setdefault(self.slot, {"position": {}, "id": None, "previous": None})
        if kind == 3 and code == 57:
            state["id"] = value if value >= 0 else None
            state["previous"] = None
            self.jumps.clear()
            self.new_contact = self.new_contact or value >= 0
        if kind == 3 and code in (53, 54):
            state["position"][code] = value
        if kind == 3 and code == 55:
            state["tool"] = value
        if (kind, code) != (0, 0):
            return decisions
        if self.last_frame is not None and timestamp - self.last_frame > 5 and not self.new_contact:
            self.suppress_until = timestamp + 3
            self.jumps.clear()
        self.last_frame = timestamp
        self.new_contact = False
        for slot, state in self.slots.items():
            position = state["position"]
            if len(position) != 2 or state["id"] is None:
                continue
            point = (position[53], position[54])
            if state["previous"]:
                old_time, old_point = state["previous"]
                elapsed = timestamp - old_time
                distance = math.hypot(
                    (point[0] - old_point[0]) / self.axes["x"]["resolution"],
                    (point[1] - old_point[1]) / self.axes["y"]["resolution"],
                )
                if (timestamp >= self.suppress_until and state.get("tool", 0) != 2 and 0 < elapsed <= 0.02
                        and distance >= 40 and distance / elapsed >= 2500):
                    decisions.append({"event": "touch_jump", "time": timestamp,
                                      "slot": slot, "distance_mm": distance})
                    self.jumps = [t for t in self.jumps if timestamp - t <= 0.2] + [timestamp]
                    if len(self.jumps) >= 2:
                        self.requests = [t for t in self.requests if timestamp - t < 3600]
                        if timestamp - self.last_request >= 120 and len(self.requests) < 3:
                            decisions.append({"event": "recovery_requested", "time": timestamp})
                            self.last_request = timestamp
                            self.requests.append(timestamp)
                        self.jumps.clear()
            state["previous"] = timestamp, point
        return decisions


class StripDetector:
    """Notice the dead-strip episode seen in the 2026-11 captures; it only reports.

    The firmware loses a lone moving finger at one side of a band and starts a
    new contact on the far side within tens of milliseconds. Several such
    restarts crossing the same band, with few reports inside it, is the
    signature. Short contacts, mid-stroke second contacts, the contact-start
    rate and the multi-contact share are reported as supporting evidence only:
    taps and two-finger scrolling look the same on a healthy pad.
    """
    WINDOW = 30.0
    RESTART_GAP = 0.06
    RESTART_MM = 8.0
    MIN_RESTARTS = 4
    MIN_OVERLAP = 3
    MAX_DENSITY = 0.5
    MIN_FLANK_REPORTS = 40
    COOLDOWN = 600.0
    HOURLY = 3

    def __init__(self, axes):
        self.axes = axes
        self.identity = None
        self.alerts = []
        self.clear()

    def clear(self):
        self.slot = 0
        self.slots = {}
        self.ended = []
        self.lone_end = None
        self.restarts = deque()
        self.points = deque()
        self.frames = deque()
        self.starts = deque()
        self.blips = deque()
        self.mids = deque()
        self.seconds = deque()
        self.last_touch_frame = None

    def feed(self, event):
        timestamp, kind, code, value = event[:4]
        if len(event) >= 5 and event[4] != "touchpad":
            return []
        decisions = []
        if len(event) >= 6 and event[5] != self.identity:
            self.identity = event[5]
            self.clear()
        resolution = (self.axes["x"]["resolution"], self.axes["y"]["resolution"])
        if min(resolution) <= 0:
            return decisions
        if (kind, code) == (0, 3):
            self.clear()
            return decisions
        if kind == 3 and code == 47:
            self.slot = value
            return decisions
        state = self.slots.setdefault(self.slot, {"id": None, 53: None, 54: None})
        if kind == 3 and code == 57:
            if state["id"] is not None:
                self.ended.append(dict(state))
            state.update(id=value if value >= 0 else None, new=value >= 0, frames=0, start=None)
        elif kind == 3 and code in (53, 54):
            state[code] = value
        if (kind, code) != (0, 0):
            return decisions
        return self.frame(timestamp, resolution)

    def frame(self, now, resolution):
        active = [state for state in self.slots.values()
                  if state["id"] is not None and state[53] is not None and state[54] is not None]
        continuing = [state for state in active if not state.get("new")]
        for gone in self.ended:
            if gone.get("frames", 0) and gone["frames"] <= 2:
                self.blips.append((now,))
            if not continuing and gone[53] is not None and gone[54] is not None:
                self.lone_end = (now, gone[53], gone[54])
        self.ended = []
        for state in active:
            if not state.get("new"):
                continue
            state["new"] = False
            state["start"] = now
            self.starts.append((now,))
            if len(active) == 1 and self.lone_end and now - self.lone_end[0] <= self.RESTART_GAP:
                dx = (state[53] - self.lone_end[1]) / resolution[0]
                dy = (state[54] - self.lone_end[2]) / resolution[1]
                if math.hypot(dx, dy) >= self.RESTART_MM:
                    axis, code, index = ("x", 53, 1) if abs(dx) >= abs(dy) else ("y", 54, 2)
                    ends = sorted((self.lone_end[index], state[code]))
                    self.restarts.append((now, axis, ends[0], ends[1]))
            elif len(active) > 1 and any(other is not state and other.get("start") is not None
                                         and now - other["start"] >= 0.2 for other in active):
                self.mids.append((now,))
            self.lone_end = None
        for state in active:
            state["frames"] = state.get("frames", 0) + 1
        if active:
            if self.last_touch_frame is not None:
                self.seconds.append((now, min(now - self.last_touch_frame, 0.02)))
            self.last_touch_frame = now
            self.frames.append((now, len(active)))
            if len(active) == 1:
                self.points.append((now, active[0][53], active[0][54]))
        else:
            self.last_touch_frame = None
        for queue in (self.restarts, self.points, self.frames, self.starts, self.blips, self.mids,
                      self.seconds):
            while queue and now - queue[0][0] > self.WINDOW:
                queue.popleft()
        return self.evaluate(now, resolution)

    def evaluate(self, now, resolution):
        if len(self.restarts) < self.MIN_RESTARTS:
            return []
        best = None
        for axis in ("x", "y"):
            spans = [(low, high) for _, name, low, high in self.restarts if name == axis]
            for edge in sorted({low for low, _ in spans}):
                covering = [(low, high) for low, high in spans if low <= edge <= high]
                if best is None or len(covering) > len(best[1]):
                    best = (axis, covering)
        axis, covering = best
        if len(covering) < self.MIN_OVERLAP:
            return []
        low, high = max(span[0] for span in covering), min(span[1] for span in covering)
        index = 1 if axis == "x" else 2
        width = max(high - low, 1)
        inside = sum(low < point[index] < high for point in self.points)
        flanks = sum(low - width <= point[index] <= low or high <= point[index] <= high + width
                     for point in self.points)
        density = (inside / width) / (flanks / (2 * width)) if flanks else None
        if flanks >= self.MIN_FLANK_REPORTS and density > self.MAX_DENSITY:
            return []
        self.alerts = [moment for moment in self.alerts if now - moment < 3600]
        if (self.alerts and now - self.alerts[-1] < self.COOLDOWN) or len(self.alerts) >= self.HOURLY:
            return []
        self.alerts.append(now)
        touched = sum(seconds for _, seconds in self.seconds)
        scale = resolution[0 if axis == "x" else 1]
        return [{
            "event": "dead_strip_suspected", "time": now, "axis": axis,
            "band": [low, high], "band_mm": [round(low / scale, 1), round(high / scale, 1)],
            "restarts": sum(1 for item in self.restarts if item[1] == axis),
            "restarts_across_band": len(covering), "window_s": self.WINDOW,
            "density_ratio": None if density is None else round(density, 2),
            "contact_starts_per_touch_second": round(len(self.starts) / touched, 2) if touched else None,
            "multi_contact_fraction": round(sum(count > 1 for _, count in self.frames) / len(self.frames), 3)
            if self.frames else None,
            "short_contacts": len(self.blips),
            "mid_stroke_second_contacts": len(self.mids),
            "advice": "Mark it with fixtouchpad --mark. A hands-off recalibration "
                      "(Ctrl+Alt+Shift+F12) may help, but has not been shown to move this band.",
        }]


class HealthMeter:
    """Per-minute touchpad health aggregates for the persistent log; never raw coordinates.

    A minute starts at the first touched frame and is taken after 60 s, or
    earlier when the charger, calibration or device state changes.
    """
    MINUTE = 60.0
    TAP_SECONDS = 0.18
    TAP_UNITS = 100
    RESTART_GAP = 0.1
    RESTART_UNITS = 150
    FROZEN_FRAMES = 10
    FROZEN_UNITS = 150
    FRAME_CAP = 0.02
    BAND_WINDOW = 120.0   # touched seconds of single-contact frames behind the band score
    BAND_BIN = 100
    BAND_MIN_FRAMES = 1500
    BAND_MIN_FLANK = 30
    LATE_SECOND = 0.2
    COUNTERS = ("touched_frames", "contact_starts", "multi_contact_frames", "late_second_contacts",
                "tap_like_contacts", "fast_drop_restarts", "frozen_x_runs", "frozen_y_runs")

    def __init__(self):
        self.identity = None
        self.minute = None
        self.window = deque()
        self.clock = 0.0
        self.reset_contacts()

    def reset_contacts(self):
        self.slot = 0
        self.slots = {}
        self.ended = []
        self.lone_end = None
        self.last_frame = None

    def recalibrated(self):
        """Forget contacts and the band histogram: a new firmware baseline may differ."""
        self.reset_contacts()
        self.window.clear()

    def feed(self, event):
        timestamp, kind, code, value = event[:4]
        if len(event) >= 5 and event[4] != "touchpad":
            return
        if len(event) >= 6 and event[5] != self.identity:
            if self.identity is not None:
                self.recalibrated()
            self.identity = event[5]
        if (kind, code) == (0, 3):
            self.reset_contacts()
        elif kind == 3 and code == 47:
            self.slot = value
        elif kind == 3 and code == 57:
            state = self.slots.setdefault(self.slot, {"id": None, 53: None, 54: None})
            if state["id"] is not None:
                self.ended.append(dict(state))
            state.update(id=value if value >= 0 else None, new=value >= 0)
        elif kind == 3 and code in (53, 54):
            self.slots.setdefault(self.slot, {"id": None, 53: None, 54: None})[code] = value
        elif (kind, code) == (0, 0):
            self.frame(timestamp)

    def finish_runs(self, state):
        for axis in ("x", "y"):
            run = state.get("run_" + axis)
            if run and run[1] >= self.FROZEN_FRAMES and run[3] - run[2] >= self.FROZEN_UNITS:
                self.minute["frozen_%s_runs" % axis] += 1

    def frame(self, now):
        active = [state for state in self.slots.values()
                  if state["id"] is not None and state[53] is not None and state[54] is not None]
        if self.minute is None and (active or self.ended):
            self.minute = dict.fromkeys(self.COUNTERS, 0) | {"start": now, "touched_seconds": 0.0}
        continuing = [state for state in active if not state.get("new")]
        for gone in self.ended:
            if gone.get("start") is None:
                continue
            self.finish_runs(gone)
            if now - gone["start"] < self.TAP_SECONDS and gone["reach"] < self.TAP_UNITS:
                self.minute["tap_like_contacts"] += 1
            if not continuing:
                self.lone_end = (now, gone[53], gone[54])
        self.ended = []
        for state in active:
            if state.get("new"):
                state.update(new=False, start=now, origin=(state[53], state[54]), reach=0,
                             run_x=None, run_y=None)
                self.minute["contact_starts"] += 1
                if any(other.get("start") is not None and now - other["start"] >= self.LATE_SECOND
                       for other in continuing):
                    self.minute["late_second_contacts"] += 1
                if (len(active) == 1 and self.lone_end and now - self.lone_end[0] <= self.RESTART_GAP
                        and math.hypot(state[53] - self.lone_end[1], state[54] - self.lone_end[2])
                        >= self.RESTART_UNITS):
                    self.minute["fast_drop_restarts"] += 1
                self.lone_end = None
            x, y = state[53], state[54]
            state["reach"] = max(state["reach"], math.hypot(x - state["origin"][0], y - state["origin"][1]))
            for axis, value, other in (("x", x, y), ("y", y, x)):
                run = state.get("run_" + axis)
                if run and run[0] == value:
                    run[1] += 1
                    run[2], run[3] = min(run[2], other), max(run[3], other)
                else:
                    if run:
                        self.finish_runs({"run_" + axis: run})
                    state["run_" + axis] = [value, 1, other, other]
        if not active:
            self.last_frame = None
            return
        step = min(now - self.last_frame, self.FRAME_CAP) if self.last_frame is not None else 0.0
        self.last_frame = now
        self.minute["touched_seconds"] += step
        self.minute["touched_frames"] += 1
        self.minute["multi_contact_frames"] += len(active) > 1
        if len(active) == 1:
            self.clock += step
            self.window.append((self.clock, active[0][53] // self.BAND_BIN, active[0][54] // self.BAND_BIN))
            while self.window and self.clock - self.window[0][0] > self.BAND_WINDOW:
                self.window.popleft()

    def band(self, index):
        """Sparse-band score (0 even .. 1 empty) and centre of the emptiest bin between busy flanks."""
        if len(self.window) < self.BAND_MIN_FRAMES:
            return None, None
        counts = {}
        for entry in self.window:
            counts[entry[index]] = counts.get(entry[index], 0) + 1
        worst = None
        for centre in range(min(counts) + 3, max(counts) - 2):
            flanks = [counts.get(centre + offset, 0) for offset in (-3, -2, 2, 3)]
            if min(flanks) < self.BAND_MIN_FLANK:
                continue
            ratio = counts.get(centre, 0) / (sum(flanks) / 4)
            if worst is None or ratio < worst[0]:
                worst = (ratio, centre)
        if worst is None:
            return None, None
        return round(max(0.0, 1 - worst[0]), 2), worst[1] * self.BAND_BIN + self.BAND_BIN // 2

    def take(self, now, force=False):
        """Return the finished minute's aggregates, or None if not due or untouched."""
        if self.minute is None or (not force and now - self.minute["start"] < self.MINUTE):
            return None
        minute, self.minute = self.minute, None
        if not minute["touched_frames"]:
            return None
        start = minute.pop("start")
        minute["duration_s"] = round(now - start, 1)
        minute["touched_seconds"] = round(minute["touched_seconds"], 2)
        minute["sparse_x_score"], minute["sparse_x_at"] = self.band(1)
        minute["sparse_y_score"], minute["sparse_y_at"] = self.band(2)
        return minute


class HidContacts:
    """Decode ELAN input report 0x54 into the evdev-style frames HealthMeter reads.

    Health is measured from hidraw because touchpad-filter's EVIOCGRAB hides
    the evdev stream; hidraw always carries the firmware's raw contacts. The
    slot and tracking-ID rules follow hid-multitouch and input-mt: the first
    `contact count` entries are valid, a contact keeps its slot while its
    Contact ID stays active, Tip 0 or absence ends it, and contacts are
    released 100 ms after the last report (MT_QUIRK_STICKY_FINGERS). Frame
    times follow the report's scan time (100 us units), anchored to the read
    time, so reads that bunch up do not distort gaps.
    """
    REPORT_ID = 0x54
    SIZE = 29
    SLOTS = 5
    STICKY = 0.1
    ANCHOR_GAP = 1.0

    def __init__(self, identity=None):
        self.identity = identity
        self.slots = [None] * self.SLOTS     # (contact id, tracking id) per active slot
        self.next_id = 0
        self.last = None                     # (read time, scan time, frame time)

    def frame_time(self, read_time, scan):
        if self.last is None or read_time - self.last[0] > self.ANCHOR_GAP:
            return read_time
        moment = self.last[2] + ((scan - self.last[1]) & 0xFFFF) / 10000
        # Never ahead of the read, never far behind it.
        return read_time if moment > read_time or read_time - moment > 0.5 else moment

    def event(self, moment, code, value):
        return [moment, 3, code, value, "touchpad", self.identity]

    def release_all(self, moment):
        events = []
        for slot, held in enumerate(self.slots):
            if held is not None:
                events += [self.event(moment, 47, slot), self.event(moment, 57, -1)]
                self.slots[slot] = None
        return events + [[moment, 0, 0, 0, "touchpad", self.identity]] if events else []

    def feed(self, read_time, report):
        if len(report) < self.SIZE or report[0] != self.REPORT_ID:
            return []
        events = []
        scan = report[2] | report[3] << 8
        if self.last is not None and any(self.slots):
            # Reads can bunch up; the scan clock shows the gap the kernel's timer saw.
            gap = (float("inf") if read_time - self.last[0] > self.ANCHOR_GAP
                   else ((scan - self.last[1]) & 0xFFFF) / 10000)
            if gap > self.STICKY:
                events += self.release_all(self.last[2] + self.STICKY)
        moment = self.frame_time(read_time, scan)
        self.last = (read_time, scan, moment)
        used = set()
        for index in range(min(report[1] >> 4, self.SLOTS)):
            flags, x, y = struct.unpack_from("<BHH", report, 4 + 5 * index)
            contact, tip = flags >> 4, flags & 2
            slot = next((number for number, held in enumerate(self.slots)
                         if held is not None and held[0] == contact), None)
            if slot is None and tip:
                slot = next((number for number, held in enumerate(self.slots)
                             if held is None and number not in used), None)
            if slot is None:
                continue
            used.add(slot)
            if not tip:
                self.slots[slot] = None
                events += [self.event(moment, 47, slot), self.event(moment, 57, -1)]
                continue
            events.append(self.event(moment, 47, slot))
            if self.slots[slot] is None:
                self.slots[slot] = (contact, self.next_id)
                events.append(self.event(moment, 57, self.next_id))
                self.next_id = (self.next_id + 1) & 0xFFFF
            events += [self.event(moment, 53, x), self.event(moment, 54, y)]
        for slot, held in enumerate(self.slots):
            if held is not None and slot not in used:
                self.slots[slot] = None
                events += [self.event(moment, 47, slot), self.event(moment, 57, -1)]
        return events + [[moment, 0, 0, 0, "touchpad", self.identity]]


def hid_reports(trace):
    """(time, bytes) for every HID report in a touchpad-watch recording or converted capture."""
    hid = trace.get("hid") or {}
    rows = [(row[0], row[-1]) for row in hid.get("reports", [])] + [
        (row[0], row[-1]) for row in trace.get("hid_reports", [])]
    return [(moment, bytes.fromhex(data)) for moment, data in sorted(rows, key=lambda row: row[0])]


FILTER_STATUS = Path("/run/touchpad-filter/status.json")


class FilterState:
    """Per-minute touchpad-filter fields from its status file; counts are deltas between minute lines."""
    STALE = 15.0
    POLL = 2.0

    def __init__(self, path=FILTER_STATUS):
        self.path = path
        self.base = None
        self.seen = False
        self.next_poll = 0.0

    def read(self, now):
        try:
            data = json.loads(self.path.read_text())
            stats = data.get("stats") or {}
            counts = (data["instance"], int(stats.get("bridged_drops", 0)), int(stats.get("suppressed_ghosts", 0)))
            active = data.get("state") == "active" and now - float(data["mono"]) < self.STALE
            return active, counts
        except (OSError, ValueError, KeyError, TypeError):
            return False, None

    def poll(self, now):
        if now < self.next_poll:
            return
        self.next_poll = now + self.POLL
        active, counts = self.read(now)
        self.seen = self.seen or active
        if self.base is None and counts is not None:
            self.base = counts

    def fields(self, now):
        active, counts = self.read(now)
        bridged = suppressed = 0
        if counts is not None:
            base = self.base if self.base is not None and self.base[0] == counts[0] else (counts[0], 0, 0)
            bridged, suppressed = max(0, counts[1] - base[1]), max(0, counts[2] - base[2])
            self.base = counts
        on, self.seen = self.seen or active, active
        return {"filter_on": on, "bridged_drops": bridged, "suppressed_ghosts": suppressed}


UPOWER_STATES = {0: "unknown", 1: "charging", 2: "discharging", 3: "empty",
                 4: "fully-charged", 5: "pending-charge", 6: "pending-discharge"}
# UPower's cached properties over the system bus. Never read /sys/class/power_supply:
# ACPI battery reads have hung this laptop.
POWER_COMMAND = ["/bin/sh", "-c",
                 "busctl --system --json=short --timeout=2 get-property org.freedesktop.UPower "
                 "/org/freedesktop/UPower org.freedesktop.UPower OnBattery && "
                 "busctl --system --json=short --timeout=2 get-property org.freedesktop.UPower "
                 "/org/freedesktop/UPower/devices/DisplayDevice org.freedesktop.UPower.Device "
                 "State Percentage EnergyRate"]
POWER_KEY = "upower"
NO_POWER = {"ac_online": None, "battery_state": None, "battery_pct": None, "energy_rate_w": None}


def find_cpu_temperature(root=Path("/sys/class/thermal")):
    """The x86_pkg_temp zone is read from a CPU MSR; ACPI zones are avoided on purpose."""
    for zone in sorted(root.glob("thermal_zone*")):
        try:
            if (zone / "type").read_text().strip() == "x86_pkg_temp":
                return zone / "temp"
        except OSError:
            continue
    return None


class PowerPoller:
    """Poll UPower in a child process whose output arrives through the selector; never blocks."""
    PERIOD = 10.0
    TIMEOUT = 5.0

    def __init__(self, selector, command=POWER_COMMAND):
        self.selector = selector
        self.command = command
        self.process = None
        self.output = bytearray()
        self.started = None
        self.next_poll = 0.0
        self.snapshot = dict(NO_POWER, power_error="not polled yet")
        self.previous = self.snapshot
        self.snapshot_started = None
        self.snapshot_done = None

    def start(self, now):
        if self.process is not None or now < self.next_poll:
            return None
        self.next_poll = now + self.PERIOD
        self.started = now
        self.output.clear()
        try:
            self.process = subprocess.Popen(self.command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                            stderr=subprocess.DEVNULL, close_fds=True)
        except OSError as error:
            return self.finish(now, str(error))
        os.set_blocking(self.process.stdout.fileno(), False)
        self.selector.register(self.process.stdout, selectors.EVENT_READ, POWER_KEY)
        return None

    def readable(self, now):
        try:
            data = os.read(self.process.stdout.fileno(), 4096)
        except BlockingIOError:
            return None
        if data:
            self.output.extend(data)
            return None
        return self.finish(now)

    def expire(self, now):
        if self.process is not None and now - self.started > self.TIMEOUT:
            return self.finish(now, "timeout")
        return None

    def finish(self, now, error=None):
        """Store the new snapshot and return it; values are null when UPower did not answer."""
        if self.process is not None:
            self.selector.unregister(self.process.stdout)
            self.process.stdout.close()
            if error:
                self.process.kill()
            try:
                status = self.process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                status = None
            if not error and status:
                error = f"exit status {status}"
            self.process = None
        snapshot = dict(NO_POWER)
        if not error:
            try:
                values = [json.loads(line)["data"] for line in self.output.decode().splitlines() if line]
                on_battery, state, percent, rate = values
                snapshot = {"ac_online": not on_battery, "battery_state": UPOWER_STATES.get(state, str(state)),
                            "battery_pct": round(percent, 1), "energy_rate_w": round(rate, 2)}
            except (ValueError, KeyError, TypeError):
                error = "unreadable UPower reply"
        if error:
            snapshot["power_error"] = error
        self.previous = self.snapshot
        self.snapshot, self.snapshot_started, self.snapshot_done = snapshot, self.started, now
        return snapshot


class HealthLog:
    """Append-only JSON lines, world-readable, rotated by size: at most 3 x LIMIT bytes."""
    LIMIT = 20 * 1024 * 1024
    KEEP = 2

    def __init__(self, directory):
        self.path = directory / "health.jsonl"
        self.failed = False

    def write(self, record):
        line = (json.dumps(record, separators=(",", ":")) + "\n").encode()
        try:
            if self.path.exists() and self.path.stat().st_size + len(line) > self.LIMIT:
                for index in range(self.KEEP, 0, -1):
                    source = self.path.with_name(f"{self.path.name}.{index - 1}") if index > 1 else self.path
                    if source.exists():
                        source.replace(self.path.with_name(f"{self.path.name}.{index}"))
            fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_CLOEXEC, 0o644)
            try:
                os.fchmod(fd, 0o644)
                os.write(fd, line)
            finally:
                os.close(fd)
            self.failed = False
        except OSError as error:
            if not self.failed:
                emit({"event": "health_log_failed", "error": str(error)})
            self.failed = True


class HealthMonitor:
    """Tie the per-minute meter to charger state and calibration context for health.jsonl.

    Calibration context is the moment the firmware may have taken a new
    baseline: a driver rebind (new HID device) or a resume from suspend,
    detected as a jump of CLOCK_BOOTTIME against CLOCK_MONOTONIC. The charger
    state recorded for that moment is the first UPower poll started at least
    SETTLE seconds afterwards (UPower may be stale right after resume),
    otherwise the last state known before it.
    """
    SETTLE = 2.0
    SETTLE_LIMIT = 30.0
    RESUME_GAP = 1.0

    def __init__(self, selector, directory, command=POWER_COMMAND, boot_id=None, temperature=None,
                 wall=time.time, filter_status=FILTER_STATUS):
        self.poller = PowerPoller(selector, command)
        self.log = HealthLog(directory)
        self.meter = HealthMeter()
        self.contacts = None
        self.source = "evdev"
        self.filter = FilterState(filter_status)
        self.boot_id = boot_id
        self.temperature = temperature
        self.wall = wall
        self.hid = None
        self.events = {}
        self.offset = None
        self.power_key = None
        self.started = False

    def record(self, kind, now, power=None, **extra):
        power = power or self.poller.snapshot
        record = {"ts": round(self.wall(), 3), "kind": kind, "boot_id": self.boot_id, "hid": self.hid}
        record.update(power)
        record["power_age_s"] = (round(now - self.poller.snapshot_done, 1)
                                 if self.poller.snapshot_done is not None else None)
        latest = max(self.events.values(), key=lambda item: item["mono"], default=None)
        record["calibration_kind"] = latest["kind"] if latest else "unknown"
        record["seconds_since_calibration"] = round(now - latest["mono"], 1) if latest else None
        for name, event in (("calibration", latest), ("rebind", self.events.get("rebind")),
                            ("resume", self.events.get("resume"))):
            state = (event["settled"] or event["power"]) if event else NO_POWER
            record[f"{name}_ts"] = event["ts"] if event else None
            for field in ("ac_online", "battery_state", "battery_pct"):
                record[f"{name}_{field}"] = state.get(field)
        record["cpu_pkg_temp_c"] = self.read_temperature()
        record.update(extra)
        self.log.write(record)

    def read_temperature(self):
        try:
            return round(int(self.temperature.read_text()) / 1000, 1) if self.temperature else None
        except (OSError, ValueError):
            return None

    def flush(self, now, force=False, power=None):
        minute = self.meter.take(now, force)
        if minute:
            self.record("minute", now, power, health_source=self.source, **minute, **self.filter.fields(now))

    def calibration_event(self, kind, now, **extra):
        self.flush(now, force=True)
        self.meter.recalibrated()
        self.events[kind] = {"kind": kind, "mono": now, "ts": round(self.wall(), 3),
                             "power": dict(self.poller.snapshot), "settled": None}
        self.record(kind, now, **extra)
        self.poller.next_poll = min(self.poller.next_poll, now + self.SETTLE + 0.5)

    def device(self, hid, now):
        if hid == self.hid:
            return
        previous, self.hid = self.hid, hid
        if previous is not None:
            self.calibration_event("rebind", now, previous_hid=previous)

    def feed(self, event):
        self.meter.feed(event)

    def feed_hid(self, read_time, identity, report):
        """Raw firmware contacts; unlike evdev, unaffected by touchpad-filter's grab."""
        if self.contacts is None or self.contacts.identity != identity:
            self.contacts = HidContacts(identity)
        self.source = "hid"
        for event in self.contacts.feed(read_time, report):
            self.meter.feed(event)

    def power_readable(self, now):
        snapshot = self.poller.readable(now)
        if snapshot is not None:
            self.power_done(now, snapshot)

    def power_done(self, now, snapshot):
        for event in self.events.values():
            if (event["settled"] is None
                    and event["mono"] + self.SETTLE <= self.poller.snapshot_started <= event["mono"] + self.SETTLE_LIMIT
                    and snapshot["ac_online"] is not None):
                event["settled"] = dict(snapshot)
        key = (snapshot["ac_online"], snapshot["battery_state"])
        if not self.started:
            self.started = True
            self.power_key = key if None not in key else None
            self.record("service_start", now)
            return
        if None in key:
            return
        if self.power_key is not None and key != self.power_key:
            previous = self.power_key
            self.power_key = key
            # The minute so far ran under the old state; label it with that.
            self.flush(now, force=True, power=self.poller.previous)
            self.record("power_change", now, previous_ac_online=previous[0],
                        previous_battery_state=previous[1])
        self.power_key = key

    def tick(self, now, boottime):
        offset = boottime - now
        if self.offset is not None and offset - self.offset > self.RESUME_GAP:
            self.calibration_event("resume", now, suspended_s=round(offset - self.offset, 1))
        self.offset = offset
        snapshot = self.poller.expire(now) or self.poller.start(now)
        if snapshot is not None:
            self.power_done(now, snapshot)
        self.filter.poll(now)
        self.flush(now)


def open_input(path, expected_name):
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        name = bytearray(256)
        fcntl.ioctl(fd, 0x81004506, name)
        identity = bytearray(8)
        fcntl.ioctl(fd, 0x80084502, identity)
        if (name.split(b"\0", 1)[0].decode() != expected_name
                or struct.unpack("HHHH", identity)[:3] != (0x18, 0x04F3, 0x31EC)):
            raise ValueError("Input device identity does not match this ELAN device")
        fcntl.ioctl(fd, 0x400445A0, struct.pack("i", time.CLOCK_MONOTONIC))
        axes = {}
        if NAMES[expected_name] == "touchpad":
            for axis, code in (("x", 53), ("y", 54)):
                info = bytearray(24)
                fcntl.ioctl(fd, 0x80184540 + code, info)
                _, minimum, maximum, fuzz, flat, resolution = struct.unpack("6i", info)
                axes[axis] = dict(minimum=minimum, maximum=maximum, resolution=resolution,
                                  fuzz=fuzz, flat=flat)
        return fd, axes
    except BaseException:
        os.close(fd)
        raise


def open_hidraw(path):
    """Open the ELAN hidraw node read-only after checking bus, IDs and name; never writes."""
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        info = bytearray(8)
        fcntl.ioctl(fd, HIDIOCGRAWINFO, info)
        name = bytearray(256)
        fcntl.ioctl(fd, HIDIOCGRAWNAME, name)
        bus, vendor, product = struct.unpack("Ihh", info)
        if ((bus, vendor & 0xFFFF, product & 0xFFFF) != (0x18, 0x04F3, 0x31EC)
                or not name.split(b"\0", 1)[0].decode(errors="replace").startswith(HID_NAME)):
            raise ValueError("hidraw identity does not match this ELAN device")
        return fd
    except BaseException:
        os.close(fd)
        raise


def discover(device=DEVICE):
    """Map each ELAN evdev and hidraw sysfs node to (device path, source, input name)."""
    found = {}
    for name_path in device.glob("*/input/input*/name"):
        try:
            name = name_path.read_text().strip()
            if name not in NAMES:
                continue
            for node in name_path.parent.glob("event*"):
                found[str(node.resolve())] = (Path("/dev/input") / node.name, NAMES[name], name)
        except OSError:
            continue
    for node in device.glob("*/hidraw/hidraw*"):
        found[str(node.resolve())] = (Path("/dev") / node.name, "hid", HID_NAME)
    return found


def stream_identity(key, source):
    node = Path(key)
    if source == "hid":
        return f"{node.parent.parent.name}|{node.name}"
    return f"{node.parent.parent.parent.name}|{node.parent.name}"


def read_marker(path):
    with path.open() as handle:
        token = handle.read(64).strip()
    return token if len(token) == 32 and all(char in "0123456789abcdef" for char in token) else ""


def write_atomic(path, record):
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(record))
    temporary.replace(path)


def save_in_child(recorder, timestamp, reason, selector, runtime, marker=None, detail=None):
    pid = os.fork()
    if pid:
        return pid
    try:
        for key in list(selector.get_map().values()):
            os.close(key.fd)
        selector.close()
        saved = recorder.save(timestamp, reason, detail)
        if marker is not None:
            saved["marker"] = marker
            write_atomic(runtime / "last-marker", saved)
        emit(saved)
    except Exception as error:
        emit({"event": "recording_failed", "error": str(error)})
        os._exit(1)
    os._exit(0)


def watch(directory=Path("/var/lib/touchpad-watch"), runtime=Path("/run/touchpad-watch"),
          logs=Path("/var/log/touchpad-watch"), device=DEVICE, require_root=True):
    """The service loop. The path arguments exist only for an unprivileged smoke test."""
    if require_root and os.geteuid() != 0:
        raise SystemExit("Raw input recording needs the installed root touchpad-watch service.")
    runtime.mkdir(mode=0o750, parents=True, exist_ok=True)
    marker_path = runtime / "mark"
    marker_path.touch(mode=0o660, exist_ok=True)
    marker_path.chmod(0o660)
    last_marker = read_marker(marker_path)
    selector = selectors.DefaultSelector()
    streams = {}
    axes = {"x": {"resolution": 0}, "y": {"resolution": 0}}
    recorder = Recorder(axes, directory)
    detectors = [Detector(axes), StripDetector(axes)]
    try:
        logs.mkdir(mode=0o755, exist_ok=True)
        boot_id = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    except OSError as error:
        emit({"event": "health_log_failed", "error": str(error)})
        boot_id = None
    monitor = HealthMonitor(selector, logs, boot_id=boot_id, temperature=find_cpu_temperature())
    next_discovery = 0
    writer_pid = None
    emit({"event": "started", "automatic_reset": False})

    health_errors = set()

    def health(action, *args):
        # The health log must never stop the incident recorder, or flood the journal.
        try:
            action(*args)
        except Exception as error:
            text = f"{type(error).__name__}: {error}"
            if text not in health_errors and len(health_errors) < 50:
                health_errors.add(text)
                emit({"event": "health_error", "error": text})

    def drop(key, error):
        fd = streams.pop(key)[0]
        selector.unregister(fd)
        os.close(fd)
        emit({"event": "read_failed", "identity": key, "error": str(error)})

    def save(timestamp, reason, detail=None):
        nonlocal writer_pid
        if writer_pid is None:
            writer_pid = save_in_child(recorder, timestamp, reason, selector, runtime, detail=detail)
        else:
            emit({"event": "recording_busy", "time": timestamp})

    while True:
        now = time.monotonic()
        if writer_pid is not None and os.waitpid(writer_pid, os.WNOHANG)[0]:
            writer_pid = None
        health(monitor.tick, now, time.clock_gettime(time.CLOCK_BOOTTIME))
        if now >= next_discovery:
            next_discovery = now + 2
            found = discover(device)
            for key in list(streams):
                if key not in found:
                    fd = streams.pop(key)[0]
                    selector.unregister(fd)
                    os.close(fd)
                    emit({"event": "disconnected", "identity": key})
            for key, (path, source, name) in found.items():
                if key in streams:
                    continue
                device_axes = {}
                try:
                    if source == "hid":
                        # Read the descriptor first so a failure cannot leak an open fd.
                        descriptor = (Path(key).parent.parent / "report_descriptor").read_bytes().hex()
                        fd = open_hidraw(path)
                        recorder.hid_descriptors[stream_identity(key, source)] = descriptor
                    else:
                        fd, device_axes = open_input(path, name)
                except (OSError, ValueError) as error:
                    emit({"event": "open_failed", "path": str(path), "error": str(error)})
                    continue
                streams[key] = (fd, source, bytearray())
                selector.register(fd, selectors.EVENT_READ, key)
                if source in ("touchpad", "hid"):
                    health(monitor.device, stream_identity(key, source).split("|")[0], now)
                if device_axes:
                    axes = device_axes
                    recorder.axes = axes
                    for detector in detectors:
                        detector.axes = axes
                emit({"event": "connected", "source": source, "identity": key, "axes": device_axes})
            write_atomic(runtime / "status", {"sources": sorted(value[1] for value in streams.values()),
                                              "automatic_reset": False, "time": now})
        for selected, _ in selector.select(timeout=0.2):
            key = selected.data
            if key == POWER_KEY:
                health(monitor.power_readable, time.monotonic())
                continue
            if key not in streams:
                continue
            fd, source, pending = streams[key]
            identity = stream_identity(key, source)
            if source == "hid":
                # One report per read; drain so the kernel's 64-report queue never fills.
                try:
                    for _ in range(256):
                        report = os.read(fd, 4096)
                        if not report:
                            raise OSError("HID stream closed")
                        read_time = time.monotonic()
                        recorder.feed_hid(read_time, identity, report.hex())
                        health(monitor.feed_hid, read_time, identity, report)
                except BlockingIOError:
                    pass
                except OSError as error:
                    drop(key, error)
                    next_discovery = 0
                continue
            try:
                data = os.read(fd, INPUT_EVENT.size * 256)
                if not data:
                    raise OSError("Input stream closed")
            except BlockingIOError:
                continue
            except OSError as error:
                drop(key, error)
                next_discovery = 0
                continue
            pending.extend(data)
            complete = len(pending) // INPUT_EVENT.size * INPUT_EVENT.size
            for second, microsecond, kind, code, value in INPUT_EVENT.iter_unpack(pending[:complete]):
                timestamp = second + microsecond / 1_000_000
                event = [timestamp, kind, code, value, source, identity]
                recorder.feed(event)
                for detector in detectors:
                    for decision in detector.feed(event):
                        decision["automatic_reset"] = False
                        emit(decision)
                        if decision["event"] == "recovery_requested":
                            save(timestamp, "candidate_only")
                        elif decision["event"] == "dead_strip_suspected":
                            write_atomic(runtime / "alert", dict(decision, wall_time=time.time()))
                            save(timestamp, "strip_candidate", decision)
            del pending[:complete]
        marker = read_marker(marker_path)
        if marker and marker != last_marker and writer_pid is None:
            last_marker = marker
            writer_pid = save_in_child(recorder, time.monotonic(), "manual_incident", selector, runtime, marker)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--replay", type=Path)
    mode.add_argument("--watch", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--health", action="store_true",
                        help="with --replay: print per-minute health aggregates instead of detector events")
    parser.add_argument("--hid", action="store_true",
                        help="with --health: measure from the recording's raw HID reports, as the service does")
    args = parser.parse_args()
    if args.watch:
        if args.output_dir:
            parser.error("--output-dir is only for replay")
        watch()
        return
    trace = json.loads(args.replay.read_text())
    if args.health:
        meter = HealthMeter()
        events = trace.get("initial_events", []) + trace["events"]
        if args.hid:
            decoder = HidContacts("replay")
            events = [event for moment, report in hid_reports(trace) for event in decoder.feed(moment, report)]
        for event in events:
            meter.feed(event)
            minute = meter.take(event[0]) if event[1:3] == [0, 0] else None
            if minute:
                print(json.dumps(dict(minute, event="health")))
        if events:
            minute = meter.take(events[-1][0], force=True)
            if minute:
                print(json.dumps(dict(minute, event="health")))
        return
    detectors = [Detector(trace["axes"]), StripDetector(trace["axes"])]
    for event in trace.get("initial_events", []):
        for detector in detectors:
            detector.feed(event)
    recorder = Recorder(trace["axes"], args.output_dir) if args.output_dir else None
    hid = trace.get("hid") or {}
    reports = deque(sorted(hid.get("reports", []), key=lambda report: report[0]))
    if recorder:
        recorder.hid_descriptors.update(hid.get("descriptors", {}))
    markers = iter(sorted(trace.get("markers", [])))
    marker = next(markers, None)
    reason = trace.get("reason", "manual_incident")

    def feed_reports(until):
        while recorder and reports and reports[0][0] <= until:
            recorder.feed_hid(*reports.popleft())

    for event in trace["events"]:
        while recorder and marker is not None and marker < event[0]:
            feed_reports(marker)
            print(json.dumps(recorder.save(marker, reason)))
            marker = next(markers, None)
        feed_reports(event[0])
        if recorder:
            recorder.feed(event)
        for detector in detectors:
            for decision in detector.feed(event):
                print(json.dumps(decision))
    while recorder and marker is not None:
        feed_reports(marker)
        print(json.dumps(recorder.save(marker, reason)))
        marker = next(markers, None)
    print(json.dumps({"event": "replay_complete", "frames": sum(
        event[1:3] == [0, 0] for event in trace["events"]
    )}))


if __name__ == "__main__":
    main()
