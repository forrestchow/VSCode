"""
项目配置中心
所有可配置项集中管理，支持 .env 文件覆盖
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

# 加载 .env（如果存在）
load_dotenv(PROJECT_ROOT / ".env")

# ─── Chrome / CDP ───────────────────────────────────────
# 察尔汗 Chrome debug port
CDP_PORT = int(os.getenv("CDP_PORT", "9222"))

# 察尔汗 Chrome 的 user-data-dir（自动发现 or 手动指定）
# 如果设置了环境变量 CHAYAN_PROFILE，优先使用
CHAYAN_PROFILE = os.getenv("CHAYAN_PROFILE", "")

# 察尔汗 Chrome 可执行文件路径（可选，用于 auto-launch）
CHAYAN_EXECUTABLE = os.getenv("CHAYAN_EXECUTABLE", "")

# 常见察尔汗 profile 搜索路径
CHAYAN_PROFILE_SEARCH_PATHS = [
    os.path.expandvars(r"%LOCALAPPDATA%\察尔汗\User Data"),
    os.path.expandvars(r"%APPDATA%\察尔汗\User Data"),
    r"C:\Program Files\察尔汗\User Data",
    r"C:\察尔汗\User Data",
]

# ─── PostgreSQL ─────────────────────────────────────────
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "ecommerce_bi")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

DB_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# ─── 数据采集 ───────────────────────────────────────────
# 请求间隔（秒），避免触发风控
REQUEST_DELAY = float(os.getenv("REQUEST_DELAY", "2.0"))

# HTML 快照存储目录
SNAPSHOT_DIR = PROJECT_ROOT / "html_snapshots"
