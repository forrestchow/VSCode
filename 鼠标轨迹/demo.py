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
from config import STEPS_INTERCEPT, STEPS_SLOPE

# ── 可调参数 ──
# 帧间隔时间: 每发送帧的物理间隔，Hz 越高越细腻
SEND_HZ = 2000              # 发送频率 (Hz): 1000=1ms, 2000=0.5ms, 8000=0.125ms
# 每帧相对距离: 每帧允许的最大位移，值越小轨迹越密、越慢
TARGET_PX_PER_FRAME = 0.5   # 目标每帧位移 (px): 0.25=更密更慢, 0.5=正常, 0.75=更快
# 速度倍率: 等比缩放整体速度
SPEED_MULT = 1.0            # 速度: 0.5=慢一半, 1.0=正常, 2.0=快一倍

# 键盘快捷键（运行中实时调节）:
#   ↑/↓  调整 SPEED_MULT (±0.25)
#   ←/→  调整 SEND_HZ (±500Hz)
#   +/-   调整 TARGET_PX_PER_FRAME (±0.1)


def predict_steps(distance_px):
    """
    根据距离预测模型应生成的步数

    来源: 训练数据线性拟合  [数据] trajectories_2026-06-17.jsonl
    公式: steps = 43.4 + 0.092 × distance_px  (r=0.68)

    Args:
        distance_px: 起点到终点的像素距离

    Returns:
        int: 推荐步数，限制在 [20, SEQ_LEN] 范围
    """
    steps = int(STEPS_INTERCEPT + STEPS_SLOPE * distance_px)
    return max(20, min(steps, SEQ_LEN))


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

        # 键盘调节参数
        root.bind("<Up>", lambda e: self._adj_speed(0.25))
        root.bind("<Down>", lambda e: self._adj_speed(-0.25))
        root.bind("<Right>", lambda e: self._adj_hz(500))
        root.bind("<Left>", lambda e: self._adj_hz(-500))
        root.bind("<plus>", lambda e: self._adj_target_px(0.1))
        root.bind("<minus>", lambda e: self._adj_target_px(-0.1))
        root.bind("<equal>", lambda e: self._adj_target_px(0.1))  # shift+= 也是 +

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

    def _adj_speed(self, delta):
        global SPEED_MULT
        SPEED_MULT = max(0.25, SPEED_MULT + delta)
        self.status.config(
            f"速度倍率: x{SPEED_MULT:.2f} | "
            f"SEND_HZ={SEND_HZ}Hz | TARGET_PX={TARGET_PX_PER_FRAME:.2f}px"
        )

    def _adj_hz(self, delta):
        global SEND_HZ
        SEND_HZ = max(125, SEND_HZ + delta)
        self.status.config(
            f"SEND_HZ: {SEND_HZ}Hz ({1000/SEND_HZ:.2f}ms/帧) | "
            f"速度倍率: x{SPEED_MULT:.2f} | TARGET_PX={TARGET_PX_PER_FRAME:.2f}px"
        )

    def _adj_target_px(self, delta):
        global TARGET_PX_PER_FRAME
        TARGET_PX_PER_FRAME = max(0.1, round(TARGET_PX_PER_FRAME + delta, 2))
        self.status.config(
            f"TARGET_PX: {TARGET_PX_PER_FRAME:.2f}px/帧 | "
            f"SEND_HZ={SEND_HZ}Hz | 速度倍率: x{SPEED_MULT:.2f}"
        )

    def _generate(self):
        """模型推理 + 自适应步数 + 终点校正 + 自适应 CR 插值"""
        cw, ch = self._canvas_size()
        sx, sy = self._start_pos
        ex, ey = self._end_pos

        # ── 方案A: 距离 → 步数预测 × 速度倍率 ──
        distance = np.sqrt((ex - sx)**2 + (ey - sy)**2)
        base_steps = predict_steps(distance)
        actual_steps = max(10, int(base_steps / SPEED_MULT))  # 倍率↑ → 步数↓ → 更快

        # ── 归一化 ──
        sx_n, sy_n = sx / cw, sy / ch
        ex_n, ey_n = ex / cw, ey / ch
        # 5 维 condition [sx, sy, ex, ey, steps/SEQ_LEN]（steps 归一化）
        condition = torch.tensor(
            [[sx_n, sy_n, ex_n, ey_n, actual_steps / SEQ_LEN]], dtype=torch.float32
        )

        with torch.no_grad():
            deltas = self.model(condition, max_steps=actual_steps).squeeze(0).numpy()

        # ── 累积 → 像素坐标 ──
        pts = np.zeros((len(deltas) + 1, 2), dtype=np.float32)
        pts[0] = [sx_n, sy_n]
        for i in range(len(deltas)):
            pts[i + 1] = pts[i] + deltas[i]
        pts[:, 0] *= cw
        pts[:, 1] *= ch

        # ── 抗蠕动: 找到位移不再增长的裁剪点 ──
        cumsum = np.cumsum(deltas, axis=0)
        total_disp = np.sqrt(cumsum[:, 0]**2 + cumsum[:, 1]**2)
        total_disp_max = total_disp[-1]
        if total_disp_max > 0:
            # 位移达到 98% 处截断，去掉后面的蠕动帧
            cutoff = int(np.searchsorted(total_disp, total_disp_max * 0.98) + 1)
            if cutoff > 0 and cutoff < len(deltas):
                deltas = deltas[:cutoff]
                # 重新累积
                pts = np.zeros((len(deltas) + 1, 2), dtype=np.float32)
                pts[0] = [sx_n, sy_n]
                for i in range(len(deltas)):
                    pts[i + 1] = pts[i] + deltas[i]
                pts[:, 0] *= cw
                pts[:, 1] *= ch

        # ── 终点校正 ──
        raw_end = pts[-1].copy()
        target = np.array([ex, ey], dtype=np.float32)
        correction = target - raw_end
        n = len(pts)
        for i in range(n):
            w = (i / max(n - 1, 1)) ** 1.5
            pts[i] += correction * w
        pts[:, 0] = np.clip(pts[:, 0], 0, cw)
        pts[:, 1] = np.clip(pts[:, 1], 0, ch)

        # ── 自适应 CR 插值: 目标每帧位移 × 速度倍率 ──
        # 倍率↑ → 允许每帧更大位移 → CR↓ → 总帧数↓ → 更快
        model_deltas = np.diff(pts, axis=0)
        avg_step = np.mean(np.sqrt(model_deltas[:, 0]**2 + model_deltas[:, 1]**2))
        target_px = TARGET_PX_PER_FRAME * SPEED_MULT
        adaptive_factor = max(2, int(avg_step / target_px))
        self._gen_points = _catmull_rom_spline(pts, upsample_factor=adaptive_factor)
        self._anim_idx = 0

        # ── 保存本次轨迹数据供 _animate 显示 ──
        self._traj_info = {
            "distance": distance,
            "base_steps": base_steps,
            "model_steps": actual_steps,
            "speed_mult": SPEED_MULT,
            "cr_factor": adaptive_factor,
            "send_points": len(self._gen_points),
            "total_time_ms": len(self._gen_points) / SEND_HZ * 1000,
            "per_step_ms": 1000 / SEND_HZ,
            "send_hz": SEND_HZ,
            "avg_px_per_send": distance / len(self._gen_points) if len(self._gen_points) > 0 else 0,
        }

        raw_err = np.sqrt((raw_end[0] - ex)**2 + (raw_end[1] - ey)**2)
        self.status.config(
            f"🟢 ({sx},{sy}) → 🔴 ({ex},{ey}) | "
            f"距离 {distance:.0f}px | 模型步数 {actual_steps} | "
            f"CR {adaptive_factor}x → {len(self._gen_points)} 发送点 | "
            f"耗时 {self._traj_info['total_time_ms']:.0f}ms | "
            f"每发送帧 {self._traj_info['per_step_ms']:.1f}ms | "
            f"原始误差 {raw_err:.0f}px | #{self._count}"
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

        # ── 轨迹信息浮层 ──
        if hasattr(self, '_traj_info') and self._traj_info:
            info = self._traj_info
            lines = [
                f"距离: {info['distance']:.0f} px",
                f"速度倍率: x{info['speed_mult']:.1f} | 步数: {info['base_steps']} -> {info['model_steps']}",
                f"CR 插值: x{info['cr_factor']} -> {info['send_points']} 发送点",
                f"发送频率: {info['send_hz']} Hz = 每帧 {info['per_step_ms']:.1f} ms",
                f"总耗时: {info['total_time_ms']:.0f} ms | 每帧 {info['avg_px_per_send']:.2f} px",
            ]
            y0 = 10
            for i, line in enumerate(lines):
                canvas.create_text(
                    10, y0 + i * 18, text=line, anchor="w",
                    font=("Consolas", 9), fill="#333333"
                )

        # ── 生成轨迹动画 ──
        if self._gen_points is not None and len(self._gen_points) >= 2:
            pts = self._gen_points
            # 完整轨迹（淡色底）
            flat = [c for pt in pts for c in pt]
            canvas.create_line(*flat, fill="#e3f2fd", width=1)

            # 动画进度（亮色前景）— 按真实时间推进
            # tkinter ~33fps(30ms/帧)，每帧应推进 30ms 对应的发送点数
            # 30ms × SEND_HZ/1000 = 应推进的发送点数
            step_size = max(1, int(30 * SEND_HZ / 1000))
            self._anim_idx = min(self._anim_idx + step_size, len(pts) - 1)
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
