"""Naming checks use temporary files only."""
from datetime import datetime
from pathlib import Path
import tempfile
import unittest

from naming import clean_title, recording_files, recording_title, next_recording_path, rename_recording
from unittest.mock import patch


class NamingTests(unittest.TestCase):
    def test_rename_preserves_container_bytes_unicode_and_legacy_recovery(self):
        with tempfile.TemporaryDirectory() as folder:
            for extension in ('.mp4', '.mkv'):
                source = Path(folder, 'RecIt-2026-10-22-113059' + extension)
                source.write_bytes(b'original video')
                renamed = rename_recording(source, '  Résumé 演示.mp4.mkv  ')
                self.assertEqual(renamed.suffix, extension)
                self.assertEqual(renamed.read_bytes(), b'original video')
                self.assertFalse(source.exists())
                self.assertTrue(recording_title(renamed).startswith('Résumé 演示'))
                self.assertIn(renamed, recording_files(folder))

    def test_rename_rejects_empty_traversal_and_symbolic_links(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder, 'original.mp4')
            source.write_bytes(b'preserved')
            for title in ('', ' ', '.', '..', '../escape', 'folder/title', 'folder\\title', '\x00', '.mp4', '...'):
                with self.subTest(title=title), self.assertRaises(ValueError):
                    rename_recording(source, title)
                self.assertEqual(source.read_bytes(), b'preserved')
            link = Path(folder, 'link.mp4')
            link.symlink_to(source)
            with self.assertRaises(ValueError):
                rename_recording(link, 'changed')

    def test_rename_collisions_case_container_and_race_never_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder, 'original.mkv')
            source.write_bytes(b'original')
            Path(folder, 'DEMO.mp4').write_bytes(b'existing')
            Path(folder, 'demo (2).mkv').mkdir()
            renamed = rename_recording(source, 'demo')
            self.assertEqual(renamed.name, 'demo (3).mkv')
            self.assertEqual(Path(folder, 'DEMO.mp4').read_bytes(), b'existing')
            self.assertEqual(rename_recording(renamed, recording_title(renamed)), renamed)
            import os
            original_link = os.link
            def race(old, new, **kwargs):
                if new.name == 'race.mkv':
                    new.write_bytes(b'racing writer')
                return original_link(old, new, **kwargs)
            with patch('naming.os.link', side_effect=race):
                result = rename_recording(renamed, 'race')
            self.assertEqual(result.name, 'race (2).mkv')
            self.assertEqual(Path(folder, 'race.mkv').read_bytes(), b'racing writer')

    def test_rename_rolls_back_new_link_if_source_cannot_be_removed(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder, 'original.mp4')
            source.write_bytes(b'preserved')
            unlink = Path.unlink
            def refuse_source(path, *args, **kwargs):
                if path == source:
                    raise PermissionError('locked')
                return unlink(path, *args, **kwargs)
            with patch.object(Path, 'unlink', new=refuse_source), self.assertRaises(PermissionError):
                rename_recording(source, 'new title')
            self.assertEqual(source.read_bytes(), b'preserved')
            self.assertFalse(Path(folder, 'new title.mp4').exists())

    def test_friendly_names_and_collision_across_containers(self):
        with tempfile.TemporaryDirectory() as folder:
            now = datetime(2026, 10, 22, 11, 30)
            first = next_recording_path(folder, now=now)
            self.assertEqual(first.name, 'Camera recording - 2026-10-22 at 11.30.mkv')
            first.with_suffix('.mp4').write_bytes(b'preserved')
            second = next_recording_path(folder, now=now)
            second.touch()
            third = next_recording_path(folder, now=now)
            self.assertTrue(second.stem.endswith('(2)'))
            self.assertTrue(third.stem.endswith('(3)'))
            self.assertEqual(first.with_suffix('.mp4').read_bytes(), b'preserved')
            self.assertEqual(recording_title(second), 'Camera recording · 22 Oct 2026, 11:30 (2)')

    def test_window_title_and_safe_unicode(self):
        with tempfile.TemporaryDirectory() as folder:
            path = next_recording_path(folder, 'screen', '../Résumé / 演示\x00\u202e', datetime(2026, 10, 22))
            self.assertEqual(path.parent, Path(folder))
            self.assertIn('Résumé', path.name)
            self.assertNotIn('\u202e', path.name)
            self.assertLess(len(path.name.encode()), 255)
            self.assertLessEqual(len(clean_title('演' * 300).encode()), 160)
            self.assertEqual(clean_title(' ../\\\x00'), 'Recording')

    def test_legacy_and_arbitrary_filenames(self):
        for name in ('RecIt-2026-10-22-113059-123456.mkv', 'Glint-2026-10-22-113059.mp4'):
            self.assertEqual(recording_title(name), 'Recording · 22 Oct 2026, 11:30')
        for name in ('my demo.mp4', 'RecIt-2026-99-22-113059.mp4'):
            self.assertEqual(recording_title(name), Path(name).stem)
        self.assertEqual(recording_title('missing.mp4'), 'missing')

    def test_discovery_includes_new_legacy_and_recovery_files(self):
        with tempfile.TemporaryDirectory() as folder:
            for name in ('Glint-old.mkv', 'Camera recording - 2026-10-22 at 11.30.mp4', 'notes.txt'):
                Path(folder, name).touch()
            paths = recording_files(folder)
            self.assertEqual(len(paths), 2)
            self.assertEqual(set(p.suffix for p in paths), {'.mkv', '.mp4'})
            paths[0].unlink()
            self.assertEqual(len(recording_files(folder)), 1)
            self.assertEqual(recording_files(Path(folder, 'missing')), [])
