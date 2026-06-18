"""
初始化数据库:
1. 创建所有表（IF NOT EXISTS）
2. 填充 dim_date（2023-2027 年日期维度数据）
"""
import sys
from pathlib import Path

# 将项目根目录加入 path
sys.path.insert(0, str(Path(__file__).parent.parent))

from python_engine.config import DB_URL
from sqlalchemy import create_engine, text


def init_schema(engine):
    """执行 schema.sql 创建所有表"""
    schema_path = Path(__file__).parent.parent / "python_engine" / "db" / "schema.sql"
    sql = schema_path.read_text(encoding="utf-8")

    with engine.connect() as conn:
        # 逐条执行（跳过注释和空行）
        statements = [s.strip() for s in sql.split(";") if s.strip() and not s.strip().startswith("--")]
        for stmt in statements:
            if stmt:
                conn.execute(text(stmt))
        conn.commit()
    print("[DB] 表结构创建完成")


def seed_dim_date(engine):
    """填充日期维度表 2023-01-01 ~ 2027-12-31"""
    seed_sql = """
    INSERT INTO dim_date
    SELECT
        d::date AS date_id,
        EXTRACT(YEAR FROM d)::SMALLINT AS year,
        EXTRACT(QUARTER FROM d)::SMALLINT AS quarter,
        EXTRACT(MONTH FROM d)::SMALLINT AS month,
        EXTRACT(MONTH FROM d)::VARCHAR || '月' AS month_name,
        EXTRACT(WEEK FROM d)::SMALLINT AS week_of_year,
        EXTRACT(DOW FROM d)::SMALLINT AS day_of_week,
        CASE EXTRACT(DOW FROM d)
            WHEN 0 THEN '周日' WHEN 1 THEN '周一'
            WHEN 2 THEN '周二' WHEN 3 THEN '周三'
            WHEN 4 THEN '周四' WHEN 5 THEN '周五'
            WHEN 6 THEN '周六'
        END AS day_name,
        EXTRACT(DOW FROM d) IN (0, 6) AS is_weekend,
        TO_CHAR(d, 'YYYYMM') AS yyyymm,
        EXTRACT(YEAR FROM d) || 'Q' || EXTRACT(QUARTER FROM d) AS yyyyqw
    FROM generate_series('2023-01-01'::date, '2027-12-31'::date, '1 day') AS d
    ON CONFLICT (date_id) DO NOTHING;
    """

    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM dim_date"))
        existing = result.scalar()
        if existing > 0:
            print(f"[DB] dim_date 已有 {existing} 行，跳过填充")
            return

        conn.execute(text(seed_sql))
        conn.commit()

        result = conn.execute(text("SELECT COUNT(*) FROM dim_date"))
        count = result.scalar()
        print(f"[DB] dim_date 填充完成: {count} 行")


def main():
    print(f"[DB] 连接: {DB_URL}")
    engine = create_engine(DB_URL)

    # 测试连接
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    print("[DB] 连接成功")

    init_schema(engine)
    seed_dim_date(engine)
    print("[DB] [OK] 数据库初始化完成")


if __name__ == "__main__":
    main()
