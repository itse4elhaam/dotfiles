import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("cc"), "native close-button helper needs cc")
class T3LauncherTests(unittest.TestCase):
    def test_launches_newest_appimage_with_urls_and_scoped_native_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            applications = home / "Applications"
            applications.mkdir()
            for version in ("0.1.9", "0.1.10"):
                app = applications / f"T3-Code-{version}-x86_64.AppImage"
                app.write_text(
                    "#!/usr/bin/python3\n"
                    "import json, os, sys\n"
                    "from pathlib import Path\n"
                    "Path(os.environ['HOME'], 'launch.json').write_text(json.dumps({"
                    "'app': sys.argv[0], 'args': sys.argv[1:], "
                    "'modules': os.environ.get('GTK_MODULES'), "
                    "'launcher': os.environ.get('T3CODE_DESKTOP_LAUNCHER_PATH')}))\n"
                )
                app.chmod(0o755)
            env = dict(os.environ, HOME=directory, XDG_CACHE_HOME=str(home / "cache"),
                       GTK_MODULES="existing-module")
            subprocess.run([str(ROOT / "scripts/t3"), "t3code://test"], env=env,
                           check=True, capture_output=True, text=True)
            record = home / "launch.json"
            for _ in range(100):
                if record.exists():
                    break
                time.sleep(.01)
            launch = json.loads(record.read_text())
            self.assertTrue(launch["app"].endswith("T3-Code-0.1.10-x86_64.AppImage"))
            self.assertEqual(launch["args"], ["--no-sandbox", "t3code://test"])
            previous, module = launch["modules"].split(":", 1)
            self.assertEqual(previous, "existing-module")
            self.assertTrue(Path(module).is_file())
            self.assertEqual(launch["launcher"], str(home / ".local/bin/t3"))


if __name__ == "__main__":
    unittest.main()
