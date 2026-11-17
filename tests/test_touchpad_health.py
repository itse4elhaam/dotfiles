import importlib.util
import json
import os
from pathlib import Path
import selectors
import struct
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_touchpad_watch import contact, strokes  # noqa: E402
from touchpad_captures import load_capture  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("touchpad_watch_health", REPO / "scripts/touchpad-watch.py")
watch = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(watch)
RAW_FIELDS = {"x", "y", "position", "positions", "events", "points"}


def minutes_for(events, minute=60.0):
    meter = watch.HealthMeter()
    meter.MINUTE = minute
    out = []
    for event in events:
        meter.feed(event)
        if event[1:3] == [0, 0]:
            minute = meter.take(event[0])
            if minute:
                out.append(minute)
    minute = meter.take(events[-1][0], force=True)
    return out + ([minute] if minute else [])


class HealthMeterTests(unittest.TestCase):
    def test_continuous_strokes_have_no_drops_or_taps_and_count_touch_time(self):
        [minute] = minutes_for(strokes(6))
        self.assertEqual(minute["fast_drop_restarts"], 0)
        self.assertEqual(minute["tap_like_contacts"], 0)
        self.assertEqual(minute["contact_starts"], 6)
        self.assertAlmostEqual(minute["touched_seconds"], 6 * 33 * 0.007, delta=0.05)
        self.assertFalse(RAW_FIELDS & set(minute))

    def test_finger_lost_across_a_band_counts_one_drop_per_crossing(self):
        [minute] = minutes_for(strokes(6, dead=(1600, 1900)))
        self.assertEqual(minute["fast_drop_restarts"], 6)
        self.assertEqual(minute["contact_starts"], 12)

    def test_drops_with_another_finger_down_are_not_counted(self):
        [minute] = minutes_for(strokes(6, dead=(1600, 1900), rest=(3000, 2200)))
        self.assertEqual(minute["fast_drop_restarts"], 0)
        self.assertGreater(minute["multi_contact_frames"], 0)

    def test_short_still_contacts_are_tap_like(self):
        events, moment = [], 0.0
        for index in range(5):
            tap, moment = contact(moment, 10 + index, [1000 + 300 * index] * 8, 1200)
            events += tap
            moment += 0.5
        [minute] = minutes_for(events)
        self.assertEqual(minute["tap_like_contacts"], 5)
        self.assertEqual(minute["fast_drop_restarts"], 0)

    def test_a_late_second_contact_on_a_moving_finger_is_counted(self):
        first, end = contact(0.0, 1, list(range(1000, 2001, 10)), 1000)
        second, _ = contact(0.35, 2, [2500] * 5, 1000, slot=1)
        [minute] = minutes_for(sorted(first + second, key=lambda event: event[0]))
        self.assertEqual(minute["late_second_contacts"], 1)
        self.assertGreaterEqual(minute["multi_contact_frames"], 5)

    def test_x_frozen_while_y_moves_is_a_frozen_run(self):
        events, _ = contact(0.0, 1, [1500] * 30, 1000)
        for index, event in enumerate(event for event in events if event[1:3] == [3, 54]):
            event[3] = 1000 + 10 * index
        [minute] = minutes_for(events)
        self.assertEqual(minute["frozen_x_runs"], 1)

    def test_a_minute_line_per_touched_minute_and_none_for_idle_time(self):
        events = strokes(2) + strokes(2, start=70) + strokes(2, start=400)
        lines = minutes_for(events)
        self.assertEqual(len(lines), 3)
        self.assertTrue(all(line["touched_frames"] for line in lines))

    def test_band_score_points_at_the_dead_band(self):
        events = strokes(60, dead=(1600, 1900))
        lines = minutes_for(events)
        located = [line for line in lines if line["sparse_x_at"] is not None]
        self.assertTrue(located)
        self.assertTrue(all(1600 <= line["sparse_x_at"] <= 1900 for line in located), located)
        self.assertGreater(located[-1]["sparse_x_score"], 0.8)


