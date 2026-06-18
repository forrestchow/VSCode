"""
数据写入 — PostgreSQL Upsert

将归一化后的 DataFrame 批量写入数据库。
"""
import pandas as pd
from sqlalchemy import Engine, text, inspect


def upsert_dim_product(engine: Engine, df: pd.DataFrame):
    """写入/更新产品维度表"""
    if df.empty:
        return 0

    count = 0
    with engine.connect() as conn:
        for _, row in df.iterrows():
            if pd.isna(row["product_id"]):
                continue
            stmt = text("""
                INSERT INTO dim_product (product_id, product_name, short_name, platform, category, is_active, created_date)
                VALUES (:pid, :name, :sname, :plat, :cat, :active, CURRENT_DATE)
                ON CONFLICT (product_id) DO UPDATE
                SET product_name = EXCLUDED.product_name,
                    short_name = EXCLUDED.short_name,
                    is_active = EXCLUDED.is_active
            """)
            conn.execute(stmt, {
                "pid": str(row["product_id"]),
                "name": str(row["product_name"])[:200],
                "sname": str(row.get("short_name", ""))[:100] if pd.notna(row.get("short_name")) else None,
                "plat": str(row["platform"]),
                "cat": str(row.get("category", ""))[:50] if pd.notna(row.get("category")) else None,
                "active": bool(row.get("is_active", True)),
            })
            count += 1
        conn.commit()
    return count


def upsert_dim_shop(engine: Engine, df: pd.DataFrame):
    """写入/更新店铺维度表"""
    if df.empty:
        return 0

    count = 0
    with engine.connect() as conn:
        for _, row in df.iterrows():
            if pd.isna(row["shop_id"]):
                continue
            stmt = text("""
                INSERT INTO dim_shop (shop_id, shop_name, platform, is_active, created_date)
                VALUES (:sid, :sname, :plat, :active, CURRENT_DATE)
                ON CONFLICT (shop_id) DO UPDATE
                SET shop_name = EXCLUDED.shop_name,
                    is_active = EXCLUDED.is_active
            """)
            conn.execute(stmt, {
                "sid": str(row["shop_id"]),
                "sname": str(row["shop_name"])[:100],
                "plat": str(row["platform"]),
                "active": bool(row.get("is_active", True)),
            })
            count += 1
        conn.commit()
    return count


def upsert_fact_sales(engine: Engine, df: pd.DataFrame):
    """批量写入销售事实表"""
    if df.empty:
        return 0

    with engine.connect() as conn:
        for _, row in df.iterrows():
            if pd.isna(row["product_id"]) or pd.isna(row["date_id"]):
                continue
            stmt = text("""
                INSERT INTO fact_sales
                    (date_id, product_id, shop_id, sales_amount, sales_volume,
                     order_count, avg_price, unit_price, data_source, imported_at)
                VALUES
                    (:date_id, :product_id, :shop_id, :sales_amount, :sales_volume,
                     :order_count, :avg_price, :unit_price, :data_source, CURRENT_TIMESTAMP)
                ON CONFLICT (date_id, product_id, shop_id) DO UPDATE
                SET sales_volume = EXCLUDED.sales_volume,
                    avg_price = EXCLUDED.avg_price,
                    imported_at = CURRENT_TIMESTAMP
            """)
            conn.execute(stmt, {
                "date_id": str(row["date_id"]),
                "product_id": str(row["product_id"]),
                "shop_id": str(row["shop_id"]),
                "sales_amount": float(row.get("sales_amount", 0) or 0),
                "sales_volume": int(row.get("sales_volume", 0) or 0),
                "order_count": int(row.get("order_count", 0) or 0),
                "avg_price": float(row.get("avg_price", 0) or 0),
                "unit_price": float(row.get("unit_price", 0) or 0),
                "data_source": str(row.get("data_source", "")),
            })
        conn.commit()

    return len(df)
