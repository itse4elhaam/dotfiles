import unittest

from transcribe import clean


class CleanupTests(unittest.TestCase):
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
