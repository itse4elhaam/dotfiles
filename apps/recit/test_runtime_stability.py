"""Exercise the real Qt runtime in a subprocess so native crashes fail safely."""
import os
from pathlib import Path
import subprocess
import sys
import unittest


class RuntimeStabilityChecks(unittest.TestCase):
    def test_repeated_microphone_updates_survive_and_exit_cleanly(self):
        result = subprocess.run(
            [sys.executable, '-X', 'faulthandler', '-c', '''
from PySide6.QtWidgets import QApplication
from microphone_meter import MicrophoneMeter
app = QApplication([])
meter = MicrophoneMeter()
for i in range(20000):
    meter.show_status(dict(state='quiet', peak_db=-70), 'Test microphone')
    if i % 100 == 0:
        app.processEvents()
assert meter.message.text() == 'Very quiet input · -70 dBFS'
meter.close()
del meter
app.processEvents()
print('updates completed', flush=True)
'''],
            cwd=Path(__file__).resolve().parent,
            env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen', 'QT_ACCESSIBILITY': '0'},
            capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('updates completed', result.stdout)


if __name__ == '__main__':
    unittest.main()
