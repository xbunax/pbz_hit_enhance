"""Floating, configurable global-hotkey control panel for PBZ UnifiedHitstop."""

from pathlib import Path
import json, os, queue, sys, time, traceback
import tkinter as tk
from tkinter import ttk, messagebox
from session import GameSession, monitor
import configure
from hotkey import HotkeyWorker, SingleInstance, normalize
from paths import mod_root

ROOT = mod_root()
SETTINGS = ROOT / "ui_settings.json"
MODES = {"按比例缩放": "scale", "增加 / 减少帧数": "add", "固定帧数": "fixed"}
REVERSE = {v: k for k, v in MODES.items()}
DEFAULT = configure.defaults()
PROFILES = {
    "全局默认": "Global",
    "单手刀剑": "Blade",
    "双持武器": "DoubleBlade",
    "双手重武器": "GreatBlade",
}
PROFILE_NAMES = {v: k for k, v in PROFILES.items()}


def atomic_text(path, text):
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


class Panel:
    def __init__(self, root, instance, auto_start=False, session=None):
        self.root = root
        self.session = session
        self.exiting = False
        self.instance = instance
        self.events = queue.Queue()
        self.worker = HotkeyWorker(self.events, instance.event)
        self.worker.start()
        self.shortcut = None
        self.dialog = None
        self.save_after = None
        self.loading = False
        self.updating = False
        self.config_stamp = None
        self.last_status = {}
        self.editing_profile = "Global"
        self.value_mode = "scale"
        self.registering = False
        self.recording = False
        self.capture_pending = False
        self.drag_origin = None
        self.root.title("影之刃零 · 卡肉调节")
        self.root.withdraw()
        self.root.overrideredirect(False)
        self.root.resizable(False, False)
        self.root.geometry("670x610+70+70")
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.96)
        self.root.configure(bg="#677078")
        self.root.protocol("WM_DELETE_WINDOW", self.hide)
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            ".",
            font=("Microsoft YaHei UI", 10),
            background="#25282c",
            foreground="#e4e4e4",
        )
        style.configure("TFrame", background="#25282c")
        style.configure("TLabel", background="#25282c", foreground="#e4e4e4")
        style.configure("Dim.TLabel", foreground="#aeb5ba")
        style.configure("Title.TLabel", font=("Microsoft YaHei UI", 11, "bold"))
        style.configure("Value.TLabel", font=("Consolas", 13, "bold"), foreground="#b8d9ee")
        style.configure(
            "TButton",
            background="#3c4147",
            foreground="#f0f0f0",
            padding=(10, 5),
            borderwidth=1,
        )
        style.map("TButton", background=[("active", "#515b65"), ("pressed", "#63788b")])
        style.configure("TCheckbutton", background="#25282c", foreground="#e4e4e4")
        style.map("TCheckbutton", background=[("active", "#25282c")])
        style.configure(
            "TCombobox",
            fieldbackground="#353b42",
            foreground="#ededed",
            arrowcolor="#ededed",
            padding=3,
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", "#353b42")],
            foreground=[("readonly", "#ededed")],
        )
        style.configure(
            "TSpinbox",
            fieldbackground="#353b42",
            foreground="#ededed",
            arrowcolor="#ededed",
        )
        style.map(
            "TSpinbox",
            fieldbackground=[("readonly", "#353b42")],
            foreground=[("readonly", "#ededed")],
        )
        style.configure(
            "Horizontal.TScale",
            background="#25282c",
            troughcolor="#353b42",
            sliderlength=18,
        )
        style.configure("TNotebook", background="#25282c", borderwidth=0)
        style.configure(
            "TNotebook.Tab", background="#30353a", foreground="#c5cbd0", padding=(18, 7)
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", "#4b5b6a")],
            foreground=[("selected", "#ffffff")],
        )
        shell = ttk.Frame(root, padding=1)
        shell.pack(fill="both", expand=True, padx=1, pady=1)
        header = ttk.Frame(shell, padding=(14, 8))
        header.pack(fill="x")
        title = ttk.Label(header, text="影之刃零  /  HITSTOP", style="Title.TLabel")
        title.pack(side="left")
        ttk.Label(header, text="0.4 预览 2", style="Dim.TLabel").pack(side="left", padx=10)
        ttk.Button(header, text="隐藏", width=6, command=self.hide).pack(side="right")
        for widget in (header, title):
            widget.bind("<ButtonPress-1>", self.drag_start)
            widget.bind("<B1-Motion>", self.drag_move)
        ttk.Separator(shell).pack(fill="x")
        self.tabs = ttk.Notebook(shell)
        self.tabs.pack(fill="both", expand=True, padx=12, pady=12)
        self.main_tab = ttk.Frame(self.tabs, padding=14)
        self.key_tab = ttk.Frame(self.tabs, padding=14)
        self.info_tab = ttk.Frame(self.tabs, padding=14)
        self.tabs.add(self.main_tab, text="卡肉设置")
        self.tabs.add(self.key_tab, text="快捷键")
        self.tabs.add(self.info_tab, text="运行状态")
        self.body = self.main_tab
        self.enabled = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            self.main_tab,
            text="启用卡肉时长调整",
            variable=self.enabled,
            command=self.schedule_save,
        ).pack(anchor="w")
        self.observe_only = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            self.main_tab,
            text="仅记录命中，不修改帧数（验证分类）",
            variable=self.observe_only,
            command=self.schedule_save,
        ).pack(anchor="w")
        row = ttk.Frame(self.main_tab)
        row.pack(fill="x", pady=(12, 4))
        ttk.Label(row, text="编辑类别").pack(side="left")
        self.profile_choice = tk.StringVar(value="全局默认")
        selector = ttk.Combobox(
            row, textvariable=self.profile_choice, values=list(PROFILES), state="readonly", width=25
        )
        selector.pack(side="right")
        selector.bind("<<ComboboxSelected>>", self.switch_profile)
        self.override = tk.BooleanVar(value=False)
        self.override_control = ttk.Checkbutton(
            self.main_tab,
            text="此类别使用独立设置（取消则沿用全局）",
            variable=self.override,
            command=self.schedule_save,
        )
        self.override_control.pack(anchor="w", pady=(2, 0))
        ttk.Separator(self.main_tab).pack(fill="x", pady=14)
        row = ttk.Frame(self.main_tab)
        row.pack(fill="x")
        ttk.Label(row, text="调整方式").pack(side="left")
        self.mode = tk.StringVar(value="按比例缩放")
        combo = ttk.Combobox(
            row, textvariable=self.mode, values=list(MODES), state="readonly", width=22
        )
        combo.pack(side="right")
        combo.bind("<<ComboboxSelected>>", self.change_mode)
        row = ttk.Frame(self.main_tab)
        row.pack(fill="x", pady=(20, 6))
        ttk.Label(row, text="卡肉幅度").pack(side="left")
        self.amount = tk.DoubleVar(value=1)
        self.value_label = tk.StringVar(value="1.00 ×")
        ttk.Label(row, textvariable=self.value_label, style="Value.TLabel").pack(side="right")
        amount_row = ttk.Frame(self.main_tab)
        amount_row.pack(fill="x")
        ttk.Button(amount_row, text="−", width=3, command=lambda: self.step(-1)).pack(side="left")
        self.slider = ttk.Scale(
            amount_row, from_=0, to=4, variable=self.amount, command=self.slider_changed
        )
        self.slider.pack(side="left", fill="x", expand=True, padx=8)
        ttk.Button(amount_row, text="+", width=3, command=lambda: self.step(1)).pack(side="right")
        self.hint = tk.StringVar()
        ttk.Label(self.main_tab, textvariable=self.hint, style="Dim.TLabel", wraplength=580).pack(
            anchor="w", pady=(8, 18)
        )
        row = ttk.Frame(self.main_tab)
        row.pack(fill="x")
        ttk.Label(row, text="帧数上限").pack(side="left")
        self.cap = tk.StringVar(value="30")
        spin = ttk.Spinbox(
            row,
            from_=0,
            to=30,
            increment=1,
            textvariable=self.cap,
            width=7,
            command=self.schedule_save,
        )
        spin.pack(side="right")
        spin.bind("<Return>", lambda e: self.schedule_save())
        spin.bind("<FocusOut>", lambda e: self.schedule_save())
        ttk.Separator(self.main_tab).pack(fill="x", pady=16)
        self.note = tk.StringVar(value="拖动即保存。游戏运行时约 1 秒同步。")
        ttk.Label(self.main_tab, textvariable=self.note, style="Dim.TLabel", wraplength=580).pack(
            anchor="w"
        )
        ttk.Label(
            self.main_tab,
            text="按本次攻击标签分类，包含敌我双方匹配命中；未知类别沿用全局。\n保留原始倍率和曲线，帧数为游戏内部单位。",
            style="Dim.TLabel",
            wraplength=580,
        ).pack(anchor="w", pady=(10, 12))
        ttk.Button(self.main_tab, text="恢复当前类别默认", command=self.reset).pack(anchor="w")
        ttk.Label(self.key_tab, text="呼出 / 隐藏面板", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            self.key_tab,
            text="点击录入，然后按住单个按键或同时按住组合键，全部松开后保存。\n例如 Insert、Ctrl+Insert、A+B。无需从固定列表选择。",
            style="Dim.TLabel",
            wraplength=580,
        ).pack(anchor="w", pady=(8, 20))
        self.key_var = tk.StringVar(value="尚未录入")
        ttk.Label(
            self.key_tab, textvariable=self.key_var, style="Value.TLabel", wraplength=580
        ).pack(anchor="w", pady=12)
        row = ttk.Frame(self.key_tab)
        row.pack(fill="x")
        self.record_button = ttk.Button(row, text="点击录入按键", command=self.start_recording)
        self.record_button.pack(side="left")
        ttk.Button(row, text="取消录入", command=self.cancel_recording).pack(side="left", padx=10)
        self.hotkey_error = tk.StringVar(value="录入后点击保存；取消会保留原快捷键。")
        ttk.Label(
            self.key_tab,
            textvariable=self.hotkey_error,
            style="Dim.TLabel",
            wraplength=580,
        ).pack(anchor="w", pady=18)
        self.key_save_button = ttk.Button(
            self.key_tab, text="保存快捷键", command=self.register_selected, state="disabled"
        )
        self.key_save_button.pack(anchor="w")
        self.root.bind("<FocusOut>", self.capture_focus_out, add="+")
        self.tabs.bind("<<NotebookTabChanged>>", self.capture_tab_changed, add="+")
        ttk.Label(
            self.key_tab,
            text="支持键盘单键及多键同时组合，左右修饰键视为同一个键。\n系统保留快捷键可能被 Windows 优先处理；按键仍会传给游戏。",
            style="Dim.TLabel",
            wraplength=580,
        ).pack(anchor="w", pady=(16, 0))
        ttk.Separator(self.key_tab).pack(fill="x", pady=20)
        ttk.Label(
            self.key_tab,
            text="拖动顶部标题可移动面板。\n关闭面板时保留当前设置；快捷键可再次呼出。",
            style="Dim.TLabel",
        ).pack(anchor="w")
        self.connection = tk.StringVar(value="尚未连接 Mod")
        self.status_text = tk.StringVar(
            value="进入场景后等待自动连接。首次安装自动加载 DLL 后需重启游戏。"
        )
        ttk.Label(
            self.info_tab,
            textvariable=self.connection,
            style="Title.TLabel",
            wraplength=580,
        ).pack(anchor="w")
        ttk.Label(
            self.info_tab,
            textvariable=self.status_text,
            style="Dim.TLabel",
            wraplength=580,
        ).pack(anchor="w", pady=(10, 20))
        self.load_button = ttk.Button(self.info_tab, text="刷新连接状态", command=self.load_mod)
        self.load_button.pack(anchor="w")
        ttk.Separator(self.info_tab).pack(fill="x", pady=20)
        ttk.Label(
            self.info_tab,
            text="默认 1 倍不会额外增强卡肉。\n关闭调整后，后续命中恢复原始帧数。\n游戏结束后面板自动退出；完全卸载需要重启游戏。",
            style="Dim.TLabel",
            wraplength=580,
        ).pack(anchor="w")
        ttk.Button(self.info_tab, text="退出调节器", command=self.exit).pack(
            anchor="w", pady=(20, 0)
        )
        footer = ttk.Frame(shell, padding=(14, 8))
        footer.pack(fill="x", side="bottom")
        self.hotkey_label = tk.StringVar(value="首次启动：请设置快捷键")
        ttk.Label(footer, textvariable=self.hotkey_label, style="Dim.TLabel").pack(side="left")
        ttk.Label(footer, text="设置自动保存", style="Dim.TLabel").pack(side="right")
        self.reload_config()
        self.root.after(50, self.poll)
        if session is not None:
            monitor(self.root, session, self.exit)
        self.root.update_idletasks()
        height = max(590, self.root.winfo_reqheight() + 10)
        width = max(650, self.root.winfo_reqwidth() + 10)
        self.root.geometry(f"{width}x{height}+70+70")
        if not auto_start:
            self.root.deiconify()
        try:
            saved = json.loads(SETTINGS.read_text(encoding="utf-8"))
            shortcut = normalize(saved["hotkey"])[0]
        except (OSError, ValueError, KeyError):
            self.root.after(100, self.setup_hotkey)
        else:
            self.registering = True
            self.worker.commands.put(("set", shortcut))

    def drag_start(self, event):
        self.drag_origin = (
            event.x_root - self.root.winfo_x(),
            event.y_root - self.root.winfo_y(),
        )

    def drag_move(self, event):
        if self.drag_origin:
            x = max(0, event.x_root - self.drag_origin[0])
            y = max(0, event.y_root - self.drag_origin[1])
            self.root.geometry(f"+{x}+{y}")

    def reload_config(self):
        try:
            c = configure.read()
            configure.validate(c)
        except Exception as exc:
            c = DEFAULT.copy()
            self.note.set("配置读取失败；调整任一控件可修复。" + str(exc))
        self.c = c
        self.display_profile()
        try:
            self.config_stamp = configure.PATH.stat().st_mtime_ns
        except OSError:
            self.config_stamp = None

    def prefix(self):
        return "" if self.editing_profile == "Global" else self.editing_profile + "."

    def display_profile(self):
        self.updating = True
        prefix = self.prefix()
        self.enabled.set(self.c["Enabled"] == "true")
        self.observe_only.set(self.c["ObserveOnly"] == "true")
        self.override.set(bool(prefix) and self.c[prefix + "Override"] == "true")
        self.override_control.configure(state="normal" if prefix else "disabled")
        self.mode.set(REVERSE[self.c[prefix + "Mode"]])
        self.cap.set(self.c[prefix + "MaxFrames"])
        self.sync_amount()
        self.updating = False

    def switch_profile(self, event=None):
        if self.save_after:
            self.root.after_cancel(self.save_after)
        if not self.save():
            self.profile_choice.set(PROFILE_NAMES[self.editing_profile])
            return
        self.editing_profile = PROFILES[self.profile_choice.get()]
        self.display_profile()
        self.note.set("当前编辑：" + self.profile_choice.get() + "。未启用独立设置时沿用全局。")

    def store_amount(self, c):
        key = {"scale": "Scale", "add": "AddFrames", "fixed": "FixedFrames"}[self.value_mode]
        c[self.prefix() + key] = (
            str(round(self.amount.get(), 2))
            if self.value_mode == "scale"
            else str(int(round(self.amount.get())))
        )

    def sync_amount(self):
        mode = MODES[self.mode.get()]
        lo, hi, key = {
            "scale": (0, 4, "Scale"),
            "add": (-30, 30, "AddFrames"),
            "fixed": (0, 30, "FixedFrames"),
        }[mode]
        self.slider.configure(from_=lo, to=hi)
        self.value_mode = mode
        self.amount.set(float(self.c[self.prefix() + key]))
        self.update_caption()

    def update_caption(self):
        mode = MODES[self.mode.get()]
        n = self.amount.get()
        if mode == "scale":
            self.value_label.set(f"{n:.2f} ×")
            self.hint.set("0–4 倍。1 倍保留原始时长；例如 4 帧 × 1.5 = 6 帧。")
        elif mode == "add":
            self.value_label.set(f"{int(round(n)):+d} 帧")
            self.hint.set("在每次命中的原始帧数上增减；最低为 0 帧。")
        else:
            self.value_label.set(f"{int(round(n))} 帧")
            self.hint.set("将符合条件的普通命中统一设为这个帧数。")

    def change_mode(self, event=None):
        self.store_amount(self.c)
        self.updating = True
        self.sync_amount()
        self.updating = False
        self.schedule_save()

    def slider_changed(self, value=None):
        self.update_caption()
        if not self.updating:
            self.schedule_save()

    def step(self, direction):
        mode = MODES[self.mode.get()]
        step = 0.05 if mode == "scale" else 1
        lo, hi = (-30, 30) if mode == "add" else ((0, 4) if mode == "scale" else (0, 30))
        self.amount.set(max(lo, min(hi, round(self.amount.get() / step) * step + direction * step)))
        self.update_caption()
        self.schedule_save()

    def schedule_save(self):
        if self.updating:
            return
        if self.save_after:
            self.root.after_cancel(self.save_after)
        self.save_after = self.root.after(180, self.save)

    def save(self):
        self.save_after = None
        try:
            c = self.c.copy()
            mode = MODES[self.mode.get()]
            prefix = self.prefix()
            c[prefix + "Mode"] = mode
            c["Enabled"] = "true" if self.enabled.get() else "false"
            c["ObserveOnly"] = "true" if self.observe_only.get() else "false"
            if prefix:
                c[prefix + "Override"] = "true" if self.override.get() else "false"
            self.store_amount(c)
            c[prefix + "MaxFrames"] = self.cap.get().strip()
            configure.validate(c)
            atomic_text(configure.PATH, configure.serialize(c))
            self.c = c
            self.config_stamp = configure.PATH.stat().st_mtime_ns
            self.note.set("已保存：" + self.profile_choice.get() + "。约 1 秒同步，影响后续命中。")
            return True
        except Exception as exc:
            self.note.set("未保存：" + str(exc))
            return False

    def reset(self):
        if self.save_after:
            self.root.after_cancel(self.save_after)
            self.save_after = None
        c = self.c.copy()
        prefix = self.prefix()
        keys = configure.PROFILE_KEYS if prefix else configure.BASE_KEYS
        for key in keys:
            c[prefix + key] = DEFAULT[prefix + key]
        try:
            atomic_text(configure.PATH, configure.serialize(c))
            self.reload_config()
            self.note.set("已恢复当前类别默认；其他类别和仅记录开关保持不变。")
        except OSError as exc:
            self.note.set("未恢复：" + str(exc))

    def setup_hotkey(self):
        self.show()
        self.tabs.select(self.key_tab)
        self.key_var.set(self.shortcut or "尚未录入")
        self.hotkey_error.set(
            "首次使用：点击录入按键。" if not self.shortcut else "当前快捷键：" + self.shortcut
        )

    def start_recording(self):
        if self.registering:
            return
        self.show()
        self.tabs.select(self.key_tab)
        self.record_button.focus_set()
        self.recording = True
        self.capture_pending = True
        self.key_save_button.configure(state="disabled")
        self.key_var.set("等待按键…")
        self.hotkey_error.set(
            "先松开已按住的键，再按下想用的单键或组合，全部松开结束。15 秒内有效。"
        )
        self.worker.commands.put(("record", None))

    def cancel_recording(self, message="已取消，保留原快捷键。"):
        self.recording = False
        self.capture_pending = False
        self.worker.commands.put(("cancel", None))
        self.key_var.set(self.shortcut or "尚未录入")
        self.key_save_button.configure(state="disabled")
        self.hotkey_error.set(message)

    def capture_focus_out(self, event=None):
        def check():
            if self.capture_pending and self.root.focus_displayof() is None:
                self.cancel_recording("窗口失去焦点，已取消录入。")

        self.root.after_idle(check)

    def capture_tab_changed(self, event=None):
        if self.capture_pending and self.tabs.select() != str(self.key_tab):
            self.cancel_recording()

    def register_selected(self):
        if self.recording or self.registering or not self.capture_pending:
            return
        try:
            value = normalize(self.key_var.get())[0]
        except ValueError as exc:
            self.hotkey_error.set(str(exc))
            return
        self.registering = True
        self.hotkey_error.set("正在保存快捷键…")
        self.worker.commands.put(("set", value))

    def show(self):
        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", True)
        if self.dialog and self.dialog.winfo_exists():
            self.dialog.lift()

    def hide(self):
        if self.capture_pending:
            self.cancel_recording()
        if not self.shortcut:
            self.setup_hotkey()
            return
        if self.save_after:
            self.root.after_cancel(self.save_after)
            self.save()
        if self.dialog and self.dialog.winfo_exists():
            self.dialog.withdraw()
        self.root.withdraw()

    def load_mod(self):
        self.status()
        if not self.last_status:
            self.connection.set(
                "等待游戏自动加载。请确认 DLL 安装在真实 PBZ.exe 旁，并重新启动游戏。"
            )

    def status(self):
        try:
            content = (ROOT / "status.ini").read_text(encoding="utf-8")
            s = dict(line.split("=", 1) for line in content.splitlines() if "=" in line)
            age = time.time() - int(s["Timestamp"])
            if not {"Ready", "Fault", "Seen", "Changed", "Before", "After"} <= s.keys():
                return
            self.last_status = s
        except (OSError, ValueError, KeyError):
            return
        if self.loading:
            return
        if self.session is not None and (
            s.get("GamePid") != str(self.session.pid)
            or s.get("GameCreatedAt") != str(self.session.created_at)
        ):
            self.connection.set("等待当前游戏会话初始化")
            return
        if age > 8:
            self.connection.set("等待游戏继续运行 / Mod 重新连接")
        elif s["Fault"] == "true":
            self.connection.set("写入已自动停用：请查看 runtime.log")
        elif s["Ready"] != "true":
            self.connection.set("Mod 已加载，等待场景中的反馈接口")
        else:
            self.connection.set(
                "Mod 已连接 · " + ("调整开启" if s.get("Enabled") == "true" else "调整关闭")
            )
        if (
            age <= 8
            and s.get("Ready") == "true"
            and s.get("Fault") != "true"
            and s.get("ObserveOnly") == "true"
        ):
            self.connection.set("Mod 已连接 · 仅记录，不修改帧数")
        bootstrap = ""
        try:
            import configparser

            info = configparser.ConfigParser(interpolation=None)
            info.read(ROOT / "bootstrap.ini", encoding="utf-8-sig")
            details = info["Session"]
            bootstrap = (
                "\n安装："
                + details.get("Mode", "unknown")
                + "  游戏 PID："
                + details.get("GamePid", "?")
                + "\nUE4SS："
                + details.get("RuntimePath", "unknown")
                + "\n运行库："
                + (
                    "已验证版本"
                    if details.get("RuntimeVerified") == "true"
                    else "未经实测，能力检测兼容"
                )
            )
            if details.get("Error"):
                bootstrap += "\n启动错误：" + details["Error"]
        except (OSError, KeyError, ValueError, configparser.Error):
            pass
        self.status_text.set(
            f"最近反馈 {s['Before']} → {s['After']} 帧    已处理 {s['Seen']} 次 / 已调整 {s['Changed']} 次"
            + "\n识别类别："
            + PROFILE_NAMES.get(s.get("WeaponGroup"), "未知 / 未识别")
            + "\n采用设置："
            + PROFILE_NAMES.get(s.get("Profile"), "全局默认")
            + "\n攻击："
            + s.get("AttackType", "等待新版 Mod")
            + "\n强度："
            + s.get("Strength", "—")
            + "\n材质："
            + s.get("Material", "—")
            + "\n处理结果："
            + s.get("Reason", "—")
            + ("\n错误：" + s["Error"] if s.get("Error") else "")
            + bootstrap
        )

    def poll(self):
        while True:
            try:
                kind, value = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == "registered":
                self.registering = False
                self.shortcut = value
                self.recording = False
                self.capture_pending = False
                self.key_var.set(value)
                self.key_save_button.configure(state="disabled")
                self.hotkey_label.set("呼出 / 隐藏：" + value)
                self.hotkey_error.set("已保存：" + value)
                try:
                    atomic_text(
                        SETTINGS,
                        json.dumps(
                            {"version": 1, "hotkey": value},
                            ensure_ascii=False,
                            indent=2,
                        ),
                    )
                except OSError as exc:
                    self.note.set("快捷键已生效，但无法保存：" + str(exc))
                if self.dialog and self.dialog.winfo_exists():
                    self.dialog.destroy()
                    self.dialog = None
            elif kind == "capture_preview" and self.recording:
                self.key_var.set(value or "等待按键…")
            elif kind == "captured" and self.recording:
                self.recording = False
                self.key_var.set(value)
                self.key_save_button.configure(state="normal")
                self.hotkey_error.set("已录入：" + value + "。点击保存生效，或取消保留原快捷键。")
            elif kind == "capture_cancelled" and self.recording:
                self.cancel_recording(value)
            elif kind == "hotkey_error":
                self.registering = False
                self.show()
                self.setup_hotkey()
                self.hotkey_error.set(value)
            elif kind == "toggle" and not self.capture_pending:
                if self.root.state() == "withdrawn":
                    self.show()
                else:
                    self.hide()
            elif kind == "show":
                self.show()
            elif kind in ("loaded", "load_error"):
                self.loading = False
                self.load_button.configure(state="normal")
                if kind == "load_error":
                    self.connection.set("加载失败：" + value)
                elif value == 0:
                    self.connection.set("等待 Mod 初始化…")
                elif value == 2:
                    self.connection.set("当前已加载 UE4SS；若是旧诊断版，请重启游戏后再加载。")
                else:
                    self.connection.set("加载失败：请确认游戏已进入场景，详情见 ui_load.log。")
        self.status()
        if not self.save_after:
            try:
                if configure.PATH.stat().st_mtime_ns != self.config_stamp:
                    self.reload_config()
            except OSError:
                pass
        self.root.after(100, self.poll)

    def exit(self):
        if self.exiting:
            return
        self.exiting = True
        if self.save_after:
            self.root.after_cancel(self.save_after)
            self.save()
        self.worker.commands.put(("stop", None))
        self.worker.join(timeout=1)
        self.instance.close()
        if self.session is not None:
            self.session.close()
        self.root.destroy()


