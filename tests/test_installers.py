"""Run the distributed PowerShell installers against isolated fake game/runtime files."""

from pathlib import Path
import hashlib, json, os, subprocess, tempfile, unittest

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class InstallerTests(unittest.TestCase):
    def setUp(self):
        root = ROOT / "build/installer-tests"
        root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.game = self.base / "game [fixture]"
        self.game.mkdir()
        (self.game / "PBZ.exe").write_bytes(b"isolated fake executable, never run")
        self.data = self.base / "data [fixture]"
        self.runtime = self.base / "shared runtime"
        self.runtime.mkdir()
        (self.runtime / "UE4SS.dll").write_bytes(b"other runtime, must never be touched")
        self.mods = self.runtime / "Mods"
        self.mods.mkdir()
        (self.runtime / "UE4SS-settings.ini").write_text("[Overrides]\n", encoding="utf-8")
        (self.mods / "mods.txt").write_text(
            "OtherMod : 1\n; shared comment\nUnifiedHitstop : 0\nLastMod : 0\n", encoding="utf-8"
        )

    def package(self, mode):
        p = self.base / ("package " + mode)
        p.mkdir()
        for script in ["Install.ps1", "Uninstall.ps1"]:
            (p / script).write_text(
                (ROOT / "tools" / script).read_text(encoding="utf-8-sig"), encoding="utf-8-sig"
            )
        if mode == "with-UE4SS":
            mod = p / "PBZHitEnhance/ue4ss/Mods/UnifiedHitstop"
            (p / "dwmapi.dll").write_bytes(b"our fixture proxy")
            (p / "PBZHitEnhance/ue4ss").mkdir(parents=True)
            (p / "PBZHitEnhance/ue4ss/UE4SS.dll").write_bytes(b"bundled fixture runtime")
        else:
            mod = p / "UnifiedHitstop"
        (mod / "Scripts").mkdir(parents=True)
        (mod / "Scripts/main.lua").write_text("-- PBZ UnifiedHitstop fixture\n")
        (mod / "config.ini").write_text("Blade.Scale=1\n")
        (p / "package.json").write_text(
            json.dumps(
                {
                    "mode": mode,
                    "version": "0.4.0-preview.2",
                    "game_hash": sha(self.game / "PBZ.exe"),
                }
            )
        )
        manifest = {f.relative_to(p).as_posix(): sha(f) for f in p.rglob("*") if f.is_file()}
        (p / "package_manifest.json").write_text(json.dumps(manifest))
        return p

    def invoke(self, package, *args, ok=True, uninstall=False):
        cmd = [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(package / ("Uninstall.ps1" if uninstall else "Install.ps1")),
        ]
        if not uninstall:
            cmd += ["-GameDirectory", str(self.game), "-DataDirectory", str(self.data)]
        env = {k: v for k, v in os.environ.items() if k.casefold() != "psmodulepath"}
        result = subprocess.run(cmd + list(args), capture_output=True, timeout=30, env=env)
        output = (result.stdout + result.stderr).decode("utf-8", errors="replace")
        self.assertEqual(result.returncode == 0, ok, output)
        return output

    def record(self):
        return json.loads((self.data / "install-record.json").read_text(encoding="utf-8-sig"))

    def test_full_upgrade_then_shared_migration_and_uninstall_preserves_other_mods(self):
        full = self.package("with-UE4SS")
        only = self.package("mod-only")
        shared_hashes = {
            p: sha(p) for p in [self.runtime / "UE4SS.dll", self.runtime / "UE4SS-settings.ini"]
        }
        self.invoke(full)
        first = self.record()
        old = Path(first["data"]) / "ue4ss/Mods/UnifiedHitstop"
        (old / "config.ini").write_text("Blade.Scale=3\n")
        (old / "ui_settings.json").write_text('{"hotkey":"INSERT"}')
        self.invoke(full)
        second = self.record()
        self.assertNotEqual(first["data"], second["data"])
        self.assertEqual(
            (Path(second["data"]) / "ue4ss/Mods/UnifiedHitstop/config.ini").read_text(),
            "Blade.Scale=3\n",
        )
        self.invoke(only, "-UE4SSDirectory", str(self.runtime))
        record = self.record()
        new = Path(record["data"]) / "UnifiedHitstop"
        self.assertFalse((self.game / "dwmapi.dll").exists())
        self.assertFalse((self.game / "PBZHitEnhance.ini").exists())
        self.assertEqual((new / "config.ini").read_text(), "Blade.Scale=3\n")
        self.assertEqual(json.loads((new / "ui_settings.json").read_text())["hotkey"], "INSERT")
        text = (self.mods / "mods.txt").read_text()
        self.assertEqual(text, "OtherMod : 1\n; shared comment\nUnifiedHitstop : 1\nLastMod : 0\n")
        self.assertEqual((self.mods / "UnifiedHitstop/config.ini").read_text(), "Blade.Scale=3\n")
        with (self.mods / "mods.txt").open("a") as f:
            f.write("AddedLater : 1\n")
        self.invoke(only, "-InstallRecord", str(self.data / "install-record.json"), uninstall=True)
        self.assertFalse((self.mods / "UnifiedHitstop").exists())
        self.assertEqual(
            (self.mods / "mods.txt").read_text(),
            "OtherMod : 1\n; shared comment\nLastMod : 0\nAddedLater : 1\n",
        )
        self.assertEqual({p: sha(p) for p in shared_hashes}, shared_hashes)
        self.assertTrue((new / "config.ini").exists())

    def test_updated_game_does_not_block_installation(self):
        p = self.package("with-UE4SS")
        (self.game / "PBZ.exe").write_bytes(b"updated fake executable, never run")
        self.invoke(p)
        self.assertTrue((self.game / "dwmapi.dll").is_file())
        self.assertTrue((Path(self.record()["data"]) / "ue4ss/UE4SS.dll").is_file())

    def test_missing_game_executable_still_fails(self):
        p = self.package("with-UE4SS")
        (self.game / "PBZ.exe").unlink()
        self.invoke(p, ok=False)
        self.assertFalse(self.data.exists())

    def test_existing_proxy_is_never_overwritten(self):
        p = self.package("with-UE4SS")
        dll = self.game / "dwmapi.dll"
        dll.write_bytes(b"foreign proxy")
        self.invoke(p, ok=False)
        self.assertEqual(dll.read_bytes(), b"foreign proxy")
        self.assertFalse(self.data.exists())

    def test_tampered_package_fails_before_install(self):
        p = self.package("mod-only")
        (p / "UnifiedHitstop/config.ini").write_text("tampered")
        self.invoke(p, "-UE4SSDirectory", str(self.runtime), ok=False)
        self.assertFalse(self.data.exists())

    def test_explicit_mods_directory_keeps_controlling_file_override(self):
        p = self.package("mod-only")
        control = self.runtime / "control.txt"
        control.write_text("OtherMod : 1\n")
        (self.runtime / "UE4SS-settings.ini").write_text(
            "[Overrides]\nControllingModsTxt = control.txt\n"
        )
        original = (self.mods / "mods.txt").read_bytes()
        self.invoke(p, "-UE4SSDirectory", str(self.runtime), "-ModsDirectory", str(self.mods))
        self.assertIn("UnifiedHitstop : 1", control.read_text())
        self.assertEqual((self.mods / "mods.txt").read_bytes(), original)
        self.invoke(p, "-InstallRecord", str(self.data / "install-record.json"), uninstall=True)

    def test_mod_only_upgrade_preserves_existing_external_junction(self):
        p = self.package("mod-only")
        self.invoke(p, "-UE4SSDirectory", str(self.runtime))
        first = self.record()
        mod = Path(first["data"]) / "UnifiedHitstop"
        (mod / "config.ini").write_text("Blade.Scale=2.5\n")
        self.invoke(p, "-UE4SSDirectory", str(self.runtime))
        record = self.record()
        new = Path(record["data"]) / "UnifiedHitstop"
        self.assertEqual((new / "config.ini").read_text(), "Blade.Scale=2.5\n")
        self.assertEqual((self.mods / "UnifiedHitstop/config.ini").read_text(), "Blade.Scale=2.5\n")
        self.assertTrue((mod / "config.ini").exists())
        self.invoke(p, "-InstallRecord", str(self.data / "install-record.json"), uninstall=True)

    def test_failed_shared_upgrade_restores_old_junction_and_list(self):
        import ctypes as C
        from ctypes import wintypes as W

        package = self.package("mod-only")
        self.invoke(package, "-UE4SSDirectory", str(self.runtime))
        before = self.record()
        target = Path(before["data"]) / "UnifiedHitstop"
        (target / "config.ini").write_text("Blade.Scale=2.25\n")
        control = self.mods / "mods.txt"
        original = control.read_bytes()
        kernel = C.WinDLL("kernel32", use_last_error=True)
        kernel.CreateFileW.argtypes = [
            W.LPCWSTR,
            W.DWORD,
            W.DWORD,
            C.c_void_p,
            W.DWORD,
            W.DWORD,
            W.HANDLE,
        ]
        kernel.CreateFileW.restype = W.HANDLE
        kernel.CloseHandle.argtypes = [W.HANDLE]
        handle = kernel.CreateFileW(str(control), 0x80000000, 1, None, 3, 0, None)
        self.assertNotEqual(handle, C.c_void_p(-1).value)
        try:
            self.invoke(package, "-UE4SSDirectory", str(self.runtime), ok=False)
        finally:
            kernel.CloseHandle(handle)
        self.assertEqual(self.record()["data"], before["data"])
        self.assertEqual(
            (self.mods / "UnifiedHitstop/config.ini").read_text(), "Blade.Scale=2.25\n"
        )
        self.assertEqual(control.read_bytes(), original)
        self.invoke(
            package, "-InstallRecord", str(self.data / "install-record.json"), uninstall=True
        )
