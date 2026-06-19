import tkinter as tk
from tkinter import ttk, messagebox
import time
import winsound
import json
import os
from pathlib import Path

# --- Constants ---
CONFIG_FILE = Path.home() / ".pomodoro_config.json"
DEFAULT_WORK = 25
DEFAULT_SHORT_BREAK = 5
DEFAULT_LONG_BREAK = 15
DEFAULT_POMOS_BEFORE_LONG = 4

COLORS = {
    "bg": "#1e1e2e",
    "fg": "#cdd6f4",
    "accent": "#f38ba8",
    "work": "#f38ba8",
    "break": "#a6e3a1",
    "long_break": "#89b4fa",
    "button_bg": "#313244",
    "button_fg": "#cdd6f4",
    "button_hover": "#45475a",
    "card_bg": "#181825",
    "subtext": "#a6adc8",
}


class PomodoroTimer:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🍅 番茄钟")
        self.root.geometry("480x640")
        self.root.minsize(400, 560)
        self.root.configure(bg=COLORS["bg"])

        # Center window
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() - 480) // 2
        y = (self.root.winfo_screenheight() - 640) // 2
        self.root.geometry(f"+{x}+{y}")

        self.load_config()

        # --- State ---
        self.mode = "work"  # work | break | long_break
        self.time_left = self.work_duration * 60
        self.base_time = self.time_left
        self.running = False
        self.paused = False
        self.pomodoro_count = 0
        self.total_pomodoros = 0
        self.session_start = time.localtime()

        self._setup_styles()
        self._build_ui()
        self._update_display()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # --- Config ---
    def load_config(self):
        cfg = {}
        if CONFIG_FILE.exists():
            try:
                cfg = json.loads(CONFIG_FILE.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        self.work_duration = cfg.get("work", DEFAULT_WORK)
        self.short_break = cfg.get("short_break", DEFAULT_SHORT_BREAK)
        self.long_break = cfg.get("long_break", DEFAULT_LONG_BREAK)
        self.pomos_before_long = cfg.get("pomos_before_long", DEFAULT_POMOS_BEFORE_LONG)

    def save_config(self):
        CONFIG_FILE.write_text(json.dumps({
            "work": self.work_duration,
            "short_break": self.short_break,
            "long_break": self.long_break,
            "pomos_before_long": self.pomos_before_long,
        }, indent=2))

    # --- Styles ---
    def _setup_styles(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(".", font=("Segoe UI", 10), background=COLORS["bg"], foreground=COLORS["fg"])
        style.configure("TLabel", background=COLORS["bg"], foreground=COLORS["fg"])
        style.configure("TFrame", background=COLORS["bg"])
        style.configure("Card.TFrame", background=COLORS["card_bg"], relief="flat")
        style.configure("Timer.TLabel", font=("Segoe UI", 72, "bold"), foreground=COLORS["work"])
        style.configure("Status.TLabel", font=("Segoe UI", 14), foreground=COLORS["subtext"])
        style.configure("Count.TLabel", font=("Segoe UI", 12), foreground=COLORS["subtext"])
        style.configure("Header.TLabel", font=("Segoe UI", 12, "bold"), foreground=COLORS["fg"])
        style.configure("Accent.Horizontal.TProgressbar", troughcolor=COLORS["card_bg"],
                        background=COLORS["accent"], lightcolor=COLORS["accent"], darkcolor=COLORS["accent"])

    # --- UI ---
    def _build_ui(self):
        # Main container with padding
        main = tk.Frame(self.root, bg=COLORS["bg"])
        main.pack(fill="both", expand=True, padx=30, pady=25)

        # --- Mode label ---
        self.mode_label = tk.Label(main, text="专注中", font=("Segoe UI", 16, "bold"),
                                   bg=COLORS["bg"], fg=COLORS["work"])
        self.mode_label.pack(pady=(0, 5))

        # --- Session count ---
        self.count_label = tk.Label(main, text="今日已完成 0 个番茄", font=("Segoe UI", 11),
                                    bg=COLORS["bg"], fg=COLORS["subtext"])
        self.count_label.pack(pady=(0, 20))

        # --- Timer display card ---
        timer_card = tk.Frame(main, bg=COLORS["card_bg"], bd=0, highlightthickness=0)
        timer_card.pack(fill="x", ipady=30, ipadx=10)
        # Add rounded effect with a border frame inside
        inner = tk.Frame(timer_card, bg=COLORS["card_bg"])
        inner.pack(expand=True, fill="both", padx=20, pady=10)

        # Progress bar
        self.progress = ttk.Progressbar(inner, style="Accent.Horizontal.TProgressbar",
                                        length=360, mode="determinate")
        self.progress.pack(pady=(15, 10))

        # Timer
        self.timer_label = tk.Label(inner, text="25:00", font=("Segoe UI", 64, "bold"),
                                    bg=COLORS["card_bg"], fg=COLORS["work"])
        self.timer_label.pack(pady=(0, 5))

        # Status
        self.status_label = tk.Label(inner, text="点击「开始」进入专注", font=("Segoe UI", 11),
                                     bg=COLORS["card_bg"], fg=COLORS["subtext"])
        self.status_label.pack()

        self.timer_card = timer_card

        # --- Buttons ---
        btn_frame = tk.Frame(main, bg=COLORS["bg"])
        btn_frame.pack(pady=25)

        btn_cfg = {"font": ("Segoe UI", 12, "bold"), "bd": 0, "cursor": "hand2",
                    "width": 10, "height": 1, "relief": "flat"}

        self.start_btn = tk.Button(btn_frame, text="▶ 开始", bg=COLORS["button_bg"],
                                    fg=COLORS["fg"], activebackground=COLORS["button_hover"],
                                    activeforeground=COLORS["fg"], command=self._toggle,
                                    **btn_cfg)
        self.start_btn.pack(side="left", padx=5)

        self.reset_btn = tk.Button(btn_frame, text="↺ 重置", bg=COLORS["button_bg"],
                                    fg=COLORS["fg"], activebackground=COLORS["button_hover"],
                                    activeforeground=COLORS["fg"], command=self._reset,
                                    state="disabled", **btn_cfg)
        self.reset_btn.pack(side="left", padx=5)

        # --- Stats card ---
        stats_card = tk.Frame(main, bg=COLORS["card_bg"])
        stats_card.pack(fill="x", pady=(0, 15), ipady=12)

        stats_inner = tk.Frame(stats_card, bg=COLORS["card_bg"])
        stats_inner.pack(padx=20, pady=10, fill="x")

        # Row: today's count and streak
        tk.Label(stats_inner, text="📊 今日统计", font=("Segoe UI", 11, "bold"),
                 bg=COLORS["card_bg"], fg=COLORS["fg"]).pack(anchor="w")

        self.stats_today = tk.Label(stats_inner, text="已完成 0 个番茄",
                                     font=("Segoe UI", 10), bg=COLORS["card_bg"], fg=COLORS["subtext"])
        self.stats_today.pack(anchor="w", pady=(2, 0))

        # --- Settings card ---
        settings_card = tk.Frame(main, bg=COLORS["card_bg"])
        settings_card.pack(fill="x", pady=(0, 10), ipady=10)

        settings_inner = tk.Frame(settings_card, bg=COLORS["card_bg"])
        settings_inner.pack(padx=20, pady=10, fill="x")

        tk.Label(settings_inner, text="⚙️ 设置", font=("Segoe UI", 11, "bold"),
                 bg=COLORS["card_bg"], fg=COLORS["fg"]).pack(anchor="w")

        grid = tk.Frame(settings_inner, bg=COLORS["card_bg"])
        grid.pack(pady=(8, 0), fill="x")

        labels = ["专注 (分)", "短休 (分)", "长休 (分)", "长休间隔"]
        keys = ["work", "short_break", "long_break", "pomos_before_long"]
        defaults = [self.work_duration, self.short_break, self.long_break, self.pomos_before_long]
        self.settings_vars = {}

        for i, (lbl, key, val) in enumerate(zip(labels, keys, defaults)):
            tk.Label(grid, text=lbl, font=("Segoe UI", 10), bg=COLORS["card_bg"],
                     fg=COLORS["subtext"]).grid(row=i, column=0, sticky="w", padx=(0, 10), pady=2)
            var = tk.StringVar(value=str(val))
            self.settings_vars[key] = var
            entry = tk.Entry(grid, textvariable=var, width=6, font=("Segoe UI", 10),
                             bg=COLORS["button_bg"], fg=COLORS["fg"],
                             insertbackground=COLORS["fg"], bd=0, justify="center",
                             relief="flat")
            entry.grid(row=i, column=1, sticky="e", pady=2)

        # Bind settings changes
        for var in self.settings_vars.values():
            var.trace_add("write", self._on_settings_change)

    # --- Timer logic ---
    def _toggle(self):
        if not self.running:
            self._start()
        else:
            self._pause()

    def _start(self):
        if self.paused:
            self.paused = False
            self.running = True
            self.start_btn.config(text="⏸ 暂停")
            self.status_label.config(text="专注中...")
            self._tick()
        else:
            # Fresh start - reset timer to current mode duration
            self.running = True
            self.paused = False
            self.start_btn.config(text="⏸ 暂停")
            self.reset_btn.config(state="normal")
            self.status_label.config(text="专注中...")
            self._tick()

    def _pause(self):
        self.running = False
        self.paused = True
        self.start_btn.config(text="▶ 继续")
        self.status_label.config(text="已暂停")

    def _reset(self):
        self.running = False
        self.paused = False
        self.time_left = self._get_mode_duration() * 60
        self.base_time = self.time_left
        self.start_btn.config(text="▶ 开始")
        self.reset_btn.config(state="disabled")
        self.status_label.config(text="点击「开始」进入专注")
        self._update_display()

    def _tick(self):
        if not self.running:
            return

        if self.time_left > 0:
            self.time_left -= 1
            self._update_display()
            self.root.after(1000, self._tick)
        else:
            self._on_complete()

    def _get_mode_duration(self):
        return {"work": self.work_duration,
                "break": self.short_break,
                "long_break": self.long_break}[self.mode]

    def _update_display(self):
        mins, secs = divmod(self.time_left, 60)
        self.timer_label.config(text=f"{mins:02d}:{secs:02d}")

        total = self._get_mode_duration() * 60
        if total > 0:
            pct = (total - self.time_left) / total * 100
            self.progress["value"] = pct

    def _switch_mode(self):
        if self.mode == "work":
            self.pomodoro_count += 1
            self.total_pomodoros += 1
            if self.pomodoro_count % self.pomos_before_long == 0:
                self.mode = "long_break"
            else:
                self.mode = "break"
        else:
            self.mode = "work"

        self.time_left = self._get_mode_duration() * 60
        self.base_time = self.time_left
        self.running = False
        self.paused = False
        self.start_btn.config(text="▶ 开始")
        self.reset_btn.config(state="disabled")
        self._update_ui_mode()
        self._update_display()
        self._update_stats()
        self._auto_start()

    def _auto_start(self):
        """After a break, auto-start the next work session."""
        if self.mode == "work":
            self._start()

    def _update_ui_mode(self):
        if self.mode == "work":
            self.mode_label.config(text="🍅 专注中", fg=COLORS["work"])
            self.status_label.config(text="点击「开始」进入专注")
        elif self.mode == "break":
            self.mode_label.config(text="☕ 短休息", fg=COLORS["break"])
            self.status_label.config(text="休息一下吧！")
        else:
            self.mode_label.config(text="🌿 长休息", fg=COLORS["long_break"])
            self.status_label.config(text="辛苦了，多休息一会儿！")

    def _on_complete(self):
        self.running = False
        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        for _ in range(3):
            winsound.Beep(880, 300)
            self.root.after(100)

        if self.mode == "work":
            msg = "🍅 专注时间到！\n该休息一下了。"
        else:
            msg = "☕ 休息结束！\n准备开始新的专注吧。"

        # Show notification
        try:
            self.root.attributes("-topmost", True)
            messagebox.showinfo("番茄钟", msg)
            self.root.attributes("-topmost", False)
        except Exception:
            pass

        self._switch_mode()

    def _update_stats(self):
        self.count_label.config(text=f"今日已完成 {self.total_pomodoros} 个番茄")
        self.stats_today.config(text=f"已完成 {self.total_pomodoros} 个番茄")

    # --- Settings ---
    def _on_settings_change(self, *_):
        try:
            new_work = max(1, int(self.settings_vars["work"].get()))
            new_short = max(1, int(self.settings_vars["short_break"].get()))
            new_long = max(1, int(self.settings_vars["long_break"].get()))
            new_pomos = max(1, int(self.settings_vars["pomos_before_long"].get()))

            if not self.running and not self.paused:
                self.work_duration = new_work
                self.short_break = new_short
                self.long_break = new_long
                self.pomos_before_long = new_pomos
                self.time_left = self._get_mode_duration() * 60
                self.base_time = self.time_left
                self._update_display()
                self.save_config()
        except ValueError:
            pass

    # --- Persistence ---
    def _on_close(self):
        if self.running or self.paused:
            if not messagebox.askyesno("退出", "计时器正在运行，确定要退出吗？"):
                return
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = PomodoroTimer()
    app.run()
