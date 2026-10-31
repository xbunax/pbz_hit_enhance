"""Worker integration with deterministic key state; never send OS keyboard input."""

import queue
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "gui"))
from hotkey import HotkeyWorker


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.pressed = frozenset()
        self.sampled = threading.Event()

        def read():
            result = self.pressed
            self.sampled.set()
            return result

        self.mock = patch("hotkey.pressed_keys", read)
        self.mock.start()
        self.events = queue.Queue()
        self.worker = HotkeyWorker(self.events, None)
        self.worker.start()
        self.addCleanup(self.cleanup)

    def cleanup(self):
        self.worker.commands.put(("stop", None))
        self.worker.join(timeout=2)
        self.assertFalse(self.worker.is_alive())
        self.mock.stop()

    def keys(self, *values):
        self.pressed = frozenset(values)
        self.sampled.clear()
        self.assertTrue(self.sampled.wait(1))
        time.sleep(0.02)

    def receive(self, kind):
        end = time.monotonic() + 2
        while time.monotonic() < end:
            event = self.events.get(timeout=2)
            if event[0] == kind:
                return event[1]
        self.fail("Missing event " + kind)

    def test_record_save_and_trigger_arbitrary_chord(self):
        self.worker.commands.put(("set", "INSERT"))
        self.assertEqual(self.receive("registered"), "INSERT")
        self.worker.commands.put(("record", None))
        self.receive("capture_preview")
        self.keys(65)
        self.keys(65, 66)
        self.keys(66)
        self.keys()
        self.assertEqual(self.receive("captured"), "A+B")
        self.worker.commands.put(("set", "A+B"))
        self.assertEqual(self.receive("registered"), "A+B")
        self.keys()
        self.keys(65, 66)
        self.receive("toggle")
        self.keys(65, 66)
        self.assertTrue(self.events.empty())
        self.keys(65)
        self.keys(65, 66)
        self.assertTrue(self.events.empty())
        self.keys()
        self.keys(65, 66)
        self.receive("toggle")

    def test_cancel_restores_old_binding(self):
        self.worker.commands.put(("set", "INSERT"))
        self.receive("registered")
        self.worker.commands.put(("record", None))
        self.receive("capture_preview")
        self.keys(45)
        self.keys()
        self.assertEqual(self.receive("captured"), "INSERT")
        self.keys(45)
        self.assertTrue(self.events.empty())
        self.worker.commands.put(("cancel", None))
        self.keys()
        self.keys(45)
        self.receive("toggle")
