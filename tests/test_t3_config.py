"""Exercise configuration migration, backups, and writes through live symlinks."""

import importlib.machinery
import importlib.util
import json
from pathlib import Path
import runpy
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader("setup_t3_config", str(ROOT / "scripts/setup-t3-config"))
spec = importlib.util.spec_from_loader(loader.name, loader)
setup = importlib.util.module_from_spec(spec)
loader.exec_module(setup)


class ConfigLinksTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo, self.home = self.root / "dotfiles", self.root / "home"
        self.links = setup.config_links(self.repo, self.home, self.home / ".t3")
        for source, _ in self.links:
            source.parent.mkdir(parents=True, exist_ok=True)
            if source.name == "themes":
                source.mkdir()
                (source / "forest.json").write_text('{"name":"Forest"}\n')
            else:
                source.write_text("[]\n")
        self.backup = self.root / "backup"

    def test_migrates_existing_data_and_replaces_old_worktree_launcher(self):
        for source, destination in self.links:
            destination.parent.mkdir(parents=True, exist_ok=True)
            if source.is_dir():
                destination.mkdir()
                (destination / "old.json").write_text("old wallpaper")
            elif source.name == "t3-zen":
                destination.symlink_to(self.root / "old-worktree/scripts/t3-zen")
            else:
                destination.write_text("old config")
        setup.install_links(self.links, self.backup)
        for source, destination in self.links:
            self.assertTrue(setup.linked(source, destination))
        self.assertEqual((self.backup / "themes/old.json").read_text(), "old wallpaper")
        self.assertEqual((self.backup / "keybindings.json").read_text(), "old config")
        self.assertTrue((self.backup / "t3-zen").is_symlink())
        setup.install_links(self.links, self.root / "second-backup")
        self.assertFalse((self.root / "second-backup").exists())

    def test_writes_and_atomic_theme_replacement_reach_the_repository(self):
        setup.install_links(self.links, self.backup)
        userdata = self.home / ".t3/userdata"
        (userdata / "keybindings.json").write_text('[{"key":"ctrl+tab"}]\n')
        self.assertEqual((self.repo / ".config/t3code/keybindings.json").read_text(),
                         '[{"key":"ctrl+tab"}]\n')
        temporary = userdata / "themes/forest.json.tmp"
        temporary.write_text('{"name":"Updated forest"}\n')
        temporary.replace(userdata / "themes/forest.json")
        self.assertEqual((self.repo / ".config/t3code/themes/forest.json").read_text(),
                         '{"name":"Updated forest"}\n')
        for source, destination in self.links:
            self.assertTrue(setup.linked(source, destination))

    def test_missing_source_and_dry_run_preserve_existing_config(self):
        source, destination = self.links[1]
        destination.parent.mkdir(parents=True)
        destination.write_text("local changes")
        setup.install_links(self.links, self.backup, dry_run=True)
        self.assertEqual(destination.read_text(), "local changes")
        self.assertFalse(self.backup.exists())
        self.links[-1][0].unlink()
        with self.assertRaises(SystemExit):
            setup.install_links(self.links, self.backup)
        self.assertEqual(destination.read_text(), "local changes")


class WallpaperStackingTests(unittest.TestCase):
    """Desktop browser views are fixed layers outside the sidebar wrapper."""

    def test_rewrite_moves_both_wallpaper_forms_onto_body(self):
        rewrite = runpy.run_path(str(ROOT / "scripts/t3-wallpaper-layout"))["paint_wallpaper_on_body"]
        wrapper = ".dark [data-slot=sidebar-wrapper]{isolation:isolate;background:#0000!important}"
        layer = ".dark [data-slot=sidebar-wrapper]::before{content:\"\";position:fixed;inset:0;z-index:-1;"
        gradient = "linear-gradient(rgb(26 27 38/var(--td-shade)),rgb(26 27 38/.84))"
        for paint in (f"background:{gradient},var(--td-wallpaper) center/cover no-repeat}}",
                      f"background-image:{gradient},var(--td-wallpaper);background-size:cover}}"):
            self.assertEqual(rewrite(wrapper + layer + paint),
                             ".dark [data-slot=sidebar-wrapper]{background:#0000!important}"
                             f".dark body{{background:{gradient} fixed,"
                             "var(--td-wallpaper) center/cover no-repeat fixed!important}")

    def test_tracked_themes_keep_panel_controls_above_browser_views(self):
        for path in sorted((ROOT / ".config/t3code/themes").glob("*.json")):
            css = json.loads(path.read_text()).get("css", "")
            self.assertLessEqual(len(css), 50_000, path.name)
            self.assertNotIn("isolation:isolate", css, path.name)
            self.assertNotIn("sidebar-wrapper]::before", css, path.name)


if __name__ == "__main__":
    unittest.main()
