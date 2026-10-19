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
import time

DEVICE = Path("/sys/bus/i2c/devices/i2c-ELAN07AC:00")
NAMES = {"ELAN07AC:00 04F3:31EC Touchpad": "touchpad",
         "ELAN07AC:00 04F3:31EC Mouse": "mouse"}
INPUT_EVENT = struct.Struct("@llHHi")


def emit(record):
    print(json.dumps(record), flush=True)


class Recorder:
    def __init__(self, axes, directory):
        self.axes = axes
        self.directory = directory
        self.events = deque()
        self.seed_slots = {}
        self.seed_slot = 0
        self.seed_identity = None
        self.capacity_drop = float("-inf")

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

    def save(self, timestamp, reason):
        self.directory.mkdir(parents=True, exist_ok=True)
        while self.events and self.events[0][0] < timestamp - 60:
            self.discard_oldest()
        category = "candidate" if reason == "candidate_only" else "manual"
        path = self.directory / f"touchpad-{category}-{time.time_ns()}.json"
        path.write_text(json.dumps({"axes": self.axes, "reason": reason,
                                   "window_start": self.events[0][0] if self.events else timestamp,
                                   "truncated": self.capacity_drop >= timestamp - 60,
                                   "initial_events": self.initial_events(timestamp - 60),
                                   "markers": [timestamp], "events": [
            event for event in self.events if timestamp - 60 <= event[0] <= timestamp
        ]}))
        for old in sorted(self.directory.glob(f"touchpad-{category}-*.json"))[:-20]:
            old.unlink()
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


def read_marker(path):
    with path.open() as handle:
        token = handle.read(64).strip()
    return token if len(token) == 32 and all(char in "0123456789abcdef" for char in token) else ""


def save_in_child(recorder, timestamp, reason, selector, runtime, marker=None):
    pid = os.fork()
    if pid:
        return pid
    try:
        for key in list(selector.get_map().values()):
            os.close(key.fd)
        selector.close()
        saved = recorder.save(timestamp, reason)
        if marker is not None:
            saved["marker"] = marker
            temporary = runtime / "last-marker.tmp"
            temporary.write_text(json.dumps(saved))
            temporary.replace(runtime / "last-marker")
        emit(saved)
    except Exception as error:
        emit({"event": "recording_failed", "error": str(error)})
        os._exit(1)
    os._exit(0)


def watch():
    if os.geteuid() != 0:
        raise SystemExit("Raw input recording needs the installed root touchpad-watch service.")
    directory = Path("/var/lib/touchpad-watch")
    runtime = Path("/run/touchpad-watch")
    runtime.mkdir(mode=0o750, parents=True, exist_ok=True)
    marker_path = runtime / "mark"
    marker_path.touch(mode=0o660, exist_ok=True)
    marker_path.chmod(0o660)
    last_marker = read_marker(marker_path)
    selector = selectors.DefaultSelector()
    streams = {}
    axes = {"x": {"resolution": 0}, "y": {"resolution": 0}}
    recorder = Recorder(axes, directory)
    detector = Detector(axes)
    next_discovery = 0
    writer_pid = None
    emit({"event": "started", "automatic_reset": False})
    while True:
        now = time.monotonic()
        if writer_pid is not None and os.waitpid(writer_pid, os.WNOHANG)[0]:
            writer_pid = None
        if now >= next_discovery:
            next_discovery = now + 2
            found = {}
            for name_path in DEVICE.glob("*/input/input*/name"):
                try:
                    name = name_path.read_text().strip()
                    if name not in NAMES:
                        continue
                    for node in name_path.parent.glob("event*"):
                        found[str(node.resolve())] = (Path("/dev/input") / node.name, name)
                except OSError:
                    continue
            for key in list(streams):
                if key not in found:
                    fd, _, _ = streams.pop(key)
                    selector.unregister(fd)
                    os.close(fd)
                    emit({"event": "disconnected", "identity": key})
            for key, (path, name) in found.items():
                if key in streams:
                    continue
                try:
                    fd, device_axes = open_input(path, name)
                except (OSError, ValueError) as error:
                    emit({"event": "open_failed", "path": str(path), "error": str(error)})
                    continue
                streams[key] = (fd, NAMES[name], bytearray())
                selector.register(fd, selectors.EVENT_READ, key)
                if device_axes:
                    axes = device_axes
                    recorder.axes = axes
                    detector.axes = axes
                emit({"event": "connected", "source": NAMES[name], "identity": key,
                      "axes": device_axes})
            status = runtime / "status.tmp"
            status.write_text(json.dumps({"sources": sorted(value[1] for value in streams.values()),
                                          "automatic_reset": False, "time": now}))
            status.replace(runtime / "status")
        for selected, _ in selector.select(timeout=0.2):
            key = selected.data
            fd, source, pending = streams[key]
            try:
                data = os.read(fd, INPUT_EVENT.size * 256)
                if not data:
                    raise OSError("Input stream closed")
            except BlockingIOError:
                continue
            except OSError as error:
                selector.unregister(fd)
                os.close(fd)
                streams.pop(key)
                emit({"event": "read_failed", "identity": key, "error": str(error)})
                next_discovery = 0
                continue
            pending.extend(data)
            complete = len(pending) // INPUT_EVENT.size * INPUT_EVENT.size
            for second, microsecond, kind, code, value in INPUT_EVENT.iter_unpack(pending[:complete]):
                timestamp = second + microsecond / 1_000_000
                node = Path(key)
                identity = f"{node.parent.parent.parent.name}|{node.parent.name}"
                event = [timestamp, kind, code, value, source, identity]
                recorder.feed(event)
                decisions = detector.feed(event)
                for decision in decisions:
                    decision["automatic_reset"] = False
                    emit(decision)
                    if decision["event"] == "recovery_requested":
                        if writer_pid is None:
                            writer_pid = save_in_child(recorder, timestamp, "candidate_only", selector, runtime)
                        else:
                            emit({"event": "recording_busy", "time": timestamp})
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
    args = parser.parse_args()
    if args.watch:
        if args.output_dir:
            parser.error("--output-dir is only for replay")
        watch()
        return
    trace = json.loads(args.replay.read_text())
    detector = Detector(trace["axes"])
    for event in trace.get("initial_events", []):
        detector.feed(event)
    recorder = Recorder(trace["axes"], args.output_dir) if args.output_dir else None
    markers = iter(sorted(trace.get("markers", [])))
    marker = next(markers, None)
    reason = trace.get("reason", "manual_incident")
    for event in trace["events"]:
        while recorder and marker is not None and marker < event[0]:
            print(json.dumps(recorder.save(marker, reason)))
            marker = next(markers, None)
        if recorder:
            recorder.feed(event)
        for decision in detector.feed(event):
            print(json.dumps(decision))
    while recorder and marker is not None:
        print(json.dumps(recorder.save(marker, reason)))
        marker = next(markers, None)
    print(json.dumps({"event": "replay_complete", "frames": sum(
        event[1:3] == [0, 0] for event in trace["events"]
    )}))


if __name__ == "__main__":
    main()