class HealthLogTests(unittest.TestCase):
    def test_lines_are_world_readable_and_rotated_by_size(self):
        with tempfile.TemporaryDirectory() as directory:
            log = watch.HealthLog(Path(directory))
            log.LIMIT = 300
            old_umask = os.umask(0o027)
            try:
                for index in range(20):
                    log.write({"kind": "minute", "index": index, "pad": "x" * 40})
            finally:
                os.umask(old_umask)
            names = sorted(path.name for path in Path(directory).iterdir())
            self.assertEqual(names, ["health.jsonl", "health.jsonl.1", "health.jsonl.2"])
            self.assertEqual(os.stat(log.path).st_mode & 0o777, 0o644)
            self.assertTrue(all(path.stat().st_size <= 300 for path in Path(directory).iterdir()))
            last = json.loads(log.path.read_text().splitlines()[-1])
            self.assertEqual(last["index"], 19)


def finish_poll(poller, selector, now=None, limit=5.0):
    """Drive one poll to completion; `now` pins the poller's clock for fake-time tests."""
    clock = (lambda: now) if now is not None else time.monotonic
    deadline = time.monotonic() + limit
    while poller.process is not None and time.monotonic() < deadline:
        for _, _ in selector.select(timeout=0.05):
            result = poller.readable(clock())
            if result is not None:
                return result
        result = poller.expire(clock())
        if result is not None:
            return result
    return poller.snapshot


UPOWER_REPLY = '{"type":"b","data":%s}\n{"type":"u","data":%d}\n{"type":"d","data":%s}\n{"type":"d","data":12.5}\n'


class PowerPollerTests(unittest.TestCase):
    def test_upower_reply_is_parsed(self):
        selector = selectors.DefaultSelector()
        reply = UPOWER_REPLY % ("false", 5, "96.0")
        poller = watch.PowerPoller(selector, ["/bin/sh", "-c", f"printf '{reply}'"])
        poller.start(time.monotonic())
        self.assertEqual(finish_poll(poller, selector),
                         {"ac_online": True, "battery_state": "pending-charge", "battery_pct": 96.0,
                          "energy_rate_w": 12.5})

    def test_a_hung_upower_gives_nulls_without_blocking(self):
        selector = selectors.DefaultSelector()
        poller = watch.PowerPoller(selector, ["/bin/sleep", "30"])
        poller.TIMEOUT = 0.3
        started = time.monotonic()
        poller.start(started)
        snapshot = finish_poll(poller, selector)
        self.assertLess(time.monotonic() - started, 2)
        self.assertIsNone(snapshot["ac_online"])
        self.assertEqual(snapshot["power_error"], "timeout")
        self.assertEqual(selector.get_map(), {})

    def test_missing_busctl_is_an_error_value_not_a_crash(self):
        poller = watch.PowerPoller(selectors.DefaultSelector(), ["/nonexistent/busctl"])
        self.assertIn("power_error", poller.start(0.0))


class HealthMonitorTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.state = self.root / "upower"
        self.set_power(True, 5)
        self.selector = selectors.DefaultSelector()
        self.wall = [1794430000.0]
        self.monitor = watch.HealthMonitor(self.selector, self.root, ["/bin/cat", str(self.state)],
                                           boot_id="boot-1", wall=lambda: self.wall[0])
        self.monitor.poller.PERIOD = 1000.0
        self.boot_offset = 50.0

    def set_power(self, ac, state):
        self.state.write_text(UPOWER_REPLY % ("false" if ac else "true", state, "96.0"))

    def tick(self, now, poll=False):
        if poll:
            self.monitor.poller.next_poll = min(self.monitor.poller.next_poll, now)
        self.monitor.tick(now, now + self.boot_offset)
        if self.monitor.poller.process is not None:
            snapshot = finish_poll(self.monitor.poller, self.selector, now)
            self.monitor.power_done(now, snapshot)

    def lines(self):
        return [json.loads(line) for line in (self.root / "health.jsonl").read_text().splitlines()]

    def test_minutes_carry_charger_and_calibration_context(self):
        self.tick(100.0, poll=True)
        self.monitor.device("0018:04F3:31EC.002A", 100.0)
        for event in strokes(4, start=101.0):
            self.monitor.feed(event + ["touchpad", "0018:04F3:31EC.002A|input136"])
        self.tick(170.0)
        start, minute = self.lines()
        self.assertEqual(start["kind"], "service_start")
        self.assertEqual(minute["kind"], "minute")
        self.assertEqual((minute["ac_online"], minute["battery_state"]), (True, "pending-charge"))
        self.assertEqual(minute["hid"], "0018:04F3:31EC.002A")
        self.assertEqual(minute["boot_id"], "boot-1")
        self.assertEqual(minute["calibration_kind"], "unknown")

    def test_unplugging_flushes_the_minute_then_logs_the_change(self):
        self.tick(100.0, poll=True)
        for event in strokes(2, start=101.0):
            self.monitor.feed(event)
        self.set_power(False, 2)
        self.tick(110.0, poll=True)
        kinds = [(line["kind"], line["ac_online"]) for line in self.lines()]
        self.assertEqual(kinds, [("service_start", True), ("minute", True), ("power_change", False)])
        self.assertEqual(self.lines()[-1]["previous_battery_state"], "pending-charge")

    def test_resume_records_the_settled_charger_state_as_calibration_context(self):
        self.tick(100.0, poll=True)
        self.set_power(False, 2)
        self.boot_offset += 3600
        self.tick(200.0)
        self.tick(203.0, poll=True)
        for event in strokes(2, start=204.0):
            self.monitor.feed(event)
        self.tick(270.0)
        resume = next(line for line in self.lines() if line["kind"] == "resume")
        minute = self.lines()[-1]
        self.assertEqual(resume["suspended_s"], 3600.0)
        self.assertEqual(resume["calibration_ac_online"], True)
        self.assertEqual(minute["calibration_kind"], "resume")
        self.assertEqual(minute["calibration_ac_online"], False)
        self.assertEqual(minute["resume_battery_state"], "discharging")
        self.assertAlmostEqual(minute["seconds_since_calibration"], 70.0)

    def test_driver_rebind_is_a_calibration_event_with_the_previous_device(self):
        self.tick(100.0, poll=True)
        self.monitor.device("0018:04F3:31EC.002A", 100.0)
        self.monitor.device("0018:04F3:31EC.002B", 150.0)
        rebind = self.lines()[-1]
        self.assertEqual((rebind["kind"], rebind["previous_hid"], rebind["hid"]),
                         ("rebind", "0018:04F3:31EC.002A", "0018:04F3:31EC.002B"))
        self.assertEqual(rebind["rebind_ac_online"], True)


