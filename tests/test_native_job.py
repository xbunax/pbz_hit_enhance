"""Test the production Job launcher with normal and abrupt host termination."""

from pathlib import Path
import subprocess, sys, tempfile, time, unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "gui"))
from session import GameSession

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "build/native/Release/pbz_job_fixture.exe"


@unittest.skipUnless(FIXTURE.is_file(), "Native fixture is built before CI tests")
class NativeJobTests(unittest.TestCase):
    def run_case(self, abrupt):
        folder = ROOT / "build/job-tests"
        folder.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=folder) as temp:
            output = Path(temp) / "child.pid"
            host = subprocess.Popen(
                [str(FIXTURE), sys.executable, str(output), temp, "60000" if abrupt else "700"],
                creationflags=0x08000000,
            )
            try:
                end = time.monotonic() + 3
                while not output.exists() and time.monotonic() < end:
                    time.sleep(0.01)
                self.assertTrue(output.exists(), "Native launch failed")
                child = GameSession(int(output.read_text()))
                try:
                    self.assertTrue(child.alive())
                    if abrupt:
                        host.terminate()
                    host.wait(timeout=3)
                    end = time.monotonic() + 2
                    while child.alive() and time.monotonic() < end:
                        time.sleep(0.01)
                    self.assertFalse(child.alive(), "Job child survived its host")
                finally:
                    child.close()
            finally:
                if host.poll() is None:
                    host.terminate()
                    host.wait(timeout=3)

    def test_normal_host_exit_reclaims_child(self):
        self.run_case(False)

    def test_abrupt_host_exit_reclaims_child(self):
        self.run_case(True)
