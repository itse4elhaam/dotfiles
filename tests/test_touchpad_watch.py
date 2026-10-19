import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]


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


if __name__ == "__main__":
    unittest.main()
