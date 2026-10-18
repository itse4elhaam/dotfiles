"""Headless checks of the actual Neovim exit protocol and desktop handoff."""
import importlib.machinery
import os
import shlex
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
helper = importlib.machinery.SourceFileLoader('nvim_anywhere', str(ROOT / 'scripts/nvim-anywhere-edit')).load_module()


class EditorProtocol(unittest.TestCase):
    def editor(self, commands, user_config=False):
        with tempfile.TemporaryDirectory() as folder:
            draft = Path(folder) / 'draft.md'
            marker = Path(folder) / 'commit'
            draft.write_text('original\n')
            env = dict(os.environ, NVIM_ANYWHERE_DRAFT=str(draft), NVIM_ANYWHERE_COMMIT=str(marker))
            args = ['nvim', '--headless']
            if not user_config:
                args += ['-u', 'NONE']
            args += ['--cmd', f"lua dofile('{ROOT}/scripts/nvim-anywhere/editor.lua')", str(draft)]
            for command in commands:
                args += ['-c', command]
            result = subprocess.run(args, env=env, cwd=folder, capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            return marker.exists(), draft.read_text()

    def test_save_and_quit(self):
        self.assertEqual(self.editor(["call setline(1, 'edited 😀')", 'wq']), (True, 'edited 😀\n'))

    def test_cancel(self):
        self.assertEqual(self.editor(["call setline(1, 'discard')", 'q!']), (False, 'original\n'))

    def test_plain_quit_does_not_commit(self):
        self.assertFalse(self.editor(['q'])[0])

    def test_write_then_unsaved_change_cancel(self):
        self.assertFalse(self.editor(['w', "call setline(1, 'discard')", 'q!'])[0])

    def test_interactive_force_quit_after_save_cancels(self):
        self.assertFalse(self.editor(['w', r'call feedkeys(":q!\<CR>", "xt")'])[0])

    def test_actual_user_config(self):
        self.assertTrue(self.editor(["call setline(1, 'configured editor')", 'wq'], True)[0])


class DesktopHandoff(unittest.TestCase):
    def test_blank_commit_and_failure_recovery(self):
        for mode, fail_return in ((mode, failed) for mode in ('--blank', '--whole-field', '--selection', '') for failed in (False, True)):
            with self.subTest(mode=mode, fail_return=fail_return), tempfile.TemporaryDirectory() as folder:
                pasted = []
                keys = []
                notices = []
                def fake_run(*args, **kwargs):
                    if args[0] == 'ghostty':
                        self.assertIn('--font-size=17', args)
                        env = kwargs['env']
                        editor = shlex.split(args[-1])
                        self.assertEqual(editor, ['/bin/tool', '--cmd', 'lua dofile(vim.env.NVIM_ANYWHERE_LUA)', env['NVIM_ANYWHERE_DRAFT']])
                        self.assertEqual(env['NVIM_ANYWHERE_LUA'], str(ROOT / 'scripts/nvim-anywhere/editor.lua'))
                        self.assertEqual(Path(env['NVIM_ANYWHERE_DRAFT']).read_bytes(), b'' if mode == '--blank' else b'captured text')
                        self.assertEqual('ctrl+a' in keys, mode not in ('--blank', '--selection'))
                        Path(env['NVIM_ANYWHERE_DRAFT']).write_text('new text')
                        Path(env['NVIM_ANYWHERE_COMMIT']).touch()
                        return subprocess.CompletedProcess(args, 0)
                    if fail_return and args[1] == 'windowactivate':
                        raise subprocess.CalledProcessError(1, args)
                    if args[0] == 'xdotool' and args[1] == 'key':
                        keys.append(args[-1])
                    if args[-1] == 'ctrl+v':
                        pasted.append(True)
                    return subprocess.CompletedProcess(args, 0)
                with patch.dict(os.environ, XDG_SESSION_TYPE='x11', XDG_STATE_HOME=folder), \
                     patch('sys.argv', ['nvim-anywhere-edit'] + ([mode] if mode else [])), \
                     patch.object(helper.shutil, 'which', return_value='/bin/tool'), \
                     patch.object(helper, 'output', return_value='123'), \
                     patch.object(helper, 'copy_text', side_effect=([b'old clipboard'] if mode == '--blank' else [b'old clipboard', subprocess.CalledProcessError(1, ['xclip']), b'captured text'])), \
                     patch.object(helper, 'clipboard'), patch.object(helper.time, 'sleep'), \
                     patch.object(helper, 'notify', side_effect=notices.append), \
                     patch.object(helper, 'run', side_effect=fake_run), \
                     patch.object(helper.subprocess, 'run', side_effect=lambda args, **kw: fake_run(*args, **kw)):
                    helper.main()
                self.assertEqual(bool(pasted), not fail_return)
                self.assertEqual(next(Path(folder).glob('nvim-anywhere/draft-*/draft.md')).read_text(), 'new text')
                self.assertIn('Return failed' if fail_return else 'Text returned', notices[-1])


if __name__ == '__main__':
    unittest.main()