class ReportTests(unittest.TestCase):
    def write_log(self, directory, rows):
        with open(Path(directory) / "health.jsonl", "w") as handle:
            for row in rows:
                handle.write(json.dumps(row) + "\n")

    def minute(self, ts, ac, state, drops=0, multi=0, taps=0, late=0, calibration=(True, "pending-charge")):
        return {"ts": ts, "kind": "minute", "ac_online": ac, "battery_state": state,
                "calibration_ac_online": calibration[0], "calibration_battery_state": calibration[1],
                "touched_seconds": 30.0, "touched_frames": 4000, "contact_starts": 20,
                "multi_contact_frames": multi, "late_second_contacts": late, "tap_like_contacts": taps,
                "fast_drop_restarts": drops, "frozen_x_runs": 0, "sparse_x_at": 2150, "cpu_pkg_temp_c": 55.0}

    def report(self, directory, *extra):
        return subprocess.run([sys.executable, "-I", str(REPO / "scripts/touchpad-health-report"),
                               "--log", str(directory), *extra], capture_output=True, text=True, timeout=10)

    def test_rates_are_split_by_charger_state_now_and_at_calibration(self):
        with tempfile.TemporaryDirectory() as directory:
            base = 1794430000
            rows = [self.minute(base + 60 * i, True, "pending-charge", drops=10) for i in range(2)]
            rows += [self.minute(base + 200 + 60 * i, True, "pending-charge") for i in range(2)]
            rows += [self.minute(base + 500 + 60 * i, False, "discharging", multi=200, taps=10, late=4,
                                 calibration=(False, "discharging")) for i in range(4)]
            # Healthy tap-to-click and two-finger scrolling: many taps and 2+ contact frames, no late seconds.
            rows += [self.minute(base + 800 + 60 * i, True, "charging", multi=200, taps=10) for i in range(2)]
            rows.append({"ts": base + 490, "kind": "power_change", "ac_online": False})
            self.write_log(directory, rows)
            result = self.report(directory)
            self.assertEqual(result.returncode, 0, result.stderr)
            text = result.stdout
            now_section = text.split("By charger state now")[1].split("By charger state at")[0]
            full = next(line for line in now_section.splitlines() if line.startswith("AC full"))
            battery = next(line for line in now_section.splitlines() if line.startswith("battery"))
            self.assertIn("50.0% (15-85)", full)
            self.assertIn(" 0.0% (0-49)", full)
            self.assertIn("100.0% (51-100)", battery)
            self.assertIn("2150 (2 min)", full)
            charging = next(line for line in now_section.splitlines() if line.startswith("AC charging"))
            self.assertIn(" 0.0% (0-66)", charging.split("%", 1)[1])
            self.assertIn("power_change 1", text)
            self.assertIn("By charger state at the last calibration", text)
            self.assertNotIn("Touchpad filter on in", text)

    def test_filter_minutes_are_grouped_and_totalled(self):
        with tempfile.TemporaryDirectory() as directory:
            base = 1794430000
            rows = [dict(self.minute(base + 60 * i, True, "pending-charge", drops=10), filter_on=True,
                         bridged_drops=8, suppressed_ghosts=1, health_source="hid") for i in range(3)]
            rows += [dict(self.minute(base + 400 + 60 * i, True, "pending-charge"), filter_on=False,
                          bridged_drops=0, suppressed_ghosts=0, health_source="hid") for i in range(2)]
            self.write_log(directory, rows)
            result = self.report(directory)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Touchpad filter on in 3 of 5 touched minutes; it bridged 24 drops and "
                          "suppressed 3 ghost contacts.", result.stdout)
            section = result.stdout.split("By touchpad filter")[1]
            self.assertTrue(any(line.startswith("filter on") for line in section.splitlines()))
            self.assertTrue(any(line.startswith("filter off") for line in section.splitlines()))

    def test_event_study_pairs_minutes_on_each_side_of_an_unplug(self):
        with tempfile.TemporaryDirectory() as directory:
            base = 1794430000
            rows = [self.minute(base + 60 * i, True, "pending-charge", drops=12) for i in range(6)]
            # The minute flushed by the change shares the event's timestamp and stays "before".
            rows.append(self.minute(base + 400, True, "pending-charge", drops=12))
            rows.append({"ts": base + 400, "kind": "power_change", "ac_online": False,
                         "battery_state": "discharging", "previous_ac_online": True,
                         "previous_battery_state": "pending-charge"})
            rows += [self.minute(base + 460 + 60 * i, False, "discharging") for i in range(3)]
            rows.append({"ts": base + 700, "kind": "resume", "ac_online": False, "battery_state": "discharging"})
            rows += [self.minute(base + 760, False, "discharging", drops=3)]
            self.write_log(directory, rows)
            result = self.report(directory)
            self.assertEqual(result.returncode, 0, result.stderr)
            study = result.stdout.split("Event study:")[1].split("By charger state now")[0]
            unplug = next(line for line in study.splitlines() if "unplug AC full -> battery" in line)
            self.assertRegex(unplug, r"\s5\s+24\.0\s.*\s3\s+0\.0\s")
            summary = study.split("summary")[1]
            self.assertRegex(next(line for line in summary.splitlines() if line.startswith("unplug")),
                             r"24\.0 -> 0\.0.*1 of 1")
            self.assertRegex(next(line for line in summary.splitlines() if line.startswith("resume")),
                             r"0\.0 -> 6\.0")

    def test_since_filters_older_records(self):
        with tempfile.TemporaryDirectory() as directory:
            self.write_log(directory, [self.minute(1000.0, False, "discharging")])
            result = self.report(directory, "--since", "2026-01-01")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("No health records", result.stderr)


def hid_report(contacts, scan, button=0):
    """ELAN report 0x54: contacts are (contact id, tip, x, y)."""
    data = bytearray([0x54, button | len(contacts) << 4]) + struct.pack("<H", scan & 0xFFFF)
    for contact, tip, x, y in contacts:
        data += struct.pack("<BHH", contact << 4 | (2 if tip else 0) | 1, x, y)
    return bytes(data + bytes(29 - len(data)))


def hid_minutes(reports, minute=60.0):
    decoder, meter, out = watch.HidContacts("0018:04F3:31EC.002C|hidraw0"), watch.HealthMeter(), []
    meter.MINUTE = minute
    events = []
    for moment, report in reports:
        events += decoder.feed(moment, report)
    for event in events:
        meter.feed(event)
        if event[1:3] == [0, 0]:
            line = meter.take(event[0])
            if line:
                out.append(line)
    line = meter.take(events[-1][0], force=True) if events else None
    return out + ([line] if line else []), events


