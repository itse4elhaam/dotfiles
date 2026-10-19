from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import threading
import time
import unittest


REPO = Path(__file__).resolve().parents[1]


class DriverResetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="touchpad-sysfs-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.driver = self.root / "bus/i2c/drivers/i2c_hid_acpi"
        self.device = self.root / "bus/i2c/devices/i2c-ELAN07AC:00"
        self.driver.mkdir(parents=True)
        self.device.mkdir(parents=True)
        (self.root / "run").mkdir()
        (self.driver / "bind").touch()
        (self.driver / "unbind").touch()
        (self.device / "driver").symlink_to(self.driver, target_is_directory=True)
        self.input = self.device / "0018:04F3:31EC.0001/input/input13"
        self.input.mkdir(parents=True)
        (self.input / "name").write_text("ELAN07AC:00 04F3:31EC Touchpad\n")
        (self.input / "event9").mkdir()

    def command(self):
        return ["bash", str(REPO / "scripts/reset-touchpad-driver"),
                "--sysfs-root", str(self.root)]

    def test_existing_named_input_is_not_proof_that_reset_worked(self):
        result = subprocess.run(self.command(), capture_output=True, text=True, timeout=8)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("identity unchanged", result.stderr)

    def test_event_number_change_alone_does_not_verify_hardware_recreation(self):
        (self.input / "event9").rmdir()
        (self.input / "event10").mkdir()
        def change_event():
            while not (self.driver / "bind").read_text():
                time.sleep(0.005)
            (self.input / "event10").rmdir()
            (self.input / "event11").mkdir()
        thread = threading.Thread(target=change_event, daemon=True)
        thread.start()
        result = subprocess.run(self.command(), capture_output=True, text=True, timeout=8)
        thread.join(timeout=1)
        self.assertNotEqual(result.returncode, 0)

    def emulate_kernel(self):
        stop = threading.Event()
        self.addCleanup(stop.set)

        def kernel():
            while not stop.is_set() and not (self.driver / "unbind").read_text():
                time.sleep(0.005)
            if stop.is_set():
                return
            (self.device / "driver").unlink()
            shutil.rmtree(self.device / "0018:04F3:31EC.0001")
            while not stop.is_set() and not (self.driver / "bind").read_text():
                time.sleep(0.005)
            if stop.is_set():
                return
            new_input = self.device / "0018:04F3:31EC.0002/input/input99"
            new_input.mkdir(parents=True)
            (new_input / "name").write_text("ELAN07AC:00 04F3:31EC Touchpad\n")
            (new_input / "event9").mkdir()  # evdev minor numbers can be reused.
            (self.device / "driver").symlink_to(self.driver, target_is_directory=True)

        thread = threading.Thread(target=kernel, daemon=True)
        thread.start()
        self.addCleanup(lambda: thread.join(timeout=1))
        return thread

    def test_new_hid_and_input_identity_verifies_rebind_even_if_event_number_is_reused(self):
        self.emulate_kernel()
        result = subprocess.run(self.command(), capture_output=True, text=True, timeout=8)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(".0001|input13|event9 -> 0018:04F3:31EC.0002|input99|event9", result.stdout)

    def test_wrong_driver_is_refused_without_unbinding(self):
        (self.device / "driver").unlink()
        (self.device / "driver").symlink_to(self.root / "bus/i2c/drivers/some_other_driver")
        (self.root / "bus/i2c/drivers/some_other_driver").mkdir()
        result = subprocess.run(self.command(), capture_output=True, text=True, timeout=8)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.driver / "unbind").read_text(), "")

    def test_interruption_after_unbinding_restores_driver(self):
        kernel = self.emulate_kernel()
        process = subprocess.Popen(self.command(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        deadline = time.monotonic() + 3
        while (self.device / "driver").exists() and time.monotonic() < deadline:
            time.sleep(0.005)
        self.assertFalse((self.device / "driver").exists())
        process.send_signal(signal.SIGTERM)
        process.communicate(timeout=3)
        kernel.join(timeout=1)
        self.assertEqual(process.returncode, 143)
        self.assertTrue((self.device / "0018:04F3:31EC.0002/input/input99/name").exists())


if __name__ == "__main__":
    unittest.main()
