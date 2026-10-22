"""Exercise sign-in script with a fake CLI, never an account or browser."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


class ConnectChecks(unittest.TestCase):
    def test_consent_and_login_failures_keep_terminal_message_and_stop(self):
        script = Path(__file__).with_name('connect-loom.sh')
        for failure, expected in [('consent', ['consent']), ('login', ['consent', 'login']), ('none', ['consent', 'login'])]:
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                cli = root / 'fake cli'
                log = root / 'calls'
                cli.write_text('#!/bin/bash\nprintf "%s\\n" "$1" >> "$MOCK_LOG"\n[[ "$1" != "$MOCK_FAIL" ]]\n')
                cli.chmod(0o700)
                result = subprocess.run(['bash', str(script), str(cli)], input='\n', text=True,
                    capture_output=True, timeout=5,
                    env={**os.environ, 'MOCK_LOG': str(log), 'MOCK_FAIL': failure})
                self.assertEqual(log.read_text().splitlines(), expected)
                self.assertEqual(result.returncode, 0 if failure == 'none' else 1)
                self.assertIn('Connection finished' if failure == 'none' else 'No video was uploaded', result.stdout)
