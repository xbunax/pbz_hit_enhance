"""Keyboard chord names and edge/recording state, independent of Windows and Tk."""

KEYS = {
    "CTRL": 0x11,
    "ALT": 0x12,
    "SHIFT": 0x10,
    "WIN": 0x5B,
    "BACKSPACE": 0x08,
    "TAB": 0x09,
    "ENTER": 0x0D,
    "PAUSE": 0x13,
    "CAPSLOCK": 0x14,
    "ESC": 0x1B,
    "SPACE": 0x20,
    "PAGEUP": 0x21,
    "PAGEDOWN": 0x22,
    "END": 0x23,
    "HOME": 0x24,
    "LEFT": 0x25,
    "UP": 0x26,
    "RIGHT": 0x27,
    "DOWN": 0x28,
    "PRINTSCREEN": 0x2C,
    "INSERT": 0x2D,
    "DELETE": 0x2E,
    "MENU": 0x5D,
    **{c: ord(c) for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"},
    **{f"NUM{i}": 0x60 + i for i in range(10)},
    "NUMMULTIPLY": 0x6A,
    "NUMADD": 0x6B,
    "NUMSEPARATOR": 0x6C,
    "NUMSUBTRACT": 0x6D,
    "NUMDECIMAL": 0x6E,
    "NUMDIVIDE": 0x6F,
    **{f"F{i}": 0x6F + i for i in range(1, 25)},
    "NUMLOCK": 0x90,
    "SCROLLLOCK": 0x91,
    "SEMICOLON": 0xBA,
    "EQUALS": 0xBB,
    "COMMA": 0xBC,
    "MINUS": 0xBD,
    "PERIOD": 0xBE,
    "SLASH": 0xBF,
    "BACKTICK": 0xC0,
    "LBRACKET": 0xDB,
    "BACKSLASH": 0xDC,
    "RBRACKET": 0xDD,
    "QUOTE": 0xDE,
}
# Poll keyboard keys we can bind, not reserved VKs or media-device state.
# A multimedia device may report PLAY/PAUSE as held indefinitely.
# Left/right modifiers are equivalent; their duplicate VK codes are not scanned.
SCAN_KEYS = frozenset(KEYS.values())
NAMES = {vk: name for name, vk in KEYS.items()}
ALIASES = {"CONTROL": "CTRL", "INS": "INSERT", "ESCAPE": "ESC", "RETURN": "ENTER", "DEL": "DELETE"}
MODIFIERS = (0x11, 0x12, 0x10, 0x5B)


def chord_name(keys):
    return "+".join(
        NAMES[k]
        for k in (*[v for v in MODIFIERS if v in keys], *sorted(set(keys) - set(MODIFIERS)))
    )


def normalize(value):
    if not isinstance(value, str):
        raise ValueError("请先录入按键")
    parts = [ALIASES.get(p.strip().upper(), p.strip().upper()) for p in value.split("+")]
    if any(p not in KEYS for p in parts) or len(set(parts)) != len(parts):
        raise ValueError("快捷键格式无效，请重新录入")
    keys = frozenset(KEYS[p] for p in parts)
    return chord_name(keys), keys


class ChordLatch:
    """Fire once per complete press; require release before enabling a new binding."""

    def __init__(self, keys=()):
        self.keys = frozenset(keys)
        self.armed = False

    def step(self, pressed):
        if not self.keys.intersection(pressed):
            self.armed = True
        modifiers_match = set(pressed).intersection(MODIFIERS) == self.keys.intersection(MODIFIERS)
        if self.keys and self.armed and self.keys.issubset(pressed) and modifiers_match:
            self.armed = False
            return True
        return False


class Recorder:
    """Ignore already-held keys; record simultaneous keys until the first release."""

    def __init__(self):
        self.armed = False
        self.chord = frozenset()
        self.releasing = False

    def step(self, pressed):
        pressed = frozenset(pressed)
        if not self.armed:
            self.armed = not pressed
            return None
        if self.chord - pressed:
            self.releasing = True
        if self.releasing:
            return chord_name(self.chord) if not pressed else None
        self.chord = pressed
        return None
