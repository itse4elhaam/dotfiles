import os
from pathlib import Path
import subprocess
import tempfile
import unittest


DOTFILES = Path(__file__).resolve().parents[1]
HELPER = DOTFILES / "scripts/worktree-deps"
HOOK = DOTFILES / ".config/git/templates/hooks/post-checkout"


class WorktreeDependencyTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.base = Path(scratch.name)
        self.primary = self.base / "primary checkout"
        self.env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
        self.git(self.base, "init", "--template=", "-b", "main", self.primary)
        self.git(self.primary, "config", "user.name", "Worktree Test")
        self.git(self.primary, "config", "user.email", "worktree@example.invalid")
        self.git(self.primary, "config", "core.excludesFile", DOTFILES / ".config/git/ignore")
        self.git(self.primary, "config", "core.hooksPath", self.base / "hooks")
        hooks = self.base / "hooks"
        hooks.mkdir()
        self.hook = hooks / "post-checkout"
        self.hook.write_text(HOOK.read_text().replace('"$HOME/dotfiles/scripts/worktree-deps"', f'"{HELPER}"'))
        self.hook.chmod(0o755)
        self.package(self.primary)
        self.package(self.primary / "nested package")
        self.git(self.primary, "add", ".")
        self.git(self.primary, "commit", "-m", "test fixture")

    def git(self, cwd, *args):
        result = subprocess.run(["git", "-C", cwd, *args], capture_output=True, env=self.env)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        return result.stdout

    def package(self, directory):
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "package.json").write_text('{"name":"fixture"}')
        (directory / "package-lock.json").write_text("fixture-lock")
        (directory / "node_modules").mkdir()
        (directory / "node_modules/marker").write_text("shared install")

    def add_worktree(self, *args):
        linked = self.base / "linked checkout"
        self.git(self.primary, "worktree", "add", *args, linked)
        return linked

    def test_add_links_dependencies_and_checkout_does_not_restore_removed_links(self):
        linked = self.add_worktree("--detach")
        self.assertEqual((linked / "node_modules").resolve(), self.primary / "node_modules")
        self.assertEqual((linked / "nested package/node_modules").resolve(), self.primary / "nested package/node_modules")
        self.assertEqual(self.git(linked, "status", "--short"), b"")
        (linked / "node_modules").unlink()
        self.git(linked, "checkout", "-b", "fresh-branch")
        self.assertFalse((linked / "node_modules").exists())
        self.git(linked, "checkout", "--orphan", "unborn-branch")
        self.git(linked, "checkout", "fresh-branch")
        self.assertFalse((linked / "node_modules").exists())

    def test_cached_checkout_receives_null_old_head_and_uses_the_same_helper(self):
        linked = self.add_worktree("--detach", "--no-checkout")
        head = self.git(self.primary, "rev-parse", "HEAD").strip().decode()
        self.git(linked, "read-tree", "--reset", "-u", head)
        self.assertFalse((linked / "node_modules").exists())
        subprocess.run([self.hook, "0" * len(head), head, "1"], cwd=linked, env=self.env, check=True)
        self.assertTrue((linked / "node_modules").is_symlink())

    def test_different_dependency_inputs_and_external_package_links_stay_local(self):
        (self.primary / "package-lock.json").write_text("different")
        (self.primary / "nested package/node_modules/external").symlink_to(self.primary / "nested package")
        linked = self.add_worktree("--detach")
        self.assertFalse((linked / "node_modules").exists())
        self.assertFalse((linked / "nested package/node_modules").exists())

    def test_local_install_detaches_the_link_without_writing_through_it(self):
        linked = self.add_worktree("--detach")
        subprocess.run([HELPER, "install", "mkdir", "node_modules"], cwd=linked, env=self.env, check=True)
        self.assertTrue((linked / "node_modules").is_dir())
        self.assertFalse((linked / "node_modules").is_symlink())
        self.assertEqual((self.primary / "node_modules/marker").read_text(), "shared install")

    def test_retrofit_preserves_existing_hooks_and_is_idempotent(self):
        self.git(self.primary, "config", "--unset", "core.hooksPath")
        destination = self.primary / ".git/hooks/post-checkout"
        destination.parent.mkdir()
        for _ in range(2):
            subprocess.run([HELPER, "install-hook", self.primary], env=self.env, check=True)
        self.assertEqual(destination.resolve(), HOOK)
        destination.unlink()
        destination.write_text("existing hook")
        result = subprocess.run([HELPER, "install-hook", self.primary], env=self.env, capture_output=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(destination.read_text(), "existing hook")


if __name__ == "__main__":
    unittest.main()
