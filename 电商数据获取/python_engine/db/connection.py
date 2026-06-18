"""
数据库连接管理 — SQLAlchemy
"""
from sqlalchemy import create_engine, Engine, text
from sqlalchemy.orm import sessionmaker, Session


def get_engine(db_url: str | None = None) -> Engine:
    """创建 SQLAlchemy engine"""
    if db_url is None:
        from python_engine.config import DB_URL
        db_url = DB_URL

    return create_engine(
        db_url,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,  # 每次从池中取连接时检测是否有效
    )


def get_session(engine: Engine | None = None) -> Session:
    """创建数据库 session"""
    if engine is None:
        engine = get_engine()
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def test_connection(db_url: str | None = None) -> bool:
    """测试数据库连接"""
    try:
        engine = get_engine(db_url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f"[DB] 连接失败: {e}")
        return False
