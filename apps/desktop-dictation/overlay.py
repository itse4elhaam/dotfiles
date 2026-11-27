import math
import time
from collections import deque

import cairo
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkX11", "3.0")
from gi.repository import Gdk, GLib, Gtk, Pango


class Overlay(Gtk.Window):
    def __init__(self):
        super().__init__(type=Gtk.WindowType.POPUP)
        self.set_accept_focus(False)
        self.set_type_hint(Gdk.WindowTypeHint.NOTIFICATION)
        self.set_app_paintable(True)
        self.set_keep_above(True)
        visual = self.get_screen().get_rgba_visual()
        if visual:
            self.set_visual(visual)
        self.set_name("dictation")
        self.levels = deque([0] * 31, maxlen=31)
        self.wave = Gtk.DrawingArea()
        self.wave.set_size_request(93, 22)
        self.wave.connect("draw", self.draw_wave)
        self.label = Gtk.Label(xalign=0)
        self.label.set_ellipsize(Pango.EllipsizeMode.START)
        row = Gtk.Box(spacing=14)
        row.set_border_width(14)
        row.pack_start(self.wave, False, False, 0)
        row.pack_start(self.label, True, True, 0)
        self.add(row)
        style = Gtk.CssProvider()
        style.load_from_data(b"#dictation {background:rgba(17,30,48,.97);border:1px solid #477091;border-radius:18px;} #dictation label {color:#f3f8ff;font:15px 'Inter',sans-serif;}")
        Gtk.StyleContext.add_provider_for_screen(self.get_screen(), style, 600)
        self.connect("realize", lambda *_: self.get_window().input_shape_combine_region(cairo.Region(), 0, 0))
        self.serial = 0

    def present_at(self, window):
        self.serial += 1
        screen = self.get_display()
        monitor = screen.get_monitor_at_window(window) if window else screen.get_primary_monitor()
        area = (monitor or screen.get_monitor(0)).get_workarea()
        width = min(480, area.width - 24)
        self.set_size_request(width, 52)
        self.levels = deque([0] * 31, maxlen=31)
        self.label.set_text("Listening…")
        x = area.x + (area.width - width) // 2
        y = area.y + area.height - 80
        self.move(x, y + 14)
        self.show_all()
        start, serial = time.monotonic(), self.serial

        def rise():
            if serial != self.serial:
                return False
            progress = min(1, (time.monotonic() - start) / .16)
            self.move(x, y + round(14 * (1 - progress) ** 2))
            return progress < 1
        GLib.timeout_add(16, rise)

    def message(self, text, duration):
        self.serial += 1
        serial = self.serial
        self.label.set_text(text)
        def dismiss():
            if self.serial == serial:
                self.hide()
            return False
        GLib.timeout_add(duration, dismiss)

    def level(self, rms):
        self.levels.append(min(1, math.sqrt(rms / 5000)))
        self.wave.queue_draw()

    def draw_wave(self, widget, cr):
        cr.set_line_width(2)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        mid = widget.get_allocated_height() / 2
        for i, level in enumerate(self.levels):
            cr.set_source_rgb(.26, .65 + level * .18, .99)
            cr.move_to(2 + i * 3, mid - 1 - level * 9)
            cr.line_to(2 + i * 3, mid + 1 + level * 9)
            cr.stroke()
