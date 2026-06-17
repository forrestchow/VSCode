"""
鼠标轨迹数据集 — 加载 JSONL → 归一化 → delta 序列 → PyTorch Dataset
"""

import json
import numpy as np
import torch
from torch.utils.data import Dataset
from pathlib import Path


class MouseTrajectoryDataset(Dataset):
    """
    每条样本：
        condition: [start_x, start_y, end_x, end_y]  归一化到 [0, 1]
        deltas:    [(dx1,dy1), ..., (dxN,dyN)]      归一化 delta 序列
        mask:      [1, 1, ..., 1, 0, 0, 0]         有效位 mask
    """

    def __init__(self, jsonl_paths, seq_len=200):
        """
        Args:
            jsonl_paths: JSONL 文件路径 或 路径列表
            seq_len: 统一序列长度
        """
        self.seq_len = seq_len

        if isinstance(jsonl_paths, (str, Path)):
            jsonl_paths = [jsonl_paths]

        self.samples = []
        for path in jsonl_paths:
            self._load_file(Path(path))

        if not self.samples:
            raise ValueError(f"未找到有效轨迹数据，请检查: {jsonl_paths}")

        print(f"加载 {len(self.samples)} 条轨迹")

    def _load_file(self, path: Path):
        """加载一个 JSONL 文件"""
        if not path.exists():
            print(f"  [跳过] 文件不存在: {path}")
            return

        count = 0
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    processed = self._preprocess(obj)
                    if processed is not None:
                        self.samples.append(processed)
                        count += 1
                except (json.JSONDecodeError, KeyError) as e:
                    print(f"  [跳过] JSON 解析错误: {e}")

        print(f"  {path.name}: {count} 条")

    def _preprocess(self, obj: dict):
        """预处理单条轨迹 → normalized deltas"""
        trajectory = obj.get("trajectory", [])
        if len(trajectory) < 3:
            return None

        cw, ch = obj.get("canvas_size", [1920, 1080])
        if cw <= 0 or ch <= 0:
            return None

        # ── 提取绝对坐标 ──
        xs = np.array([p[0] for p in trajectory], dtype=np.float32)
        ys = np.array([p[1] for p in trajectory], dtype=np.float32)

        # ── 归一化到 [0, 1] ──
        xs_norm = xs / cw
        ys_norm = ys / ch

        # ── 转为 delta 序列 ──
        dx = np.diff(xs_norm)
        dy = np.diff(ys_norm)
        deltas = np.stack([dx, dy], axis=-1)  # (T, 2)

        if len(deltas) < 2:
            return None

        # ── 条件向量：[start_x, start_y, end_x, end_y] 归一化 ──
        start_x, start_y = xs_norm[0], ys_norm[0]
        end_x, end_y = xs_norm[-1], ys_norm[-1]
        condition = np.array([start_x, start_y, end_x, end_y], dtype=np.float32)

        # ── 统一长度 ──
        deltas, mask = self._pad_or_truncate(deltas)

        return {
            "condition": condition,
            "deltas": deltas,
            "mask": mask,
        }

    def _pad_or_truncate(self, deltas: np.ndarray):
        """
        将 delta 序列填充/截断到 self.seq_len

        关键：截断时必须在**绝对坐标**上重采样再算 delta，
        否则截断后的 delta 累加和 ≠ 原始位移，导致终点误差放大。
        """
        T = len(deltas)

        if T >= self.seq_len:
            # ── 截断：在绝对坐标上均匀重采样 ──
            # 还原绝对坐标（相对坐标累加）
            abs_pos = np.zeros((T + 1, 2), dtype=np.float32)
            abs_pos[0] = [0.0, 0.0]
            for i in range(T):
                abs_pos[i + 1] = abs_pos[i] + deltas[i]

            # 均匀采样 seq_len+1 个位置点
            new_indices = np.linspace(0, T, self.seq_len + 1)
            new_abs = np.zeros((self.seq_len + 1, 2), dtype=np.float32)
            for d in range(2):
                new_abs[:, d] = np.interp(new_indices, np.arange(T + 1), abs_pos[:, d])

            # 重新计算 delta
            deltas = np.diff(new_abs, axis=0)  # (seq_len, 2)
            mask = np.ones(self.seq_len, dtype=np.float32)
        else:
            # ── 填充：末尾补零 ──
            pad_len = self.seq_len - T
            deltas = np.pad(deltas, ((0, pad_len), (0, 0)), mode="constant")
            mask = np.concatenate([
                np.ones(T, dtype=np.float32),
                np.zeros(pad_len, dtype=np.float32),
            ])

        return deltas, mask

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        s = self.samples[idx]
        return (
            torch.from_numpy(s["condition"]),
            torch.from_numpy(s["deltas"]),
            torch.from_numpy(s["mask"]),
        )

    @property
    def input_dim(self):
        return 4  # [sx, sy, ex, ey]

    @property
    def output_dim(self):
        return 2  # (dx, dy)


def create_dataloaders(jsonl_path, seq_len=200, batch_size=16,
                       train_ratio=0.7, val_ratio=0.15, seed=42):
    """
    从 JSONL 文件创建 train/val/test DataLoader
    """
    from torch.utils.data import random_split, DataLoader

    full_dataset = MouseTrajectoryDataset(jsonl_path, seq_len=seq_len)
    n = len(full_dataset)

    # 计算划分
    n_train = int(n * train_ratio)
    n_val = int(n * val_ratio)
    n_test = n - n_train - n_val

    generator = torch.Generator().manual_seed(seed)
    train_ds, val_ds, test_ds = random_split(
        full_dataset, [n_train, n_val, n_test],
        generator=generator,
    )

    print(f"划分: train={n_train}  val={n_val}  test={n_test}")

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)
    test_loader = DataLoader(test_ds, batch_size=batch_size, shuffle=False)

    return train_loader, val_loader, test_loader, full_dataset
