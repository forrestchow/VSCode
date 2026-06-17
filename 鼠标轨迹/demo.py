"""
LSTM 轨迹模型演示器

操作:
    点击第一下 → 起点（绿点）
    点击第二下 → 终点（红点）→ 模型生成轨迹 → 蓝色动画播放
    点击第三下 → 上一终点变新起点 → 循环往复
    右键 → 重置
    ESC → 退出
"""

import sys
import tkinter as tk
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent / "training"))
from model import create_model
from config import SEQ_LEN, HIDDEN_SIZE, NUM_LAYERS, DROPOUT, MODEL_DIR

# ── 插值参数 ──
SMOOTH_FACTOR = 4  # 模型输出 200 点 → 插值到 800 点（4倍）


def _catmull_rom_spline(points, upsample_factor=4):
    """
    Catmull-Rom 样条插值 — 在关键点之间生成平滑曲线
    不依赖 scipy，纯 numpy 实现

    Args:
        points: (N, 2) 原始轨迹点
        upsample_factor: 每段插入的点数倍数

    Returns:
        (N*upsample_factor, 2) 平滑后的轨迹点
    """
    pts = np.asarray(points, dtype=np.float32)
    n = len(pts)
    if n < 4:
        # 点太少，用线性插值
        t_old = np.linspace(0, 1, n)
        t_new = np.linspace(0, 1, n * upsample_factor)
        result = np.zeros((len(t_new), 2), dtype=np.float32)
        result[:, 0] = np.interp(t_new, t_old, pts[:, 0])
        result[:, 1] = np.interp(t_new, t_old, pts[:, 1])
        return result

    # 首尾补虚拟点（镜像延拓）
    p0 = 2 * pts[0] - pts[1]      # 虚拟前一点
    pN = 2 * pts[-1] - pts[-2]    # 虚拟后一点

    result = [pts[0]]  # 保留起点

    for i in range(n - 1):
        p1 = pts[i - 1] if i > 0 else p0
        p2 = pts[i]
        p3 = pts[i + 1]
        p4 = pts[i + 2] if i + 2 < n else pN

        for k in range(1, upsample_factor + 1):
            t = k / (upsample_factor + 1)
            t2 = t * t
            t3 = t2 * t
            pt = 0.5 * (
                (2 * p2) +
                (-p1 + p3) * t +
                (2 * p1 - 5 * p2 + 4 * p3 - p4) * t2 +
                (-p1 + 3 * p2 - 3 * p3 + p4) * t3
            )
            result.append(pt)

    result.append(pts[-1])  # 保留终点
    return np.array(result, dtype=np.float32)


