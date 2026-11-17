import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("touchpad_watch", REPO / "scripts/touchpad-watch.py")
watch = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(watch)
AXES = {"x": {"resolution": 32}, "y": {"resolution": 31}}


def replay_trace(trace, output_dir=None):
    with tempfile.TemporaryDirectory(prefix="touchpad-replay-") as directory:
        recording = Path(directory) / "trace.json"
        recording.write_text(json.dumps(trace))
        command = [sys.executable, str(REPO / "scripts/touchpad-watch.py"), "--replay", str(recording)]
        if output_dir:
            command += ["--output-dir", str(output_dir)]
        result = subprocess.run(command, capture_output=True, text=True, timeout=20)
    if result.returncode:
        raise AssertionError(result.stderr)
    return [json.loads(line) for line in result.stdout.splitlines()]


def contact(start, tracking_id, xs, y, slot=0, step=0.007):
    """One finger: tracking ID, a frame per x position, then lift."""
    events = [[start, 3, 47, slot], [start, 3, 57, tracking_id]]
    for index, x in enumerate(xs):
        moment = round(start + index * step, 6)
        if index:
            events.append([moment, 3, 47, slot])
        events += [[moment, 3, 53, x], [moment, 3, 54, y], [moment, 0, 0, 0]]
    end = round(start + len(xs) * step, 6)
    return events + [[end, 3, 47, slot], [end, 3, 57, -1], [end, 0, 0, 0]], end


def strokes(count, dead=None, rest=None, start=0.0):
    """Side-to-side single-finger strokes from x=900 to x=2600; `dead` drops a band."""
    events, moment, tracking_id = [], start, 100
    for number in range(count):
        xs = list(range(900, 2601, 50))
        if number % 2:
            xs.reverse()
        y = 1000 + 60 * number
        if dead:
            low_side = [x for x in xs if x < dead[0]]
            high_side = [x for x in xs if x > dead[1]]
            before, after = (low_side, high_side) if xs[0] < xs[-1] else (high_side, low_side)
            part, moment = contact(moment, tracking_id, before, y)
            events += part
            part, moment = contact(moment + 0.014, tracking_id + 1, after, y)
        else:
            part, moment = contact(moment, tracking_id, xs, y)
        events += part
        tracking_id += 2
        moment += 0.4
    if rest:
        events = [[start - 1, 3, 47, 1], [start - 1, 3, 57, 9], [start - 1, 3, 53, rest[0]],
                  [start - 1, 3, 54, rest[1]], [start - 1, 0, 0, 0]] + events
    return sorted(events, key=lambda event: event[0])


