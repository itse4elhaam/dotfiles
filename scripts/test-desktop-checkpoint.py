#!/usr/bin/env python3
"""Regression checks for login restoration and interrupted checkpoint writes."""
import json
import os
import runpy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).with_name('desktop-session-checkpoint')


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        with patch.dict(os.environ, HOME=temporary.name):
            previous = os.umask(0o077)
            try:
                self.api = runpy.run_path(str(SCRIPT))
            finally:
                os.umask(previous)

    def test_edge_playlist_renumber_during_login(self):
        def tabs(index=3, video='v1', selected=0, reverse=False):
            urls = [f'https://www.youtube.com/watch?v={video}&list=pl&index={index}',
                    'https://example.org/test']
            if reverse:
                urls.reverse()
            return self.api['tab_signature']([{'pages': [
                {'url': url, 'active': i == selected} for i, url in enumerate(urls)
            ]}])

        self.assertEqual(tabs(), tabs(index=2))
        self.assertNotEqual(tabs(), tabs(video='v2'))
        self.assertNotEqual(tabs(), tabs(selected=1))
        self.assertNotEqual(tabs(), tabs(reverse=True))

    def test_changing_title_after_login(self):
        edge = self.api['edge']
        saved = [
            dict(cls=edge, id='1', title='HP PDF'),
            dict(cls=edge, id='2', title='Proposals'),
        ]
        live = [
            dict(cls=edge, id='8', title='Proposals'),
            dict(cls=edge, id='9', title='h20195.www2.hp.com'),
        ]
        self.assertEqual(self.api['match'](saved, live), {'1': '9', '2': '8'})
        live[0]['title'] = 'Loading'
        self.assertEqual(self.api['match'](saved, live), {})

    def test_window_closed_during_save_preserves_previous_generation(self):
        save = self.api['save']
        root = self.api['root']
        windows = [{'id': '1'}]
        state = {'windows': windows}
        with patch.dict(save.__globals__, snapshot=lambda: state, windows=lambda: windows,
                        details='/usr/bin/true'):
            save()
            current = (root / 'current').resolve()
            with patch.dict(save.__globals__, windows=lambda: []):
                with self.assertRaisesRegex(RuntimeError, 'Window list changed'):
                    save()
        self.assertEqual((root / 'current').resolve(), current)
        self.assertEqual(json.loads((current / 'layout.json').read_text()), state)
        self.assertEqual(list(root.glob('session-*')), [current])


if __name__ == '__main__':
    unittest.main()
