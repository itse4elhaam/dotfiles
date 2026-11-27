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
        self.saved = None
        self.recipient = None
        self.other_clients = {}
        # Outstanding shortcuts survive ownership changes. Only suppress reads
        # while serving a restored selection or an explicitly guarded copy.
        self.outstanding = set()
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
        self.recipient = recipient
        self.other_clients = backup.values
        self.restore = on_read
        self.text = text
        self.time = timestamp
        return True

    def copy(self, text, timestamp):
        self.window.set_selection_owner(self.atom, X.CurrentTime)
        self.saved = None
        self.text = text
        self.time = timestamp
        self.guarded_reads = self.outstanding.copy()
        self.x.flush()

    def serve(self, request):
        prop = request.property or request.target
        target = request.target
        client = self.client_id(request.requestor.id)
        saved = self.saved
        delivering = self.restore is not None and client == self.recipient
        if self.restore and not delivering:
            saved = self.other_clients
        if request.selection != self.atom:
            prop = X.NONE
        elif target == self.targets:
            request.requestor.change_property(prop, Xatom.ATOM, 32,
                                              [self.targets, self.timestamp, *(saved if saved is not None else self.formats)])
        elif target == self.timestamp:
            request.requestor.change_property(prop, Xatom.INTEGER, 32, [self.time])
        elif client in self.guarded_reads and target in self.formats:
            # Complete one late text read without inserting unrelated clipboard
            # data into the field. Other clients still get the restored formats.
            request.requestor.change_property(prop, target, 8, b"")
            self.guarded_reads.discard(client)
            self.outstanding.discard(client)
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
            request.requestor.change_property(prop, target, 8, value)
        else:
            prop = X.NONE
        request.requestor.send_event(SelectionNotify(
            time=request.time, requestor=request.requestor, selection=request.selection,
            target=target, property=prop))
        self.x.flush()
        if delivering and prop and target in self.formats:
            self.restore()

    def put_back(self, backup, late_client=None):
        self.restore = None
        self.recipient = None
        self.other_clients = {}
        self.text = ""
        if late_client is not None:
            self.outstanding.add(late_client)
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
