"""Process handles, session singleton and the real Tk shutdown path."""

import os
from pathlib import Path
import queue
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "gui"))
from session import GameSession
from hotkey import SingleInstance, k

try:
    import tkinter as tk
    import panel
except ImportError:
    tk = None


class SessionTests(unittest.TestCase):
    def child(self, seconds=30):
        p = subprocess.Popen(
            [sys.executable, "-c", f"import time;time.sleep({seconds})"], creationflags=0x08000000
        )
        self.addCleanup(lambda: p.poll() is None and (p.terminate(), p.wait(timeout=3)))
        return p

    def test_handle_detects_process_exit_and_rejects_reused_identity(self):
        p = self.child()
        session = GameSession(p.pid)
        self.addCleanup(session.close)
        self.assertTrue(session.alive())
        with self.assertRaises(ValueError):
            GameSession(p.pid, session.created_at + 1, session.executable)
        with self.assertRaises(ValueError):
            GameSession(p.pid, session.created_at, Path(sys.executable).with_name("other.exe"))
        p.terminate()
        p.wait(timeout=3)
        self.assertFalse(session.alive())

    def test_natural_exit_is_signalled(self):
        p = self.child(0.1)
        session = GameSession(p.pid)
        self.addCleanup(session.close)
        p.wait(timeout=3)
        self.assertFalse(session.alive())

    def test_singleton_is_per_session_and_repeated_launch_signals_show(self):
        token = f"test_{os.getpid()}"
        a = SingleInstance(False, token)
        self.addCleanup(a.close)
        b = SingleInstance(True, token)
        self.addCleanup(b.close)
        c = SingleInstance(False, token + "_new")
        self.addCleanup(c.close)
        self.assertFalse(a.existing)
        self.assertTrue(b.existing)
        self.assertFalse(c.existing)
        self.assertEqual(k.WaitForSingleObject(a.event, 0), 0)


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


@unittest.skipIf(tk is None, "Tk not installed")
class TkLifecycleTests(unittest.TestCase):
    def test_game_exit_closes_hidden_panel_within_three_seconds(self):
        import tempfile

        folder = Path(__file__).resolve().parents[1] / "build/session-tests"
        folder.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=folder) as directory:
            data = Path(directory)
            config = data / "config.ini"
            config.write_text(panel.configure.serialize(panel.configure.defaults()))
            (data / "ui_settings.json").write_text('{"hotkey":"CTRL+F10"}')
            child = subprocess.Popen(
                [sys.executable, "-c", "import time;time.sleep(.35)"], creationflags=0x08000000
            )
            session = GameSession(child.pid)
            try:
                with (
                    patch.object(panel, "ROOT", data),
                    patch.object(panel, "SETTINGS", data / "ui_settings.json"),
                    patch.object(panel.configure, "PATH", config),
                    patch.object(panel, "HotkeyWorker", Worker),
                ):
                    root = tk.Tk()
                    p = panel.Panel(root, Instance(), auto_start=True, session=session)
                    root.after(2500, p.exit)
                    start = time.monotonic()
                    root.mainloop()
                    elapsed = time.monotonic() - start
                    self.assertLess(elapsed, 2)
                    self.assertTrue(p.exiting)
                    self.assertIsNone(session.handle)
            finally:
                if child.poll() is None:
                    child.terminate()
                child.wait(timeout=3)
                session.close()

    def test_no_game_manual_launch_displays_message_and_returns(self):
        with (
            patch.object(
                panel.GameSession, "from_arguments", side_effect=ValueError("请先启动游戏")
            ),
            patch.object(panel.messagebox, "showinfo") as message,
            patch.object(sys, "argv", ["panel.py"]),
        ):
            panel.main()
            message.assert_called_once()
