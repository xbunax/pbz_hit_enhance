"""Bind a panel to an exact Windows process, including creation time (PID reuse safe)."""

import argparse
import ctypes as C
import ctypes.wintypes as W
import hashlib
import json
from pathlib import Path

k = C.WinDLL("kernel32", use_last_error=True)
k.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
k.OpenProcess.restype = W.HANDLE
k.CloseHandle.argtypes = [W.HANDLE]
k.CloseHandle.restype = W.BOOL
k.GetProcessTimes.argtypes = [W.HANDLE, *[C.POINTER(W.FILETIME)] * 4]
k.GetProcessTimes.restype = W.BOOL
k.QueryFullProcessImageNameW.argtypes = [W.HANDLE, W.DWORD, W.LPWSTR, C.POINTER(W.DWORD)]
k.QueryFullProcessImageNameW.restype = W.BOOL
k.WaitForSingleObject.argtypes = [W.HANDLE, W.DWORD]
k.WaitForSingleObject.restype = W.DWORD


class GameSession:
    def __init__(self, pid, created_at=None, executable=None):
        self.handle = k.OpenProcess(0x100000 | 0x1000, False, pid)
        if not self.handle:
            raise OSError("无法连接游戏进程，请先启动游戏。")
        try:
            times = [W.FILETIME() for _ in range(4)]
            if not k.GetProcessTimes(self.handle, *[C.byref(t) for t in times]):
                raise C.WinError(C.get_last_error())
            self.created_at = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
            name = C.create_unicode_buffer(32768)
            length = W.DWORD(len(name))
            if not k.QueryFullProcessImageNameW(self.handle, 0, name, C.byref(length)):
                raise C.WinError(C.get_last_error())
            self.executable = Path(name.value).resolve()
            self.pid = pid
            if created_at is not None and self.created_at != created_at:
                raise ValueError("游戏进程已经变化，请重新启动面板。")
            if (
                executable is not None
                and str(self.executable).casefold() != str(Path(executable).resolve()).casefold()
            ):
                raise ValueError("游戏进程路径不匹配。")
            if not self.alive():
                raise ValueError("游戏已退出。")
        except BaseException:
            self.close()
            raise

    @property
    def token(self):
        return f"{self.pid}_{self.created_at}"

    def alive(self):
        result = k.WaitForSingleObject(self.handle, 0)
        if result == 0xFFFFFFFF:
            raise C.WinError(C.get_last_error())
        return result == 0x102

    def close(self):
        if self.handle:
            k.CloseHandle(self.handle)
            self.handle = None

    @classmethod
    def from_arguments(cls, mod_dir):
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument("--game-pid", type=int)
        parser.add_argument("--game-created-at", type=int)
        parser.add_argument("--game-exe")
        args, _ = parser.parse_known_args()
        values = (args.game_pid, args.game_created_at, args.game_exe)
        if any(v is not None for v in values):
            if any(v is None for v in values):
                raise ValueError("游戏会话参数不完整。")
            session = cls(*values)
            if session.executable.name.casefold() != "pbz.exe":
                session.close()
                raise ValueError("目标不是影之刃零游戏进程。")
            return session
        ps = C.WinDLL("psapi", use_last_error=True)
        ps.EnumProcesses.argtypes = [C.POINTER(W.DWORD), W.DWORD, C.POINTER(W.DWORD)]
        ps.EnumProcesses.restype = W.BOOL
        ids = (W.DWORD * 8192)()
        size = W.DWORD()
        if not ps.EnumProcesses(ids, C.sizeof(ids), C.byref(size)):
            raise C.WinError(C.get_last_error())
        metadata = json.loads((Path(mod_dir) / "dependencies.json").read_text())
        expected = metadata["game"]["exe_sha256"]
        matches = []
        for pid in ids[: size.value // 4]:
            try:
                session = cls(pid)
            except (OSError, ValueError):
                continue
            if session.executable.name.casefold() != "pbz.exe":
                session.close()
                continue
            try:
                with session.executable.open("rb") as f:
                    valid = hashlib.file_digest(f, "sha256").hexdigest() == expected
            except OSError:
                valid = False
            if valid:
                matches.append(session)
            else:
                session.close()
        if len(matches) != 1:
            for session in matches:
                session.close()
            raise ValueError(
                "请先启动受支持的游戏，再打开面板。"
                if not matches
                else "检测到多个游戏进程，请通过对应游戏自动启动面板。"
            )
        return matches[0]


def monitor(root, session, on_exit):
    """Tk timer; independent of game pause, map loading and Lua heartbeat."""

    def check():
        try:
            alive = session.alive()
        except OSError:
            alive = False
        if not alive:
            on_exit()
        else:
            root.after(250, check)

    root.after(250, check)
