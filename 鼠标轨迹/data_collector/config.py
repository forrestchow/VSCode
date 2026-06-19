"""
数据采集器配置
"""
from pathlib import Path

# --- 屏幕 ---
SCREEN_MARGIN = 50          # 起点/终点距屏幕边缘的最小距离 (px)
MIN_DISTANCE = 200          # 起点和终点之间的最小距离 (px)
MAX_DISTANCE = 1400         # 起点和终点之间的最大距离 (px)

# --- 视觉 ---
START_COLOR = "#00CC00"     # 起点圆圈颜色 (绿)
END_COLOR = "#FF3333"       # 终点圆圈颜色 (红)
CIRCLE_RADIUS = 16          # 圆圈半径
CIRCLE_WIDTH = 3            # 圆圈线宽
OVERLAY_ALPHA = 0.40        # 遮罩透明度 (0-1, 越小越透明)

# 点击判定容差 (px): 用户点击位置距离圆心在此范围内则视为命中
CLICK_TOLERANCE = 35

# --- 显示 ---
STATUS_FONT = ("Microsoft YaHei", 12)
STATUS_BG = "#1a1a2e"
STATUS_TEXT_COLOR = "#e0e0e0"
HINT_FONT = ("Microsoft YaHei", 10)
HINT_COLOR = "#aaaaaa"

# --- 数据存储 ---
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_FILENAME_TEMPLATE = "trajectories_{date}.jsonl"

# --- 其他 ---
SAVE_DELAY_MS = 500         # 保存后等待时间（给用户缓冲）
DISPLAY_REFRESH_MS = 33     # 显示刷新间隔 (~30fps)
