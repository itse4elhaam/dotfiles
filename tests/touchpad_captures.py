"""Load the labelled 2026-11-11 captures (libinput record --with-hidraw) for replay tests.

The recordings are private and live outside the repo; tests that need them
skip when they are absent. Set TOUCHPAD_CAPTURES to another captures folder.
"""
import os
from pathlib import Path
import re
import unittest

CAPTURES = Path(os.environ.get("TOUCHPAD_CAPTURES",
                               Path.home() / ".local/state/touchpad-investigation/2026-11-05/captures"))
# docs/touchpad-investigation/2026-11-11-hid-capture.md
CAPTURE_DIRS = {"A": "incident-_b94gx60", "B": "incident-27ttjtf9", "C": "incident-nch2tt7q",
                "D": "incident-skpyyyt0"}
EVDEV = re.compile(r"- \[\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(-?\d+)\]")
TIME = re.compile(r"time: \[\s*(\d+),\s*(\d+)\]")
_cache = {}


def load_capture(name):
    """{"axes", "events": [[t, type, code, value]], "hid_reports": [[t, hex]]}, or skip the test."""
    if name in _cache:
        return _cache[name]
    path = CAPTURES / CAPTURE_DIRS[name] / "hid-evdev.yml"
    if not path.exists():
        raise unittest.SkipTest(f"capture {name} not found under {CAPTURES} (set TOUCHPAD_CAPTURES)")
    events, reports, report, moment, mode, started = [], [], None, None, None, False
    with path.open() as handle:
        for line in handle:
            text = line.strip()
            if not started:
                started = text == "events:"
                continue
            if text.startswith("- hid:") or text.startswith("- evdev:"):
                if report:
                    reports.append([moment, bytes(report).hex()])
                report, mode = ([], "hid") if text.startswith("- hid:") else (None, "evdev")
                continue
            if mode == "hid":
                match = TIME.search(text)
                if match:
                    moment = int(match[1]) + int(match[2]) / 1e6
                elif not text.startswith("hidraw"):
                    report.extend(int(value, 16) for value in re.findall(r"0x([0-9a-f]{2})", text))
            elif mode == "evdev":
                match = EVDEV.search(text)
                if match:
                    second, micro, kind, code, value = map(int, match.groups())
                    events.append([second + micro / 1e6, kind, code, value])
    if report:
        reports.append([moment, bytes(report).hex()])
    trace = {"axes": {"x": {"resolution": 32}, "y": {"resolution": 31}}, "events": events,
             "hid_reports": reports}
    _cache[name] = trace
    return trace
