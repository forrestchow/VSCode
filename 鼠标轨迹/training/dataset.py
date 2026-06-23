"""
鼠标轨迹数据集 — 方案A: 步数自适应 + 数据增强

每条样本:
    condition: [start_x, start_y, end_x, end_y, steps]  归一化 5 维
    deltas:    [(dx1,dy1), ..., (dxN,dyN)]              归一化 delta
    mask:      [1, 1, ..., 1, 0, 0, 0]                 有效位 mask

方案A 核心: condition 包含 steps（目标步数），训练时通过数据增强让模型
学会「同一距离、不同步数」的映射，推理时根据距离动态决定步数。
"""

import json
import numpy as np
import torch
from torch.utils.data import Dataset
from pathlib import Path

from config import (
    SEQ_LEN, STEP_AUGMENT_FIXED, STEP_AUGMENT_RELATIVE,
    STEP_AUGMENT_MIN, STEP_AUGMENT_MAX,
)


class MouseTrajectoryDataset(Dataset):
    """
    方案A 数据集:
    - condition: (5,) → [sx, sy, ex, ey, steps]
    - 数据增强: 每条原始轨迹造多个 steps 版本
    - 统一 pad 到 SEQ_LEN
    """

    def __init__(self, jsonl_paths, seq_len=SEQ_LEN):
        self.seq_len = seq_len

        if isinstance(jsonl_paths, (str, Path)):
            jsonl_paths = [jsonl_paths]

        self.samples = []
        for path in jsonl_paths:
            self._load_file(Path(path))

        if not self.samples:
            raise ValueError(f"未找到有效轨迹数据，请检查: {jsonl_paths}")

        print(f"加载 {len(self.samples)} 条样本（含增强）")
        # 统计目标步数分布
        steps_vals = [s["condition"][4] for s in self.samples]
        print(f"  目标步数范围: {min(steps_vals):.0f} – {max(steps_vals):.0f}")

    def _load_file(self, path: Path):
        """加载一个 JSONL 文件，对每条轨迹做数据增强"""
        if not path.exists():
            print(f"  [跳过] 文件不存在: {path}")
            return

        raw_count = 0
        aug_count = 0
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    augmented = self._preprocess(obj)
                    if augmented:
                        self.samples.extend(augmented)
                        raw_count += 1
                        aug_count += len(augmented)
                except (json.JSONDecodeError, KeyError) as e:
                    print(f"  [跳过] JSON 解析错误: {e}")

        print(f"  {path.name}: {raw_count} 条原始轨迹 → {aug_count} 条增强样本")

    def _preprocess(self, obj: dict):
        """
        预处理单条轨迹 → 返回 N 条增强样本的列表

        每份增强样本:
          condition: (5,) → [sx, sy, ex, ey, target_steps]
          deltas: (seq_len, 2) → pad 到统一长度
          mask: (seq_len,) → 有效位
        """
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

        # ── 原始 delta 序列 ──
        dx = np.diff(xs_norm)
        dy = np.diff(ys_norm)
        raw_deltas = np.stack([dx, dy], axis=-1)  # (T_orig, 2)
        T_orig = len(raw_deltas)

        if T_orig < 2:
            return None

        # ── 起点终点（归一化） ──
        sx, sy = xs_norm[0], ys_norm[0]
        ex, ey = xs_norm[-1], ys_norm[-1]

        # ── 方案A 数据增强: 多种目标步数 ──
        target_steps_list = self._get_target_steps(T_orig)

        results = []
        for target_steps in target_steps_list:
            # 重采样到目标步数
            deltas = self._resample_deltas(raw_deltas, target_steps)

            # pad 到 SEQ_LEN
            deltas, mask = self._pad_to_len(deltas)

            # 5 维 condition（steps 归一化到 [0,1]，与其他 4 维尺度一致）
            condition = np.array([sx, sy, ex, ey, target_steps / self.seq_len], dtype=np.float32)

            results.append({
                "condition": condition,
                "deltas": deltas,
                "mask": mask,
            })

        return results

    def _get_target_steps(self, original_steps: int):
        """
        根据原始步数生成目标步数列表（数据增强）

        包含:
          - 固定档位 (30, 60, 90, ...)
          - 相对倍率 (0.5x, 1.0x, 1.5x, 2.0x)
        去重后过滤到 [MIN, MAX] 范围
        """
        candidates = set()

        # 固定档位
        for s in STEP_AUGMENT_FIXED:
            if STEP_AUGMENT_MIN <= s <= STEP_AUGMENT_MAX:
                candidates.add(s)

        # 相对原始步数的倍率
        for factor in STEP_AUGMENT_RELATIVE:
            s = int(original_steps * factor)
            if STEP_AUGMENT_MIN <= s <= STEP_AUGMENT_MAX:
                candidates.add(s)

        # 确保原始步数一定在列表里
        if STEP_AUGMENT_MIN <= original_steps <= STEP_AUGMENT_MAX:
            candidates.add(original_steps)

        return sorted(candidates)

    def _resample_deltas(self, deltas: np.ndarray, target_steps: int):
        """
        索引均匀重采样 delta 序列到 target_steps

        原理: 在绝对坐标上做 index-uniform 插值，保留速度曲线形状
        适用于上采样(target > T)和下采样(target < T)
        [代码] 等同原 _pad_or_truncate 截断分支的逻辑，此处泛化
        """
        T = len(deltas)
        if T == target_steps:
            return deltas.copy()

        # 还原绝对坐标
        abs_pos = np.zeros((T + 1, 2), dtype=np.float32)
        for i in range(T):
            abs_pos[i + 1] = abs_pos[i] + deltas[i]

        # 按目标步数均匀索引插值
        new_indices = np.linspace(0, T, target_steps + 1)
        new_abs = np.zeros((target_steps + 1, 2), dtype=np.float32)
        for d in range(2):
            new_abs[:, d] = np.interp(new_indices, np.arange(T + 1), abs_pos[:, d])

        return np.diff(new_abs, axis=0)

    def _pad_to_len(self, deltas: np.ndarray):
        """
        将 delta 序列 pad 到 self.seq_len，返回 (deltas, mask)
        """
        T = len(deltas)

        if T >= self.seq_len:
            # 极少情况：截断（兜底）
            deltas = deltas[:self.seq_len]
            mask = np.ones(self.seq_len, dtype=np.float32)
        else:
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
        return 5  # [sx, sy, ex, ey, steps]

    @property
    def output_dim(self):
        return 2  # (dx, dy)


def create_dataloaders(jsonl_path, seq_len=SEQ_LEN, batch_size=16,
                       train_ratio=0.7, val_ratio=0.15, seed=42):
    """
    从 JSONL 文件创建 train/val/test DataLoader
    """
    from torch.utils.data import random_split, DataLoader

    full_dataset = MouseTrajectoryDataset(jsonl_path, seq_len=seq_len)
    n = len(full_dataset)

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
