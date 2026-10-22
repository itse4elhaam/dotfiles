"""Offline regressions for the all-zero AAC track in the 10:59 OnePlus file.

Only generated temporary media is decoded. No OBS/device capture or playback.
"""
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock

from engine import recording_audio_warning
from app import FinishWorker


class SavedAudioTests(unittest.TestCase):
    def test_actual_decoded_audio_not_track_presence_or_low_bitrate(self):
        with tempfile.TemporaryDirectory() as directory:
            for name, audio, expected in (
                ('silent', 'anullsrc=r=48000:cl=stereo', 'silent'),
                ('quiet', 'sine=frequency=440:sample_rate=48000,volume=0.0001', ''),
                ('audible', 'sine=frequency=440:sample_rate=48000', ''),
                ('missing', None, 'no audio track'),
            ):
                with self.subTest(name=name):
                    path = Path(directory) / f'{name}.mp4'
                    args = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-nostdin',
                            '-f', 'lavfi', '-i', 'color=size=16x16:rate=10']
                    if audio:
                        args += ['-f', 'lavfi', '-i', audio]
                    subprocess.run(args + ['-t', '0.3', '-c:v', 'libx264', '-c:a', 'aac',
                                           str(path)], check=True, capture_output=True)
                    warning = recording_audio_warning(path)
                    if expected:
                        self.assertIn(expected, warning)
                    else:
                        self.assertEqual(warning, '')

    def test_decode_failure_does_not_claim_silence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'bad.mp4'
            path.write_bytes(b'broken')
            self.assertIn('could not be verified', recording_audio_warning(path))

    def test_finish_checks_after_stop_and_propagates_warning(self):
        from unittest.mock import patch
        engine = Mock(audio_expected=True, errors=[])
        worker = FinishWorker(engine, Path('/fake/recording.mkv'))
        with patch('app.recording_audio_warning', return_value='Audio is silent.') as check:
            check.side_effect = lambda path, trace: (engine.stop.assert_called_once(), 'Audio is silent.')[1]
            worker.run()
        self.assertEqual(engine.errors, ['Audio is silent.'])

    def test_intentional_audio_off_skips_check(self):
        from unittest.mock import patch
        engine = Mock(audio_expected=False)
        with patch('app.recording_audio_warning') as check:
            FinishWorker(engine, Path('/fake/recording.mkv')).run()
        check.assert_not_called()
