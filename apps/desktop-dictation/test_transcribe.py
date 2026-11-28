import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from transcribe import clean, read_settings


class CleanupTests(unittest.TestCase):
    def test_invalid_preferences_leave_recognition_available(self):
        with TemporaryDirectory() as temp, redirect_stderr(StringIO()):
            path = Path(temp) / "settings.json"
            for value in ("{", '{"speechCustomWords":[{"term":"hello","aliases":null}]}'):
                path.write_text(value)
                self.assertEqual(read_settings(path), {})

    def test_longest_alias_first_with_literal_punctuation(self):
        settings = {"speechCustomWords": [
            {"term": "VS", "aliases": ["v s"]},
            {"term": "VS Code", "aliases": ["v s code"]},
            {"term": "C++", "aliases": ["see plus plus"]},
        ]}
        self.assertEqual(clean("V S CODE and see plus plus", settings), "VS Code and C++")

    def test_filler_boundaries_and_newlines(self):
        self.assertEqual(clean("Uh, Album\nhmm, aluminum. ммм.", {}), "Album\n aluminum.")

    def test_configured_correction_cue_is_preserved(self):
        self.assertEqual(clean("Hm, uh, fine.", {"speechCorrectionWord": "hm"}), "Hm, fine.")

    def test_filler_removal_disabled(self):
        self.assertEqual(clean("Uh, fine.", {"speechRemoveFillerWords": False}), "Uh, fine.")

    def test_numeric_repair(self):
        self.assertEqual(clean("Set it to 4.5, sorry, 7.", {}), "Set it to 7.")
        sentence = "Set it to 4 volts, sorry, 7."
        self.assertEqual(clean(sentence, {}), sentence)


if __name__ == "__main__":
    unittest.main()
