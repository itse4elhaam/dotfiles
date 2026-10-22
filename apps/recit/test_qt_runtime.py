"""Subprocess regression for the Qt/Python reference-count crash; no capture."""
import os
from pathlib import Path
import subprocess
import sys
import textwrap
import unittest


class QtRuntimeChecks(unittest.TestCase):
    def test_repeated_meter_updates_do_not_abort_python(self):
        env = os.environ.copy()
        env.pop('DISPLAY', None)
        env['QT_QPA_PLATFORM'] = 'offscreen'
        code = textwrap.dedent('''
            import resource
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
            from PySide6.QtWidgets import QApplication
            from microphone_meter import MicrophoneMeter
            app = QApplication([])
            meter = MicrophoneMeter()
            for i in range(10000):
                meter.show_status(dict(source='synthetic', state='signal', peak_db=-18),
                                  'Synthetic microphone')
            meter.close()
            print('meter update stress passed')
        ''')
        result = subprocess.run([sys.executable, '-c', code],
                                cwd=Path(__file__).parent, env=env,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr[-4000:])
        self.assertIn('meter update stress passed', result.stdout)
