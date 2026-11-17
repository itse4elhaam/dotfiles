import datetime as dt
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]


def load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


notify = load("touchpad_notify", REPO / "scripts/touchpad-notify")
report = load("touchpad_health_report", REPO / "scripts/touchpad-health-report")

DAY = dt.datetime(2026, 11, 12)
BATTERY = lambda percent: {"on_battery": True, "state": "discharging", "percent": percent}
PLUGGED = {"on_battery": False, "state": "pending-charge", "percent": 96.0}


def at(hour, minute=0):
    return DAY.replace(hour=hour, minute=minute)


def minute_line(ts, late, seconds=30.0):
    return {"kind": "minute", "ts": ts, "touched_seconds": seconds, "late_second_contacts": late,
            "touched_frames": 4000, "multi_contact_frames": 0, "tap_like_contacts": 0,
            "fast_drop_restarts": 0}


class OutageGuardTests(unittest.TestCase):
    def setUp(self):
        self.planner = notify.Planner(notify.Settings())

    def titles(self, now, power, lines=()):
        return [note[2] for note in self.planner.step(now, power, list(lines))]

    def test_nags_on_battery_before_the_outage_every_15_minutes(self):
        self.assertEqual(self.titles(at(18, 10), BATTERY(80)), ["Plug in: power outage at 7 pm"])
        self.assertEqual(self.titles(at(18, 20), BATTERY(79)), [])
        self.assertEqual(self.titles(at(18, 26), BATTERY(78)), ["Plug in: power outage at 7 pm"])

    def test_silent_when_plugged_in_and_rearms_after_unplugging(self):
        self.assertEqual(self.titles(at(18, 5), BATTERY(90)), ["Plug in: power outage at 7 pm"])
        self.assertEqual(self.titles(at(18, 7), PLUGGED), [])
        self.assertEqual(self.titles(at(18, 9), BATTERY(90)), ["Plug in: power outage at 7 pm"])

    def test_no_plug_in_nags_during_the_outage(self):
        self.assertEqual(self.titles(at(19, 30), BATTERY(40)), [])
        self.assertEqual(self.titles(at(20, 59), BATTERY(20)), [])

    def test_low_battery_reminder_outside_the_outage(self):
        self.assertEqual(self.titles(at(14), BATTERY(60)), [])
        self.assertEqual(self.titles(at(14, 1), BATTERY(50)), ["Battery at 50%: plug in"])
        self.assertEqual(self.titles(at(14, 10), BATTERY(48)), [])
        self.assertEqual(self.titles(at(14, 21), BATTERY(45)), ["Battery at 45%: plug in"])
        self.assertEqual(self.titles(at(21, 30), BATTERY(30)), ["Battery at 30%: plug in"])

    def test_unknown_power_state_never_notifies(self):
        self.assertEqual(self.titles(at(18, 30), dict(notify.NO_POWER)), [])

    def test_settings_override_times(self):
        planner = notify.Planner(notify.Settings({"prep_start": "16:30", "outage_start": "17:00",
                                                  "outage_end": "19:00"}))
        notes = planner.step(at(16, 45), BATTERY(80), [])
        self.assertEqual([note[2] for note in notes], ["Plug in: power outage at 5 pm"])
        self.assertIn("5 pm to 7 pm", notes[0][3])


