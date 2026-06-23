"""
LSTM 鼠标轨迹模型训练脚本

用法:
    python train.py                          # 使用默认 JSONL
    python train.py --jsonl data/my.jsonl    # 指定文件
    python train.py --overfit               # 过拟合测试（50条）
"""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

# 添加父目录到 path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dataset import MouseTrajectoryDataset, create_dataloaders
from model import create_model, count_parameters
from config import (
    SEQ_LEN, BATCH_SIZE,
    TRAIN_RATIO, VAL_RATIO,
    HIDDEN_SIZE, NUM_LAYERS, DROPOUT,
    LEARNING_RATE, WEIGHT_DECAY,
    EPOCHS, EARLY_STOP_PATIENCE, GRAD_CLIP,
    DATA_DIR, MODEL_DIR,
    STEPS_INTERCEPT, STEPS_SLOPE, STEP_AUGMENT_MIN, STEP_AUGMENT_MAX,
)


def compute_loss(pred, target, mask):
    """
    MSE Loss，仅计算非 padding 位置
    pred:   (B, T, 2)
    target: (B, T, 2)
    mask:   (B, T)
    """
    diff = (pred - target) ** 2          # (B, T, 2)
    per_step = diff.mean(dim=-1)         # (B, T)
    masked = per_step * mask             # (B, T)
    loss = masked.sum() / (mask.sum() + 1e-8)
    return loss


def compute_endpoint_error(pred_deltas, condition, mask, canvas_size=(942, 621)):
    """
    计算终点误差（像素）
    pred_deltas: 归一化 delta 序列 (B, T, 2)
    condition:   归一化起点终点 (B, 4) → [sx, sy, ex, ey]
    """
    cw, ch = canvas_size

    # 累积 delta → 得到绝对位置
    cumsum = torch.cumsum(pred_deltas, dim=1)  # (B, T, 2)

    # 获取每个样本的实际序列长度
    lengths = mask.sum(dim=1).long() - 1       # (B,)
    lengths = torch.clamp(lengths, min=0)

    # 取最后一个有效位置
    batch_indices = torch.arange(len(lengths))
    final_pos = cumsum[batch_indices, lengths, :]  # (B, 2)

    # 目标终点（相对于起点的偏移）
    # condition 方案A: (B, 5) = [sx, sy, ex, ey, steps]
    start = condition[:, :2]   # (B, 2)  sx, sy
    end = condition[:, 2:4]    # (B, 2)  ex, ey
    target_delta = end - start  # (B, 2)

    # 像素误差
    px_error_x = (final_pos[:, 0] - target_delta[:, 0]).abs() * cw
    px_error_y = (final_pos[:, 1] - target_delta[:, 1]).abs() * ch
    px_error = torch.sqrt(px_error_x ** 2 + px_error_y ** 2)

    return px_error.mean().item()


def train_epoch(model, loader, optimizer, device):
    """训练一个 epoch"""
    model.train()
    total_loss = 0.0
    n_batches = 0

    for condition, deltas, mask in loader:
        condition = condition.to(device)
        deltas = deltas.to(device)
        mask = mask.to(device)

        optimizer.zero_grad()
        pred = model(condition, deltas)  # Teacher Forcing
        loss = compute_loss(pred, deltas, mask)
        loss.backward()

        # 梯度裁剪
        torch.nn.utils.clip_grad_norm_(model.parameters(), GRAD_CLIP)

        optimizer.step()

        total_loss += loss.item()
        n_batches += 1

    return total_loss / max(n_batches, 1)


@torch.no_grad()
def validate(model, loader, device):
    """验证"""
    model.eval()
    total_loss = 0.0
    total_ep_err = 0.0
    n_batches = 0

    for condition, deltas, mask in loader:
        condition = condition.to(device)
        deltas = deltas.to(device)
        mask = mask.to(device)

        pred = model(condition, deltas)
        loss = compute_loss(pred, deltas, mask)
        ep_err = compute_endpoint_error(pred, condition, mask)

        total_loss += loss.item()
        total_ep_err += ep_err
        n_batches += 1

    return total_loss / max(n_batches, 1), total_ep_err / max(n_batches, 1)


def find_latest_jsonl(data_dir: Path) -> Path:
    """自动查找最新的 JSONL 文件"""
    jsonl_files = sorted(data_dir.glob("trajectories_*.jsonl"))
    if not jsonl_files:
        raise FileNotFoundError(f"在 {data_dir} 中未找到 trajectories_*.jsonl 文件")
    return jsonl_files[-1]


