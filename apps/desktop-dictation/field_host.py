#!/usr/bin/python3
"""Chrome starts this host for one extension invocation and one edit."""
import fcntl
import os
import select
import socket
import sys
from browser_field import private_directory, read_message, write_message


def main():
    if sys.argv[1:2] != ["chrome-extension://klchocbgbfpleclhlhnheaklnlofodpk/"]:
        return
    incoming, outgoing = sys.stdin.buffer, sys.stdout.buffer
    if read_message(incoming) != {"armed": True}:
        return
    path = private_directory() / f"{os.getppid()}.sock"
    # Chrome can terminate a native host without letting it unlink the socket.
    # Reclaim it only while holding the browser-specific, kernel-released lock.
    with path.with_suffix(".lock").open("a") as lock, socket.socket(socket.AF_UNIX) as server:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        path.unlink(missing_ok=True)
        server.bind(str(path))
        try:
            server.listen(1)
            write_message(outgoing, {"ready": True})
            ready, _, _ = select.select([server, incoming], [], [], 360)
            if incoming in ready or server not in ready:
                return
            with server.accept()[0] as conn, conn.makefile("rwb") as stream:
                conn.sendall(b"1")
                ready, _, _ = select.select([conn, incoming], [], [], 360)
                if incoming in ready or conn not in ready:
                    return
                conn.settimeout(1)
                message = read_message(stream)
                write_message(outgoing, message)
                if select.select([incoming], [], [], 1)[0]:
                    write_message(stream, read_message(incoming))
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    try:
        main()
    except (EOFError, OSError, KeyError, ValueError):
        pass
