import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
import unittest


REPO = Path(__file__).resolve().parents[1]
HEADER = "            CPU0       CPU1       CPU2\n"
# Real tools the script needs. PATH holds only these links and the stubs below,
# so no test can reach the real sudo (whose rule would reset the live touchpad).
TOOLS = ("bash", "awk", "flock", "sleep", "cat", "touch", "date", "grep")


class HardwareRecalibrationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="fixtouchpad-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        for tool in TOOLS:
            (self.bin / tool).symlink_to(shutil.which(tool))
        self.log = self.root / "calls.log"
        self.interrupts = self.root / "interrupts"
        self.count = 1000
        self.write_interrupts()
        self.stub("sudo", 'echo "sudo $* $(date +%s.%N)" >> "$CALLS"\n'
                          '[[ -z ${ON_RESET:-} ]] || touch "$ON_RESET"\n')
        self.stub("xinput", 'echo "xinput $*" >> "$CALLS"\n'
                            'if [[ $1 == list-props ]]; then printf "\\tDevice Enabled (187):\\t1\\n"; fi\n')
        self.stub("notify-send", 'echo "notify-send $*" >> "$CALLS"\n')
        self.env = {
            "PATH": str(self.bin), "HOME": str(self.root), "DISPLAY": ":99",
            "XDG_SESSION_TYPE": "x11", "XDG_RUNTIME_DIR": str(self.root),
            "CALLS": str(self.log), "FIXTOUCHPAD_INTERRUPTS": str(self.interrupts),
            "FIXTOUCHPAD_WATCH_DIR": str(self.root / "no-recorder"),
            "FIXTOUCHPAD_QUIET_SECONDS": "0.4", "FIXTOUCHPAD_QUIET_TIMEOUT": "2",
            "FIXTOUCHPAD_VERIFY_SECONDS": "0.4",
            "FIXTOUCHPAD_FILTER_STATUS": str(self.root / "no-filter.json"),
        }

    def stub(self, name, body):
        path = self.bin / name
        path.write_text("#!/bin/bash\n" + body)
        path.chmod(0o755)

    def write_interrupts(self, elan=True):
        lines = [HEADER, " 9:          0          4          0  IR-IO-APIC    9-fasteoi   acpi\n"]
        if elan:
            lines.append(f"166:          0 {self.count:10d}          0  intel-gpio  323  ELAN07AC:00\n")
        temporary = self.interrupts.with_suffix(".tmp")
        temporary.write_text("".join(lines))
        temporary.replace(self.interrupts)

    def touch_for(self, seconds, start_event=None):
        def run():
            if start_event is not None:
                start_event.wait(5)
            deadline = time.monotonic() + seconds
            while time.monotonic() < deadline:
                self.count += 7
                self.write_interrupts()
                time.sleep(0.03)
            self.last_touch = time.time()
        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        self.addCleanup(lambda: thread.join(timeout=seconds + 6))
        return thread

    def run_fixtouchpad(self, *args, extra=None):
        env = dict(self.env, **(extra or {}))
        return subprocess.run(["bash", str(REPO / "scripts/fixtouchpad"), *args],
                              env=env, capture_output=True, text=True, timeout=20)

    def calls(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def resets(self):
        return [line for line in self.calls()
                if line.startswith("sudo -n /usr/local/sbin/reset-touchpad-driver")]

    def test_untouched_pad_is_recalibrated_and_verified_quiet(self):
        result = self.run_fixtouchpad("--hardware")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.resets()), 1)
        self.assertIn("stayed quiet", result.stdout)
        self.assertIn("Lift", result.stderr)

    def test_pad_touched_throughout_skips_the_reset(self):
        self.touch_for(4)
        result = self.run_fixtouchpad("--hardware")
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertEqual(self.resets(), [])
        self.assertIn("recalibration was skipped", result.stderr)

    def test_reset_waits_until_the_pad_has_been_untouched_long_enough(self):
        self.last_touch = None
        self.touch_for(0.8).join(timeout=3)
        thread = self.touch_for(0.8)
        result = self.run_fixtouchpad("--hardware")
        thread.join(timeout=3)
        self.assertEqual(result.returncode, 0, result.stderr)
        reset_time = float(self.resets()[0].split()[-1])
        self.assertGreaterEqual(reset_time - self.last_touch, 0.35)

    def test_touches_right_after_the_reset_are_reported(self):
        marker = self.root / "reset-done"
        started = threading.Event()

        def watch_for_reset():
            deadline = time.monotonic() + 10
            while not marker.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            started.set()
        threading.Thread(target=watch_for_reset, daemon=True).start()
        self.touch_for(1.5, start_event=started)
        result = self.run_fixtouchpad("--hardware", extra={"ON_RESET": str(marker)})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("reported touches right afterwards", result.stdout)

    def test_missing_interrupt_counter_warns_and_still_resets(self):
        self.write_interrupts(elan=False)
        result = self.run_fixtouchpad("--hardware")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Cannot see the touchpad interrupt counter", result.stderr)
        self.assertEqual(len(self.resets()), 1)
        self.assertIn("could not confirm", result.stdout)

    def test_hardware_interrupt_number_is_not_counted_as_a_touch(self):
        lines = HEADER + "166:          0       1000          0  intel-gpio  323  ELAN07AC:00\n"
        self.interrupts.write_text(lines)
        result = self.run_fixtouchpad("--hardware")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("stayed quiet", result.stdout)

    def test_shortcut_mode_shows_the_lift_notice_as_a_desktop_notification(self):
        result = self.run_fixtouchpad("--hardware", extra={"FIXTOUCHPAD_NOTIFY": "1"})
        self.assertEqual(result.returncode, 0, result.stderr)
        notices = [line for line in self.calls() if line.startswith("notify-send")]
        self.assertTrue(notices and "Lift your fingers" in notices[0], self.calls())
        self.assertLess(self.calls().index(notices[0]), self.calls().index(self.resets()[0]))

    def test_mark_uses_the_recorder_directory_and_waits_for_acknowledgement(self):
        watch = self.root / "recorder"
        watch.mkdir()

        def recorder():
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                mark = watch / "mark"
                if mark.exists():
                    token = mark.read_text()
                    (watch / "last-marker").write_text(
                        '{"marker": "%s", "path": "/saved/trace.json"}' % token)
                    return
                time.sleep(0.02)
        threading.Thread(target=recorder, daemon=True).start()
        result = self.run_fixtouchpad("--mark", extra={"FIXTOUCHPAD_WATCH_DIR": str(watch)})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Incident recorded: /saved/trace.json", result.stdout)
        self.assertEqual(self.resets(), [])


