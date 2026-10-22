"""Synthetic media import, collisions and safe failure; never captures hardware."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch, Mock
from video_import import import_video
import test_app
import app


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / 'Tab recording.webm'
        self.source.write_bytes(b'original')
        self.destination = self.root / 'library'

    def test_synthetic_webm_converts_and_keeps_original_and_collision(self):
        subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=c=blue:s=64x48:r=10',
            '-f','lavfi','-i','sine=frequency=440:sample_rate=48000','-t','0.3',
            '-c:v','libvpx','-c:a','libopus',str(self.source)],check=True,capture_output=True)
        original = self.source.read_bytes()
        first = import_video(self.source,self.destination)
        second = import_video(self.source,self.destination)
        self.assertNotEqual(first,second)
        self.assertEqual(self.source.read_bytes(),original)
        result = subprocess.run(['ffprobe','-v','error','-show_streams','-of','json',str(first)],
            check=True,capture_output=True)
        self.assertEqual([s['codec_name'] for s in json.loads(result.stdout)['streams']], ['h264','aac'])
        self.assertEqual(first.read_bytes(),second.read_bytes())

    def test_compatible_streams_copy_and_names_stay_in_library(self):
        probe = {'streams':[{'codec_type':'video','codec_name':'h264','pix_fmt':'yuv420p'},
                            {'codec_type':'audio','codec_name':'aac'}]}
        self.source = self.source.rename(self.root / '..\\..\\outside.webm')
        commands = []
        def run(command, **kwargs):
            commands.append(command)
            if command[0] == 'ffprobe':
                return Mock(stdout=json.dumps(probe).encode())
            Path(command[-1]).write_bytes(b'converted')
        with patch('video_import.subprocess.run',side_effect=run):
            result = import_video(self.source,self.destination)
            self.assertEqual(result.parent,self.destination)
            self.assertNotIn('\\', result.name)
            self.assertEqual(commands[1][commands[1].index('-c:v')+1],'copy')
            self.assertEqual(commands[1][commands[1].index('-c:a')+1],'copy')
            self.assertIn('file,pipe',commands[0])
            # Existing files and symlinks are both occupied, never overwritten.
            result.unlink(); result.symlink_to(self.source)
            another = import_video(self.source,self.destination)
            self.assertNotEqual(result,another)
            self.assertTrue(result.is_symlink())
            self.assertEqual(self.source.read_bytes(),b'original')

    def test_conversion_failure_removes_staging_and_preserves_original(self):
        def run(command, **kwargs):
            if command[0] == 'ffprobe':
                return Mock(stdout=b'{"streams":[{"codec_type":"video","codec_name":"vp8"}]}')
            Path(command[-1]).write_bytes(b'partial')
            raise subprocess.CalledProcessError(1,command)
        with patch('video_import.subprocess.run',side_effect=run), self.assertRaises(subprocess.CalledProcessError):
            import_video(self.source,self.destination)
        self.assertEqual(self.source.read_bytes(),b'original')
        self.assertEqual(list(self.destination.iterdir()),[])

    def test_invalid_file_or_audio_only_does_not_convert(self):
        link = self.root / 'link.webm'; link.symlink_to(self.source)
        with patch('video_import.subprocess.run') as run:
            with self.assertRaises(ValueError):
                import_video(link,self.destination)
            run.assert_not_called()
            run.return_value.stdout = b'{"streams":[{"codec_type":"audio"}]}'
            with self.assertRaises(ValueError):
                import_video(self.source,self.destination)
            self.assertEqual(run.call_count,1)
        self.assertEqual(self.source.read_bytes(),b'original')


class ImportUiTests(unittest.TestCase):
    setUp = test_app.AppChecks.setUp
    tearDown = test_app.AppChecks.tearDown

    def test_import_never_triggers_auto_upload_and_cancel_does_nothing(self):
        w = self.window
        w.prefs.setValue('auto_upload',True)
        w.open_recordings()
        with patch.object(app.QFileDialog,'getOpenFileName',return_value=('', '')), patch('video_import.ImportWorker') as worker:
            w.import_video()
            worker.assert_not_called()
        output = app.VIDEOS / 'imported.mp4'; output.write_bytes(b'imported')
        with patch.object(app.QFileDialog,'getOpenFileName',return_value=('/download/tab.webm', '')), \
                patch('video_import.ImportWorker') as worker, patch.object(w,'upload') as upload:
            w.import_video()
            self.assertTrue(w.busy)
            callback = worker.return_value.result.connect.call_args.args[0]
            callback(output,'')
            self.assertFalse(w.busy)
            self.assertEqual(w.last_file,output)
            upload.assert_not_called()
