"""Single-use streams to explicitly armed Chrome fields (Linux native messaging)."""
import json
import os
from pathlib import Path
import socket
import stat
import struct
import time

BROWSER_CLASSES = {"google-chrome", "chromium", "chromium-browser", "com.t3tools.t3code"}
MAX_FRAME = 65536


def is_browser_class(wm_class):
    return any(name.lower() in BROWSER_CLASSES for name in wm_class or ())


def private_directory():
    path = Path(os.environ["XDG_RUNTIME_DIR"]) / "desktop-dictation-fields"
    path.mkdir(mode=0o700, exist_ok=True)
    info = path.lstat()
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700 or not stat.S_ISDIR(info.st_mode):
        raise PermissionError("Expected a private runtime directory")
    return path


def read_message(stream):
    header = stream.read(4)
    if len(header) != 4:
        raise EOFError
    size, = struct.unpack("=I", header)
    if size > MAX_FRAME:
        raise ValueError("Oversize field message")
    data = stream.read(size)
    if len(data) != size:
        raise EOFError
    return json.loads(data)


def write_message(stream, message):
    data = json.dumps(message, ensure_ascii=False).encode()
    if len(data) > MAX_FRAME:
        raise ValueError("Oversize field message")
    stream.write(struct.pack("=I", len(data)) + data)
    stream.flush()


def capture_field(client):
    if client[0] != "process":
        return None
    sock = socket.socket(socket.AF_UNIX)
    try:
        path = private_directory() / f"{client[1]}.sock"
        sock.settimeout(0.4)
        sock.connect(str(path))
        pid, uid, _ = struct.unpack("3i", sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
        parent = int(Path(f"/proc/{pid}/stat").read_bytes().rsplit(b")", 1)[1].split()[1])
        if uid != os.getuid() or parent != client[1] or sock.recv(1) != b"1":
            sock.close()
            return None
        return sock
    except (OSError, KeyError, ValueError, IndexError):
        sock.close()
        return None


def commit_field(sock, text):
    if sock is None or not 0 < len(text) <= 8192:
        return False
    try:
        with sock.makefile("rwb") as stream:
            write_message(stream, {"text": text, "deadline": time.time_ns() // 1_000_000 + 350})
            reply = read_message(stream)
            return isinstance(reply, dict) and reply.get("ok") is True
    except (EOFError, OSError, ValueError):
        return False