FILTERED = "ELAN07AC:00 04F3:31EC Touchpad (filtered)"


class FilterAwareTests(unittest.TestCase):
    """While touchpad-filter runs, libinput reads its virtual twin."""
    # Same harness as above, without re-running its tests.
    stub = HardwareRecalibrationTests.stub
    write_interrupts = HardwareRecalibrationTests.write_interrupts
    run_fixtouchpad = HardwareRecalibrationTests.run_fixtouchpad
    calls = HardwareRecalibrationTests.calls

    def setUp(self):
        HardwareRecalibrationTests.setUp(self)
        self.filter_status = self.root / "filter.json"
        self.env["FIXTOUCHPAD_FILTER_STATUS"] = str(self.filter_status)
        self.stub("xinput", 'echo "xinput $*" >> "$CALLS"\n'
                            'if [[ $1 == list-props ]]; then printf "\\tDevice Enabled (187):\\t1\\n"; fi\n'
                            f'if [[ $1 == list ]]; then printf "%s\\n" "ELAN07AC:00 04F3:31EC Touchpad" "{FILTERED}"; fi\n')

    def test_soft_reset_also_cycles_the_filtered_device(self):
        result = self.run_fixtouchpad()
        self.assertEqual(result.returncode, 0, result.stderr)
        cycles = [line for line in self.calls() if line.split()[1] in ("disable", "enable")]
        self.assertEqual(cycles, [f"xinput disable ELAN07AC:00 04F3:31EC Touchpad", f"xinput disable {FILTERED}",
                                  f"xinput enable ELAN07AC:00 04F3:31EC Touchpad", f"xinput enable {FILTERED}"])

    def test_check_lists_the_filtered_device_and_filter_state(self):
        self.filter_status.write_text('{"state": "active", "hid": "0018:04F3:31EC.002C"}')
        result = self.run_fixtouchpad("--check")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"{FILTERED}:", result.stdout)
        self.assertIn("Touchpad filter: active", result.stdout)

    def test_hardware_reset_reports_the_filter_reattaching(self):
        self.filter_status.write_text('{"state": "active", "hid": "0018:04F3:31EC.002C"}')
        self.stub("sudo", 'echo "sudo $* $(date +%s.%N)" >> "$CALLS"\n'
                          f'printf \'{{"state": "active", "hid": "0018:04F3:31EC.002D"}}\' > {self.filter_status}\n')
        result = self.run_fixtouchpad("--hardware")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("The touchpad filter reattached", result.stdout)

    def test_hardware_reset_says_when_the_filter_did_not_come_back(self):
        self.filter_status.write_text('{"state": "active", "hid": "0018:04F3:31EC.002C"}')
        self.stub("sudo", 'echo "sudo $* $(date +%s.%N)" >> "$CALLS"\n'
                          f'printf \'{{"state": "device-gone", "hid": "0018:04F3:31EC.002C"}}\' > {self.filter_status}\n')
        result = self.run_fixtouchpad("--hardware")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("did not reattach (state: device-gone); the touchpad is unfiltered", result.stdout)


if __name__ == "__main__":
    unittest.main()
