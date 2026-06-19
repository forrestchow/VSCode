"""
鼠标轨迹数据采集器 — 窗口内画布交互版（v3 调试增强）

用法:
    python collector.py

工作流程:
    1. 点击「开始采集」→ 绿色起点出现
    2. 点击绿色起点 → 录制开始，红色终点出现
    3. 点击红色终点 → 保存轨迹，终点变新起点 → 新终点出现 → 循环

快捷键: ESC=退出  R=重随终点  Space=暂停
"""

import json
import math
import random
import sys
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path

from pynput import mouse
from pynput.keyboard import Key, Listener as KeyboardListener

from config import (
    MIN_DISTANCE, MAX_DISTANCE,
    START_COLOR, END_COLOR, CIRCLE_RADIUS, CIRCLE_WIDTH,
    CLICK_TOLERANCE, DATA_DIR, DATA_FILENAME_TEMPLATE,
    SAVE_DELAY_MS, DISPLAY_REFRESH_MS,
)

WINDOW_WIDTH = 950
WINDOW_HEIGHT = 700
TOOLBAR_HEIGHT = 44


def _distance(x1, y1, x2, y2):
    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)


class TrajectoryCollector:

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("鼠标轨迹采集器")
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+200+100")
        self.root.minsize(500, 400)
        self.root.configure(bg="#2c2c2c")

        # ── 状态 ──
        self._lock = threading.Lock()
        self._phase = "idle"          # idle | wait_start | recording | saving
        self._start_pos = None
        self._end_pos = None
        self._trajectory: list = []
        self._record_start_ts = 0.0
        self._count = 0
        self._running = True
        self._paused = False

        # ── 调试信息（直接显示在 GUI 上） ──
        self._dbg_click = "(无)"
        self._dbg_phase = "idle"
        self._dbg_start = "None"
        self._dbg_end = "None"

        # ── 构建 UI ──
        self._setup_ui()

        # ── pynput ──
        self._mouse_listener = None
        self._kb_listener = None
        self._start_listeners()

        # ── 显示刷新 ──
        self._update_display()

    # ═══════════════════════════════════════════════════════════════
    # UI
    # ═══════════════════════════════════════════════════════════════

    def _setup_ui(self):
        root = self.root

        # ── 工具栏 ──
        toolbar = tk.Frame(root, height=TOOLBAR_HEIGHT, bg="#1e1e1e")
        toolbar.pack(fill="x", side="top")
        toolbar.pack_propagate(False)

        self.btn_start = tk.Button(
            toolbar, text="▶  开始采集", font=("Microsoft YaHei", 11, "bold"),
            bg="#4caf50", fg="white", activebackground="#388e3c",
            padx=16, pady=2, bd=0, cursor="hand2",
            command=self._on_start_button,
        )
        self.btn_start.pack(side="left", padx=(12, 16), pady=8)

        self.lbl_count = tk.Label(toolbar, text="已采集: 0 条",
                                  font=("Microsoft YaHei", 10),
                                  bg="#1e1e1e", fg="#b0b0b0")
        self.lbl_count.pack(side="left", padx=(0, 12))

        self.lbl_dist = tk.Label(toolbar, text="距离: --",
                                 font=("Microsoft YaHei", 10),
                                 bg="#1e1e1e", fg="#b0b0b0")
        self.lbl_dist.pack(side="left", padx=(0, 12))

        # ★ 调试标签：直接显示在工具栏
        self.lbl_dbg = tk.Label(toolbar, text="",
                                font=("Consolas", 8),
                                bg="#1e1e1e", fg="#ffa726")
        self.lbl_dbg.pack(side="left", padx=(0, 12))

        hint = tk.Label(toolbar, text="ESC 退出 | R 重随 | Space 暂停",
                        font=("Microsoft YaHei", 8),
                        bg="#1e1e1e", fg="#555555")
        hint.pack(side="right", padx=(0, 12))

        # ── 画布 ──
        canvas_frame = tk.Frame(root, bg="#3a3a3a")
        canvas_frame.pack(fill="both", expand=True, side="top")

        self.canvas = tk.Canvas(
            canvas_frame, bg="#f5f5f5",
            highlightthickness=1, highlightbackground="#555555",
        )
        self.canvas.pack(fill="both", expand=True, padx=4, pady=4)

        # ★★★ 核心：画布点击绑定 ★★★
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        # 也绑定到 canvas_frame 作为后备
        self.canvas.bind("<ButtonRelease-1>", self._on_canvas_click)

        # ── 底部状态栏 ──
        self.status_bar = tk.Label(
            root, text="就绪 — 请点击「开始采集」按钮",
            font=("Microsoft YaHei", 9), bg="#1e1e1e", fg="#888888",
            anchor="w", padx=10, height=1,
        )
        self.status_bar.pack(fill="x", side="bottom", ipady=2)

        # ── 键盘 ──
        root.bind("<Escape>", lambda e: self._shutdown())
        root.bind("<r>", lambda e: self._reroll_target())
        root.bind("<R>", lambda e: self._reroll_target())
        root.bind("<space>", lambda e: self._toggle_pause())
        root.protocol("WM_DELETE_WINDOW", self._shutdown)

    def _canvas_size(self):
        return self.canvas.winfo_width(), self.canvas.winfo_height()

    # ═══════════════════════════════════════════════════════════════
    # pynput
    # ═══════════════════════════════════════════════════════════════

    def _start_listeners(self):
        try:
            self._mouse_listener = mouse.Listener(on_move=self._on_move)
            self._mouse_listener.start()
        except Exception as e:
            print(f"鼠标监听失败: {e}")
            self.root.destroy()
            sys.exit(1)

        try:
            self._kb_listener = KeyboardListener(on_press=self._on_key_press)
            self._kb_listener.start()
        except Exception:
            pass

    def _on_move(self, screen_x, screen_y):
        canvas_x = screen_x - self.canvas.winfo_rootx()
        canvas_y = screen_y - self.canvas.winfo_rooty()
        with self._lock:
            if self._phase == "recording" and not self._paused:
                now = time.perf_counter()
                t_ms = (now - self._record_start_ts) * 1000.0
                self._trajectory.append((canvas_x, canvas_y, round(t_ms, 1)))

    def _on_key_press(self, key):
        try:
            if key == Key.esc:
                self.root.after(0, self._shutdown)
            elif hasattr(key, 'char') and key.char is not None:
                ch = key.char.lower()
                if ch == 'r':
                    self.root.after(0, self._reroll_target)
                elif ch == ' ':
                    self.root.after(0, self._toggle_pause)
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════
    # ★ 画布点击 — 统一入口
    # ═══════════════════════════════════════════════════════════════

    def _on_canvas_click(self, event):
        """画布上任何位置的点击"""
        x, y = event.x, event.y

        with self._lock:
            phase = self._phase
            start_pos = self._start_pos
            end_pos = self._end_pos

        # 更新调试信息（GUI 可见）
        hit_start = start_pos and _distance(x, y, *start_pos) <= CLICK_TOLERANCE
        hit_end = end_pos and _distance(x, y, *end_pos) <= CLICK_TOLERANCE
        d_start = f"{_distance(x, y, *start_pos):.0f}" if start_pos else "-"
        d_end = f"{_distance(x, y, *end_pos):.0f}" if end_pos else "-"

        self._dbg_click = f"click=({x},{y}) phase={phase} dS={d_start} dE={d_end}"
        self._dbg_phase = phase
        self._dbg_start = str(start_pos)
        self._dbg_end = str(end_pos)

        # 根据阶段处理
        if phase == "wait_start" and hit_start:
            self._handle_start_click(x, y)
        elif phase == "recording" and not self._paused and hit_end:
            self._handle_end_click(x, y)

    # ═══════════════════════════════════════════════════════════════
    # 点击处理
    # ═══════════════════════════════════════════════════════════════

    def _handle_start_click(self, x, y):
        with self._lock:
            self._start_pos = (x, y)
            self._generate_end_position()
            self._phase = "recording"
            self._trajectory.clear()
            self._record_start_ts = time.perf_counter()
            self._trajectory.append((x, y, 0.0))
        self._set_status("● 录制中... 移动到红色终点并点击")

    def _handle_end_click(self, x, y):
        with self._lock:
            now = time.perf_counter()
            t_ms = (now - self._record_start_ts) * 1000.0
            self._trajectory.append((x, y, round(t_ms, 1)))
            self._phase = "saving"
        self._save_trajectory()
        self._count += 1
        self.root.after(SAVE_DELAY_MS, self._continue_loop)

    def _on_start_button(self):
        with self._lock:
            if self._phase != "idle":
                return
            self._generate_start_position()
            self._phase = "wait_start"
            self._paused = False
        self._set_status("请点击画布中的 ● 绿色起点")

    # ═══════════════════════════════════════════════════════════════
    # 位置生成
    # ═══════════════════════════════════════════════════════════════

    def _generate_start_position(self):
        cw, ch = self._canvas_size()
        margin = 60
        w, h = max(cw, 400), max(ch, 300)
        self._start_pos = (
            random.randint(margin, max(margin + 1, w - margin)),
            random.randint(margin, max(margin + 1, h - margin)),
        )
        self._end_pos = None

    def _generate_end_position(self):
        cw, ch = self._canvas_size()
        margin = 40
        w, h = max(cw, 400), max(ch, 300)
        sx, sy = self._start_pos

        for _ in range(200):
            ex = random.randint(margin, max(margin + 1, w - margin))
            ey = random.randint(margin, max(margin + 1, h - margin))
            if MIN_DISTANCE <= _distance(sx, sy, ex, ey) <= MAX_DISTANCE:
                self._end_pos = (ex, ey)
                return

        self._end_pos = (
            random.randint(margin, max(margin + 1, w - margin)),
            random.randint(margin, max(margin + 1, h - margin)),
        )

    def _reroll_target(self):
        with self._lock:
            if self._phase == "recording":
                self._generate_end_position()
        self._set_status("↻ 终点已重新随机")

    def _toggle_pause(self):
        with self._lock:
            self._paused = not self._paused
        self._set_status("⏸ 已暂停" if self._paused else "● 录制继续")

    # ═══════════════════════════════════════════════════════════════
    # 保存
    # ═══════════════════════════════════════════════════════════════

    def _save_trajectory(self):
        if len(self._trajectory) < 2:
            return
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now().strftime("%Y-%m-%d")
        filepath = DATA_DIR / DATA_FILENAME_TEMPLATE.format(date=date_str)

        sx, sy, _ = self._trajectory[0]
        ex, ey, _ = self._trajectory[-1]
        dur = self._trajectory[-1][2] - self._trajectory[0][2]

        sample = {
            "start_pos": [sx, sy],
            "end_pos": [ex, ey],
            "target_pos": list(self._end_pos) if self._end_pos else [ex, ey],
            "trajectory": self._trajectory,
            "total_duration_ms": round(dur, 1),
            "point_count": len(self._trajectory),
            "canvas_size": list(self._canvas_size()),
            "collected_at": datetime.now().isoformat(),
        }
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(sample, ensure_ascii=False) + "\n")
        self._set_status(
            f"✓ 已保存 #{self._count + 1}  ({len(self._trajectory)} 点, {dur:.0f}ms)"
        )

    # ═══════════════════════════════════════════════════════════════
    # 流程
    # ═══════════════════════════════════════════════════════════════

    def _continue_loop(self):
        with self._lock:
            if self._end_pos is None:
                self._phase = "idle"
                return
            self._start_pos = self._end_pos
            self._generate_end_position()
            self._phase = "recording"
            self._trajectory.clear()
            self._record_start_ts = time.perf_counter()
            self._trajectory.append((self._start_pos[0], self._start_pos[1], 0.0))
        self._set_status("● 录制中... 移动到新的红色终点并点击")

    # ═══════════════════════════════════════════════════════════════
    # 显示刷新
    # ═══════════════════════════════════════════════════════════════

    def _update_display(self):
        if not self._running:
            return

        canvas = self.canvas
        canvas.delete("all")
        cw, ch = self._canvas_size()

        with self._lock:
            phase = self._phase
            start_pos = self._start_pos
            end_pos = self._end_pos
            count = self._count
            recording = (phase == "recording") and not self._paused
            paused = self._paused
            traj = list(self._trajectory) if recording else []

        # ── 空闲 ──
        if phase == "idle":
            canvas.create_text(cw // 2, ch // 2,
                               text="点击上方「▶  开始采集」按钮开始",
                               font=("Microsoft YaHei", 14), fill="#999999")

        # ── 起点 ──
        if start_pos and phase in ("wait_start", "recording", "saving"):
            sx, sy = start_pos
            r = CIRCLE_RADIUS
            fill = START_COLOR if phase == "wait_start" else ""
            canvas.create_oval(sx - r, sy - r, sx + r, sy + r,
                               outline=START_COLOR, width=CIRCLE_WIDTH, fill=fill)
            cr = r + 5
            canvas.create_line(sx - cr, sy, sx + cr, sy, fill=START_COLOR, width=1)
            canvas.create_line(sx, sy - cr, sx, sy + cr, fill=START_COLOR, width=1)
            if phase == "wait_start":
                canvas.create_text(sx, sy - r - 16, text="点击开始",
                                   font=("Microsoft YaHei", 9),
                                   fill=START_COLOR, anchor="s")

        # ── 终点 ──
        if (phase == "recording" or phase == "saving") and end_pos:
            ex, ey = end_pos
            r = CIRCLE_RADIUS
            canvas.create_oval(ex - r, ey - r, ex + r, ey + r,
                               outline=END_COLOR, width=CIRCLE_WIDTH, fill="")
            cr = r + 5
            canvas.create_line(ex - cr, ey, ex + cr, ey, fill=END_COLOR, width=1)
            canvas.create_line(ex, ey - cr, ex, ey + cr, fill=END_COLOR, width=1)
            canvas.create_text(ex, ey - r - 16, text="终点",
                               font=("Microsoft YaHei", 9),
                               fill=END_COLOR, anchor="s")

        # ── 轨迹 ──
        if traj and len(traj) >= 2:
            flat = [c for pt in traj for c in (pt[0], pt[1])]
            canvas.create_line(*flat, fill="#2196f3", width=2, smooth=True)

        # ── 工具栏更新 ──
        self.lbl_count.config(text=f"已采集: {count} 条")
        if start_pos and end_pos:
            self.lbl_dist.config(text=f"距离: {_distance(*start_pos, *end_pos):.0f}px")
        else:
            self.lbl_dist.config(text="距离: --")

        # ★ 调试信息显示在工具栏
        self.lbl_dbg.config(text=self._dbg_click)

        btn_state = "normal" if phase == "idle" else "disabled"
        btn_text = "▶  开始采集" if phase == "idle" else "... 运行中"
        self.btn_start.config(state=btn_state, text=btn_text)

        self.root.after(DISPLAY_REFRESH_MS, self._update_display)

    def _set_status(self, msg):
        try:
            self.status_bar.config(text=msg)
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════
    # 生命周期
    # ═══════════════════════════════════════════════════════════════

    def run(self):
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            pass
        finally:
            self._shutdown()

    def _shutdown(self):
        self._running = False
        if self._mouse_listener:
            self._mouse_listener.stop()
        if self._kb_listener:
            self._kb_listener.stop()
        try:
            self.root.destroy()
        except Exception:
            pass


if __name__ == "__main__":
    TrajectoryCollector().run()