class HidContactTests(unittest.TestCase):
    """Health comes from hidraw, which touchpad-filter's evdev grab cannot hide."""

    def test_contacts_follow_hid_multitouch_slot_and_tracking_id_rules(self):
        reports = [(0.000, hid_report([(0, 1, 1000, 1000)], 0)),
                   (0.007, hid_report([(0, 1, 1010, 1000)], 70)),
                   (0.014, hid_report([(0, 1, 1020, 1000), (1, 1, 1800, 1000)], 140)),
                   (0.021, hid_report([(0, 0, 1020, 1000), (1, 1, 1810, 1000)], 210)),
                   (0.028, hid_report([(1, 1, 1820, 1000)], 280)),
                   (0.035, hid_report([], 350)),
                   (0.042, hid_report([(1, 1, 900, 900)], 420)),
                   (0.049, hid_report([(1, 1, 905, 900)], 490))]
        _, events = hid_minutes(reports)
        tracking = [(event[0], event[3]) for index, event in enumerate(events) if event[1:3] == [3, 57]]
        self.assertEqual(tracking, [(0.0, 0), (0.014, 1), (0.021, -1), (0.035, -1), (0.042, 2)])
        slots = [event[3] for event in events if event[1:3] == [3, 47]]
        self.assertIn(1, slots)
        self.assertTrue(all(event[4:] == ["touchpad", "0018:04F3:31EC.002C|hidraw0"] for event in events))

    def test_frame_times_follow_scan_time_when_reads_bunch_up(self):
        reports = [(5.0, hid_report([(0, 1, 1000, 1000)], 65500))]
        reports += [(5.2, hid_report([(0, 1, 1000 + index, 1000)], 65500 + 70 * index)) for index in range(1, 5)]
        _, events = hid_minutes(reports)
        times = sorted({event[0] for event in events})
        self.assertEqual([round(moment, 4) for moment in times], [5.0, 5.007, 5.014, 5.021, 5.028])

    def test_a_contact_without_reports_is_released_after_100_ms(self):
        reports = [(1.0, hid_report([(0, 1, 1000, 1000)], 0)), (1.5, hid_report([(0, 1, 1500, 1000)], 5000))]
        _, events = hid_minutes(reports)
        self.assertEqual([(event[0], event[3]) for event in events if event[1:3] == [3, 57]],
                         [(1.0, 0), (1.1, -1), (1.5, 1)])

    def test_other_reports_are_ignored(self):
        self.assertEqual(watch.HidContacts().feed(0.0, bytes([0x5C]) + bytes(28)), [])
        self.assertEqual(watch.HidContacts().feed(0.0, bytes([0x54, 0x10])), [])

    def test_hid_and_evdev_give_the_same_health_counts_on_the_captures(self):
        for name in "ABCD":
            with self.subTest(capture=name):
                trace = load_capture(name)
                [from_evdev] = minutes_for(trace["events"], minute=1e9)
                [from_hid], _ = hid_minutes(watch.hid_reports(trace), minute=1e9)
                for field in ("multi_contact_frames", "late_second_contacts", "tap_like_contacts",
                              "frozen_x_runs", "frozen_y_runs"):
                    self.assertEqual(from_hid[field], from_evdev[field], field)
                # Captures C and D begin mid-touch: evdev shows that contact no start, HID does.
                self.assertIn(from_hid["contact_starts"] - from_evdev["contact_starts"], (0, 1))
                # One of A's restarts sits on the 100 ms threshold.
                self.assertLessEqual(abs(from_hid["fast_drop_restarts"] - from_evdev["fast_drop_restarts"]), 1)
                # The firmware's scan clock runs about 1% slower than the kernel's timestamps.
                self.assertAlmostEqual(from_hid["touched_seconds"] / from_evdev["touched_seconds"], 0.99,
                                       delta=0.01)


class FilterFieldTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / "status.json"
        self.state = watch.FilterState(self.path)

    def write(self, state="active", bridged=0, suppressed=0, instance="one", mono=100.0):
        self.path.write_text(json.dumps({"state": state, "instance": instance, "mono": mono,
                                         "stats": {"bridged_drops": bridged, "suppressed_ghosts": suppressed}}))

    def test_minute_counts_are_deltas_and_survive_a_filter_restart(self):
        self.write(bridged=5, suppressed=1)
        self.state.poll(100.0)
        self.write(bridged=9, suppressed=1, mono=160.0)
        self.assertEqual(self.state.fields(161.0), {"filter_on": True, "bridged_drops": 4, "suppressed_ghosts": 0})
        self.write(state="stopped", bridged=9, suppressed=1, mono=170.0)
        self.state.next_poll = 0
        self.state.poll(171.0)
        self.write(bridged=2, suppressed=3, instance="two", mono=200.0)
        self.assertEqual(self.state.fields(201.0), {"filter_on": True, "bridged_drops": 2, "suppressed_ghosts": 3})

    def test_a_stale_or_missing_status_means_off(self):
        self.assertEqual(self.state.fields(10.0), {"filter_on": False, "bridged_drops": 0, "suppressed_ghosts": 0})
        self.write(mono=100.0)
        self.assertFalse(self.state.fields(200.0)["filter_on"])

    def test_health_minutes_carry_filter_fields_and_their_source(self):
        root = Path(self.path.parent)
        self.write(bridged=3, mono=time.monotonic())
        monitor = watch.HealthMonitor(selectors.DefaultSelector(), root, ["/bin/true"],
                                      filter_status=self.path)
        monitor.poller.PERIOD = 1000.0
        base = time.monotonic()
        monitor.tick(base, base + 50)
        reports = [(base + 1 + index * 0.007, hid_report([(0, 1, 1000 + 5 * index, 1000)], 70 * index))
                   for index in range(800)]
        for moment, report in reports:
            monitor.feed_hid(moment, "0018:04F3:31EC.002C|hidraw0", report)
        self.write(bridged=7, mono=time.monotonic())
        monitor.flush(base + 70, force=True)
        minute = [json.loads(line) for line in (root / "health.jsonl").read_text().splitlines()][-1]
        self.assertEqual((minute["kind"], minute["health_source"], minute["filter_on"], minute["bridged_drops"]),
                         ("minute", "hid", True, 4))
        self.assertEqual(minute["contact_starts"], 1)

    def test_replay_can_measure_health_from_hid_reports(self):
        trace = {"axes": {"x": {"resolution": 32}, "y": {"resolution": 31}}, "events": [],
                 "hid_reports": [[index * 0.007, hid_report([(0, 1, 1000 + index, 1000)], 70 * index).hex()]
                                 for index in range(50)]}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trace.json"
            path.write_text(json.dumps(trace))
            result = subprocess.run([sys.executable, "-I", str(REPO / "scripts/touchpad-watch.py"), "--replay",
                                     str(path), "--health", "--hid"], capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        [line] = [json.loads(text) for text in result.stdout.splitlines()]
        self.assertEqual((line["contact_starts"], line["touched_frames"]), (1, 50))


class ServiceLoopSmokeTests(unittest.TestCase):
    def test_watch_loop_starts_and_writes_the_health_log_without_devices(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "sysfs").mkdir()
            code = (f"import importlib.util, pathlib\n"
                    f"spec = importlib.util.spec_from_file_location('tw', {str(REPO / 'scripts/touchpad-watch.py')!r})\n"
                    f"tw = importlib.util.module_from_spec(spec); spec.loader.exec_module(tw)\n"
                    f"tw.POWER_COMMAND[:] = ['/bin/printf', {UPOWER_REPLY % ('true', 2, '41.0')!r}]\n"
                    f"r = pathlib.Path({directory!r})\n"
                    f"tw.watch(r / 'state', r / 'run', r / 'log', r / 'sysfs', require_root=False)\n")
            process = subprocess.Popen([sys.executable, "-I", "-c", code],
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                deadline = time.monotonic() + 8
                log = root / "log/health.jsonl"
                while not log.exists() and time.monotonic() < deadline and process.poll() is None:
                    time.sleep(0.1)
                time.sleep(0.5)
                self.assertIsNone(process.poll(), process.stderr.read() if process.poll() is not None else "")
            finally:
                process.terminate()
                stdout, stderr = process.communicate(timeout=5)
            self.assertNotIn("Traceback", stderr)
            self.assertNotIn("health_error", stdout)
            [start] = [json.loads(line) for line in log.read_text().splitlines()]
            self.assertEqual((start["kind"], start["ac_online"], start["battery_state"]),
                             ("service_start", False, "discharging"))
            status = json.loads((root / "run/status").read_text())
            self.assertEqual(status["sources"], [])


if __name__ == "__main__":
    unittest.main()
