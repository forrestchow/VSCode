"""
LSTM 轨迹生成/推理脚本

用法:
    python generate.py                          # 交互式输入起点终点
    python generate.py --jsonl data/xxx.jsonl   # 用 JSONL 中的第一条做对比
    python generate.py --compare N              # 随机抽取 N 条真实轨迹做对比
"""

import argparse
import json
import random
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent / "training"))

from model import create_model
from config import SEQ_LEN, HIDDEN_SIZE, NUM_LAYERS, DROPOUT, MODEL_DIR, DATA_DIR
from config import STEPS_INTERCEPT, STEPS_SLOPE


def predict_steps(distance_px):
    """
    根据距离预测模型应生成的步数

    来源: 训练数据线性拟合  [数据] trajectories_2026-06-17.jsonl
    公式: steps = 43.4 + 0.092 × distance_px  (r=0.68)
    """
    steps = int(STEPS_INTERCEPT + STEPS_SLOPE * distance_px)
    return max(20, min(steps, SEQ_LEN))


def load_model(model_path=None):
    """加载训练好的模型"""
    if model_path is None:
        model_path = MODEL_DIR / "best_model.pt"

    if not Path(model_path).exists():
        raise FileNotFoundError(f"模型不存在: {model_path}\n请先运行 train.py")

    checkpoint = torch.load(model_path, map_location="cpu", weights_only=False)
    cfg = checkpoint.get("config", {})

    model = create_model(
        hidden_size=cfg.get("hidden_size", HIDDEN_SIZE),
        num_layers=cfg.get("num_layers", NUM_LAYERS),
        dropout=cfg.get("dropout", DROPOUT),
    )
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    print(f"模型已加载: {model_path} (epoch {checkpoint.get('epoch', '?')})")
    return model


def generate_trajectory(model, start_x, start_y, end_x, end_y,
                        canvas_w=942, canvas_h=621, max_steps=SEQ_LEN):
    """
    生成一条轨迹（方案A: 步数自适应）

    Args:
        model: 训练好的模型
        start_x, start_y: 起点（画布坐标）
        end_x, end_y: 终点（画布坐标）
        canvas_w, canvas_h: 画布尺寸
        max_steps: 最大步数（默认 SEQ_LEN，实际按距离自适应）

    Returns:
        normalized_points: [(x, y), ...] 归一化坐标列表
        pixel_points: [(x, y), ...] 像素坐标列表
    """
    # 归一化
    sx = start_x / canvas_w
    sy = start_y / canvas_h
    ex = end_x / canvas_w
    ey = end_y / canvas_h

    # ── 方案A: 距离 → 步数 ──
    distance_px = np.sqrt((end_x - start_x)**2 + (end_y - start_y)**2)
    actual_steps = predict_steps(distance_px)
    actual_steps = min(actual_steps, max_steps)  # 不超过 max_steps

    # 5 维 condition [sx, sy, ex, ey, steps/SEQ_LEN]（steps 归一化）
    condition = torch.tensor(
        [[sx, sy, ex, ey, actual_steps / SEQ_LEN]], dtype=torch.float32
    )

    with torch.no_grad():
        deltas_norm = model(condition, max_steps=actual_steps)  # (1, T, 2)
        deltas_norm = deltas_norm.squeeze(0).numpy()            # (T, 2)

    # ── 抗蠕动裁剪 ──
    cumsum = np.cumsum(deltas_norm, axis=0)
    total_disp = np.sqrt(cumsum[:, 0]**2 + cumsum[:, 1]**2)
    total_disp_max = total_disp[-1]
    if total_disp_max > 0:
        cutoff = int(np.searchsorted(total_disp, total_disp_max * 0.98) + 1)
        if 0 < cutoff < len(deltas_norm):
            deltas_norm = deltas_norm[:cutoff]

    # 累积 → 绝对坐标（归一化）
    norm_points = np.zeros((len(deltas_norm) + 1, 2), dtype=np.float32)
    norm_points[0] = [sx, sy]
    for i in range(len(deltas_norm)):
        norm_points[i + 1] = norm_points[i] + deltas_norm[i]

    # 转为像素坐标
    pixel_points = norm_points.copy()
    pixel_points[:, 0] *= canvas_w
    pixel_points[:, 1] *= canvas_h

    return norm_points, pixel_points


