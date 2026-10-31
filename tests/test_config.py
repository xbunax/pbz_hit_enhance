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

    def test_single_key_shortcuts(self):
        self.assertEqual(normalize("Insert"), ("INSERT", frozenset({0x2D})))
        self.assertEqual(normalize(" ins "), ("INSERT", frozenset({0x2D})))
        self.assertEqual(normalize("F10"), ("F10", frozenset({0x79})))
        self.assertEqual(normalize("a"), ("A", frozenset({0x41})))
        self.assertEqual(normalize("Shift+Insert"), ("SHIFT+INSERT", frozenset({0x10, 0x2D})))

    def test_malformed_shortcuts_rejected(self):
        for value in (
            "",
            "CTRL+",
            "+INSERT",
            "CTRL+CTRL+INSERT",
            "F25",
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize(value)

    def test_legacy_migration_and_roundtrip(self):
        old = "\n".join(k + "=" + configure.BASE_DEFAULT[k] for k in configure.BASE_KEYS)
        c = configure.parse(old.replace("Scale=1", "Scale=3.09"))
        self.assertEqual(c["Scale"], "3.09")
        self.assertEqual(c["ObserveOnly"], "false")
        self.assertEqual(c["Blade.Override"], "false")
        self.assertEqual(configure.parse(configure.serialize(c)), c)

    def test_profile_validation(self):
        for patch in [
            {"Blade.FixedFrames": "nan"},
            {"GreatBlade.FixedFrames": "31"},
            {"DoubleBlade.Override": "yes"},
            {"Blade.Mode": "oops"},
            {"ObserveOnly": "yes"},
        ]:
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                configure.validate(configure.defaults() | patch)
        with self.assertRaises(ValueError):
            configure.validate(configure.BASE_DEFAULT | {"Blade.Override": "true"})
        with self.assertRaises(ValueError):
            configure.parse(configure.serialize(configure.defaults()) + "Blade.Scale=2\n")

    def test_profiles_preserved_by_serialization(self):
        c = configure.defaults()
        for profile, frames in zip(configure.PROFILES, (5, 7, 9)):
            c[profile + ".FixedFrames"] = str(frames)
            c[profile + ".Override"] = "true"
        self.assertEqual(configure.parse(configure.serialize(c)), c)
