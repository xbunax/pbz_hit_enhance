"""Global hotkey worker. UI thread communicates only through queues."""

import ctypes as C, ctypes.wintypes as W, queue, threading, time

u = C.WinDLL("user32", use_last_error=True)
k = C.WinDLL("kernel32", use_last_error=True)
u.GetAsyncKeyState.argtypes = [C.c_int]
u.GetAsyncKeyState.restype = C.c_short
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
from keybinds import normalize, SCAN_KEYS, ChordLatch, Recorder, chord_name


def pressed_keys():
    keys = {key for key in SCAN_KEYS if u.GetAsyncKeyState(key) & 0x8000}
    if u.GetAsyncKeyState(0x5C) & 0x8000:
        keys.add(0x5B)
    return frozenset(keys)


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
        latch = ChordLatch()
        recorder = None
        suspended = False
        deadline = 0
        preview = None
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
                if action == "record":
                    recorder = Recorder()
                    suspended = True
                    deadline = time.monotonic() + 15
                    preview = None
                elif action == "cancel":
                    recorder = None
                    suspended = False
                    latch.armed = False
                elif action == "set":
                    try:
                        name, keys = normalize(value)
                        latch = ChordLatch(keys)
                        recorder = None
                        suspended = False
                        self.outbox.put(("registered", name))
                    except Exception as exc:
                        self.outbox.put(("hotkey_error", str(exc)))
            if not running:
                break
            pressed = pressed_keys()
            if recorder:
                if time.monotonic() >= deadline:
                    recorder = None
                    suspended = False
                    latch.armed = False
                    self.outbox.put(("capture_cancelled", "录入超时，保留原快捷键。"))
                else:
                    captured = recorder.step(pressed)
                    current = chord_name(recorder.chord)
                    if current != preview:
                        preview = current
                        self.outbox.put(("capture_preview", current))
                    if captured:
                        recorder = None
                        self.outbox.put(("captured", captured))
            elif not suspended and latch.step(pressed):
                self.outbox.put(("toggle", None))
            if self.event and k.WaitForSingleObject(self.event, 0) == 0:
                self.outbox.put(("show", None))
            time.sleep(0.015)
