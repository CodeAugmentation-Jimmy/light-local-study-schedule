"""Dashboard layout based on the approved cool-blue desktop mockup."""
import tkinter as tk
from tkinter import ttk

from .desktop_features import statistics

NAVY = "#102348"
BLUE = "#2473f4"
MUTED = "#62738f"
PAGE = "#f5f9ff"
WHITE = "#ffffff"


class Card(tk.Canvas):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, background=PAGE, highlightthickness=0, **kwargs)
        self.body = tk.Frame(self, background=WHITE)
        self.panel = self.create_polygon(0, 0, 1, 1, fill=WHITE, outline="#dce8f8", smooth=True)
        self.content = self.create_window(16, 16, window=self.body, anchor="nw")
        self.bind("<Configure>", self.resize)

    def resize(self, event):
        w, h, r = event.width - 2, event.height - 2, 14
        self.coords(self.panel, r, 1, w-r, 1, w, 1, w, r, w, h-r, w, h,
                    w-r, h, r, h, 1, h, 1, h-r, 1, r, 1, 1)
        self.itemconfigure(self.content, width=max(1, w-32), height=max(1, h-32))


def label(parent, text="", size=11, color=NAVY, bold=False, **kwargs):
    return tk.Label(parent, text=text, background=WHITE, foreground=color,
                    font=("Microsoft YaHei UI", size, "bold" if bold else "normal"), **kwargs)


