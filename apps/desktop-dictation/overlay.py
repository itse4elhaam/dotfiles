import math
import time
from collections import deque
from pathlib import Path

import cairo
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkX11", "3.0")
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk, Pango


class Overlay(Gtk.Window):
    """A focus-free transcription card using T3's Zen / Tokyo Drift Forest palette."""

    def __init__(self):
        super().__init__(type=Gtk.WindowType.POPUP)
        self.set_accept_focus(False)
        self.set_type_hint(Gdk.WindowTypeHint.NOTIFICATION)
        self.set_app_paintable(True)
        self.set_keep_above(True)
        visual = self.get_screen().get_rgba_visual()
        if visual:
            self.set_visual(visual)
        self.forest = GdkPixbuf.Pixbuf.new_from_file(str(Path(__file__).with_name("forest.jpg")))
        self.levels = deque([0.] * 90, maxlen=90)
        self.serial = 0
        self.dismiss_on_release = False
        self.recovery = None
        self.pending = []
        self.started = 0
        self.listening = False
        self.set_name("dictation")
        self.connect("draw", self.background)
        self.connect("realize", lambda *_: self.clickable(False))
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        body.set_margin_start(21)
        body.set_margin_end(21)
        body.set_margin_top(13)
        body.set_margin_bottom(11)
        head = Gtk.Box(spacing=8)
        self.indicator = Gtk.Label(label="●", name="indicator")
        self.status = Gtk.Label(name="status", xalign=0)
        self.clock = Gtk.Label(name="clock")
        self.escape = Gtk.Label(label="esc", name="keycap")
        self.hint = Gtk.Label(label="Cancel", name="hint")
        for widget in (self.indicator, self.status, self.clock):
            head.pack_start(widget, False, False, 0)
        head.pack_end(self.hint, False, False, 0)
        head.pack_end(self.escape, False, False, 0)
        self.actions = Gtk.Box(spacing=6)
        self.actions.set_no_show_all(True)
        self.resume = Gtk.Button.new_with_label("Resume")
        self.resume.set_focus_on_click(False)
        self.resume.set_tooltip_text("Resume automatic paste for future recordings in this application")
        self.resume.connect("clicked", self.resume_paste)
        self.actions.add(self.resume)
        for title, callback in (("Copy", self.copy_recovery), ("×", self.dismiss_recovery)):
            button = Gtk.Button.new_with_label(title)
            button.set_focus_on_click(False)
            button.set_tooltip_text("Copy transcript" if title == "Copy" else "Dismiss")
            button.connect("clicked", callback)
            self.actions.add(button)
            button.show()
        head.pack_end(self.actions, False, False, 0)
        self.label = Gtk.Label(name="transcript", xalign=0, yalign=.5)
        self.label.set_line_wrap(True)
        self.label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self.label.set_ellipsize(Pango.EllipsizeMode.START)
        self.label.set_lines(2)
        self.label.set_max_width_chars(1)  # Wrap to the allocated card width.
        self.wave = Gtk.DrawingArea()
        self.wave.set_size_request(-1, 21)
        self.wave.connect("draw", self.draw_wave)
        body.pack_start(head, False, False, 0)
        body.pack_start(self.label, True, True, 0)
        self.hold_notice = Gtk.Label(label="Mic off for this hold · release and press again", name="status", xalign=0)
        self.hold_notice.set_no_show_all(True)
        body.pack_end(self.hold_notice, False, False, 0)
        body.pack_end(self.wave, False, False, 0)
        self.add(body)
        style = Gtk.CssProvider()
        style.load_from_data(b"""
            #dictation label {font-family: 'Inter', 'Noto Sans', sans-serif; color: #dbe4ff;}
            #dictation #transcript {font-size: 18px; font-weight: 400;}
            #dictation #status {font-size: 13px; font-weight: 600;}
            #dictation #clock, #dictation #keycap {font: 11px 'JetBrains Mono', monospace; color: #acb7db;}
            #dictation #keycap {padding: 0 5px; border: 1px solid rgba(195,210,255,.22); border-radius: 4px;}
            #dictation #hint {font-size: 11px; color: #a9b4ce;}
            #dictation #indicator {font-size: 10px; color: #8ddbd9;}
            #dictation button {min-height: 16px; padding: 1px 7px; border-radius: 6px; background: #313950; color: #dde7ff;}
        """)
        Gtk.StyleContext.add_provider_for_screen(self.get_screen(), style, 600)

    def background(self, widget, cr):
        w, h = self.get_allocated_width(), self.get_allocated_height()
        r = 17
        cr.save()
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        for x, y, angle in ((w-r, r, -90), (w-r, h-r, 0), (r, h-r, 90), (r, r, 180)):
            cr.arc(x, y, r-.5, math.radians(angle), math.radians(angle+90))
        cr.close_path()
        cr.clip_preserve()
        # Retain the actual forest silhouettes at the trailing edge of the card.
        cr.save()
        cr.scale(w / self.forest.get_width(), h / self.forest.get_height())
        Gdk.cairo_set_source_pixbuf(cr, self.forest, 0, 0)
        cr.paint_with_alpha(.92)
        cr.restore()
        glaze = cairo.LinearGradient(0, 0, w, h*.5)
        glaze.add_color_stop_rgba(0, .105, .115, .18, .99)
        glaze.add_color_stop_rgba(.52, .12, .14, .21, .89)
        glaze.add_color_stop_rgba(1, .09, .12, .18, .60)
        cr.set_source(glaze)
        cr.fill_preserve()
        rim = cairo.LinearGradient(0, 0, w*.4, h)
        rim.add_color_stop_rgba(0, .78, .83, 1, .40)
        rim.add_color_stop_rgba(1, .62, .74, .92, .16)
        cr.set_source(rim)
        cr.set_line_width(1.5)
        cr.stroke()
        cr.restore()
        return False

    def clickable(self, enabled):
        region = cairo.Region()
        if enabled:
            region = cairo.Region(cairo.RectangleInt(0, 0, self.get_allocated_width(), self.get_allocated_height()))
        self.get_window().input_shape_combine_region(region, 0, 0)

    def dismiss_recovery(self, *_):
        if self.recovery is not None:
            self.pending.pop()
        if self.pending:
            self.show_recovery()
            return
        if self.hold_notice.get_visible():
            self.actions.hide()
            self.clickable(False)
            self.recovery = None
            self.label.set_text("")
            self.status.set_text("Dictation")
        self.dismiss_result()

    def clear_recoveries(self):
        self.hold_notice.hide()
        self.pending.clear()
        self.hide_card()

    def reject_hold(self):
        self.wave.hide()
        self.hold_notice.show()
        self.set_opacity(1)
        self.show()

    def release_hold(self):
        if self.hold_notice.get_visible():
            self.hold_notice.hide()
            self.wave.show()
            if self.dismiss_on_release:
                self.dismiss_result()

    def dismiss_result(self):
        if self.hold_notice.get_visible():
            self.dismiss_on_release = True
        elif self.pending:
            self.show_recovery()
        else:
            self.hide_card()

    def hide_card(self):
        self.dismiss_on_release = False
        self.serial += 1
        self.recovery = None
        self.actions.hide()
        if self.get_realized():
            self.clickable(False)
        self.hide()

    def finish(self):
        self.listening = False
        self.status.set_text("Finishing")
        self.indicator.set_text("◌")
        self.hint.hide()
        self.escape.hide()

    def recover(self, text, incomplete=False, resume=None, show=True):
        self.pending.append((text, incomplete, resume))
        if show:
            self.show_recovery()

    def show_recovery(self):
        self.dismiss_on_release = False
        text, incomplete, resume = self.pending[-1]
        self.serial += 1
        self.listening = False
        self.recovery = text
        status = "Auto-paste paused" if resume else "Ready to copy"
        if incomplete:
            status = "Partial transcript"
        if len(self.pending) > 1:
            status += f" · {len(self.pending)} left"
        self.status.set_text(status)
        self.indicator.set_text("◇")
        self.clock.hide()
        self.escape.hide()
        self.hint.hide()
        self.label.set_text(text)
        self.actions.show()
        self.resume.set_visible(resume is not None)
        self.show()
        self.set_opacity(1)
        self.clickable(True)

    def resume_paste(self, *_):
        resume = self.pending[-1][2]
        if resume:
            resume()
            self.pending = [(text, incomplete, None if action is resume else action)
                            for text, incomplete, action in self.pending]
            self.show_recovery()

    def sent(self, text):
        self.serial += 1
        self.dismiss_on_release = False
        self.status.set_text("Released")
        self.indicator.set_text("✓")
        self.label.set_text(text)
        serial = self.serial
        def fade():
            if self.serial != serial:
                return False
            if self.hold_notice.get_visible():
                self.dismiss_result()
                return False
            opacity = max(0, self.get_opacity() - .16)
            self.set_opacity(opacity)
            if not opacity:
                self.dismiss_result()
            return opacity > 0
        def begin_fade():
            GLib.timeout_add(16, fade)
            return False
        GLib.timeout_add(700, begin_fade)

    def copy_recovery(self, *_):
        if self.recovery:
            Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(self.recovery, -1)
        self.dismiss_recovery()

    def present_at(self, window):
        self.hide_card()
        self.started = time.monotonic()
        self.listening = True
        self.status.set_text("Listening")
        self.indicator.set_text("●")
        self.clock.set_text("00:00")
        self.label.set_text("Speak now…")
        self.levels = deque([0.] * 90, maxlen=90)
        screen = self.get_display()
        monitor = screen.get_monitor_at_window(window) if window else screen.get_primary_monitor()
        area = (monitor or screen.get_monitor(0)).get_workarea()
        width = min(456, area.width - 24)
        height = 116
        self.set_size_request(width, height)
        self.resize(width, height)
        x = area.x + (area.width - width) // 2
        y = area.y + area.height - height - 20
        self.set_opacity(0)
        self.move(x, y + 18)
        self.show_all()
        serial = self.serial

        def rise():
            if serial != self.serial:
                return False
            progress = min(1, (time.monotonic() - self.started) / .18)
            eased = 1 - (1 - progress)**3
            self.move(x, y + round(18 * (1 - eased)))
            self.set_opacity(eased)
            return progress < 1
        GLib.timeout_add(16, rise)

    def message(self, text, duration):
        self.dismiss_on_release = False
        self.serial += 1
        serial = self.serial
        self.listening = False
        self.set_opacity(1)
        self.hint.hide()
        self.escape.hide()
        self.clock.hide()
        self.status.set_text("Dictation")
        self.indicator.set_text("◇")
        self.label.set_text(text)
        def dismiss():
            if self.serial == serial:
                self.dismiss_result()
            return False
        GLib.timeout_add(duration, dismiss)

    def level(self, rms):
        if self.listening:
            self.levels.append(min(1, math.sqrt(rms / 5200)))
            seconds = int(time.monotonic() - self.started)
            self.clock.set_text(f"{seconds // 60:02d}:{seconds % 60:02d}")
            self.wave.queue_draw()

    def draw_wave(self, widget, cr):
        w, h = widget.get_allocated_width(), widget.get_allocated_height()
        mid = h / 2
        ink = cairo.LinearGradient(0, 0, w, 0)
        for at, rgb in ((0, (.54,.48,.93)), (.35, (.53,.61,1)), (.70, (.36,.79,.99)), (1, (.50,.91,.85))):
            ink.add_color_stop_rgba(at, *rgb, .30 + .69 * min(1, at*5))
        cr.set_source(ink)
        cr.set_line_width(2.0)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        for i, amplitude in enumerate(self.levels):
            x = 1 + (w-2) * i / (self.levels.maxlen-1)
            height = max(.2, amplitude * (mid-2))
            cr.move_to(x, mid-height)
            cr.line_to(x, mid+height)
        cr.stroke()