def main():
    parser = argparse.ArgumentParser(description="训练 LSTM 鼠标轨迹模型")
    parser.add_argument("--jsonl", type=str, default=None,
                        help="JSONL 数据文件路径（默认自动查找最新）")
    parser.add_argument("--overfit", action="store_true",
                        help="过拟合测试模式")
    parser.add_argument("--epochs", type=int, default=EPOCHS,
                        help=f"训练轮数（默认 {EPOCHS}）")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE,
                        help=f"批次大小（默认 {BATCH_SIZE}）")
    parser.add_argument("--lr", type=float, default=LEARNING_RATE,
                        help=f"学习率（默认 {LEARNING_RATE}）")
    args = parser.parse_args()

    # ── 设备 ──
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"设备: {device}")

    # ── 数据 ──
    if args.jsonl:
        jsonl_path = Path(args.jsonl)
    else:
        jsonl_path = find_latest_jsonl(DATA_DIR)

    print(f"数据: {jsonl_path}")

    if args.overfit:
        # 过拟合测试：只用少量数据
        print(">>> 过拟合测试模式 <<<")
        dataset = MouseTrajectoryDataset(jsonl_path, seq_len=SEQ_LEN)
        # 取前 8 条
        subset = torch.utils.data.Subset(dataset, range(min(8, len(dataset))))
        train_loader = torch.utils.data.DataLoader(subset, batch_size=8, shuffle=True)
        val_loader = train_loader  # 同一批数据验证
        print(f"过拟合测试: {len(subset)} 条")
    else:
        train_loader, val_loader, test_loader, dataset = create_dataloaders(
            jsonl_path, seq_len=SEQ_LEN, batch_size=args.batch_size,
            train_ratio=TRAIN_RATIO, val_ratio=VAL_RATIO,
        )

    # ── 模型 ──
    model = create_model(
        hidden_size=HIDDEN_SIZE,
        num_layers=NUM_LAYERS,
        dropout=DROPOUT,
    ).to(device)

    n_params = count_parameters(model)
    print(f"模型参数: {n_params:,}")

    # ── 优化器 ──
    optimizer = optim.Adam(model.parameters(), lr=args.lr,
                           weight_decay=WEIGHT_DECAY)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", factor=0.5, patience=10,
    )

    # ── 训练 ──
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    best_val_loss = float("inf")
    best_epoch = 0
    patience_counter = 0
    history = []

    print(f"\n开始训练 ({args.epochs} epochs)...")
    print("-" * 60)

    t0 = time.time()

    for epoch in range(1, args.epochs + 1):
        train_loss = train_epoch(model, train_loader, optimizer, device)
        val_loss, val_ep_err = validate(model, val_loader, device)

        scheduler.step(val_loss)
        current_lr = optimizer.param_groups[0]["lr"]

        history.append({
            "epoch": epoch,
            "train_loss": train_loss,
            "val_loss": val_loss,
            "val_ep_error_px": val_ep_err,
            "lr": current_lr,
        })

        # 打印
        marker = ""
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_epoch = epoch
            patience_counter = 0
            marker = " ★"

            # 保存最佳模型
            torch.save({
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "val_loss": val_loss,
                "config": {
                    "hidden_size": HIDDEN_SIZE,
                    "num_layers": NUM_LAYERS,
                    "dropout": DROPOUT,
                    "seq_len": SEQ_LEN,
                    # 方案A 参数
                    "input_dim": 5,                         # [sx, sy, ex, ey, steps]
                    "steps_intercept": STEPS_INTERCEPT,     # 步数预测
                    "steps_slope": STEPS_SLOPE,
                    "step_augment_min": STEP_AUGMENT_MIN,   # 增强范围
                    "step_augment_max": STEP_AUGMENT_MAX,
                },
            }, MODEL_DIR / "best_model.pt")
        else:
            patience_counter += 1

        if epoch % 5 == 0 or epoch == 1 or marker:
            print(f"Epoch {epoch:3d} | train_loss={train_loss:.6f} | "
                  f"val_loss={val_loss:.6f} | ep_err={val_ep_err:.1f}px | "
                  f"lr={current_lr:.2e}{marker}")

        # 早停
        if patience_counter >= EARLY_STOP_PATIENCE:
            print(f"\n早停 @ epoch {epoch}（{EARLY_STOP_PATIENCE} 轮未改善）")
            break

    elapsed = time.time() - t0
    print("-" * 60)
    print(f"训练完成 ({elapsed:.0f}s)")
    print(f"最佳模型: epoch {best_epoch}, val_loss={best_val_loss:.6f}")
    print(f"模型保存在: {MODEL_DIR / 'best_model.pt'}")

    # 保存训练历史
    with open(MODEL_DIR / "training_history.json", "w") as f:
        json.dump(history, f, indent=2)

    # ── 最终验证 ──
    if not args.overfit:
        print("\n=== 测试集评估 ===")
        test_loss, test_ep_err = validate(model, test_loader, device)
        print(f"Test Loss: {test_loss:.6f}")
        print(f"Test Endpoint Error: {test_ep_err:.1f} px")
    else:
        print("\n=== 过拟合验证 ===")
        final_loss, final_ep_err = validate(model, val_loader, device)
        print(f"Final Loss: {final_loss:.6f} (应接近 0)")
        print(f"Final Endpoint Error: {final_ep_err:.1f} px (应 < 5px)")

    return model, history


if __name__ == "__main__":
    main()
