"""
LSTM 鼠标轨迹训练超参数
"""

# ── 数据 ──
SEQ_LEN = 200            # 统一序列长度（填充/截断），当前数据最大132步，200足够
BATCH_SIZE = 16          # 批次大小
TRAIN_RATIO = 0.70       # 训练集比例
VAL_RATIO = 0.15         # 验证集比例
TEST_RATIO = 0.15        # 测试集比例

# ── 方案A: 数据增强 ──
# 每条原始轨迹造多个 steps 版本，让模型学会不同步数下的 delta 分布
# steps 取值: 固定档位 + 原始值 + 外推值（确保覆盖快慢两端）
STEP_AUGMENT_FIXED = [30, 60, 90, 120, 150, 180, 200]  # 固定档位
STEP_AUGMENT_RELATIVE = [0.5, 1.0, 1.5, 2.0]            # 相对原始步数的倍率
STEP_AUGMENT_MIN = 20      # 最低步数（低于此值 delta 过大，不自然）
STEP_AUGMENT_MAX = SEQ_LEN # 最高步数（超出 SEQ_LEN 的裁掉）

# ── 方案A: 推理步数预测 ──
# 来自训练数据统计分析：距离 → 步数的线性拟合
# 公式: steps = STEPS_INTERCEPT + STEPS_SLOPE × distance_px  [数据] trajectories_2026-06-17.jsonl
STEPS_INTERCEPT = 43.4
STEPS_SLOPE = 0.092

# ── 模型 ──
HIDDEN_SIZE = 128        # LSTM hidden size
NUM_LAYERS = 2           # LSTM 层数
DROPOUT = 0.2            # Dropout

# ── 训练 ──
LEARNING_RATE = 1e-3     # Adam 学习率
WEIGHT_DECAY = 1e-5      # L2 正则
EPOCHS = 200             # 最大训练轮数
EARLY_STOP_PATIENCE = 25 # 早停轮数
GRAD_CLIP = 1.0          # 梯度裁剪

# ── 路径 ──
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
MODEL_DIR = BASE_DIR / "models"