def compare_with_real(model, jsonl_path, n=3, canvas_w=942, canvas_h=621):
    """对比生成轨迹 vs 真实轨迹"""
    from training.dataset import MouseTrajectoryDataset

    dataset = MouseTrajectoryDataset(jsonl_path, seq_len=SEQ_LEN)
    indices = random.sample(range(len(dataset)), min(n, len(dataset)))

    for idx in indices:
        condition, deltas, mask = dataset[idx]
        sx, sy, ex, ey = condition.numpy()
        # 反归一化到像素
        sx_px, ex_px = sx * canvas_w, ex * canvas_w
        sy_px, ey_px = sy * canvas_h, ey * canvas_h

        # 真实轨迹反归一化
        real_len = int(mask.sum().item())
        real_deltas = deltas[:real_len].numpy()
        real_points = np.zeros((real_len + 1, 2), dtype=np.float32)
        real_points[0] = [sx, sy]
        for i in range(real_len):
            real_points[i + 1] = real_points[i] + real_deltas[i]
        real_points[:, 0] *= canvas_w
        real_points[:, 1] *= canvas_h

        # 生成轨迹
        _, gen_points = generate_trajectory(
            model, sx_px, sy_px, ex_px, ey_px, canvas_w, canvas_h,
        )

        # 终点误差
        real_end = real_points[-1]
        gen_end = gen_points[-1]
        ep_err = np.sqrt((real_end[0] - gen_end[0])**2 + (real_end[1] - gen_end[1])**2)

        print(f"\n--- 样本 #{idx} ---")
        print(f"  起点: ({sx_px:.0f}, {sy_px:.0f})")
        print(f"  终点: ({ex_px:.0f}, {ey_px:.0f})")
        print(f"  真实点数: {real_len}, 生成点数: {len(gen_points)}")
        print(f"  真实终点: ({real_end[0]:.0f}, {real_end[1]:.0f})")
        print(f"  生成终点: ({gen_end[0]:.0f}, {gen_end[1]:.0f})")
        print(f"  终点误差: {ep_err:.1f} px")


def interactive_generate(model, canvas_w=942, canvas_h=621):
    """交互式生成轨迹"""
    print(f"\n画布尺寸: {canvas_w}x{canvas_h}")
    print("输入起点和终点坐标，生成轨迹（输入 q 退出）")

    while True:
        try:
            inp = input("\n起点 x y (或 q): ").strip()
            if inp.lower() == 'q':
                break
            sx, sy = map(int, inp.split())

            inp = input("终点 x y: ").strip()
            ex, ey = map(int, inp.split())

            _, gen_points = generate_trajectory(
                model, sx, sy, ex, ey, canvas_w, canvas_h,
            )

            print(f"  生成 {len(gen_points)} 点")
            print(f"  起点: ({gen_points[0][0]:.0f}, {gen_points[0][1]:.0f})")
            print(f"  终点: ({gen_points[-1][0]:.0f}, {gen_points[-1][1]:.0f})")
            print(f"  目标: ({ex}, {ey})")

        except ValueError:
            print("  输入格式错误，请重试")
        except KeyboardInterrupt:
            break


def main():
    parser = argparse.ArgumentParser(description="LSTM 轨迹生成")
    parser.add_argument("--model", type=str, default=None, help="模型路径")
    parser.add_argument("--jsonl", type=str, default=None, help="JSONL 数据对比")
    parser.add_argument("--compare", type=int, default=0, help="随机对比 N 条")
    parser.add_argument("--canvas", type=str, default="942,621", help="画布尺寸 w,h")
    args = parser.parse_args()

    cw, ch = map(int, args.canvas.split(","))
    model = load_model(args.model)

    if args.compare > 0:
        jsonl = args.jsonl or str(sorted(DATA_DIR.glob("trajectories_*.jsonl"))[-1])
        compare_with_real(model, jsonl, n=args.compare, canvas_w=cw, canvas_h=ch)
    else:
        interactive_generate(model, canvas_w=cw, canvas_h=ch)


if __name__ == "__main__":
    main()
