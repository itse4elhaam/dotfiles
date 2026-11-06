#!/usr/bin/python3
"""Offline checks. Never launches apps or moves desktop windows."""
from pathlib import Path
import runpy
import struct

r = runpy.run_path(str(Path(__file__).with_name('desktop-recovery')))
windows = r['parse_windows']('''0x001  0 0 40 1920 1160 microsoft-edge.Microsoft-edge host Messages and 15 more pages
0x002  1 0 40 1920 1160 microsoft-edge.Microsoft-edge host YouTube
0x003  2 0 40 1920 1160 crx__zoho.Microsoft-edge host Zoho Mail
''')
assert windows[0] == dict(id='0x001', workspace=0, cls=r['EDGE'], title='Messages and 15 more pages')
monitors = r['monitors']('''Monitors: 2
 0: +HDMI-1 2560/600x1440/340+0+0 HDMI-1
 1: +*eDP-1 1920/302x1200/189+2560+240 eDP-1
''')
assert monitors[0]['primary'] and monitors[0]['x'] == 2560
assert monitors[1]['x'] == 0
assert r['monitors']('Monitors: 1\n 0: +*DP-1 1920/300x1080/200-1920+0 DP-1')[0]['x'] == -1920


def command(identifier, payload):
    return struct.pack('<HB', len(payload) + 1, identifier) + payload


def integers(identifier, *values):
    return command(identifier, struct.pack('<' + 'i' * len(values), *values))


def navigation(tab, index, url, title):
    encoded = url.encode()
    payload = struct.pack('<iii', tab, index, len(encoded)) + encoded
    payload += b'\0' * (-len(payload) % 4)
    payload += struct.pack('<i', len(title)) + title.encode('utf-16-le')
    return command(6, struct.pack('<I', len(payload)) + payload)


session = b'SNSS' + struct.pack('<I', 3)
for wid, tid, url, title in [(1, 11, 'https://www.upwork.com/ab/messages', 'Messages'),
                              (1, 12, 'https://upwork.com/jobs', 'Jobs'),
                              (2, 21, 'https://youtube.com/', 'YouTube'),
                              (2, 22, 'https://upwork.com.evil.example/', 'Other')]:
    session += integers(0, wid, tid) + integers(2, tid, 0 if tid in (11, 21) else 1)
    session += integers(7, tid, 1) + navigation(tid, 1, url, title)
# Historical Upwork visits must not inflate the count. A closed tab must not count.
session += navigation(21, 0, 'https://upwork.com/jobs', 'Old job')
session += integers(0, 1, 13) + navigation(13, 0, 'https://upwork.com/', 'Closed')
session += integers(16, 13)
parsed = r['edge_sessions'](session + b'\xff\x7f\x06partial')
assert [(w['tabs'], w['upwork']) for w in parsed] == [(2, 2), (2, 0)]
assert r['browser_workspaces'](windows[:2], parsed) == {'0x001': 1, '0x002': 0}
# Saved desktop positions handle equal counts without gratuitously swapping windows.
parsed[1]['upwork'] = 2
assert r['browser_workspaces'](windows[:2], parsed) == {'0x001': 0, '0x002': 1}
try:
    r['browser_workspaces'](windows[:2], [])
except RuntimeError:
    pass
else:
    raise AssertionError('Missing sessions must not silently misplace Edge')
print('Window parsing, monitor geometry, session tab counts and Edge placement passed.')