def build_dashboard(app):
    root = app.root
    root.configure(background=PAGE)
    root.rowconfigure(3, weight=0)
    root.rowconfigure(0, weight=1)
    root.columnconfigure(0, weight=0)
    root.columnconfigure(1, weight=1)
    style = ttk.Style(root)
    style.configure("Treeview", rowheight=43, borderwidth=0, font=("Microsoft YaHei UI", 11))
    style.configure("Treeview.Heading", font=("Microsoft YaHei UI", 10), padding=(6, 12))
    style.configure("Timer.TLabel", font=("Segoe UI", 43, "bold"), foreground=NAVY, background="#eaf2ff")
    style.configure("Nav.TButton", padding=(16, 13), background="#eaf3ff", foreground=NAVY,
                    borderwidth=0, font=("Microsoft YaHei UI", 12))
    style.map("Nav.TButton", background=[("active", "#d4e5ff")])
    style.configure("ActiveNav.TButton", background="#d6e6ff", foreground="#124cb9", padding=(16, 13),
                    borderwidth=0, font=("Microsoft YaHei UI", 12, "bold"))

    sidebar = tk.Frame(root, background="#eaf3ff", width=190)
    sidebar.grid(row=0, column=0, sticky="nsew")
    sidebar.grid_propagate(False)
    brand = tk.Canvas(sidebar, height=96, width=190, background="#eaf3ff", highlightthickness=0)
    brand.pack(fill="x", pady=(12, 8))
    brand.create_polygon(22, 30, 39, 34, 39, 60, 22, 56, fill=BLUE, outline="")
    brand.create_polygon(41, 34, 58, 30, 58, 56, 41, 60, fill="#125dd8", outline="")
    brand.create_text(117, 45, text="学习日程", font=("Microsoft YaHei UI", 16, "bold"), fill=NAVY)
    app.navigation_buttons = {}
    app.page_frame = None
    app.current_page = "home"
    for key, text, command in (
        ("home", "⌂   首页", lambda: show_home(app)),
        ("calendar", "▣   学习日程", app.show_calendar),
        ("statistics", "▥   统计分析", app.show_statistics),
        ("sync", "▱   局域网同步", app.show_sync),
        ("settings", "⚙   设置", app.show_settings),
    ):
        button = ttk.Button(sidebar, text=text, command=command, style="ActiveNav.TButton" if key == "home" else "Nav.TButton")
        button.pack(fill="x", padx=10, pady=5)
        app.navigation_buttons[key] = button
    tk.Label(sidebar, text="STUDY SCHEDULE\n让专注成为习惯", background="#eaf3ff", foreground="#748bad",
             font=("Microsoft YaHei UI", 9), justify="left").pack(side="bottom", anchor="w", padx=22, pady=24)

    main = app.dashboard = tk.Frame(root, background=PAGE, padx=14, pady=8)
    main.grid(row=0, column=1, sticky="nsew")
    main.columnconfigure(0, weight=1)
    main.rowconfigure(2, weight=1)
    header = tk.Frame(main, background=PAGE, height=86)
    header.pack_propagate(False)
    header.grid(row=0, column=0, sticky="ew", pady=(4, 10))
    tk.Label(header, text="学习日程", font=("Microsoft YaHei UI", 24, "bold"), background=PAGE, foreground=NAVY).pack(side="left")
    app.day_label = tk.Label(header, background=PAGE, foreground=NAVY, font=("Microsoft YaHei UI", 10))
    app.day_label.pack(side="left", padx=14)
    for title, command in reversed((("＋ 添加课程", lambda: show_add_course(app)),
                                    ("✎ 编辑日程", app.edit_schedule),
                                    ("局域网同步", app.show_sync), ("◷ 小计时器", app.show_mini))):
        ttk.Button(header, text=title, command=command).pack(side="right", padx=(5, 0))

    focus = Card(main, height=170)
    focus.grid(row=1, column=0, sticky="ew", pady=(0, 14))
    focus.body.columnconfigure(0, weight=1)
    focus.body.columnconfigure(1, weight=1)
    label(focus.body, "◎ 专注计时 · 当前任务", 14, bold=True).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 16))
    description = tk.Frame(focus.body, background=WHITE)
    description.grid(row=1, column=0, sticky="w")
    app.focus_name = label(description, "准备开始", 19, bold=True, wraplength=235, anchor="w", justify="left")
    app.focus_name.pack(anchor="w")
    app.remaining_text = label(description, size=9, color=MUTED, wraplength=240, justify="left")
    app.remaining_text.pack(anchor="w", pady=(8, 0))
    app.timer_text = ttk.Label(focus.body, text="00:00:00", style="Timer.TLabel", padding=(14, 2))
    app.timer_text.grid(row=1, column=1, padx=14)
    controls = tk.Frame(focus.body, background=WHITE)
    controls.grid(row=1, column=2, sticky="e")
    app.start_button = ttk.Button(controls, text="▶ 开始", command=app.start, style="Accent.TButton")
    app.pause_button = ttk.Button(controls, text="Ⅱ 暂停", command=app.toggle_pause)
    app.stop_button = ttk.Button(controls, text="■ 停止", command=app.stop)
    for button in (app.start_button, app.pause_button, app.stop_button):
        button.pack(side="left", padx=(5, 0))

    middle = tk.Frame(main, background=PAGE)
    middle.grid(row=2, column=0, sticky="nsew", pady=(0, 14))
    middle.columnconfigure(0, weight=11, uniform="middle")
    middle.columnconfigure(1, weight=10, uniform="middle")
    middle.rowconfigure(0, weight=1)
    courses = Card(middle)
    courses.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
    courses.body.rowconfigure(1, weight=1)
    courses.body.columnconfigure(0, weight=1)
    toolbar = tk.Frame(courses.body, background=WHITE)
    toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 14))
    label(toolbar, "▣ 课程日程", 15, bold=True).pack(side="left")
    ttk.Button(toolbar, text="✎ 编辑日程", command=app.edit_schedule).pack(side="right")
    app.table = ttk.Treeview(courses.body, columns=("name", "schedule", "goal", "done", "status"),
                             displaycolumns=("name", "schedule", "goal", "status"), show="headings", selectmode="browse", height=5)
    for key, title, width in (("name", "课程", 82), ("schedule", "学习安排", 137), ("goal", "学习目标", 85), ("done", "今日已学", 90), ("status", "今日状态", 110)):
        app.table.heading(key, text=title)
        app.table.column(key, width=width, minwidth=55, anchor="center")
    app.table.grid(row=1, column=0, sticky="nsew")
    scroll = ttk.Scrollbar(courses.body, orient="vertical", command=app.table.yview)
    scroll.grid(row=1, column=1, sticky="ns")
    app.table.configure(yscrollcommand=scroll.set)
    app.table.tag_configure("complete", foreground="#237554")
    app.table.tag_configure("running", foreground=BLUE)
    app.table.tag_configure("off", foreground="#98a8c0")
    app.table.bind("<<TreeviewSelect>>", lambda event: app.update_controls())
    app.show_all_courses = tk.BooleanVar(value=False)
    ttk.Checkbutton(courses.body, text="显示全部课程", variable=app.show_all_courses, command=app.refresh).grid(row=2, column=0, sticky="w", pady=(10, 2))
    menu = tk.Menu(root, tearoff=False)
    for title, command in (("修改课程安排", app.edit_schedule), ("修改学习目标", app.edit_goal), ("修改名称", app.rename_item), ("删除课程", app.delete_item), ("历史记录", app.show_history)):
        menu.add_command(label=title, command=command)
    def context_menu(event):
        identifier = app.table.identify_row(event.y)
        if identifier:
            app.table.selection_set(identifier)
            app.update_controls()
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()
    app.table.bind("<Button-3>", context_menu)
    label(courses.body, "右键课程可修改目标、改名或删除", 8, MUTED).grid(row=3, column=0, sticky="w", pady=(4, 0))

    chart = Card(middle)
    chart.grid(row=0, column=1, sticky="nsew", padx=(7, 0))
    heading = tk.Frame(chart.body, background=WHITE)
    heading.pack(fill="x", pady=(0, 20))
    label(heading, "▥ 7天学习进度", 15, bold=True).pack(side="left")
    ttk.Button(heading, text="查看统计 ›", command=app.show_statistics).pack(side="right")
    metrics = tk.Frame(chart.body, background=WHITE)
    metrics.pack(fill="x")
    app.overview_values = []
    for title in ("今日完成率", "累计专注", "学习天数"):
        column = tk.Frame(metrics, background=WHITE)
        column.pack(side="left", fill="x", expand=True)
        label(column, title, 10, MUTED).pack(anchor="w")
        value = label(column, "—", 17, BLUE if not app.overview_values else NAVY, True)
        value.pack(anchor="w", pady=(5, 0))
        app.overview_values.append(value)
    app.week_chart = tk.Canvas(chart.body, background=WHITE, highlightthickness=0, height=180)
    app.week_chart.pack(fill="both", expand=True, pady=(18, 0))
    app.week_chart.bind("<Configure>", lambda event: update_overview(app))
    app.chart_signature = None

    bottom = Card(main, height=148)
    bottom.grid(row=3, column=0, sticky="ew")
    label(bottom.body, "▥ 学习统计（近7天）", 14, bold=True).pack(anchor="w", pady=(0, 12))
    summary = tk.Frame(bottom.body, background=WHITE)
    summary.pack(fill="x")
    app.bottom_values = []
    for title in ("◷ 专注时长", "◎ 连续学习", "✓ 今日完成"):
        column = tk.Frame(summary, background=WHITE)
        column.pack(side="left", fill="x", expand=True, padx=(12, 0))
        label(column, title, 10, MUTED).pack(anchor="w")
        value = label(column, "—", 17, bold=True)
        value.pack(anchor="w", pady=(3, 0))
        app.bottom_values.append(value)
    ttk.Button(summary, text="▥ 查看详细统计", command=app.show_statistics).pack(side="right", anchor="s", pady=5)
    # Existing timing and summary widgets remain connected to the application state.
    app.summary_text = label(bottom.body)
    app.progress = ttk.Progressbar(bottom.body, maximum=100)
    footer = tk.Frame(main, background=PAGE)
    footer.grid(row=4, column=0, sticky="ew", pady=(8, 0))
    app.options_text = tk.Label(footer, background=PAGE, foreground=MUTED, font=("Microsoft YaHei UI", 8))
    app.options_text.pack(side="left")
    app.info = tk.Label(footer, background=PAGE, foreground=MUTED, font=("Microsoft YaHei UI", 8), anchor="w")
    app.save_status = tk.Label(footer, text="记录保存在本地", background=PAGE, foreground=MUTED, font=("Microsoft YaHei UI", 8))
    app.save_status.pack(side="right")
    create_course_dialog(app)


