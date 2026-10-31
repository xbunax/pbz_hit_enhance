"""Global hotkey worker. UI thread communicates only through queues."""

import ctypes as C, ctypes.wintypes as W, queue, threading, time

u = C.WinDLL("user32", use_last_error=True)
k = C.WinDLL("kernel32", use_last_error=True)
u.RegisterHotKey.argtypes = [W.HWND, C.c_int, W.UINT, W.UINT]
u.RegisterHotKey.restype = W.BOOL
u.UnregisterHotKey.argtypes = [W.HWND, C.c_int]
u.UnregisterHotKey.restype = W.BOOL
u.PeekMessageW.argtypes = [C.POINTER(W.MSG), W.HWND, W.UINT, W.UINT, W.UINT]
u.PeekMessageW.restype = W.BOOL
k.CreateMutexW.argtypes = [C.c_void_p, W.BOOL, W.LPCWSTR]
k.CreateMutexW.restype = W.HANDLE
k.CreateEventW.argtypes = [C.c_void_p, W.BOOL, W.BOOL, W.LPCWSTR]
k.CreateEventW.restype = W.HANDLE
k.SetEvent.argtypes = [W.HANDLE]
k.SetEvent.restype = W.BOOL
k.WaitForSingleObject.argtypes = [W.HANDLE, W.DWORD]
k.WaitForSingleObject.restype = W.DWORD
k.CloseHandle.argtypes = [W.HANDLE]
k.CloseHandle.restype = W.BOOL
KEYS = {
    "INSERT": 0x2D,
    **{f"F{i}": 0x6F + i for i in range(1, 13)},
    **{c: ord(c) for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"},
}


def normalize(value):
    parts = value.upper().replace("CONTROL", "CTRL").split("+")
    parts = [p.strip() for p in parts]
    if parts[-1] == "INS":
        parts[-1] = "INSERT"
    if parts[-1] not in KEYS:
        raise ValueError("请选择 Insert、F1–F12、字母或数字；修饰键可不选")
    mods = parts[:-1]
    if len(set(mods)) != len(mods) or any(p not in ("CTRL", "ALT", "SHIFT") for p in mods):
        raise ValueError("快捷键格式无效")
    names = [n for n in ("CTRL", "ALT", "SHIFT") if n in mods]
    flags = sum({"CTRL": 2, "ALT": 1, "SHIFT": 4}[n] for n in names)
    return "+".join([*names, parts[-1]]), flags, KEYS[parts[-1]]


class SingleInstance:
    def __init__(self, notify=True):
        self.mutex = k.CreateMutexW(None, False, r"Local\PBZ_UnifiedHitstop_UI_v01")
        if not self.mutex:
            raise C.WinError(C.get_last_error())
        self.existing = C.get_last_error() == 183
        self.event = k.CreateEventW(None, False, False, r"Local\PBZ_UnifiedHitstop_Show_v01")
        if not self.event:
            raise C.WinError(C.get_last_error())
        if self.existing and notify:
            k.SetEvent(self.event)

    def close(self):
        k.CloseHandle(self.event)
        k.CloseHandle(self.mutex)


class HotkeyWorker(threading.Thread):
    def __init__(self, outbox, event):
        super().__init__(daemon=True)
        self.outbox = outbox
        self.commands = queue.Queue()
        self.event = event

    def run(self):
        active = None
        active_id = None
        msg = W.MSG()
        running = True
        while running:
            while True:
                try:
                    action, value = self.commands.get_nowait()
                except queue.Empty:
                    break
                if action == "stop":
                    running = False
                    break
                if action == "set":
                    try:
                        name, mods, key = normalize(value)
                        if name != active:
                            new_id = 2 if active_id == 1 else 1
                            if not u.RegisterHotKey(None, new_id, mods | 0x4000, key):
                                raise OSError(
                                    C.get_last_error(),
                                    "快捷键已被其他程序占用，或无法注册",
                                )
                            if active_id is not None:
                                u.UnregisterHotKey(None, active_id)
                            active = name
                            active_id = new_id
                        self.outbox.put(("registered", name))
                    except Exception as exc:
                        self.outbox.put(("hotkey_error", str(exc)))
            while u.PeekMessageW(C.byref(msg), None, 0, 0, 1):
                if msg.message == 0x0312 and msg.wParam == active_id:
                    self.outbox.put(("toggle", None))
            if self.event and k.WaitForSingleObject(self.event, 0) == 0:
                self.outbox.put(("show", None))
            time.sleep(0.025)
        if active_id is not None:
            u.UnregisterHotKey(None, active_id)
