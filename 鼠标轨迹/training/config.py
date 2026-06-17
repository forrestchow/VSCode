"""
LSTM 鼠标轨迹训练超参数
"""

# ── 数据 ──
SEQ_LEN = 200            # 统一序列长度（填充/截断）
BATCH_SIZE = 16          # 批次大小
TRAIN_RATIO = 0.70       # 训练集比例
VAL_RATIO = 0.15         # 验证集比例
TEST_RATIO = 0.15        # 测试集比例

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
