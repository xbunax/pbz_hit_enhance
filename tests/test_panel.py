"""Exercise real Tk controls against an isolated config; never register global hotkeys."""

import json
from pathlib import Path
import queue
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "gui"))
try:
    import tkinter as tk
    import panel
except ImportError:
    tk = None


class Worker:
    def __init__(self, *args):
        self.commands = queue.Queue()

    def start(self):
        pass

    def join(self, **kwargs):
        pass


class Instance:
    event = None

    def close(self):
        pass


@unittest.skipIf(tk is None, "Tk is unavailable in embedded test Python")
class PanelTests(unittest.TestCase):
    def setUp(self):
        folder = Path(__file__).resolve().parents[1] / "build/ui-tests"
        folder.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=folder)
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.config = self.folder / "config.ini"
        self.config.write_text(
            panel.configure.serialize(panel.configure.defaults()), encoding="utf-8"
        )
        settings = self.folder / "ui_settings.json"
        settings.write_text(json.dumps({"hotkey": "CTRL+F10"}), encoding="utf-8")
        for target, value in [
            ("panel.ROOT", self.folder),
            ("panel.SETTINGS", settings),
            ("panel.configure.PATH", self.config),
            ("panel.HotkeyWorker", Worker),
        ]:
            p = patch(target, value)
            p.start()
            self.addCleanup(p.stop)
        self.root = tk.Tk()
        self.p = panel.Panel(self.root, Instance(), auto_start=True)
        self.root.update_idletasks()
        self.addCleanup(self.p.exit)

    def select(self, name):
        self.p.profile_choice.set(panel.PROFILE_NAMES[name])
        self.p.switch_profile()

    def fixed(self, frames):
        self.p.mode.set(panel.REVERSE["fixed"])
        self.p.change_mode()
        self.p.amount.set(frames)
        self.p.override.set(True)
        self.p.schedule_save()

    def test_switch_flushes_pending_edits_without_cross_contamination(self):
        for name, frames in [("Blade", 5), ("DoubleBlade", 7), ("GreatBlade", 9)]:
            self.select(name)
            self.fixed(frames)
        self.select("Global")
        c = panel.configure.read()
        self.assertEqual([c[k + ".FixedFrames"] for k in panel.configure.PROFILES], ["5", "7", "9"])
        self.assertEqual(c["Scale"], "1.0")
        for name, frames in [("Blade", 5), ("DoubleBlade", 7), ("GreatBlade", 9)]:
            self.select(name)
            self.assertEqual(self.p.amount.get(), frames)
            self.assertTrue(self.p.override.get())

    def test_mode_switch_preserves_each_amount(self):
        self.select("Blade")
        self.p.amount.set(2.25)
        self.p.schedule_save()
        self.fixed(8)
        self.p.mode.set(panel.REVERSE["scale"])
        self.p.change_mode()
        self.assertEqual(self.p.amount.get(), 2.25)
        self.select("Global")
        c = panel.configure.read()
        self.assertEqual(c["Blade.FixedFrames"], "8")
        self.assertEqual(c["Blade.Scale"], "2.25")

    def test_observation_and_reset_preserve_other_profiles(self):
        self.select("DoubleBlade")
        self.fixed(7)
        self.select("Blade")
        self.fixed(5)
        self.p.observe_only.set(True)
        self.p.save()
        self.p.reset()
        c = panel.configure.read()
        self.assertEqual(c["ObserveOnly"], "true")
        self.assertEqual(c["Blade.Override"], "false")
        self.assertEqual(c["DoubleBlade.FixedFrames"], "7")
        self.assertEqual(c["DoubleBlade.Override"], "true")

    def test_invalid_cap_blocks_switch_and_does_not_overwrite_file(self):
        self.select("Blade")
        before = self.config.read_bytes()
        self.p.cap.set("1.5")
        self.p.schedule_save()
        self.select("DoubleBlade")
        self.assertEqual(self.p.editing_profile, "Blade")
        self.assertEqual(self.config.read_bytes(), before)
        self.assertIn("未保存", self.p.note.get())

    def test_status_reports_observation_and_category(self):
        import time

        (self.folder / "status.ini").write_text(
            f"Timestamp={int(time.time())}\nReady=true\nFault=false\nEnabled=true\n"
            "Seen=5\nChanged=0\nBefore=4\nAfter=4\nObserveOnly=true\n"
            "WeaponGroup=DoubleBlade\nProfile=DoubleBlade\nAttackType=example\nReason=observe_only\n",
            encoding="utf-8",
        )
        self.p.status()
        self.assertIn("仅记录", self.p.connection.get())
        self.assertIn("双持", self.p.status_text.get())
        self.assertIn("4 → 4", self.p.status_text.get())

    def test_single_insert_saved_and_restored_in_controls(self):
        self.p.registering = False
        for variable in self.p.mod_vars.values():
            variable.set(False)
        self.p.key_var.set("INSERT")
        self.p.register_selected()
        queued = []
        while not self.p.worker.commands.empty():
            queued.append(self.p.worker.commands.get_nowait())
        self.assertEqual(queued[-1], ("set", "INSERT"))
        self.p.events.put(("registered", "INSERT"))
        self.p.poll()
        self.assertEqual(self.p.shortcut, "INSERT")
        self.assertEqual(self.p.key_var.get(), "INSERT")
        self.assertFalse(any(v.get() for v in self.p.mod_vars.values()))
        saved = json.loads((self.folder / "ui_settings.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["hotkey"], "INSERT")
