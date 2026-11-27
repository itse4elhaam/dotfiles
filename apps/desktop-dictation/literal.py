"""Plan a bounded string of printable X11 key strokes for Chromium editors."""
from Xlib import X
from Xlib.ext import xtest
from Xlib.protocol import rq
from gi.repository import Gdk

BROWSER_CLASSES = {"google-chrome", "chromium", "chromium-browser", "com.t3tools.t3code"}
MAX_CHARACTERS = 256


def is_browser_class(wm_class):
    return bool(wm_class and wm_class[-1].lower() in BROWSER_CLASSES)


# python-xlib has no XKB bindings. Observe mapping changes on the *guard*
# connection so one arriving during GDK translation invalidates the plan.
class UseExtension(rq.ReplyRequest):
    _request = rq.Struct(rq.Card8("opcode"), rq.Opcode(0), rq.RequestLength(),
                         rq.Card16("major"), rq.Card16("minor"))
    _reply = rq.Struct(rq.Pad(1), rq.Card8("supported"), rq.Card16("sequence_number"), rq.Pad(28))


class SelectMap(rq.Request):
    _request = rq.Struct(rq.Card8("opcode"), rq.Opcode(1), rq.RequestLength(),
                         rq.Card16("device"), rq.Card16("which"), rq.Card16("clear"),
                         rq.Card16("all"), rq.Card16("affect_map"), rq.Card16("map"))


class GetState(rq.ReplyRequest):
    _request = rq.Struct(rq.Card8("opcode"), rq.Opcode(4), rq.RequestLength(), rq.Card16("device"), rq.Pad(2))
    _reply = rq.Struct(rq.Pad(2), rq.Card16("sequence_number"), rq.Pad(4),
                       rq.Card8("mods"), rq.Card8("base"), rq.Card8("latched"),
                       rq.Card8("locked"), rq.Card8("group"), rq.Card8("locked_group"),
                       rq.Int16("base_group"), rq.Int16("latched_group"), rq.Pad(14))


def watch_layout(x):
    ext = x.query_extension("XKEYBOARD")
    if ext and UseExtension(display=x.display, opcode=ext.major_opcode, major=1, minor=0).supported:
        # NewKeyboardNotify and MapNotify, all eight mapping components.
        SelectMap(display=x.display, opcode=ext.major_opcode, device=0x100, which=3,
                  clear=0, all=3, affect_map=255, map=255)
        return ext.major_opcode


def keyboard_state(x, opcode):
    if opcode:
        s = GetState(display=x.display, opcode=opcode, device=0x100)
        if not (s.base or s.latched or s.base_group or s.latched_group):
            return s.group, s.mods
    return None


def plan_text(x, state, text):
    if not state or len(text) > MAX_CHARACTERS or not text.isprintable():
        return None
    group, mods = state
    # A fresh GDK connection reads the current XKB map even if the main
    # loop has not processed a keys-changed notification yet.
    layout_display = Gdk.Display.open(Gdk.Display.get_default().get_name())
    if not layout_display:
        return None
    try:
        keymap = Gdk.Keymap.get_for_display(layout_display)
        modifiers = x.get_modifier_mapping()
        modifier_codes = set().union(*modifiers)
        allowed = 0
        shift = None
        for index, codes in enumerate(modifiers):
            symbols = {code: keymap.translate_keyboard_state(code, Gdk.ModifierType(0), group).keyval
                       for code in codes if code}
            mask = 1 << index
            if mask == X.LockMask and set(symbols.values()) == {Gdk.KEY_Caps_Lock}:
                allowed |= mask
            if mask == X.Mod2Mask and set(symbols.values()) == {Gdk.KEY_Num_Lock}:
                allowed |= mask
            if mask == X.ShiftMask:
                shift = next((code for code, sym in symbols.items() if sym == Gdk.KEY_Shift_L), None)
        if mods & ~allowed or not shift or any(shift in codes for codes in modifiers[1:]):
            return None
        strokes = {}
        for char in set(text):
            stroke = printable_stroke(keymap, group, mods, modifier_codes, char)
            if stroke is None:
                return None
            strokes[char] = stroke
        return shift, [strokes[char] for char in text]
    finally:
        layout_display.close()


def printable_stroke(keymap, group, mods, modifier_codes, char):
    sym = Gdk.unicode_to_keyval(ord(char))
    found, entries = keymap.get_entries_for_keyval(sym)
    if found:
        for entry in entries:
            if entry.keycode in modifier_codes or entry.group != group or entry.level > 1:
                continue
            for shift_mask in (0, X.ShiftMask):
                ok, translated, effective, level, _ = keymap.translate_keyboard_state(
                    entry.keycode, Gdk.ModifierType(mods | shift_mask), group)
                if ok and translated == sym and effective == group and level <= 1:
                    return entry.keycode, bool(shift_mask)
    return None


def type_text(x, plan):
    shift, strokes = plan
    for code, shifted in strokes:
        if shifted:
            xtest.fake_input(x, X.KeyPress, shift)
        xtest.fake_input(x, X.KeyPress, code)
        xtest.fake_input(x, X.KeyRelease, code)
        if shifted:
            xtest.fake_input(x, X.KeyRelease, shift)
