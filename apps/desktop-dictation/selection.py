"""Serve the clipboard on the X connection used to guard and dispatch a paste."""
from Xlib import X, Xatom
from Xlib.protocol import request as protocol_request
from Xlib.protocol.event import SelectionNotify


class TextSelection:
    def __init__(self, x):
        self.x = x
        self.atom = x.intern_atom("CLIPBOARD")
        self.window = x.screen().root.create_window(
            0, 0, 1, 1, 0, 0, X.InputOnly, X.CopyFromParent)
        self.targets = x.intern_atom("TARGETS")
        self.timestamp = x.intern_atom("TIMESTAMP")
        self.formats = {x.intern_atom(name): encoding for name, encoding in (
            ("UTF8_STRING", "utf-8"), ("text/plain;charset=utf-8", "utf-8"),
            ("text/plain", "utf-8"), ("TEXT", "utf-8"), ("STRING", "latin-1"))}
        self.saved = None
        self.restore = None
        self.text = ""
        self.time = 0

    def claim(self, text, timestamp, on_read):
        self.window.set_selection_owner(self.atom, timestamp)
        if self.x.get_selection_owner(self.atom) != self.window:
            return False
        self.saved = None
        self.restore = on_read
        self.text = text
        self.time = timestamp
        return True

    def serve(self, request):
        prop = request.property or request.target
        target = request.target
        if request.selection != self.atom:
            prop = X.NONE
        elif target == self.targets:
            request.requestor.change_property(prop, Xatom.ATOM, 32,
                                              [self.targets, self.timestamp, *(self.saved if self.saved is not None else self.formats)])
        elif target == self.timestamp:
            request.requestor.change_property(prop, Xatom.INTEGER, 32, [self.time])
        elif self.saved is not None:
            if target in self.saved:
                type_atom, bits, data = self.saved[target]
                block = 128 * 1024
                request.requestor.change_property(prop, type_atom, bits, data[:block])
                for offset in range(block, len(data), block):
                    request.requestor.change_property(prop, type_atom, bits, data[offset:offset+block], X.PropModeAppend)
            else:
                prop = X.NONE
        elif target in self.formats:
            value = self.text.encode(self.formats[target], errors="replace")
            request.requestor.change_property(prop, target, 8, value)
        else:
            prop = X.NONE
        request.requestor.send_event(SelectionNotify(
            time=request.time, requestor=request.requestor, selection=request.selection,
            target=target, property=prop))
        self.x.flush()
        if self.restore and prop and target in self.formats:
            self.restore(request.requestor.id)

    def put_back(self, backup):
        self.restore = None
        self.text = ""
        self.x.grab_server()
        try:
            if self.x.get_selection_owner(self.atom) == self.window:
                self._restore_owned(backup)
            else:
                self.saved = None
        finally:
            self.x.ungrab_server()
            self.x.flush()

    def _restore_owned(self, backup):
        self.saved = backup.values
        # Reassert ownership so interested clipboard managers refresh TARGETS.
        if self.saved:
            self.window.set_selection_owner(self.atom, X.CurrentTime)
        else:
            protocol_request.SetSelectionOwner(display=self.x.display, window=X.NONE,
                                      selection=self.atom, time=X.CurrentTime)
        self.x.flush()


class ClipboardBackup:
    """Back up passive clipboard formats while speaking, retaining their original bytes."""
    def __init__(self, clipboard, x, owner):
        self.ready = not owner
        self.values = {}
        if owner:
            clipboard.request_targets(self._targets, x)

    def _targets(self, clipboard, targets, count, x):
        names = {atom.name() for atom in targets or ()}
        names -= {"TARGETS", "TIMESTAMP", "MULTIPLE", "SAVE_TARGETS"}
        safe = {"TEXT", "STRING", "UTF8_STRING", "COMPOUND_TEXT"}
        if not names or len(names) > 32 or any(n not in safe and "/" not in n for n in names):
            return
        remaining = set(names)
        budget = 24 * 1024 * 1024
        def received(_clipboard, data, name):
            nonlocal budget
            if data.get_length() < 0 or data.get_length() > min(8 * 1024 * 1024, budget):
                return
            payload = bytes(data.get_data() or b"")
            budget -= len(payload)
            self.values[x.intern_atom(name)] = (
                x.intern_atom(data.get_data_type().name()), data.get_format(), payload)
            remaining.remove(name)
            self.ready = not remaining
        for atom in targets:
            if atom.name() in names:
                clipboard.request_contents(atom, received, atom.name())
