"""Double-tap Ctrl must start dictation without firing during ordinary Ctrl use."""

import importlib.machinery
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader("t3_double_ctrl", str(ROOT / "scripts/t3-double-ctrl"))
spec = importlib.util.spec_from_loader(loader.name, loader)
watcher = importlib.util.module_from_spec(spec)
loader.exec_module(watcher)

CTRL_L, CTRL_R, SHIFT, KEY_C, KEY_V = 37, 105, 50, 54, 55
CLICK = watcher.BUTTON_OFFSET + 1


def triggers(events, held=()):
    """Feed (milliseconds, 'down' or 'up', code) events; return when it fired."""
    detector = watcher.DoubleCtrl((CTRL_L, CTRL_R), held)
    return [at for at, action, code in events if detector.feed(action == "down", code, at)]


def tap(code, at, hold=60):
    return [(at, "down", code), (at + hold, "up", code)]


class DoubleCtrlTests(unittest.TestCase):
    def test_two_quick_taps_of_either_ctrl_fire_once_on_the_second_release(self):
        self.assertEqual(triggers(tap(CTRL_L, 0) + tap(CTRL_L, 150)), [210])
        self.assertEqual(triggers(tap(CTRL_R, 0) + tap(CTRL_R, 150)), [210])

    def test_ordinary_ctrl_shortcuts_never_fire(self):
        copy_then_paste = [
            (0, "down", CTRL_L), (40, "down", KEY_C), (90, "up", KEY_C), (120, "up", CTRL_L),
            (200, "down", CTRL_L), (240, "down", KEY_V), (290, "up", KEY_V), (320, "up", CTRL_L),
        ]
        self.assertEqual(triggers(copy_then_paste), [])
        # One Ctrl held while typing several shortcuts, with key repeat.
        held_ctrl = [(0, "down", CTRL_L)]
        for at in range(50, 650, 100):
            held_ctrl += [(at, "down", KEY_C), (at + 20, "down", KEY_C), (at + 40, "up", KEY_C)]
        self.assertEqual(triggers(held_ctrl + [(700, "up", CTRL_L)]), [])
        # A shortcut released Ctrl-last, straight into another one.
        self.assertEqual(triggers(tap(CTRL_L, 0) + [
            (150, "down", CTRL_L), (180, "down", KEY_C), (220, "up", KEY_C), (240, "up", CTRL_L),
        ]), [])
        self.assertEqual(triggers([
            (0, "down", CTRL_L), (30, "down", KEY_C), (60, "up", KEY_C), (80, "up", CTRL_L),
        ] + tap(CTRL_L, 150)), [])

    def test_shortcut_right_after_a_double_tap_does_not_fire_again(self):
        events = tap(CTRL_L, 0) + tap(CTRL_L, 150) + [
            (300, "down", CTRL_L), (330, "down", KEY_C), (360, "up", KEY_C), (380, "up", CTRL_L),
        ]
        self.assertEqual(triggers(events), [210])

    def test_other_modifiers_and_mouse_cancel(self):
        ctrl_shift = [(0, "down", SHIFT)] + tap(CTRL_L, 20) + tap(CTRL_L, 150) + [(300, "up", SHIFT)]
        self.assertEqual(triggers(ctrl_shift), [])
        ctrl_click = [
            (0, "down", CTRL_L), (30, "down", CLICK), (60, "up", CLICK), (90, "up", CTRL_L),
        ] + tap(CTRL_L, 150)
        self.assertEqual(triggers(ctrl_click), [])
        click_between = tap(CTRL_L, 0) + tap(CLICK, 80, hold=20) + tap(CTRL_L, 150)
        self.assertEqual(triggers(click_between), [])
        self.assertEqual(triggers(tap(CTRL_L, 0) + tap(KEY_C, 80, hold=20) + tap(CTRL_L, 150)), [])

    def test_slow_held_or_mixed_taps_do_not_fire(self):
        self.assertEqual(triggers(tap(CTRL_L, 0) + tap(CTRL_L, 600)), [])
        self.assertEqual(triggers(tap(CTRL_L, 0, hold=400) + tap(CTRL_L, 450)), [])
        self.assertEqual(triggers(tap(CTRL_L, 0) + tap(CTRL_L, 150, hold=400)), [])
        self.assertEqual(triggers(tap(CTRL_L, 0) + tap(CTRL_R, 150)), [])
        # A key already held when the service starts blocks taps until released.
        self.assertEqual(triggers(tap(CTRL_L, 0) + tap(CTRL_L, 150), held=[SHIFT]), [])

    def test_rapid_tapping_fires_once_per_cooldown(self):
        events = [event for at in range(0, 1000, 100) for event in tap(CTRL_L, at, hold=40)]
        self.assertEqual(triggers(events), [140])

    def test_server_time_wraparound_still_fires(self):
        wrap = 0xFFFFFFFF
        self.assertEqual(triggers([
            (wrap - 100, "down", CTRL_L), (wrap - 40, "up", CTRL_L), (50, "down", CTRL_L), (110, "up", CTRL_L),
        ]), [110])

    def test_only_t3_windows_receive_the_key(self):
        self.assertTrue(watcher.is_t3_window(("t3code", "T3code")))
        self.assertTrue(watcher.is_t3_window(("com.t3tools.t3code", "com.t3tools.T3Code")))
        self.assertFalse(watcher.is_t3_window(("gnome-terminal-server", "Gnome-terminal")))
        self.assertFalse(watcher.is_t3_window(None))


class DictationBindingTests(unittest.TestCase):
    def setUp(self):
        self.bindings = json.loads((ROOT / ".config/t3code/keybindings.json").read_text())
        self.dictation = [b for b in self.bindings if b["command"] == "composer.dictation"]

    def test_watcher_sends_the_existing_dictation_shortcut(self):
        self.assertEqual(watcher.DICTATION_KEYS, ("Control_L", "Shift_L", "d"))
        self.assertEqual([binding["key"] for binding in self.dictation], ["mod+shift+d"])

    def test_service_runs_the_linked_watcher(self):
        unit = (ROOT / "scripts/t3-double-ctrl.service").read_text()
        self.assertIn("ExecStart=/usr/bin/python3 -I %h/.local/bin/t3-double-ctrl\n", unit)
        self.assertIn("WantedBy=graphical-session.target", unit)


if __name__ == "__main__":
    unittest.main()
