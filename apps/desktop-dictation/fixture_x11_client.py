"""Separate application process for private clipboard integration tests."""
import os
import sys

from Xlib import X, Xatom, display


if __name__ == "__main__":
    x = display.Display()
    window = x.screen().root.create_window(0, 0, 8, 8, 0, 0, X.InputOnly, X.CopyFromParent)
    # A self-declared PID must never let this process impersonate the target.
    window.change_property(x.intern_atom("_NET_WM_PID"), Xatom.CARDINAL, 32, [os.getppid()])
    window.map()
    x.sync()
    print(window.id, flush=True)
    for command in sys.stdin:
        assert command.strip() == "read"
        window.convert_selection(x.intern_atom("CLIPBOARD"), x.intern_atom("UTF8_STRING"),
                                 x.intern_atom("DICTATION_TEST_PASTE"), X.CurrentTime)
        x.flush()
