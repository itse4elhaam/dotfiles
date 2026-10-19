import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    "double_shift", Path(__file__).resolve().parents[1] / "scripts/flameshot-double-shift.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class DoubleShiftTests(unittest.TestCase):
    def run_events(self, events, held=()):
        detector = module.DoubleTap(62, held)
        return [i for i, event in enumerate(events) if detector.feed(*event)]

    def test_two_taps_and_cooldown(self):
        taps = [(True, 62, 0), (False, 62, 50), (True, 62, 150), (False, 62, 200)]
        self.assertEqual(self.run_events(taps), [3])
        self.assertEqual(self.run_events(taps + [(p, k, t + 300) for p, k, t in taps]), [3])

    def test_normal_typing_and_other_modifiers_do_not_trigger(self):
        events = [(True, 62, 0), (True, 38, 20), (False, 38, 40),
                  (False, 62, 50), (True, 62, 150), (False, 62, 200)]
        self.assertEqual(self.run_events(events), [])
        self.assertEqual(self.run_events([(True, 62, 0), (False, 62, 50),
                                         (True, 62, 150), (False, 62, 200)], held=[37]), [])

    def test_single_slow_and_held_taps(self):
        self.assertEqual(self.run_events([(True, 62, 0), (False, 62, 50)]), [])
        self.assertEqual(self.run_events([(True, 62, 0), (False, 62, 50),
                                         (True, 62, 600), (False, 62, 650)]), [])
        self.assertEqual(self.run_events([(True, 62, 0), (True, 62, 100),
                                         (False, 62, 400), (True, 62, 500),
                                         (False, 62, 550)]), [])

    def test_mouse_click_cancels_and_clock_can_wrap(self):
        self.assertEqual(self.run_events([(True, 62, 0), (False, 62, 50),
                                         (True, 257, 80), (False, 257, 90),
                                         (True, 62, 150), (False, 62, 200)]), [])
        self.assertEqual(self.run_events([(True, 62, 0xFFFFFFC0), (False, 62, 0xFFFFFFF0),
                                         (True, 62, 50), (False, 62, 100)]), [3])


if __name__ == "__main__":
    unittest.main()
