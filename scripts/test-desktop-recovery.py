#!/usr/bin/python3
"""Offline checks; --x11-staging also uses invisible, unmapped X11 windows."""
from pathlib import Path
import runpy
import struct
import sys
import time
import tempfile
from contextlib import nullcontext
from unittest.mock import patch

r = runpy.run_path(str(Path(__file__).with_name('desktop-recovery')))
windows = r['parse_windows']('''0x001  0 0 40 1920 1160 microsoft-edge.Microsoft-edge host Messages and 15 more pages
0x002  1 0 40 1920 1160 microsoft-edge.Microsoft-edge host YouTube
0x003  2 0 40 1920 1160 crx__zoho.Microsoft-edge host Zoho Mail
''')
assert windows[0] == dict(id='0x001', workspace=0, x=0, y=40, width=1920, height=1160,
                          cls=r['EDGE'], title='Messages and 15 more pages')
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
assert [w['tabs'] for w in parsed] == [2, 2]
parsed[0]['workspace'], parsed[1]['workspace'] = 0, 1
assert r['edge_inventory'](parsed, windows[:2]) == {'0x001': parsed[0], '0x002': parsed[1]}
assert r['edge_inventory'](parsed, [dict(windows[0], title='Unknown'), windows[1]]) is None

# The real cold gate waits for a fresh inventory with every saved tab and workspace.
g = r['recover_edge'].__globals__
with tempfile.TemporaryDirectory() as directory:
    state = Path(directory)
    baseline = state / 'Session_1'
    baseline.write_bytes(session)
    ready_observations = []
    saved = [dict(item) for item in parsed]
    def wait(match, settle, ready, timeout, **kwargs):
        for observed in ([dict(item, tabs=1) for item in saved],
                         [dict(saved[0], workspace=1), dict(saved[1], workspace=0)],
                         saved):
            with patch.dict(g, {'edge_snapshot': lambda: (state / 'Session_2', observed)}):
                ready_observations.append(ready(windows[:2]))
        assert ready_observations == [False, False, True]
        return windows[:2]

    def parse(_):
        return saved

    with patch.dict(g, {'STATE': state, 'windows': lambda: [],
                        'edge_snapshot': lambda: (baseline, saved),
                        'edge_sessions': parse, 'backup_edge': lambda: state,
                        'launch': lambda *args: None, 'wait_for_windows': wait}):
        r['recover_edge']()
    assert not (state / 'edge-restore-pending').exists()

# Run the full orchestration with a fake desktop and a controlled stage failure.
g = r['recover'].__globals__
for failure in (None, 'Edge', 'Discord'):
    desktop = [dict(w) for w in windows[:2]] + [
        dict(id='other', cls='editor.Editor', workspace=0)]
    events = []

    def edge():
        events.append('Edge')
        if failure == 'Edge':
            raise RuntimeError('window_timeout observed=1 timeout_seconds=60')

    def ensure(match, command, workspace, monitor):
        cls = {0: 'com.t3tools.t3code.com.t3tools.T3Code', 3: 'ghostty.Ghostty',
               5: r['WHATSAPP']}.get(workspace)
        if workspace == 4:
            cls = r['ZOHO'] if command[0] == 'microsoft-edge' else 'discord.discord'
        events.append(cls)
        if failure == 'Discord' and cls == 'discord.discord':
            raise FileNotFoundError()
        window = dict(id=cls, cls=cls, workspace=-1, x=0, y=0, width=800, height=600)
        assert match(window)
        desktop.append(window)
        return [window]

    def place(window, workspace, monitor):
        window['workspace'] = workspace

    def ghostty(match, workspace, monitor):
        current = ensure(match, ['ghostty'], workspace, monitor)
        place(current[0], workspace, monitor)
        return current

    with tempfile.TemporaryDirectory() as directory, patch.dict(g, {
        'STATE': Path(directory), 'windows': lambda: desktop,
        'run': lambda *args: 'Monitors: 1\n 0: +*DP-1 1920/300x1080/200+0+0 DP-1' if args[0] == 'xrandr' else 'desktop\n' * 6,
        'quiet_launches': nullcontext, 'ensure_app': ensure, 'recover_edge': edge,
        'place': place, 'recover_ghostty': ghostty, 'connect_earbuds': lambda: events.append('Bluetooth') or 'Connected.',
        'notify': lambda message: None,
    }), patch.dict('os.environ', {'XDG_SESSION_TYPE': 'x11', 'XDG_RUNTIME_DIR': directory}), \
            patch.object(g['subprocess'], 'run') as commands, \
            patch.object(g['time'], 'sleep'), patch.object(g['time'], 'monotonic', side_effect=range(1000)):
        g['configure_logging']()
        try:
            r['recover']()
        except RuntimeError as error:
            assert failure and failure in str(error)
        else:
            assert failure is None
        finally:
            for handler in g['LOG'].handlers[:]:
                g['LOG'].removeHandler(handler)
                handler.close()
        log = (Path(directory) / 'recovery.log').read_text()
        assert 'event=start revision=' in log
        if failure == 'Edge':
            assert events == ['Edge']
            assert 'remaining_apps_skipped' in log
        else:
            assert events == ['Edge', 'com.t3tools.t3code.com.t3tools.T3Code',
                              'ghostty.Ghostty', 'discord.discord', r['ZOHO'], r['WHATSAPP'], 'Bluetooth']
            assert [w['workspace'] for w in desktop[3:]] == ([0, 3, 4, 5] if failure else [0, 3, 4, 4, 5])
            assert 'event=stage_complete app=WhatsApp' in log
        if failure:
            assert f'event=stage_failed app={failure}' in log
        assert desktop[:3] == windows[:2] + [dict(id='other', cls='editor.Editor', workspace=0)]
        assert not any('-ia' in call.args[0] or '-s' in call.args[0] for call in commands.call_args_list)