class ModelDemo:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("LSTM 轨迹演示 — 点击设起点 → 点击设终点")
        self.root.geometry("950x700+200+100")
        self.root.configure(bg="#2c2c2c")

        # 加载模型
        self.model = self._load_model()

        # 状态
        self._start_pos = None
        self._end_pos = None
        self._gen_points = None
        self._anim_idx = 0
        self._count = 0

        self._setup_ui()
        self._animate()

    def _load_model(self):
        path = MODEL_DIR / "best_model.pt"
        if not path.exists():
            print(f"模型不存在: {path}，请先运行 training/train.py")
            sys.exit(1)
        ckpt = torch.load(path, map_location="cpu", weights_only=False)
        cfg = ckpt.get("config", {})
        model = create_model(
            hidden_size=cfg.get("hidden_size", HIDDEN_SIZE),
            num_layers=cfg.get("num_layers", NUM_LAYERS),
            dropout=cfg.get("dropout", DROPOUT),
        )
        model.load_state_dict(ckpt["model_state_dict"])
        model.eval()
        print(f"模型已加载 (epoch {ckpt.get('epoch', '?')}, val_loss={ckpt.get('val_loss', '?'):.6f})")
        return model

    def _setup_ui(self):
        root = self.root

        # 画布（占满整个窗口）
        self.canvas = tk.Canvas(root, bg="#f5f5f5",
                                highlightthickness=1, highlightbackground="#555")
        self.canvas.pack(fill="both", expand=True, padx=4, pady=4)

        # ★ 所有点击统一入口 ★
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<Button-3>", lambda e: self._reset())
        root.bind("<Escape>", lambda e: self.root.destroy())

        # 底部状态栏
        self.status = tk.Label(
            root, text="🖱 点击画布任意位置 → 设定起点",
            font=("Microsoft YaHei", 10), bg="#1e1e1e", fg="#e0e0e0",
            anchor="w", padx=10, pady=4,
        )
        self.status.pack(fill="x", side="bottom")

        # 强制获取焦点
        self.canvas.focus_set()

    def _canvas_size(self):
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        return (max(w, 100), max(h, 100))

    def _on_click(self, event):
        """画布点击 — 第一下起点 / 第二下终点 / 之后循环"""
        x, y = event.x, event.y
        print(f"点击: ({x}, {y})  start={self._start_pos}  end={self._end_pos}", flush=True)

        if self._start_pos is None:
            # 第一下 → 起点
            self._start_pos = (x, y)
            self._end_pos = None
            self._gen_points = None
            self._anim_idx = 0
            self.status.config(text=f"🟢 起点: ({x}, {y}) — 请点击终点位置")

        elif self._end_pos is None:
            # 第二下 → 终点
            self._end_pos = (x, y)
            self._generate()
            self._count += 1

        else:
            # 之后 → 终点变起点，点击位置变新终点
            self._start_pos = self._end_pos
            self._end_pos = (x, y)
            self._generate()
            self._count += 1

    def _reset(self):
        """右键重置"""
        self._start_pos = None
        self._end_pos = None
        self._gen_points = None
        self._anim_idx = 0
        self.status.config(text="🖱 已重置 — 点击画布设定起点")

    def _generate(self):
        """模型推理 + 终点校正"""
        cw, ch = self._canvas_size()
        sx, sy = self._start_pos
        ex, ey = self._end_pos

        # 归一化
        sx_n, sy_n = sx / cw, sy / ch
        ex_n, ey_n = ex / cw, ey / ch
        condition = torch.tensor([[sx_n, sy_n, ex_n, ey_n]], dtype=torch.float32)

        with torch.no_grad():
            deltas = self.model(condition, max_steps=SEQ_LEN).squeeze(0).numpy()

        # 累积 → 像素坐标
        pts = np.zeros((len(deltas) + 1, 2), dtype=np.float32)
        pts[0] = [sx_n, sy_n]
        for i in range(len(deltas)):
            pts[i + 1] = pts[i] + deltas[i]
        pts[:, 0] *= cw
        pts[:, 1] *= ch

        # 终点校正
        raw_end = pts[-1].copy()
        target = np.array([ex, ey], dtype=np.float32)
        correction = target - raw_end
        n = len(pts)
        for i in range(n):
            w = (i / max(n - 1, 1)) ** 1.5
            pts[i] += correction * w
        pts[:, 0] = np.clip(pts[:, 0], 0, cw)
        pts[:, 1] = np.clip(pts[:, 1], 0, ch)

        self._gen_points = _catmull_rom_spline(pts, upsample_factor=SMOOTH_FACTOR)
        self._anim_idx = 0

        raw_err = np.sqrt((raw_end[0] - ex)**2 + (raw_end[1] - ey)**2)
        self.status.config(
            f"🟢 ({sx},{sy}) → 🔴 ({ex},{ey}) | "
            f"模型 200 点 → 插值 {len(self._gen_points)} 点 | "
            f"原始误差: {raw_err:.0f}px | 已生成: {self._count} | 继续点击..."
        )

    def _animate(self):
        """动画循环 (~30fps)"""
        canvas = self.canvas
        canvas.delete("all")

        # ── 起点 ──
        if self._start_pos:
            sx, sy = self._start_pos
            r = 7
            canvas.create_oval(sx - r, sy - r, sx + r, sy + r,
                               fill="#4caf50", outline="#2e7d32", width=2)
            canvas.create_text(sx, sy - 14, text="起点", font=("Microsoft YaHei", 8),
                               fill="#4caf50")

        # ── 终点 ──
        if self._end_pos:
            ex, ey = self._end_pos
            r = 7
            canvas.create_oval(ex - r, ey - r, ex + r, ey + r,
                               fill="#f44336", outline="#b71c1c", width=2)
            canvas.create_text(ex, ey - 14, text="终点", font=("Microsoft YaHei", 8),
                               fill="#f44336")

        # ── 生成轨迹动画 ──
        if self._gen_points is not None and len(self._gen_points) >= 2:
            pts = self._gen_points
            # 完整轨迹（淡色底）
            flat = [c for pt in pts for c in pt]
            canvas.create_line(*flat, fill="#e3f2fd", width=1)

            # 动画进度（亮色前景）— 步长适配插值倍数
            self._anim_idx = min(self._anim_idx + 3 * SMOOTH_FACTOR, len(pts) - 1)
            anim_pts = pts[:self._anim_idx + 1]
            if len(anim_pts) >= 2:
                flat2 = [c for pt in anim_pts for c in pt]
                canvas.create_line(*flat2, fill="#2196f3", width=3, smooth=True)

            # 当前位置光点
            cx, cy = anim_pts[-1]
            canvas.create_oval(cx - 5, cy - 5, cx + 5, cy + 5,
                               fill="#ff9800", outline="white", width=2)

        self.root.after(30, self._animate)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    ModelDemo().run()
