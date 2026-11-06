import json
import math
import os
import queue
import shutil
import sys
import time
import uuid
from concurrent.futures import Future
from copy import deepcopy
from datetime import date, datetime, timedelta
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from lan_sync import Ledger, SyncServer, load_settings, local_addresses
from lan_sync.storage import data_directory, import_legacy
from lan_sync.desktop_features import DEFAULTS, export_csv, load_preferences, save_preferences, statistics
from lan_sync.schedule import MODES, WEEKDAYS, is_due, next_date, schedule_label, validate_schedule
from lan_sync.desktop_ui import open_page


DATA_FILE = data_directory() / "学习记录.json"


def duration(seconds):
    seconds = max(0, int(seconds))
    return f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


class StudyApp:
    def __init__(self, root):
        self.root = root
        self.root.title("学习日程 1.2.3")
        self.root.configure(background="#edf4fc")
        icon = Path(getattr(sys, "_MEIPASS", Path(__file__).parent / "windows" / "assets")) / "app.ico"
        if os.name == "nt" and icon.exists():
            self.root.iconbitmap(str(icon))
        self.root.geometry("1280x800")
        self.root.minsize(1160, 740)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(3, weight=1)
        self.items = []
        self.running_id = None
        self.paused = False
        self.session_seconds = 0
        self.last_tick = None
        self.last_save = time.monotonic()
        self.dirty = False
        self.notified = set()
        self.needs_backup = False
        self.needs_schedule_backup = False
        self.sync_server = None
        self.sync_requests = queue.Queue()
        self.preferences = DEFAULTS.copy()
        self.focus_end = 0
        self.pause_reason = ""
        self.mini_window = None
        self.sync_text = tk.StringVar(value="局域网同步尚未开启")
        try:
            DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
            self.sync_settings = load_settings(DATA_FILE.with_name("同步设置.json"))
        except (OSError, ValueError, TypeError) as error:
            messagebox.showerror("同步设置错误", str(error))
            raise SystemExit(1)
        self.ledger = Ledger(self.sync_settings["device"])
        self.load_data()
        try:
            self.preferences = load_preferences(DATA_FILE.with_name("桌面设置.json"))
        except (OSError, ValueError) as error:
            messagebox.showwarning("桌面设置无法读取", f"本次使用默认设置，原设置文件保留。\n{error}")
        self.root.attributes("-topmost", self.preferences["topmost"])

        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure(".", font=("Microsoft YaHei UI", 10), background="#ffffff", foreground="#172b4d")
        style.configure("TFrame", background="#ffffff")
        style.configure("Base.TFrame", background="#edf4fc")
        style.configure("Base.TLabel", background="#edf4fc", foreground="#536b8c")
        style.configure("TLabelframe", background="#ffffff", bordercolor="#d8e5f4", relief="solid", borderwidth=1)
        style.configure("TLabelframe.Label", background="#ffffff", foreground="#203b63", font=("Microsoft YaHei UI", 11, "bold"))
        style.configure("TButton", foreground="#24466d", background="#f1f6fc", bordercolor="#d2e0f0", padding=(10, 6))
        style.map("TButton", background=[("active", "#dceafa"), ("disabled", "#edf2f8")], foreground=[("disabled", "#93a7bd")])
        style.configure("Treeview", rowheight=38, background="white", fieldbackground="white", foreground="#233d5c", bordercolor="#d8e5f4", relief="flat")
        style.map("Treeview", background=[("selected", "#d7eaff")], foreground=[("selected", "#153a67")])
        style.configure("Treeview.Heading", padding=8, background="#eaf2fb", foreground="#315273", relief="flat")
        style.map("Treeview.Heading", background=[("active", "#dceafa")])
        style.configure("Accent.TButton", foreground="white", background="#2563eb", bordercolor="#2563eb", padding=(16, 8))
        style.map("Accent.TButton", background=[("active", "#1d4ed8"), ("disabled", "#b4c8df")], foreground=[("disabled", "#ffffff")])
        style.configure("Horizontal.TProgressbar", background="#4389f4", troughcolor="#e5eef9", bordercolor="#e5eef9", lightcolor="#4389f4", darkcolor="#4389f4")
        style.configure("Timer.TLabel", font=("Microsoft YaHei UI", 30, "bold"), foreground="#155bc2", background="#ffffff")
        style.configure("Heading.TLabel", font=("Microsoft YaHei UI", 17, "bold"), foreground="#112c51")
        style.configure("PageHeading.TLabel", font=("Microsoft YaHei UI", 20, "bold"), background="#edf4fc", foreground="#112c51")

        from lan_sync.desktop_ui import build_dashboard
        build_dashboard(self)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.bind("<Unmap>", self.on_window_unmap, add="+")
        self.root.bind("<Control-Return>", lambda event: self.keyboard_timer("start"))
        self.root.bind("<Control-space>", lambda event: self.keyboard_timer("pause"))
        self.refresh()
        self.tick()
        self.poll_sync()

    def load_data(self):
        if not DATA_FILE.exists():
            return
        try:
            with DATA_FILE.open("r", encoding="utf-8") as file:
                data = json.load(file)
            if not isinstance(data, list):
                raise ValueError("记录格式不正确")
            seen_ids = set()
            for item in data:
                if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not isinstance(item.get("name"), str) or not isinstance(item.get("goal"), int) or item["goal"] <= 0 or not isinstance(item.get("records"), dict):
                    raise ValueError("记录格式不正确")
                if not item["id"] or item["id"] in seen_ids:
                    raise ValueError("类目编号重复或为空")
                seen_ids.add(item["id"])
                for day in item["records"]:
                    if date.fromisoformat(day).isoformat() != day:
                        raise ValueError("学习日期格式不正确")
                if any(not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0 for value in item["records"].values()):
                    raise ValueError("学习时间格式不正确")
            self.ledger = Ledger(self.sync_settings["device"], data)
            self.items = self.ledger.active()
            self.needs_backup = any("_sync" not in item for item in data)
            self.needs_schedule_backup = any("schedule" not in item for item in data)
        except (OSError, ValueError, TypeError, KeyError) as error:
            messagebox.showerror("无法读取学习记录", f"请检查 {DATA_FILE}。为避免覆盖原文件，程序将退出。\n\n{error}")
            raise SystemExit(1)

    def save_data(self, silent=False):
        try:
            self.ledger.capture(self.items)
            if self.needs_schedule_backup and DATA_FILE.exists():
                backup = DATA_FILE.with_name("学习记录.1.2升级备份.json")
                if not backup.exists():
                    shutil.copy2(DATA_FILE, backup)
                self.needs_schedule_backup = False
            if self.needs_backup and DATA_FILE.exists():
                backup = DATA_FILE.with_name("学习记录.同步升级备份.json")
                if not backup.exists():
                    shutil.copy2(DATA_FILE, backup)
                self.needs_backup = False
            temporary = DATA_FILE.with_suffix(".tmp")
            with temporary.open("w", encoding="utf-8") as file:
                json.dump(self.ledger.stored(), file, ensure_ascii=False, indent=2, allow_nan=False)
            os.replace(temporary, DATA_FILE)
            self.dirty = False
            self.last_save = time.monotonic()
            self.save_status.config(text=f"已保存 · {datetime.now():%H:%M:%S}")
            return True
        except OSError as error:
            self.dirty = True
            self.last_save = time.monotonic()
            self.save_status.config(text="保存失败，请检查文件夹是否可写；程序将稍后重试。")
            if not silent:
                messagebox.showerror("保存失败", f"学习记录无法保存：\n{error}")
            return False

    def selected(self):
        selection = self.table.selection()
        if not selection:
            messagebox.showinfo("提示", "请先在列表中选择一个学习类目。")
            return None
        return next((item for item in self.items if item["id"] == selection[0]), None)

    def keyboard_timer(self, action):
        if action == "start" and self.table.selection() and not self.running_id:
            self.start()
        elif action == "pause" and self.running_id:
            self.toggle_pause()
        return "break"

    def schedule_fields(self, parent, item=None):
        rule = (item or {}).get("schedule", {"mode": "daily"})
        ttk.Label(parent, text="上课安排：").pack(side="left")
        mode = tk.StringVar(value=MODES[rule["mode"]])
        picker = ttk.Combobox(parent, textvariable=mode, values=list(MODES.values()), state="readonly", width=9)
        picker.pack(side="left", padx=(0, 8))
        variables, checks = [], []
        for index, title in enumerate(WEEKDAYS, 1):
            variable = tk.BooleanVar(value=index in rule.get("days", [1, 2, 3, 4, 5]))
            check = ttk.Checkbutton(parent, text=title, variable=variable)
            check.pack(side="left")
            variables.append(variable)
            checks.append(check)
        def update(event=None):
            for check in checks:
                check.state(["!disabled"] if mode.get() == MODES["weekdays"] else ["disabled"])
        picker.bind("<<ComboboxSelected>>", update)
        update()
        def read():
            key = next(key for key, label in MODES.items() if label == mode.get())
            value = {"mode": key}
            if key == "weekdays":
                value["days"] = [index for index, variable in enumerate(variables, 1) if variable.get()]
            return validate_schedule(value)
        return read

    def apply_schedule(self, identifier, rule):
        validate_schedule(rule)
        self.record_elapsed()
        item = next((item for item in self.items if item["id"] == identifier), None)
        if item is None:
            raise ValueError("这个类目已在同步时被删除，请重新选择。")
        item["schedule"] = deepcopy(rule)
        self.pause_if_unscheduled()
        self.save_data()
        self.refresh()

    def pause_if_unscheduled(self):
        item = next((item for item in self.items if item["id"] == self.running_id), None)
        if item and not self.paused and not is_due(item, date.today()):
            self.paused = True
            self.pause_reason = "今天未安排此课程，已自动暂停。可停止本次计时并选择今天的课程。"
            self.save_data(silent=True)

    def edit_schedule(self):
        item = self.selected()
        if item is None:
            return
        window = tk.Toplevel(self.root)
        window.title("修改课程安排 · " + item["name"])
        window.transient(self.root)
        form = ttk.Frame(window, padding=18)
        form.pack(fill="both", expand=True)
        row = ttk.Frame(form)
        row.pack(fill="x")
        read = self.schedule_fields(row, item)
        ttk.Label(form, text="单数日：1、3、5…31 日；双数日：2、4、6…30 日。\n跨月重新按日期判断，31 日和下月 1 日都是单数日。\n修改安排不删除历史记录；若今天不再上课，当前计时会暂停。", padding=(0, 14)).pack(anchor="w")
        def save():
            try:
                self.apply_schedule(item["id"], read())
            except ValueError as error:
                messagebox.showwarning("课程安排有误", str(error), parent=window)
                return
            window.destroy()
        ttk.Button(form, text="保存课程安排", command=save).pack(anchor="e")
        window.grab_set()
        return window

    def show_calendar(self):
        window = open_page(self, "calendar", "学习日程 · 未来14天课程表")
        frame = ttk.Frame(window, padding=14)
        frame.pack(fill="both", expand=True)
        header = ttk.Frame(frame)
        header.pack(fill="x", pady=(0, 10))
        ttk.Label(header, text="起始日期（年-月-日）：").pack(side="left")
        start = tk.StringVar(value=date.today().isoformat())
        ttk.Entry(header, textvariable=start, width=14).pack(side="left")
        table = ttk.Treeview(frame, columns=("date", "weekday", "courses"), show="headings")
        for key, title, width in (("date", "日期", 120), ("weekday", "星期", 70), ("courses", "当日课程与目标", 570)):
            table.heading(key, text=title)
            table.column(key, width=width, anchor="w")
        scroll = ttk.Scrollbar(frame, orient="vertical", command=table.yview)
        table.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        table.pack(fill="both", expand=True)
        def reload():
            try:
                first = date.fromisoformat(start.get().strip())
                last = first + timedelta(days=13)
            except (ValueError, OverflowError):
                messagebox.showwarning("日期有误", "请输入有效日期，如 2026-11-06。", parent=window)
                return
            table.delete(*table.get_children())
            for offset in range(14):
                day = first + timedelta(days=offset)
                courses = "；".join(f"{item['name']} {item['goal']}分钟" for item in self.items if is_due(item, day)) or "休息日 · 无课程安排"
                table.insert("", "end", values=(day.isoformat(), WEEKDAYS[day.weekday()], courses))
        ttk.Button(header, text="查看／刷新", command=reload).pack(side="left", padx=10)
        reload()
        return window

    def on_window_unmap(self, event=None):
        if event is None or event.widget == self.root:
            self.pause_if_minimized()

    def pause_if_minimized(self):
        if self.running_id and not self.paused and not self.preferences["background"] and self.root.state() == "iconic":
            self.record_elapsed()
            if not self.paused:
                self.paused = True
                self.pause_reason = "主窗口已最小化，计时自动暂停；返回后请手动继续。"
            self.save_data(silent=True)
            self.refresh()

    def apply_preferences(self, preferences):
        if type(preferences["focus_minutes"]) is not int or not 0 <= preferences["focus_minutes"] <= 180:
            raise ValueError("请输入 0 至 180 的整数分钟数，0 表示自由计时。")
        if any(type(preferences[key]) is not bool for key in ("background", "sound", "topmost")):
            raise ValueError("开关设置格式错误")
        self.record_elapsed()
        save_preferences(DATA_FILE.with_name("桌面设置.json"), preferences)
        if preferences["focus_minutes"] != self.preferences["focus_minutes"]:
            self.focus_end = self.session_seconds + preferences["focus_minutes"] * 60
        self.preferences = preferences.copy()
        self.root.attributes("-topmost", preferences["topmost"])
        self.pause_if_minimized()
        self.refresh()

    def show_settings(self):
        window = open_page(self, "settings", "设置 · 专注计时")
        content = ttk.Frame(window, padding=20)
        content.pack(fill="both", expand=True)
        ttk.Label(content, text="每轮专注时长（分钟，0 为自由计时）").pack(anchor="w")
        minutes = tk.StringVar(value=str(self.preferences["focus_minutes"]))
        ttk.Spinbox(content, from_=0, to=180, textvariable=minutes, width=12).pack(anchor="w", pady=8)
        presets = ttk.Frame(content)
        presets.pack(anchor="w")
        for value in (0, 25, 45, 60):
            ttk.Button(presets, text="自由" if value == 0 else f"{value} 分钟", command=lambda v=value: minutes.set(str(v))).pack(side="left", padx=(0, 8))
        ttk.Label(content, text="到时自动暂停，休息不计时；继续后开启下一轮。\n中途暂停保留剩余时间；修改时长从现在重新计算一轮。", wraplength=460).pack(anchor="w", pady=12)
        variables = {}
        for key, title in (("background", "主窗口最小化后继续计时"), ("sound", "完成目标或专注轮次时响铃"), ("topmost", "主窗口始终置顶")):
            variables[key] = tk.BooleanVar(value=self.preferences[key])
            ttk.Checkbutton(content, text=title, variable=variables[key]).pack(anchor="w", pady=4)
        ttk.Label(content, text="关闭后台计时后，最小化会暂停，回来需手动继续。\n切换到其他软件不暂停。设置仅用于这台电脑。\n快捷键：Ctrl+Enter 开始，Ctrl+空格 暂停／继续。", wraplength=460).pack(anchor="w", pady=12)
        saved_status = ttk.Label(content)
        saved_status.pack(anchor="w", pady=8)
        def save():
            try:
                preferences = {key: variable.get() for key, variable in variables.items()}
                preferences["focus_minutes"] = int(minutes.get())
                self.apply_preferences(preferences)
            except (ValueError, OSError) as error:
                messagebox.showerror("设置未保存", str(error), parent=window)
                return
            saved_status.config(text="设置已保存")
        ttk.Button(content, text="保存设置", command=save, style="Accent.TButton").pack(anchor="e")
        return window

    def restore_main(self):
        self.root.deiconify()
        self.root.lift()

    def show_mini(self):
        if self.mini_window is not None and self.mini_window.winfo_exists():
            self.mini_window.lift()
            return self.mini_window
        window = self.mini_window = tk.Toplevel(self.root)
        window.title("学习日程 · 迷你计时")
        window.geometry("390x240")
        window.minsize(350, 220)
        window.attributes("-topmost", True)
        content = ttk.Frame(window, padding=14)
        content.pack(fill="both", expand=True)
        self.mini_name = ttk.Label(content)
        self.mini_name.pack(anchor="w")
        self.mini_timer = ttk.Label(content, style="Timer.TLabel")
        self.mini_timer.pack(anchor="w")
        self.mini_status = ttk.Label(content, wraplength=350)
        self.mini_status.pack(anchor="w", pady=(0, 8))
        actions = ttk.Frame(content)
        actions.pack(fill="x")
        self.mini_pause = ttk.Button(actions, command=self.toggle_pause)
        self.mini_pause.pack(side="left", padx=(0, 6))
        self.mini_stop = ttk.Button(actions, text="停止", command=self.stop)
        self.mini_stop.pack(side="left", padx=(0, 6))
        ttk.Button(actions, text="回主窗口", command=self.restore_main).pack(side="left")
        self.refresh()
        return window

    def export_records(self, start=None, end=None, parent=None):
        parent = parent or self.root
        path = filedialog.asksaveasfilename(parent=parent, title="导出学习记录", defaultextension=".csv",
                                          initialfile=f"学习记录-{date.today().isoformat()}.csv", filetypes=[("CSV 表格", "*.csv")])
        if not path:
            return
        try:
            target = Path(path)
            protected = [DATA_FILE, DATA_FILE.with_name("同步设置.json"), DATA_FILE.with_name("桌面设置.json")]
            if target.resolve() in [item.resolve() for item in protected]:
                raise ValueError("不能覆盖应用的数据或设置文件，请另选 CSV 文件名。")
            self.record_elapsed()
            count = export_csv(target, self.items, start, end)
            messagebox.showinfo("导出完成", f"已导出 {count} 条记录，可使用 Excel 打开。\n{path}", parent=parent)
        except (OSError, ValueError) as error:
            messagebox.showerror("导出失败", str(error), parent=parent)

    def show_statistics(self):
        window = open_page(self, "statistics", "统计分析")
        content = ttk.Frame(window, padding=14)
        content.pack(fill="both", expand=True)
        toolbar = ttk.Frame(content)
        toolbar.pack(fill="x")
        period = tk.StringVar(value="7")
        ttk.Label(toolbar, text="最近天数：").pack(side="left")
        picker = ttk.Combobox(toolbar, values=("7", "30"), state="readonly", textvariable=period, width=6)
        picker.pack(side="left", padx=(0, 12))
        total_label = ttk.Label(content, style="Heading.TLabel")
        total_label.pack(anchor="w", pady=(12, 4))
        note = ttk.Label(content)
        note.pack(anchor="w")
        canvas = tk.Canvas(content, height=170, background="#f3f6fc", highlightthickness=0)
        canvas.pack(fill="x", pady=10)
        notebook = ttk.Notebook(content)
        notebook.pack(fill="both", expand=True)
        tables = []
        for title, columns in (("每日明细", (("date", "日期"), ("time", "学习时长"))), ("类目合计", (("name", "学习类目"), ("time", "学习时长")))):
            frame = ttk.Frame(notebook)
            notebook.add(frame, text=title)
            table = ttk.Treeview(frame, columns=[key for key, _ in columns], show="headings")
            for key, label in columns:
                table.heading(key, text=label)
                table.column(key, anchor="center", width=280)
            scroll = ttk.Scrollbar(frame, orient="vertical", command=table.yview)
            table.configure(yscrollcommand=scroll.set)
            scroll.pack(side="right", fill="y")
            table.pack(fill="both", expand=True)
            tables.append(table)
        ttk.Label(content, text="有学习时长即计为学习日；今天尚未学习时，连续天数统计截至昨天。统计包含同步记录。", wraplength=790).pack(anchor="w", pady=(10, 0))
        data = {}
        def draw(event=None):
            canvas.delete("all")
            rows = data.get("daily", [])
            if not rows:
                return
            width = max(300, canvas.winfo_width())
            step = (width - 30) / len(rows)
            maximum = max(1, max(seconds for _, seconds in rows))
            for index, (day, seconds) in enumerate(rows):
                x = 15 + step * index
                height = seconds / maximum * 110
                canvas.create_rectangle(x + 2, 135 - height, x + step - 2, 135, fill="#2563eb", outline="")
                if len(rows) <= 7 or index % 5 == 0 or index == len(rows) - 1:
                    canvas.create_text(x + step / 2, 151, text=day[5:], fill="#64748b", font=("Microsoft YaHei UI", 9))
                if len(rows) <= 7:
                    canvas.create_text(x + step / 2, 125 - height, text=f"{seconds / 60:.1f}分", fill="#334155", font=("Microsoft YaHei UI", 9))
        def reload():
            self.record_elapsed()
            self.refresh()
            data.clear()
            data.update(statistics(self.items, date.today(), int(period.get())))
            total_label.config(text=f"近 {period.get()} 天累计 {duration(data['total'])}")
            note.config(text=f"学习 {data['studied_days']}/{period.get()} 天 · 连续学习 {data['streak']} 天 · 日均 {duration(data['total'] / int(period.get()))}")
            for table, rows in zip(tables, (data["daily"], data["categories"])):
                table.delete(*table.get_children())
                for label, seconds in rows:
                    table.insert("", "end", values=(label, duration(seconds)))
            draw()
        ttk.Button(toolbar, text="刷新统计", command=reload).pack(side="left")
        ttk.Button(toolbar, text="导出当前范围 CSV", command=lambda: self.export_records(data["daily"][0][0], data["daily"][-1][0], window)).pack(side="right")
        picker.bind("<<ComboboxSelected>>", lambda event: reload())
        canvas.bind("<Configure>", draw)
        reload()
        return window

    def add_item(self):
        name = self.name.get().strip()
        try:
            goal = int(self.minutes.get())
            if not name or len(name) > 200 or not 1 <= goal <= 1000000:
                raise ValueError
            rule = self.read_new_schedule()
        except ValueError:
            messagebox.showwarning("输入有误", "请输入 1 至 200 字的类目名称和 1 至 1000000 的整数分钟数；指定星期时至少选择一天。")
            return
        if any(item["name"] == name for item in self.items):
            messagebox.showwarning("名称重复", "这个学习类目已经存在。")
            return
        self.items.append({"id": uuid.uuid4().hex, "name": name, "goal": goal, "schedule": rule, "records": {}})
        self.save_data()
        self.name.delete(0, tk.END)
        self.minutes.delete(0, tk.END)
        self.refresh()

    def start(self):
        item = self.selected()
        if item is None:
            return
        if not is_due(item, date.today()):
            messagebox.showinfo("今天未安排", "今天没有安排这门课程，可在“修改课程安排”中调整。")
            return
        if self.running_id:
            messagebox.showinfo("正在计时", "请先停止当前学习类目的计时。")
            return
        self.running_id = item["id"]
        self.paused = False
        self.session_seconds = 0
        self.focus_end = self.preferences["focus_minutes"] * 60
        self.pause_reason = ""
        self.last_tick = time.monotonic()
        self.refresh()

    def toggle_pause(self):
        if not self.running_id:
            return
        was_paused = self.paused
        item = next((item for item in self.items if item["id"] == self.running_id), None)
        if was_paused and item and not is_due(item, date.today()):
            messagebox.showinfo("今天未安排", "请停止本次计时并选择今天的课程，或修改课程安排。")
            return
        self.record_elapsed()
        if was_paused:
            if not self.preferences["background"] and self.root.state() == "iconic":
                self.restore_main()
            self.paused = False
            self.pause_reason = ""
            if self.session_seconds >= self.focus_end:
                self.focus_end = self.session_seconds + self.preferences["focus_minutes"] * 60
        elif not self.paused:
            self.paused = True
            self.pause_reason = "已手动暂停"
        self.last_tick = time.monotonic()
        self.save_data()
        self.refresh()

    def record_elapsed(self):
        if not self.running_id or self.paused:
            return
        tick = time.monotonic()
        elapsed = max(0, tick - self.last_tick)
        self.last_tick = tick
        now = time.time()
        counted = min(elapsed, max(0, self.focus_end - self.session_seconds)) if self.preferences["focus_minutes"] else elapsed
        item = next(item for item in self.items if item["id"] == self.running_id)
        today = date.today().isoformat()
        before = item["records"].get(today, 0)
        # 用单调时钟统计时长，避免修改系统时间导致多计或少计。
        start = now - elapsed
        now = start + counted
        recorded = 0
        schedule_ended = False
        # 跨过午夜时，将时间分别计入对应的日期。
        while start < now:
            current = datetime.fromtimestamp(start)
            if not is_due(item, current.date()):
                schedule_ended = True
                break
            midnight = datetime.combine(current.date() + timedelta(days=1), datetime.min.time()).timestamp()
            end = min(now, midnight)
            key = current.date().isoformat()
            item["records"][key] = item["records"].get(key, 0) + end - start
            recorded += end - start
            start = end
        self.session_seconds += recorded
        self.dirty = self.dirty or recorded > 0
        if schedule_ended or not is_due(item, date.today()):
            self.paused = True
            self.pause_reason = "日历已切换，今天未安排此课程。计时已暂停，请选择今天的课程。"
            self.save_data(silent=True)
        round_finished = bool(self.preferences["focus_minutes"] and self.session_seconds >= self.focus_end)
        if round_finished and not self.paused:
            self.paused = True
            self.pause_reason = "本轮专注完成，休息后点击“继续学习”开启下一轮。"
            self.save_data(silent=True)
            if self.preferences["sound"]:
                self.root.bell()
        key = (today, item["id"])
        if before < item["goal"] * 60 <= item["records"].get(today, 0) and key not in self.notified:
            self.notified.add(key)
            self.info.config(text=f"✓ “{item['name']}”今日目标已完成！你可以停止计时或继续学习。")
            if self.preferences["sound"] and not round_finished:
                self.root.bell()

    def stop(self):
        if not self.running_id:
            messagebox.showinfo("提示", "目前没有正在计时的学习类目。")
            return
        self.record_elapsed()
        self.running_id = None
        self.paused = False
        self.session_seconds = 0
        self.last_tick = None
        self.save_data()
        self.refresh()

    def edit_goal(self):
        item = self.selected()
        if item is None:
            return
        goal = simpledialog.askinteger("修改目标", f"请输入“{item['name']}”的新每日目标（分钟）：", initialvalue=item["goal"], minvalue=1, maxvalue=1000000, parent=self.root)
        if goal is not None:
            item = next((current for current in self.items if current["id"] == item["id"]), None)
            if item is None:
                messagebox.showinfo("类目已删除", "这个类目已在同步时被删除。")
                return
            item["goal"] = goal
            self.save_data()
            self.refresh()

    def rename_item(self):
        item = self.selected()
        if item is None:
            return
        name = simpledialog.askstring("修改名称", "请输入新的学习类目名称：", initialvalue=item["name"], parent=self.root)
        if name is None:
            return
        item = next((current for current in self.items if current["id"] == item["id"]), None)
        if item is None:
            messagebox.showinfo("类目已删除", "这个类目已在同步时被删除。")
            return
        name = name.strip()
        if not name or len(name) > 200:
            messagebox.showwarning("输入有误", "类目名称须为 1 至 200 个字符。")
            return
        if any(other is not item and other["name"] == name for other in self.items):
            messagebox.showwarning("名称重复", "这个学习类目已经存在。")
            return
        item["name"] = name
        self.save_data()
        self.refresh()

    def show_history(self):
        self.record_elapsed()
        window = tk.Toplevel(self.root)
        window.title("学习历史记录")
        window.geometry("620x420")
        header = ttk.Frame(window, padding=10)
        header.pack(fill="x")
        history_summary = ttk.Label(header)
        history_summary.pack(side="left")
        frame = ttk.Frame(window, padding=(10, 0, 10, 10))
        frame.pack(fill="both", expand=True)
        table = ttk.Treeview(frame, columns=("date", "name", "time"), show="headings")
        for key, title in (("date", "日期"), ("name", "学习类目"), ("time", "学习时长")):
            table.heading(key, text=title)
            table.column(key, anchor="center", width=180)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=table.yview)
        table.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        table.pack(side="left", fill="both", expand=True)
        def reload_history():
            self.record_elapsed()
            self.refresh()
            table.delete(*table.get_children())
            rows = [(day, item["name"], seconds) for item in self.items for day, seconds in item["records"].items() if seconds > 0]
            for day, name, seconds in sorted(rows, key=lambda row: row[0], reverse=True):
                table.insert("", "end", values=(day, name, duration(seconds)))
            history_summary.config(text=f"累计学习：{duration(sum(row[2] for row in rows))} · {len({row[0] for row in rows})} 天" if rows else "还没有学习记录。")
        ttk.Button(header, text="刷新记录", command=reload_history).pack(side="right")
        ttk.Button(header, text="导出全部 CSV", command=lambda: self.export_records(parent=window)).pack(side="right", padx=8)
        reload_history()

    def delete_item(self):
        item = self.selected()
        if item is None:
            return
        if item["id"] == self.running_id:
            messagebox.showinfo("提示", "请先停止该类目的计时，再删除。")
            return
        if messagebox.askyesno("删除类目", f"确定删除“{item['name']}”及其全部学习记录吗？"):
            item = next((current for current in self.items if current["id"] == item["id"]), None)
            if item is None:
                return
            self.items.remove(item)
            self.save_data()
            self.refresh()

    def refresh(self):
        # 更新已有行，保留选择、滚动位置和键盘焦点。
        existing = set(self.table.get_children())
        today_date = date.today()
        current_ids = {item["id"] for item in self.items if self.show_all_courses.get() or is_due(item, today_date)}
        for removed in existing - current_ids:
            self.table.delete(removed)
        today = date.today().isoformat()
        total_seconds = 0
        completed = 0
        goal_seconds = 0
        credited_seconds = 0
        scheduled_count = 0
        for item in self.items:
            seconds = item["records"].get(today, 0)
            total_seconds += seconds
            due = is_due(item, today_date)
            if due:
                scheduled_count += 1
                goal_seconds += item["goal"] * 60
                credited_seconds += min(seconds, item["goal"] * 60)
                if seconds >= item["goal"] * 60:
                    completed += 1
            if item["id"] not in current_ids:
                continue
            status = "已完成" if seconds >= item["goal"] * 60 else "未完成"
            if not due:
                status = f"下次 {next_date(item, today_date):%m-%d}"
            if item["id"] == self.running_id:
                status += "（已暂停）" if self.paused else "（计时中）"
            values = (item["name"], schedule_label(item), f"{item['goal']} 分钟", duration(seconds), status)
            tags = ("off",) if not due else ("running",) if item["id"] == self.running_id else ("complete",) if seconds >= item["goal"] * 60 else ()
            if item["id"] in existing:
                self.table.item(item["id"], values=values, tags=tags)
            else:
                self.table.insert("", "end", iid=item["id"], values=values, tags=tags)
        percentage = credited_seconds / goal_seconds * 100 if goal_seconds else 0
        self.progress["value"] = percentage
        self.summary_text.config(text=f"今日累计：{duration(total_seconds)}　|　今日课程：{scheduled_count} 门　|　已完成：{completed}/{scheduled_count}　|　目标进度：{percentage:.1f}%")
        self.day_label.config(text=f"{today_date:%Y-%m-%d} {WEEKDAYS[today_date.weekday()]} · {'单' if today_date.day % 2 else '双'}数日")
        self.timer_text.config(text=duration(self.session_seconds))
        minutes = self.preferences["focus_minutes"]
        self.options_text.config(text=(f"每轮专注 {minutes} 分钟 · 到时自动暂停" if minutes else "自由计时 · 手动启停")
                                 + ("　|　最小化继续计时" if self.preferences["background"] else "　|　最小化自动暂停"))
        if self.running_id:
            item = next(item for item in self.items if item["id"] == self.running_id)
            remaining = max(0, item["goal"] * 60 - item["records"].get(today, 0))
            self.focus_name.config(text=f"{'已暂停' if self.paused else '正在学习'} · {item['name']} · 本次专注")
            self.remaining_text.config(text=f"距离今日目标还需 {duration(math.ceil(remaining))}" if remaining else "✓ 今日目标已完成，可以继续学习或停止计时。")
            if minutes:
                self.remaining_text.config(text=self.remaining_text.cget("text") + f"　|　本轮剩余 {duration(math.ceil(max(0, self.focus_end - self.session_seconds)))}")
            self.info.config(text=self.pause_reason if self.paused else "今日目标已完成！计时仍在继续，由你手动停止。" if not remaining else "专注当前类目，休息时可暂停，结束时点击“停止计时”。")
        else:
            self.focus_name.config(text="准备开始")
            self.remaining_text.config(text="选中下方的今日课程，然后开始计时。" if scheduled_count else "今天没有课程安排，可以休息；勾选“显示全部课程”可管理其他日期的课程。")
            self.info.config(text="课程按电脑系统日历自动切换；如需查看其他日期，点击“查看未来课程表”。")
        self.update_controls()
        from lan_sync.desktop_ui import update_overview
        update_overview(self)
        if self.mini_window is not None and self.mini_window.winfo_exists():
            self.mini_name.config(text=self.focus_name.cget("text"))
            self.mini_timer.config(text=duration(self.session_seconds))
            self.mini_status.config(text=self.pause_reason if self.running_id and self.paused else
                                    f"本轮剩余 {duration(math.ceil(max(0, self.focus_end - self.session_seconds)))}" if self.running_id and minutes else
                                    "自由计时 · 手动启停" if self.running_id else "请在主窗口选择类目并开始。")
            self.mini_pause.config(text="继续" if self.paused else "暂停")
            for control in (self.mini_pause, self.mini_stop):
                control.state(["!disabled"] if self.running_id else ["disabled"])

    def update_controls(self):
        selection = self.table.selection()
        chosen = next((item for item in self.items if selection and item["id"] == selection[0]), None)
        active = next((item for item in self.items if item["id"] == self.running_id), None)
        self.start_button.state(["!disabled"] if chosen and is_due(chosen, date.today()) and not self.running_id else ["disabled"])
        self.pause_button.state(["!disabled"] if active and (not self.paused or is_due(active, date.today())) else ["disabled"])
        self.stop_button.state(["!disabled"] if self.running_id else ["disabled"])
        self.pause_button.config(text="继续学习" if self.paused else "暂停")

    def show_sync(self):
        window = open_page(self, "sync", "局域网同步")
        content = ttk.Frame(window, padding=18)
        content.pack(fill="both", expand=True)
        ttk.Label(content, text="手机和电脑连接同一个 Wi-Fi，然后在手机上填写以下信息。", wraplength=510).pack(anchor="w", pady=(0, 10))
        ttk.Label(content, textvariable=self.sync_text, wraplength=510).pack(anchor="w", pady=(0, 10))
        ttk.Label(content, text="电脑地址（选择与手机同网段的地址）：").pack(anchor="w")
        addresses = local_addresses(self.sync_server.port if self.sync_server else 8765)
        address_box = ttk.Entry(content)
        address_box.insert(0, "  /  ".join(addresses) if addresses else "未找到地址，请运行 ipconfig 查看 IPv4 地址，端口为 8765")
        address_box.configure(state="readonly")
        address_box.pack(fill="x", pady=(4, 10))
        ttk.Label(content, text=f"配对码：{self.sync_settings['token']}", font=("Microsoft YaHei UI", 14, "bold")).pack(anchor="w")
        ttk.Label(content, text="两端均需 1.2 或以上版本，课程安排也会同步。请在可信局域网使用；数据通过本地 HTTP 传输。", wraplength=510).pack(anchor="w", pady=10)
        actions = ttk.Frame(content)
        actions.pack(anchor="w")
        ttk.Button(actions, text="开启同步", command=self.enable_sync).pack(side="left", padx=(0, 10))
        ttk.Button(actions, text="关闭同步", command=self.disable_sync).pack(side="left")
        return window

    def enable_sync(self):
        if self.sync_server:
            return
        try:
            self.sync_server = SyncServer(self.sync_settings["token"], self.queue_exchange)
            self.sync_server.start()
            self.sync_text.set("同步已开启 · 等待手机连接（端口 8765）")
        except OSError as error:
            self.sync_server = None
            messagebox.showerror("无法开启同步", f"端口 8765 可能已被占用。\n{error}")

    def disable_sync(self):
        if self.sync_server:
            self.sync_server.close()
            self.sync_server = None
        while not self.sync_requests.empty():
            _, future = self.sync_requests.get_nowait()
            if not future.done():
                future.set_exception(OSError("同步已关闭"))
        self.sync_text.set("局域网同步已关闭")

    def queue_exchange(self, document):
        future = Future()
        self.sync_requests.put((document, future))
        try:
            return future.result(timeout=15)
        except TimeoutError:
            future.cancel()
            raise

    def exchange(self, document):
        # 所有界面和学习记录的变动都在 Tk 主线程完成。
        self.record_elapsed()
        self.ledger.capture(self.items)
        self.ledger.merge(document)
        self.items = self.ledger.active()
        if self.running_id and not any(item["id"] == self.running_id for item in self.items):
            self.running_id = None
            self.paused = False
            self.session_seconds = 0
            self.last_tick = None
        self.pause_if_unscheduled()
        if not self.save_data(silent=True):
            raise OSError("无法保存同步记录")
        self.refresh()
        self.sync_text.set(f"同步成功 · {datetime.now():%H:%M:%S}")
        return deepcopy(self.ledger.document)

    def poll_sync(self):
        for _ in range(5):
            try:
                document, future = self.sync_requests.get_nowait()
            except queue.Empty:
                break
            if future.set_running_or_notify_cancel():
                try:
                    future.set_result(self.exchange(document))
                except Exception as error:
                    future.set_exception(error)
        self.sync_after_id = self.root.after(100, self.poll_sync)

    def tick(self):
        self.pause_if_minimized()
        self.record_elapsed()
        if self.dirty and time.monotonic() - self.last_save >= 30:
            self.save_data(silent=True)
        self.refresh()
        self.after_id = self.root.after(1000, self.tick)

    def close(self):
        self.record_elapsed()
        if self.save_data():
            self.disable_sync()
            self.root.after_cancel(self.after_id)
            self.root.after_cancel(self.sync_after_id)
            self.root.destroy()


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--import-legacy":
        try:
            import_legacy(sys.argv[2], DATA_FILE.parent)
        except Exception:
            raise SystemExit(2)
        raise SystemExit(0)
    if len(sys.argv) == 3 and sys.argv[1] == "--self-test":
        from lan_sync.package_check import run_check
        run_check(sys.modules[__name__], sys.argv[2])
        raise SystemExit(0)
    root = tk.Tk()
    instance_handle = None
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        import hashlib
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
        kernel.CreateMutexW.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        identifier = hashlib.sha256(str(DATA_FILE.resolve()).casefold().encode("utf-8")).hexdigest()
        mutex_name = "Local\\StudyScheduleDesktop" if getattr(sys, "frozen", False) else "Local\\StudySchedule_" + identifier
        instance_handle = kernel.CreateMutexW(None, False, mutex_name)
        if not instance_handle:
            root.withdraw()
            messagebox.showerror("无法启动", "无法建立程序锁，请稍后重试。")
            raise SystemExit(1)
        if ctypes.get_last_error() == 183:
            kernel.CloseHandle(instance_handle)
            root.withdraw()
            messagebox.showinfo("程序已经打开", "请使用已打开的学习日程窗口，避免同时修改同一份记录。")
            raise SystemExit(0)
    try:
        StudyApp(root)
        root.mainloop()
    finally:
        if instance_handle:
            kernel.CloseHandle(instance_handle)