# Already connected buds are reused, unavailable buds do not fail recovery,
# and no scan or pairing request is ever sent.
bluetooth = r['connect_earbuds']
for connected in (True, False):
    replies = ['Device 00:A4:1C:30:BC:76 OnePlus Buds 4\n',
               'Connected: yes' if connected else 'Connected: no']
    if not connected:
        replies += ['Connection successful', 'Connected: yes']
    with patch.object(g['subprocess'], 'check_output', side_effect=replies) as calls:
        assert bluetooth() == 'OnePlus Buds 4 connected.'
        assert len(calls.call_args_list) == (2 if connected else 4)
        assert all('scan' not in call.args[0] and 'pair' not in call.args[0] for call in calls.call_args_list)
with patch.object(g['subprocess'], 'check_output', side_effect=FileNotFoundError):
    assert 'unavailable' in bluetooth()

# Repeated recovery reuses T3, and failed launches restore the focus policy.
with patch.dict(g, {'windows': lambda: desktop}), patch.dict(g, {'launch': None, 'stage_windows': None}):
    r['ensure_app'](r['is_t3'], ['gtk-launch', 't3code'], 4, monitors[0])
with patch.dict(g, {'run': lambda *args: next(policies)}), patch.object(g['subprocess'], 'run') as commands:
    policies = iter(["'smart'", "'strict'"])
    try:
        with r['quiet_launches']():
            raise RuntimeError('Launch failed')
    except RuntimeError:
        pass
    assert commands.call_args.args[0][-1] == "'smart'"

print('Session recovery, workspace placement, failure isolation and Bluetooth checks passed.')

if '--x11-staging' in sys.argv:
    from Xlib import X, Xatom, display
    connection = display.Display()
    try:
        for late_class in (False, True):
            with r['stage_windows'](lambda w: w['cls'] == 'recovery-probe.RecoveryProbe', 4, monitors[1]):
                window = connection.screen().root.create_window(0, 0, 100, 100, 0, X.CopyFromParent)
                if late_class:
                    connection.sync()
                    time.sleep(.1)
                window.set_wm_class('recovery-probe', 'RecoveryProbe')
                connection.sync()
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline:
                    prop = window.get_full_property(connection.intern_atom('_NET_WM_DESKTOP'), Xatom.CARDINAL)
                    if prop is not None:
                        break
                    time.sleep(.05)
                assert prop is not None and list(prop.value) == [4]
                assert list(window.get_full_property(connection.intern_atom('_NET_WM_USER_TIME'), Xatom.CARDINAL).value) == [0]
                geometry = window.get_geometry()
                assert (geometry.x, geometry.y) == (monitors[1]['x'] + 40, monitors[1]['y'] + 70)
                assert window.get_attributes().map_state == X.IsUnmapped
                window.destroy()
                connection.sync()
    finally:
        connection.close()
    print('Real X11 staging passed without mapping a window or changing the visible desktop.')
