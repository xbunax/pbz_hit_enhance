import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "gui"))
from keybinds import normalize, ChordLatch, Recorder


class ChordTests(unittest.TestCase):
    def test_free_combinations_and_legacy(self):
        for value, expected in [
            ("b+a", "A+B"),
            ("Control+F10", "CTRL+F10"),
            ("win+ins", "WIN+INSERT"),
            ("shift", "SHIFT"),
            ("NUM1+HOME", "HOME+NUM1"),
            ("Ctrl+Alt+Delete", "CTRL+ALT+DELETE"),
            ("BACKTICK", "BACKTICK"),
        ]:
            self.assertEqual(normalize(value)[0], expected)
            self.assertEqual(normalize(normalize(value)[0]), normalize(value))

    def test_no_repeat_until_entire_chord_released(self):
        latch = ChordLatch({65, 66})
        sequence = [set(), {65}, {65, 66}, {65, 66}, {65}, {65, 66}, set(), {65, 66}]
        self.assertEqual(
            [latch.step(x) for x in sequence],
            [False, False, True, False, False, False, False, True],
        )

    def test_extra_keys_and_initial_hold_do_not_trigger(self):
        latch = ChordLatch({45})
        self.assertFalse(latch.step({45}))
        self.assertFalse(latch.step(set()))
        self.assertFalse(latch.step({17, 45}))
        self.assertFalse(latch.step({65, 45}))
        self.assertTrue(latch.step({45}))

    def test_recording_waits_for_old_keys_then_captures_chord(self):
        record = Recorder()
        values = [record.step(x) for x in [{17}, set(), {65}, {65, 66}, {66}, set()]]
        self.assertEqual(values, [None, None, None, None, None, "A+B"])

    def test_sequential_keys_are_not_combined(self):
        record = Recorder()
        values = [record.step(x) for x in [set(), {65}, {66}, set()]]
        self.assertEqual(values, [None, None, None, "A"])

    def test_single_modifier_and_insert(self):
        for key, name in [(45, "INSERT"), (17, "CTRL"), (27, "ESC")]:
            record = Recorder()
            record.step(set())
            record.step({key})
            self.assertEqual(record.step(set()), name)