class ReplayTests(unittest.TestCase):
    def replay(self, events):
        with tempfile.TemporaryDirectory(prefix="touchpad-replay-") as directory:
            recording = Path(directory) / "events.json"
            recording.write_text(json.dumps({
                "device": "ELAN07AC:00 04F3:31EC Touchpad",
                "axes": {"x": {"resolution": 31}, "y": {"resolution": 31}},
                "events": events,
            }))
            result = subprocess.run(
                [sys.executable, str(REPO / "scripts/touchpad-watch.py"),
                 "--replay", str(recording)],
                capture_output=True, text=True, timeout=5,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            return [json.loads(line) for line in result.stdout.splitlines()]

    def test_normal_single_finger_movement_does_not_request_a_reset(self):
        events = [
            [0, 3, 47, 0], [0, 3, 57, 11],
            [0, 3, 53, 1000], [0, 3, 54, 1000], [0, 0, 0, 0],
            [0.01, 3, 53, 1010], [0.01, 3, 54, 1010], [0.01, 0, 0, 0],
            [0.02, 3, 53, 1020], [0.02, 3, 54, 1020], [0.02, 0, 0, 0],
        ]
        self.assertFalse(any(item["event"] == "recovery_requested" for item in self.replay(events)))

    def test_repeated_large_jumps_of_same_finger_request_recovery(self):
        events = [
            [0, 3, 47, 0], [0, 3, 57, 11],
            [0, 3, 53, 1000], [0, 3, 54, 1000], [0, 0, 0, 0],
            [0.01, 3, 53, 3000], [0.01, 0, 0, 0],
            [0.02, 3, 53, 1000], [0.02, 0, 0, 0],
        ]
        requests = [item for item in self.replay(events) if item["event"] == "recovery_requested"]
        self.assertEqual(len(requests), 1)

    def test_new_fingers_at_distant_positions_are_not_jumps(self):
        events = [
            [0, 3, 47, 0], [0, 3, 57, 11],
            [0, 3, 53, 1000], [0, 3, 54, 1000], [0, 0, 0, 0],
            [0.01, 3, 57, 12], [0.01, 3, 53, 3000], [0.01, 0, 0, 0],
            [0.02, 3, 57, 13], [0.02, 3, 53, 1000], [0.02, 0, 0, 0],
        ]
        self.assertFalse(any(item["event"] == "touch_jump" for item in self.replay(events)))

    def test_two_fingers_in_separate_slots_keep_independent_positions(self):
        events = [
            [0, 3, 47, 0], [0, 3, 57, 11], [0, 3, 53, 1000], [0, 3, 54, 1000],
            [0, 3, 47, 1], [0, 3, 57, 12], [0, 3, 53, 3000], [0, 3, 54, 1000], [0, 0, 0, 0],
            [0.01, 3, 47, 0], [0.01, 3, 53, 1010], [0.01, 0, 0, 0],
            [0.02, 3, 47, 1], [0.02, 3, 53, 3010], [0.02, 0, 0, 0],
        ]
        self.assertFalse(any(item["event"] == "touch_jump" for item in self.replay(events)))

    def test_palm_contacts_are_not_classified_as_faulty_finger_motion(self):
        events = [
            [0, 3, 47, 0], [0, 3, 57, 11], [0, 3, 55, 2],
            [0, 3, 53, 1000], [0, 3, 54, 1000], [0, 0, 0, 0],
            [0.01, 3, 53, 3000], [0.01, 0, 0, 0],
            [0.02, 3, 53, 1000], [0.02, 0, 0, 0],
        ]
        self.assertFalse(any(item["event"] == "touch_jump" for item in self.replay(events)))

    def test_lost_events_require_a_new_contact_before_detection_resumes(self):
        events = [
            [0, 3, 47, 0], [0, 3, 57, 11],
            [0, 3, 53, 1000], [0, 3, 54, 1000], [0, 0, 0, 0],
            [0.005, 0, 3, 0],
            [0.01, 3, 53, 3000], [0.01, 0, 0, 0],
            [0.02, 3, 53, 1000], [0.02, 0, 0, 0],
        ]
        self.assertFalse(any(item["event"] == "touch_jump" for item in self.replay(events)))

    def test_recovery_requests_have_a_two_minute_cooldown(self):
        events = []
        for start in (0, 60):
            events.extend([
                [start, 3, 47, 0], [start, 3, 57, 11],
                [start, 3, 53, 1000], [start, 3, 54, 1000], [start, 0, 0, 0],
                [start + 0.01, 3, 53, 3000], [start + 0.01, 0, 0, 0],
                [start + 0.02, 3, 53, 1000], [start + 0.02, 0, 0, 0],
            ])
        requests = [item for item in self.replay(events) if item["event"] == "recovery_requested"]
        self.assertEqual(len(requests), 1)

    def test_recovery_requests_are_limited_to_three_per_hour(self):
        events = []
        for start in (0, 121, 242, 363):
            events.extend([
                [start, 3, 47, 0], [start, 3, 57, 11],
                [start, 3, 53, 1000], [start, 3, 54, 1000], [start, 0, 0, 0],
                [start + 0.01, 3, 53, 3000], [start + 0.01, 0, 0, 0],
                [start + 0.02, 3, 53, 1000], [start + 0.02, 0, 0, 0],
            ])
        requests = [item for item in self.replay(events) if item["event"] == "recovery_requested"]
        self.assertEqual(len(requests), 3)

    def test_secondary_mouse_frames_do_not_change_touchpad_timing(self):
        events = [
            [0, 3, 47, 0], [0, 3, 57, 11], [0, 3, 53, 1000], [0, 3, 54, 1000], [0, 0, 0, 0],
            [0.02, 0, 0, 0, "mouse"],
            [0.03, 3, 53, 3000], [0.03, 0, 0, 0],
            [0.05, 0, 0, 0, "mouse"],
            [0.06, 3, 53, 1000], [0.06, 0, 0, 0],
        ]
        self.assertFalse(any(item["event"] == "touch_jump" for item in self.replay(events)))

    def test_marked_recording_keeps_preceding_minute_and_both_input_sources(self):
        with tempfile.TemporaryDirectory(prefix="touchpad-window-") as directory:
            recording = Path(directory) / "trace.json"
            recording.write_text(json.dumps({
                "axes": {"x": {"resolution": 31}, "y": {"resolution": 31}},
                "events": [[1, 0, 0, 0, "touchpad"], [10, 0, 0, 0, "mouse"],
                           [65, 0, 0, 0, "touchpad"]],
                "markers": [65],
            }))
            result = subprocess.run(
                [sys.executable, str(REPO / "scripts/touchpad-watch.py"),
                 "--replay", str(recording), "--output-dir", directory],
                capture_output=True, text=True, timeout=5,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            saves = [json.loads(line) for line in result.stdout.splitlines()
                     if json.loads(line)["event"] == "recording_saved"]
            self.assertEqual(len(saves), 1)
            saved = json.loads(Path(saves[0]["path"]).read_text())
            self.assertEqual(saved["events"], [[10, 0, 0, 0, "mouse"], [65, 0, 0, 0, "touchpad"]])

    def test_unknown_resolution_records_without_guessing_physical_distance(self):
        with tempfile.TemporaryDirectory() as directory:
            trace = Path(directory) / "trace.json"
            trace.write_text(json.dumps({"axes": {"x": {"resolution": 0}, "y": {"resolution": 0}},
                "events": [[0, 3, 57, 1], [0, 3, 53, 1000], [0, 3, 54, 1000],
                           [0, 0, 0, 0], [0.01, 3, 53, 3000], [0.01, 0, 0, 0]]}))
            result = subprocess.run([sys.executable, str(REPO / "scripts/touchpad-watch.py"),
                                     "--replay", str(trace)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn('"event": "touch_jump"', result.stdout)

    def test_resume_gap_suppresses_stale_contact_jumps_for_three_seconds(self):
        events = [[0, 3, 57, 1], [0, 3, 53, 1000], [0, 3, 54, 1000], [0, 0, 0, 0],
                  [60, 0, 0, 0], [60.01, 3, 53, 3000], [60.01, 0, 0, 0],
                  [60.02, 3, 53, 1000], [60.02, 0, 0, 0]]
        self.assertFalse(any(item["event"] == "touch_jump" for item in self.replay(events)))

    def test_saved_window_replays_a_contact_that_started_before_the_window(self):
        with tempfile.TemporaryDirectory() as directory:
            trace = Path(directory) / "trace.json"
            trace.write_text(json.dumps({
                "axes": {"x": {"resolution": 31}, "y": {"resolution": 31}},
                "events": [[0, 3, 57, 1], [0, 3, 53, 1000], [0, 3, 54, 1000], [0, 0, 0, 0],
                           [10, 0, 0, 0], [65, 0, 0, 0], [68, 0, 0, 0],
                           [68.01, 3, 53, 3000], [68.01, 0, 0, 0],
                           [68.02, 3, 53, 1000], [68.02, 0, 0, 0]], "markers": [68.02]}))
            command = [sys.executable, str(REPO / "scripts/touchpad-watch.py"), "--replay"]
            saved = subprocess.run(command + [str(trace), "--output-dir", directory],
                                   capture_output=True, text=True, check=True)
            path = next(json.loads(line)["path"] for line in saved.stdout.splitlines()
                        if json.loads(line)["event"] == "recording_saved")
            replayed = subprocess.run(command + [path], capture_output=True, text=True, check=True)
            self.assertIn('"event": "recovery_requested"', replayed.stdout)

    def test_reconnection_does_not_clear_the_recovery_cooldown(self):
        events = []
        for start, identity in ((0, 'old-device'), (10, 'new-device')):
            burst = [[start, 3, 57, 1], [start, 3, 53, 1000], [start, 3, 54, 1000], [start, 0, 0, 0],
                     [start + 4, 0, 0, 0], [start + 4.01, 3, 53, 3000], [start + 4.01, 0, 0, 0],
                     [start + 4.02, 3, 53, 1000], [start + 4.02, 0, 0, 0]]
            events.extend(event + ['touchpad', identity] for event in burst)
        decisions = self.replay(events)
        self.assertEqual(sum(item['event'] == 'device_changed' for item in decisions), 2)
        self.assertEqual(sum(item['event'] == 'recovery_requested' for item in decisions), 1)

    def test_capacity_limited_recording_reports_that_the_window_was_truncated(self):
        with tempfile.TemporaryDirectory() as directory:
            trace = Path(directory) / "trace.json"
            trace.write_text(json.dumps({
                "axes": {"x": {"resolution": 31}, "y": {"resolution": 31}},
                "events": [[100, 0, 0, 0, 'mouse']] * 50100, "markers": [100]}))
            result = subprocess.run([sys.executable, str(REPO / 'scripts/touchpad-watch.py'),
                                     '--replay', str(trace), '--output-dir', directory],
                                    capture_output=True, text=True, check=True)
            path = next(json.loads(line)['path'] for line in result.stdout.splitlines()
                        if json.loads(line)['event'] == 'recording_saved')
            saved = json.loads(Path(path).read_text())
            self.assertTrue(saved['truncated'])
            self.assertEqual(saved['window_start'], 100)
            self.assertEqual(len(saved['events']), 50000)

    def test_candidate_rotation_preserves_manual_incident_recordings(self):
        with tempfile.TemporaryDirectory() as directory:
            trace = Path(directory) / 'trace.json'
            command = [sys.executable, str(REPO / 'scripts/touchpad-watch.py'),
                       '--replay', str(trace), '--output-dir', directory]
            data = {'axes': {'x': {'resolution': 31}, 'y': {'resolution': 31}},
                    'events': [[100, 0, 0, 0]], 'markers': [100], 'reason': 'manual_incident'}
            trace.write_text(json.dumps(data))
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            manual = next(json.loads(line)['path'] for line in result.stdout.splitlines()
                          if json.loads(line)['event'] == 'recording_saved')
            data.update(reason='candidate_only', markers=[100] * 21)
            trace.write_text(json.dumps(data))
            subprocess.run(command, capture_output=True, text=True, check=True)
            self.assertTrue(Path(manual).exists())


class HidRingTests(unittest.TestCase):
    IDENTITY = "0018:04F3:31EC.002A|hidraw0"

    def test_marked_recording_keeps_hid_reports_from_the_same_minute(self):
        with tempfile.TemporaryDirectory() as directory:
            reports = [[2, self.IDENTITY, "5400"], [10, self.IDENTITY, "5401"],
                       [64, self.IDENTITY, "5402"], [66, self.IDENTITY, "54ff"]]
            output = replay_trace({"axes": AXES, "markers": [65],
                                   "events": [[1, 0, 0, 0, "touchpad"], [65, 0, 0, 0, "touchpad"]],
                                   "hid": {"descriptors": {self.IDENTITY: "05010902"}, "reports": reports}},
                                  directory)
            path = next(item["path"] for item in output if item["event"] == "recording_saved")
            saved = json.loads(Path(path).read_text())
            self.assertEqual(saved["hid"]["reports"], reports[1:3])
            self.assertEqual(saved["hid"]["descriptors"], {self.IDENTITY: "05010902"})
            self.assertFalse(saved["hid"]["truncated"])

    def test_hid_capacity_limit_is_reported_as_truncation(self):
        with tempfile.TemporaryDirectory() as directory:
            recorder = watch.Recorder(AXES, Path(directory))
            for index in range(watch.HID_CAPACITY + 100):
                recorder.feed_hid(index / 1000, self.IDENTITY, "54")
            saved = json.loads(Path(recorder.save(10, "manual_incident")["path"]).read_text())
            self.assertTrue(saved["hid"]["truncated"])
            self.assertEqual(len(saved["hid"]["reports"]), watch.HID_CAPACITY)

    def test_discovery_finds_evdev_and_hidraw_nodes_of_the_elan_device_only(self):
        with tempfile.TemporaryDirectory() as directory:
            device = Path(directory) / "i2c-ELAN07AC:00"
            hid = device / "0018:04F3:31EC.002A"
            for number, name in ((134, "Mouse"), (136, "Touchpad")):
                node = hid / f"input/input{number}"
                (node / f"event{number - 130}").mkdir(parents=True)
                (node / "name").write_text(f"ELAN07AC:00 04F3:31EC {name}\n")
            (hid / "input/input137/event9").mkdir(parents=True)
            (hid / "input/input137/name").write_text("Some other device\n")
            (hid / "hidraw/hidraw0").mkdir(parents=True)
            found = watch.discover(device)
            self.assertEqual(sorted(source for _, source, _ in found.values()), ["hid", "mouse", "touchpad"])
            key = next(key for key, value in found.items() if value[1] == "hid")
            self.assertEqual(found[key][0], Path("/dev/hidraw0"))
            self.assertEqual(watch.stream_identity(key, "hid"), self.IDENTITY)


class RetentionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.directory = Path(temp.name)
        self.budget = watch.STORE_BUDGET
        self.addCleanup(setattr, watch, "STORE_BUDGET", self.budget)

    def make(self, category, stamp, size):
        path = self.directory / f"touchpad-{category}-{stamp}.json"
        path.write_bytes(b"x" * size)
        return path

    def test_store_budget_removes_automatic_captures_before_marked_incidents(self):
        manual = self.make("manual", 1, 400)
        candidate = self.make("candidate", 2, 400)
        strip = self.make("strip", 3, 400)
        newest = self.make("manual", 4, 400)
        watch.STORE_BUDGET = 1300
        watch.prune_recordings(self.directory, newest)
        self.assertFalse(candidate.exists())
        self.assertTrue(manual.exists() and strip.exists() and newest.exists())

    def test_store_budget_never_removes_the_recording_just_saved(self):
        newest = self.make("strip", 9, 5000)
        watch.STORE_BUDGET = 100
        watch.prune_recordings(self.directory, newest)
        self.assertTrue(newest.exists())

    def test_strip_candidates_rotate_without_touching_jump_candidates(self):
        jump = self.make("candidate", 1, 10)
        strips = [self.make("strip", stamp, 10) for stamp in range(2, 24)]
        watch.prune_recordings(self.directory, strips[-1])
        self.assertTrue(jump.exists())
        self.assertEqual(sorted(self.directory.glob("touchpad-strip-*.json")), sorted(strips[-20:]))


class StripDetectorTests(unittest.TestCase):
    def alerts(self, events):
        return [item for item in replay_trace({"axes": AXES, "events": events})
                if item["event"] == "dead_strip_suspected"]

    def test_finger_lost_and_restarted_across_one_band_is_flagged(self):
        alerts = self.alerts(strokes(6, dead=(1600, 1900)))
        self.assertEqual(len(alerts), 1)
        alert = alerts[0]
        self.assertEqual(alert["axis"], "x")
        self.assertLessEqual(alert["band"][0], 1600)
        self.assertGreaterEqual(alert["band"][1], 1900)
        self.assertLess(alert["density_ratio"], 0.5)
        self.assertFalse(alert.get("automatic_reset", False))

    def test_continuous_strokes_and_separate_taps_are_not_flagged(self):
        events = strokes(6)
        moment = events[-1][0] + 0.5
        for index in range(20):
            tap, _ = contact(moment, 500 + index, [700 + 120 * index] * 6, 1200 + 40 * index)
            events += tap
            moment += 0.25
        self.assertEqual(self.alerts(events), [])

    def test_restarts_while_another_finger_rests_are_not_counted(self):
        self.assertEqual(self.alerts(strokes(6, dead=(1600, 1900), rest=(3000, 2200))), [])

    def test_alerts_have_a_ten_minute_cooldown(self):
        events = strokes(6, dead=(1600, 1900)) + strokes(6, dead=(1600, 1900), start=120)
        self.assertEqual(len(self.alerts(events)), 1)

    def test_reports_inside_the_band_veto_the_alert(self):
        events, moment = [], 0.0
        for index in range(8):
            dwell, moment = contact(moment, 700 + index, list(range(1650, 1851, 5)), 1500)
            events += dwell
            moment += 0.3
        events += strokes(6, dead=(1600, 1900), start=moment + 1)
        self.assertEqual(self.alerts(events), [])


class AlertNotifierTests(unittest.TestCase):
    def test_each_alert_is_shown_once_with_the_band_and_the_hands_off_advice(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "notify-send").write_text('#!/bin/sh\nprintf "%s|" "$@" >> "$CALLS"; echo >> "$CALLS"\n')
            (root / "notify-send").chmod(0o755)
            alert = root / "alert"
            alert.write_text(json.dumps({"axis": "x", "band_mm": [28.6, 38.9], "restarts_across_band": 4,
                                         "window_s": 30.0, "wall_time": 1794430000.5}))
            env = dict(os.environ, PATH=f"{root}:/usr/bin:/bin", CALLS=str(root / "calls"))
            command = [sys.executable, "-I", str(REPO / "scripts/touchpad-alert"),
                       "--alert", str(alert), "--state", str(root / "last")]
            for _ in range(2):
                subprocess.run(command, env=env, check=True, timeout=5)
            calls = (root / "calls").read_text().splitlines()
            self.assertEqual(len(calls), 1)
            self.assertIn("between 28.6 and 38.9 mm from the left edge", calls[0])
            self.assertIn("Ctrl+Alt+Shift+F12", calls[0])


if __name__ == "__main__":
    unittest.main()