def main():
    auto_start = "--auto-start" in sys.argv
    try:
        session = GameSession.from_arguments(ROOT)
    except (OSError, ValueError, KeyError) as exc:
        if not auto_start:
            window = tk.Tk()
            window.withdraw()
            messagebox.showinfo("影之刃零 · 卡肉调节", str(exc), parent=window)
            window.destroy()
        return
    instance = SingleInstance(notify=not auto_start, token=session.token)
    if instance.existing:
        instance.close()
        session.close()
        return
    try:
        root = tk.Tk()
        ui = Panel(root, instance, auto_start=auto_start, session=session)
        try:
            root.mainloop()
        finally:
            if not ui.exiting:
                ui.exit()
    finally:
        instance.close()
        session.close()


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        destination = Path(sys.argv[sys.argv.index("--self-test") + 1])
        try:
            configure.validate(configure.read())
            window = tk.Tk()
            window.withdraw()
            ttk.Label(window, text="面板资源自检").pack()
            window.update_idletasks()
            window.destroy()
            result = {
                "config_valid": True,
                "hotkey_valid": normalize("CTRL+F10")[0] == "CTRL+F10"
                and normalize("Insert")[0] == "INSERT"
                and normalize("b+a")[0] == "A+B",
                "tk_window_created": True,
                "tk_version": str(tk.TkVersion),
                "mod_dir": str(ROOT),
            }
        except Exception:
            destination.write_text(json.dumps({"error": traceback.format_exc()}), encoding="utf-8")
            raise SystemExit(1)
        destination.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        raise SystemExit(0)
    try:
        main()
    except Exception:
        (ROOT / "ui_error.log").write_text(traceback.format_exc(), encoding="utf-8")
        raise