def select_navigation(app, key):
    app.current_page = key
    for page, button in app.navigation_buttons.items():
        button.configure(style="ActiveNav.TButton" if page == key else "Nav.TButton")


def show_home(app):
    if app.page_frame is not None and app.page_frame.winfo_exists():
        app.page_frame.destroy()
    app.page_frame = None
    app.dashboard.grid()
    select_navigation(app, "home")
    app.refresh()


def open_page(app, key, title):
    if app.page_frame is not None and app.page_frame.winfo_exists():
        app.page_frame.destroy()
    app.dashboard.grid_remove()
    page = app.page_frame = tk.Frame(app.root, background=PAGE, padx=24, pady=22)
    page.grid(row=0, column=1, sticky="nsew")
    header = tk.Frame(page, background=PAGE)
    header.pack(fill="x", pady=(0, 20))
    tk.Label(header, text=title, background=PAGE, foreground=NAVY,
             font=("Microsoft YaHei UI", 22, "bold")).pack(side="left")
    ttk.Button(header, text="返回首页", command=lambda: show_home(app)).pack(side="right")
    select_navigation(app, key)
    return page


def create_course_dialog(app):
    window = app.course_dialog = tk.Toplevel(app.root)
    window.title("添加课程")
    window.transient(app.root)
    window.withdraw()
    window.protocol("WM_DELETE_WINDOW", window.withdraw)
    frame = ttk.Frame(window, padding=20)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="学习类目").pack(anchor="w")
    app.name = ttk.Entry(frame, width=30)
    app.name.pack(anchor="w", pady=(5, 12))
    ttk.Label(frame, text="学习目标（分钟）").pack(anchor="w")
    app.minutes = ttk.Entry(frame, width=12)
    app.minutes.pack(anchor="w", pady=(5, 16))
    rules = ttk.Frame(frame)
    rules.pack(fill="x")
    app.read_new_schedule = app.schedule_fields(rules)
    ttk.Button(frame, text="添加课程", command=app.add_item, style="Accent.TButton").pack(anchor="e", pady=(20, 0))