class GhostAlertTests(unittest.TestCase):
    def setUp(self):
        self.planner = notify.Planner(notify.Settings())
        self.base = at(14).timestamp()

    def test_two_ghost_minutes_while_plugged_in_advise_unplugging(self):
        self.assertEqual(self.planner.step(at(14, 1), PLUGGED, [minute_line(self.base, 4)]), [])
        notes = self.planner.step(at(14, 2), PLUGGED, [minute_line(self.base + 60, 3)])
        self.assertEqual(notes[0][2], "Touchpad is ghosting")
        self.assertIn("Unplug the charger", notes[0][3])

    def test_evening_and_battery_advise_recalibration(self):
        evening = at(18, 30).timestamp()
        notes = self.planner.step(at(18, 32), PLUGGED,
                                  [minute_line(evening, 4), minute_line(evening + 60, 4)])
        self.assertIn("Ctrl+Alt+Shift+F12", notes[0][3])
        self.assertNotIn("Unplug", notes[0][3])
        planner = notify.Planner(notify.Settings())
        notes = planner.step(at(14, 2), BATTERY(80), [minute_line(self.base, 4), minute_line(self.base + 60, 4)])
        self.assertNotIn("Unplug", [n for n in notes if n[2] == "Touchpad is ghosting"][0][3])

    def test_single_or_distant_ghost_minutes_and_healthy_use_stay_silent(self):
        lines = [minute_line(self.base, 4), minute_line(self.base + 600, 4),
                 minute_line(self.base + 660, 0), minute_line(self.base + 720, 1)]
        self.assertEqual(self.planner.step(at(14, 13), PLUGGED, lines), [])

    def test_cooldown_limits_ghost_alerts_to_one_per_30_minutes(self):
        pair = lambda start: [minute_line(start, 4), minute_line(start + 60, 4)]
        self.assertEqual(len(self.planner.step(at(14, 2), PLUGGED, pair(self.base))), 1)
        self.assertEqual(self.planner.step(at(14, 12), PLUGGED, pair(self.base + 600)), [])
        self.assertEqual(len(self.planner.step(at(14, 33), PLUGGED, pair(self.base + 1900))), 1)

    def test_ghost_rule_matches_the_health_report(self):
        samples = [minute_line(0, late, seconds) for late in (0, 1, 2, 3, 6)
                   for seconds in (4.0, 6.0, 20.0, 30.0, 60.0)]
        for line in samples:
            verdict = report.classify(line)
            self.assertEqual(notify.is_ghost(line), bool(verdict and verdict[1]), line)


class PlumbingTests(unittest.TestCase):
    def test_follower_reads_new_lines_and_survives_rotation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "health.jsonl"
            path.write_text(json.dumps({"kind": "old"}) + "\n")
            follower = notify.Follower(path)
            self.assertEqual(follower.read(), [])
            with path.open("a") as handle:
                handle.write(json.dumps({"kind": "minute", "n": 1}) + "\n" + '{"kind": "min')
            self.assertEqual(follower.read(), [{"kind": "minute", "n": 1}])
            with path.open("a") as handle:
                handle.write('ute", "n": 2}\n')
            self.assertEqual(follower.read(), [{"kind": "minute", "n": 2}])
            path.rename(Path(directory) / "health.jsonl.1")
            path.write_text(json.dumps({"kind": "minute", "n": 3}) + "\n")
            self.assertEqual(follower.read(), [{"kind": "minute", "n": 3}])

    def test_read_power_parses_busctl_and_degrades_to_unknown(self):
        outputs = iter(['{"type":"b","data":true}\n',
                        '{"type":"u","data":2}\n{"type":"d","data":9.1e+01}\n'])
        fake = lambda *a, **k: subprocess.CompletedProcess(a, 0, next(outputs), "")
        self.assertEqual(notify.read_power(fake), {"on_battery": True, "state": "discharging", "percent": 91.0})
        failing = lambda *a, **k: subprocess.CompletedProcess(a, 1, "", "no bus")
        self.assertEqual(notify.read_power(failing), notify.NO_POWER)

        def hang(*a, **k):
            raise subprocess.TimeoutExpired(a, 5)
        self.assertEqual(notify.read_power(hang), notify.NO_POWER)

    def test_never_reads_power_supply_sysfs(self):
        source = (REPO / "scripts/touchpad-notify").read_text()
        code = [line for line in source.splitlines() if not line.lstrip().startswith("#")]
        self.assertFalse(any("/sys/class/power_supply" in line and "never" not in line for line in code))


if __name__ == "__main__":
    unittest.main()
