#!/usr/bin/python3
"""Observe X11 input without grabbing keys; double-tap Right Shift for Flameshot."""


class DoubleTap:
    def __init__(self, keycode, held=()):
        self.keycode = keycode
        self.held = set(held)
        self.pressed_at = None
        self.first_tap = None
        self.last_trigger = None

    def feed(self, pressed, keycode, timestamp):
        elapsed = lambda start: (timestamp - start) & 0xFFFFFFFF
        if keycode != self.keycode:
            self.first_tap = self.pressed_at = None
            if pressed:
                self.held.add(keycode)
            else:
                self.held.discard(keycode)
            return False
        if pressed:
            if keycode not in self.held:
                self.pressed_at = timestamp if not self.held else None
            self.held.add(keycode)
            return False
        self.held.discard(keycode)
        started, self.pressed_at = self.pressed_at, None
        if started is None or elapsed(started) > 250 or self.held:
            self.first_tap = None
            return False
        if self.last_trigger is not None and elapsed(self.last_trigger) < 850:
            self.first_tap = None
            return False
        if self.first_tap is not None and elapsed(self.first_tap) <= 400:
            self.first_tap = None
            self.last_trigger = timestamp
            return True
        self.first_tap = timestamp
        return False


def main():
    import subprocess
    from Xlib import X, XK, display
    from Xlib.ext import record
    from Xlib.protocol import rq

    connection = display.Display()
    if not connection.has_extension("RECORD"):
        raise SystemExit("X11 RECORD extension is required")
    keycode = connection.keysym_to_keycode(XK.string_to_keysym("Shift_R"))
    keymap = connection.query_keymap()
    held = [i for i in range(256) if keymap[i // 8] & (1 << (i % 8))]
    detector = DoubleTap(keycode, held)

    def receive(reply):
        if reply.category != record.FromServer or reply.client_swapped or not reply.data:
            return
        data = reply.data
        while data:
            event, data = rq.EventField(None).parse_binary_value(data, connection.display, None, None)
            if event.type not in (X.KeyPress, X.KeyRelease, X.ButtonPress, X.ButtonRelease):
                continue
            # Mouse buttons cancel a partial double tap, just like another key.
            code = event.detail + (256 if event.type in (X.ButtonPress, X.ButtonRelease) else 0)
            if detector.feed(event.type in (X.KeyPress, X.ButtonPress), code, event.time):
                subprocess.Popen(
                    ["/usr/bin/flameshot", "gui", "--clipboard", "--accept-on-select"],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )

    context = connection.record_create_context(0, [record.AllClients], [{
        "core_requests": (0, 0), "core_replies": (0, 0),
        "ext_requests": (0, 0, 0, 0), "ext_replies": (0, 0, 0, 0),
        "delivered_events": (0, 0), "device_events": (X.KeyPress, X.ButtonRelease),
        "errors": (0, 0), "client_started": False, "client_died": False,
    }])
    print("Listening for two Right Shift taps within 400 ms", flush=True)
    try:
        connection.record_enable_context(context, receive)
    finally:
        connection.record_free_context(context)
        connection.close()


if __name__ == "__main__":
    main()
