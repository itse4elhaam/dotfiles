"""Real textbox capture/paste on an isolated X11 display.

Run with NVIM_ANYWHERE_TEST_DISPLAY=:91 on a separate Xvfb display.
The test opens no windows on the user's desktop. Gtk3 and python3-gi are needed.
"""
import importlib.machinery
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
helper = importlib.machinery.SourceFileLoader('nvim_anywhere_x11', str(ROOT / 'scripts/nvim-anywhere-edit')).load_module()
TEXT = 'Existing textbox text\nSecond line with Unicode: café'
APP = '''
import gi, pathlib, sys
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib
win = Gtk.Window(title='Nvim capture regression')
view = Gtk.TextView()
buf = view.get_buffer()
buf.set_text(sys.argv[2])
buf.connect('changed', lambda b: pathlib.Path(sys.argv[1]).write_text(b.get_text(b.get_start_iter(), b.get_end_iter(), False)))
win.add(view)
win.show_all()
view.grab_focus()
def selection_state():
    pathlib.Path(sys.argv[3]).write_text(str(bool(buf.get_selection_bounds())))
    return True
GLib.timeout_add(20, selection_state)
Gtk.main()
'''


@unittest.skipUnless(os.environ.get('NVIM_ANYWHERE_TEST_DISPLAY'), 'requires an isolated Xvfb display')
class X11Capture(unittest.TestCase):
    def test_default_captures_existing_text_and_replaces_field(self):
        self.roundtrip(TEXT)

    def test_default_opens_empty_field(self):
        self.roundtrip('')

    def roundtrip(self, text):
        real_run = subprocess.run
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, DISPLAY=os.environ['NVIM_ANYWHERE_TEST_DISPLAY'], XDG_SESSION_TYPE='x11', XDG_STATE_HOME=folder):
            result_file = Path(folder) / 'result'
            selection_file = Path(folder) / 'selection'
            with open(Path(folder) / 'gtk.log', 'w') as log:
                app = subprocess.Popen(['/usr/bin/python3', '-c', APP, str(result_file), text, str(selection_file)], stdout=log, stderr=log)
                try:
                    for _ in range(50):
                        found = real_run(['xdotool', 'search', '--name', '^Nvim capture regression$'], capture_output=True, text=True)
                        if found.returncode == 0:
                            break
                        time.sleep(.1)
                    self.assertEqual(found.returncode, 0, (Path(folder) / 'gtk.log').read_text())
                    window = found.stdout.strip().splitlines()[-1]
                    # Xvfb has no window manager. Supply the active-window property
                    # and focus directly; selection/copy/paste still use real X11.
                    real_run(['xprop', '-root', '-f', '_NET_ACTIVE_WINDOW', '32x', '-set', '_NET_ACTIVE_WINDOW', hex(int(window))], check=True, stdout=subprocess.DEVNULL)
                    real_run(['xdotool', 'windowfocus', '--sync', window], check=True)
                    def launch(args, **kwargs):
                        if args[0] == 'ghostty':
                            draft = Path(kwargs['env']['NVIM_ANYWHERE_DRAFT'])
                            self.assertEqual(draft.read_text(), text)
                            time.sleep(.05)
                            self.assertEqual(selection_file.read_text(), 'False', 'Source field remains highlighted')
                            editor = shlex.split(args[-1])
                            editor[1:1] = ['--headless']
                            editor += ['-c', '%delete _', '-c', "call setline(1, 'edited in neovim')", '-c', 'wq']
                            return real_run(editor, timeout=30, **kwargs)
                        if list(args[:2]) == ['xdotool', 'windowactivate']:
                            args = ['xdotool', 'windowfocus', '--sync', window]
                        return real_run(args, **kwargs)
                    real_output = helper.output
                    def active_window(*args):
                        return window if args == ('xdotool', 'getactivewindow') else real_output(*args)
                    with patch.object(helper, 'output', side_effect=active_window), patch('sys.argv', ['nvim-anywhere-edit']), patch.object(helper.subprocess, 'run', side_effect=launch), patch.object(helper, 'log_status'):
                        helper.main()
                    for _ in range(30):
                        if result_file.exists() and result_file.read_text() == 'edited in neovim\n':
                            break
                        time.sleep(.1)
                    self.assertEqual(result_file.read_text(), 'edited in neovim\n')
                finally:
                    app.terminate()
                    app.wait(timeout=5)


if __name__ == '__main__':
    unittest.main()
