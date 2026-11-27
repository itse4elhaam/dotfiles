"""Click-through recording light around the original dictation window."""
from collections import deque

import cairo
import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, Gtk


class RecordingGlow(Gtk.Window):
    def __init__(self):
        super().__init__(type=Gtk.WindowType.POPUP)
        self.set_accept_focus(False)
        self.set_focus_on_map(False)
        self.set_type_hint(Gdk.WindowTypeHint.NOTIFICATION)
        self.set_keep_above(True)
        self.set_app_paintable(True)
        visual = self.get_screen().get_rgba_visual()
        if visual:
            self.set_visual(visual)
        self.target = None
        self.bounds = None
        self.samples = deque([0.] * 32, maxlen=32)
        self.connect("draw", self.draw_light)

    def track(self, target):
        self.stop()
        self.target = target

    def stop(self):
        self.hide()
        self.target = None
        self.bounds = None
        self.samples = deque([0.] * 32, maxlen=32)

    def place(self):
        if not self.target or self.target.is_destroyed() or not self.target.is_viewable():
            self.stop()
            return False
        # The client rectangle excludes the compositor's invisible resize margins.
        _, x, y = self.target.get_origin()
        _, _, width, height = self.target.get_geometry()
        if width < 4 or height < 4:
            self.stop()
            return False
        soft = self.get_screen().is_composited() and self.get_visual().get_depth() == 32
        bounds = (x, y, width, height, soft)
        if self.bounds != bounds:
            self.bounds = bounds
            self.move(x, y)
            self.resize(width, height)
            self.realize()
            rim = 9 if soft else 2
            bottom = min(36, max(4, height // 8)) if soft else 2
            region = cairo.Region(cairo.RectangleInt(0, 0, width, height))
            if width > 2 * rim and height > rim + bottom:
                region.subtract(cairo.RectangleInt(rim, rim, width - 2 * rim, height - rim - bottom))
            self.shape_combine_region(region)
            self.input_shape_combine_region(cairo.Region())
            self.queue_draw()
        return True

    def level(self, energy):
        if not self.target:
            return
        if self.bounds is None and not self.place():
            return
        smoothed = self.samples[-1] * .4 + energy * .6
        self.samples.append(smoothed)
        if not self.get_visible():
            self.show()
        _, _, width, height, _ = self.bounds
        self.queue_draw_area(0, max(0, height - 36), width, min(36, height))

    def draw_light(self, widget, cr):
        if self.bounds is None:
            return False
        _, _, w, h, soft = self.bounds
        cr.set_operator(cairo.OPERATOR_CLEAR)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        # A quiet, continuous rim stays visible between words.
        ink = cairo.LinearGradient(0, 0, w, h * .35)
        for at, rgb in ((0, (.60, .55, 1)), (.48, (.39, .69, 1)), (1, (.40, .87, .92))):
            ink.add_color_stop_rgba(at, *rgb, .90)
        if soft:
            for depth, alpha in ((8, .03), (5, .07), (3, .16)):
                cr.rectangle(depth / 2, depth / 2, max(0, w-depth), max(0, h-depth))
                cr.set_line_width(depth)
                cr.set_source_rgba(.42, .68, 1, alpha)
                cr.stroke()
            # Overlapping elliptical gradients give each recent sound sample
            # a soft crest along the bottom without covering the text above it.
            samples = list(self.samples)
            for index in range(0, len(samples), 2):
                at = index / (len(samples) - 2)
                energy = samples[index]
                cr.save()
                cr.translate(at * w, h + 1)
                cr.scale(max(1, w * .115), 7 + 29 * energy)
                light = cairo.RadialGradient(0, 0, 0, 0, 0, 1)
                rgb = (.44 + .14 * (1-at), .57 + .27 * at, 1)
                light.add_color_stop_rgba(0, *rgb, .64 + .24 * energy)
                light.add_color_stop_rgba(.43, *rgb, .27 + .18 * energy)
                light.add_color_stop_rgba(1, *rgb, 0)
                cr.set_source(light)
                cr.rectangle(-1, -1, 2, 1)
                cr.fill()
                cr.restore()
        cr.set_source(ink)
        cr.set_line_width(2)
        cr.rectangle(1, 1, w-2, h-2)
        cr.stroke()
        if not soft:
            cr.set_source_rgba(.69, .92, 1, self.samples[-1])
            cr.move_to(0, h-1)
            cr.line_to(w, h-1)
            cr.stroke()
        return False
