import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "gui"))
import configure
from hotkey import normalize


class ConfigurationTests(unittest.TestCase):
    def test_default_config_valid(self):
        value = configure.read()
        configure.validate(value)
        self.assertEqual(value["Scale"], "1")

    def test_invalid_values_rejected(self):
        for key, bad in [
            ("Scale", "nan"),
            ("Scale", "5"),
            ("Enabled", "yes"),
            ("FixedFrames", "1.5"),
        ]:
            with self.subTest(key=key):
                value = configure.read()
                value[key] = bad
                with self.assertRaises(ValueError):
                    configure.validate(value)

    def test_shortcut_normalization(self):
        self.assertEqual(normalize("Alt+Control+F10")[0], "CTRL+ALT+F10")

    def test_shortcut_without_modifier_rejected(self):
        with self.assertRaises(ValueError):
            normalize("F10")
