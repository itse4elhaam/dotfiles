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
MAX_GESTURES = 65536


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
        self.gestures = {}  # Dispatched V timestamp -> process identity (None on collision)
        self.replay = None
        self.press_time = None
        self.allow_current_time = False
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
        # Keep exact tombstones even across clock wrap. At capacity use Copy
        # until restart instead of forgetting a potentially queued conversion.
        if len(self.gestures) >= MAX_GESTURES:
            return False
        self.replay = None
        self.window.set_selection_owner(self.atom, timestamp)
        if self.x.get_selection_owner(self.atom) != self.window:
            return False
        self.saved = None
        self.press_time = None
        self.allow_current_time = False
        self.recipient = recipient
        self.other_clients = backup.values
        self.restore = on_read
        self.text = text
        self.time = timestamp
        return True

    def dispatch(self, timestamp):
        self.press_time = timestamp
        # A wrapped timestamp can name two queued gestures. Suppress reads
        # for that time regardless of which process eventually converts it.
        self.allow_current_time = bool(timestamp) and timestamp not in self.gestures
        if timestamp:
            self.gestures[timestamp] = self.recipient if self.allow_current_time else None

    def copy(self, text, timestamp, paused_clients):
        self.replay = None
        self.window.set_selection_owner(self.atom, X.CurrentTime)
        self.saved = None
        self.text = text
        self.time = timestamp
        self.guarded_reads = set(paused_clients)
        self.x.flush()

    def serve(self, request, interrupted_client=None):
        prop = request.property or request.target
        target = request.target
        client = self.client_id(request.requestor.id)
        saved = self.saved
        recipient = self.restore is not None and client == self.recipient
        previous = self.gestures.get(request.time)
        delivering = (recipient and previous == client and request.time == self.press_time
                      and self.replay is None)
        # CurrentTime identifies neither the shortcut nor the field. Treat a
        # matching process's read during this one outstanding paste as a read
        # of its offer. A delayed callback and a fresh read look identical.
        untagged = (recipient and self.allow_current_time and request.time == X.CurrentTime)
        # An unidentified second connection could belong to the target. Keep
        # the previous clipboard private until a distinct process is proven.
        unknown_reader = client[0] != "process" and (
            self.restore is not None or bool(self.guarded_reads) or interrupted_client is not None)
        if self.restore and not recipient and not unknown_reader:
            saved = self.other_clients
        guard = client == interrupted_client or client in self.guarded_reads or unknown_reader
        # Requests carrying an old V timestamp can arrive after restore,
        # Copy or Resume. Only the most recent successful offer can replay.
        repeated = (request.time in self.gestures and not delivering
                    and (previous is None or previous == client or client[0] != "process"))
        value_text = self.text
        if repeated:
            saved = None
            if previous == client and self.replay and request.time == self.replay[0]:
                value_text = self.replay[1]
            else:
                guard = True
        elif recipient and not delivering and not untagged:
            guard = True
        # Refuse the whole conversion, including TARGETS and fallback formats.
        # A successful empty payload tells GTK to replace the selected text.
        if request.selection != self.atom or guard:
            prop = X.NONE
        elif target == self.targets:
            request.requestor.change_property(prop, Xatom.ATOM, 32,
                                              [self.targets, self.timestamp, *(saved if saved is not None else self.formats)])
        elif target == self.timestamp:
            request.requestor.change_property(prop, Xatom.INTEGER, 32, [self.time])
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
            value = value_text.encode(self.formats[target], errors="replace")
            type_atom = self.utf8 if target == self.text_atom else target
            request.requestor.change_property(prop, type_atom, 8, value)
        else:
            prop = X.NONE
        self.notify(request, prop)
        if not recipient or guard or request.selection != self.atom:
            return
        if self.replay:
            # After a CurrentTime payload, an editor can switch timestamps as
            # it negotiates further formats. Even a refusal can lead to a
            # fallback read. Keep the offer until that negotiation goes quiet.
            if self.allow_current_time and request.time in (X.CurrentTime, self.press_time):
                self.restore(untagged=True)
        elif (untagged or delivering) and prop and target in self.formats:
            self.allow_current_time = untagged
            self.replay = (self.press_time, self.text)
            self.restore(untagged=untagged)

    def notify(self, request, prop):
        request.requestor.send_event(SelectionNotify(
            time=request.time, requestor=request.requestor, selection=request.selection,
            target=request.target, property=prop))
        self.x.flush()

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
    def __init__(self, clipboard, x, owner, saved=None):
        self.ready = saved is not None or not owner
        self.values = {} if saved is None else saved
        if not self.ready:
            clipboard.request_targets(self._targets, x)

    # Gtk.Clipboard.set_image on Pop!_OS advertises one pixbuf through these
    # encoders in order. ICO cannot encode a large screenshot. Match the full
    # offer, since a subset or an extra target can be independently authored.
    _gtk_image_offer = (
        "TIMESTAMP", "TARGETS", "MULTIPLE", "SAVE_TARGETS", "image/png", "image/jpeg",
        "image/bmp", "image/x-bmp", "image/x-MS-bmp", "image/x-icon", "image/x-ico",
        "image/x-win-bitmap", "image/vnd.microsoft.icon", "application/ico",
        "image/ico", "image/icon", "text/ico", "image/tiff",
    )

    @staticmethod
    def _valid_png(data, payload):
        if (data.get_format() != 8 or data.get_data_type().name() != "image/png"
                or not payload.startswith(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")
                or not payload.endswith(b"\x00\x00\x00\x00IEND\xaeB`\x82")):
            return False
        width = int.from_bytes(payload[16:20], "big")
        height = int.from_bytes(payload[20:24], "big")
        # Bound the decoded RGBA allocation independently of compressed size.
        if not (0 < width * height <= 16 * 1024 * 1024):
            return False
        image = data.get_pixbuf()
        return image is not None and (image.get_width(), image.get_height()) == (width, height)

    def _targets(self, clipboard, targets, count, x):
        if not targets or count != len(targets):
            return
        atoms = {atom.name(): atom for atom in targets}
        gtk_image = tuple(atom.name() for atom in targets) == self._gtk_image_offer
        protocol = {"TIMESTAMP", "TARGETS", "MULTIPLE", "SAVE_TARGETS"}
        names = ["image/png"] if gtk_image else [name for name in atoms if name not in protocol]
        safe = {"TEXT", "STRING", "UTF8_STRING", "COMPOUND_TEXT"}
        if not names or len(names) > 32 or any(n not in safe and "/" not in n for n in names):
            return

        values = {}
        budget = 24 * 1024 * 1024

        def received(_clipboard, data, name):
            nonlocal budget
            size = data.get_length()
            if not 0 <= size <= min(8 * 1024 * 1024, budget):
                return
            bits = data.get_format()
            # GDK can expose format-32 words as native longs. Only retain
            # formats whose bytes can be replayed directly as X11 elements.
            if bits not in (8, 16) or size % (bits // 8) or not data.get_data_type():
                return
            payload = bytes(data.get_data() or b"")
            if len(payload) != size or (gtk_image and not self._valid_png(data, payload)):
                return
            budget -= size
            values[x.intern_atom(name)] = (
                x.intern_atom(data.get_data_type().name()), bits, payload)
            if len(values) == len(names):
                self.values = values
                self.ready = True
            else:
                next_name = names[len(values)]
                clipboard.request_contents(atoms[next_name], received, next_name)

        clipboard.request_contents(atoms[names[0]], received, names[0])
