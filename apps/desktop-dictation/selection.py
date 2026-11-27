"""Serve the clipboard on the X connection used to guard and dispatch a paste."""
from pathlib import Path

from Xlib import X, Xatom, error
from Xlib.protocol import request as protocol_request, rq
from Xlib.protocol.event import SelectionNotify


# python-xlib does not ship bindings for X-Resource. Issue the two XRes
# requests on the selection owner's connection, which can hold a server grab.
class XResVersion(rq.ReplyRequest):
    _request = rq.Struct(rq.Card8("opcode"), rq.Opcode(0), rq.RequestLength(),
                         rq.Card8("major"), rq.Card8("minor"), rq.Pad(2))
    _reply = rq.Struct(rq.Pad(2), rq.Card16("sequence_number"), rq.Pad(4),
                       rq.Card16("major"), rq.Card16("minor"), rq.Pad(20))


class QueryClientIds(rq.ReplyRequest):
    _request = rq.Struct(rq.Card8("opcode"), rq.Opcode(4), rq.RequestLength(),
                         rq.Card32("count"), rq.Card32("client"), rq.Card32("mask"))
    _reply = rq.Struct(rq.Pad(2), rq.Card16("sequence_number"), rq.ReplyLength(),
                       rq.Card32("count"), rq.Pad(20), rq.List("words", rq.Card32Obj))


LOCAL_CLIENT_PID_MASK = 2


def xres_opcode(x):
    extension = x.query_extension("X-Resource")
    if extension:
        try:
            version = XResVersion(display=x.display, opcode=extension.major_opcode, major=1, minor=2)
            if (version.major, version.minor) >= (1, 2):
                return extension.major_opcode
        except error.XError:
            pass
    return None


class TextSelection:
    def __init__(self, x):
        self.x = x
        self.xres = xres_opcode(x)
        self.atom = x.intern_atom("CLIPBOARD")
        self.window = x.screen().root.create_window(
            0, 0, 1, 1, 0, 0, X.InputOnly, X.CopyFromParent)
        self.targets = x.intern_atom("TARGETS")
        self.timestamp = x.intern_atom("TIMESTAMP")
        self.formats = {x.intern_atom(name): encoding for name, encoding in (
            ("UTF8_STRING", "utf-8"), ("text/plain;charset=utf-8", "utf-8"),
            ("text/plain", "utf-8"), ("TEXT", "utf-8"), ("STRING", "latin-1"))}
        self.text_atom = x.intern_atom("TEXT")
        self.utf8 = x.intern_atom("UTF8_STRING")
        self.compound = x.intern_atom("COMPOUND_TEXT")
        self.press_time = None
        self.saved = None
        self.recipient = None
        self.other_clients = {}
        # Processes whose delayed shortcut could read the selection we serve.
        self.guarded_reads = set()
        self.restore = None
        self.text = ""
        self.time = 0

    def client_id(self, window_id):
        base = window_id & ~self.x.display.info.resource_id_mask
        if self.xres and base:
            try:
                ids = QueryClientIds(display=self.x.display, opcode=self.xres, count=1,
                                     client=window_id, mask=LOCAL_CLIENT_PID_MASK)
                # One ClientIdValue: connection base, mask, byte length, PID.
                if ids.count == 1 and list(ids.words[:3]) == [base, LOCAL_CLIENT_PID_MASK, 4] and len(ids.words) == 4:
                    pid = ids.words[3]
                    # A paused paste can outlive the process. Include its Linux
                    # start time (stat field 22; comm may contain parentheses).
                    stat = Path(f"/proc/{pid}/stat").read_bytes()
                    return ("process", pid, int(stat.rsplit(b")", 1)[1].split()[19]))
            except (error.XError, OSError, IndexError, ValueError):
                pass
        return ("connection", base)

    def claim(self, text, timestamp, recipient, backup, on_read):
        self.window.set_selection_owner(self.atom, timestamp)
        if self.x.get_selection_owner(self.atom) != self.window:
            return False
        self.saved = None
        self.press_time = None
        self.recipient = recipient
        self.other_clients = backup.values
        self.restore = on_read
        self.text = text
        self.time = timestamp
        return True

    def copy(self, text, timestamp, paused_clients):
        self.window.set_selection_owner(self.atom, X.CurrentTime)
        self.saved = None
        self.text = text
        self.time = timestamp
        self.guarded_reads = set(paused_clients)
        self.x.flush()

    def empty_text_format(self, target, saved):
        if saved is not None and target in saved:
            if (target in self.formats or target == self.compound or
                    self.x.get_atom_name(target).lower().startswith("text/")):
                return saved[target][:2]
        elif target in self.formats:
            return (self.utf8 if target == self.text_atom else target), 8
        return None

    def serve(self, request):
        prop = request.property or request.target
        target = request.target
        client = self.client_id(request.requestor.id)
        saved = self.saved
        recipient = self.restore is not None and client == self.recipient
        delivering = recipient and request.time != X.CurrentTime and request.time == self.press_time
        # An unidentified second connection could belong to the target. Keep
        # the previous clipboard private until a distinct process is proven.
        unknown_reader = client[0] != "process" and (self.restore is not None or bool(self.guarded_reads))
        if self.restore and not recipient and not unknown_reader:
            saved = self.other_clients
        guard = client in self.guarded_reads or unknown_reader or (recipient and not delivering)
        if request.selection != self.atom:
            prop = X.NONE
        elif target == self.targets:
            request.requestor.change_property(prop, Xatom.ATOM, 32,
                                              [self.targets, self.timestamp, *(saved if saved is not None else self.formats)])
        elif target == self.timestamp:
            request.requestor.change_property(prop, Xatom.INTEGER, 32, [self.time])
        elif guard and (empty_format := self.empty_text_format(target, saved)):
            # A clipboard read cannot identify the field or retire a delayed shortcut.
            type_atom, bits = empty_format
            request.requestor.change_property(prop, type_atom, bits, b"")
        elif saved is not None:
            if target in saved:
                type_atom, bits, data = saved[target]
                block = 128 * 1024
                request.requestor.change_property(prop, type_atom, bits, data[:block])
                for offset in range(block, len(data), block):
                    request.requestor.change_property(prop, type_atom, bits, data[offset:offset+block], X.PropModeAppend)
            else:
                prop = X.NONE
        elif target in self.formats:
            value = self.text.encode(self.formats[target], errors="replace")
            type_atom = self.utf8 if target == self.text_atom else target
            request.requestor.change_property(prop, type_atom, 8, value)
        else:
            prop = X.NONE
        request.requestor.send_event(SelectionNotify(
            time=request.time, requestor=request.requestor, selection=request.selection,
            target=target, property=prop))
        self.x.flush()
        if delivering and not guard and prop and target in self.formats:
            self.restore()

    def put_back(self, backup, late_client=None):
        self.restore = None
        self.recipient = None
        self.other_clients = {}
        self.text = ""
        self.x.grab_server()
        try:
            if self.x.get_selection_owner(self.atom) == self.window:
                self._restore_owned(backup)
                # Only our restored selection can receive this delayed request.
                if backup.values and late_client is not None:
                    self.guarded_reads.add(late_client)
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