def show_add_course(app):
    app.course_dialog.update_idletasks()
    width = app.course_dialog.winfo_reqwidth()
    height = app.course_dialog.winfo_reqheight()
    x = max(0, app.root.winfo_rootx() + (app.root.winfo_width() - width) // 2)
    y = max(0, app.root.winfo_rooty() + (app.root.winfo_height() - height) // 2)
    app.course_dialog.geometry(f"+{x}+{y}")
    app.course_dialog.deiconify()
    app.course_dialog.lift()
    app.name.focus_set()


def update_overview(app):
    from datetime import date
    data = statistics(app.items, date.today(), 7)
    ratio = float(app.progress["value"])
    total = int(data["total"])
    hours, minutes = total // 3600, total % 3600 // 60
    time_text = f"{hours}小时 {minutes}分"
    app.overview_values[0].config(text=f"{ratio:.0f}%")
    app.overview_values[1].config(text=time_text)
    app.overview_values[2].config(text=f"{data['studied_days']} 天")
    app.bottom_values[0].config(text=time_text)
    app.bottom_values[1].config(text=f"{data['streak']} 天")
    from .schedule import is_due
    due = [item for item in app.items if is_due(item, date.today())]
    done = sum(item["records"].get(date.today().isoformat(), 0) >= item["goal"] * 60 for item in due)
    app.bottom_values[2].config(text=f"{done} / {len(due)} 门")
    canvas = app.week_chart
    width, height = canvas.winfo_width(), canvas.winfo_height()
    signature = (tuple(data["daily"]), width, height)
    if signature == app.chart_signature:
        return
    app.chart_signature = signature
    canvas.delete("all")
    step = max(1, width - 12) / 7
    maximum = max(60, max(value for _, value in data["daily"]))
    for index, (day, seconds) in enumerate(data["daily"]):
        x = 6 + step * index
        bar_height = max(5, seconds / maximum * max(25, height - 60))
        y = height - 30
        canvas.create_rectangle(x + 5, y - bar_height, x + step - 5, y, fill="#418afa" if seconds else "#e7eef8", outline="")
        canvas.create_text(x + step / 2, y - bar_height - 13, text=f"{seconds / 60:.0f}分" if seconds else "—", fill=NAVY, font=("Microsoft YaHei UI", 9))
        canvas.create_text(x + step / 2, y + 17, text=day[5:], fill=MUTED, font=("Microsoft YaHei UI", 9))
