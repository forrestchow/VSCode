"""
多平台字段归一化

将各平台清洗后的 DataFrame 映射到统一的数据库 schema 字段。
"""
import pandas as pd


def normalize_products(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """
    将商品数据拆分为 dim_product 和 dim_shop 两表

    Args:
        df: clean_products() 的输出

    Returns:
        {"dim_product": DataFrame, "dim_shop": DataFrame}
    """
    if df.empty:
        return {"dim_product": pd.DataFrame(), "dim_shop": pd.DataFrame()}

    # ── dim_product ──
    products = pd.DataFrame()
    products["product_id"] = df["productId"].fillna(
        df["productUrl"].str.extract(r"[?&]id=(\d+)")[0]
    )
    products["product_name"] = df["title"]
    products["short_name"] = df["title"].str[:50]  # 前50字符做简称
    products["platform"] = df["platform"]
    products["category"] = "食用盐"  # 默认品类，后续可从标题提取
    products["is_active"] = True
    products = products.drop_duplicates(subset=["product_id"])

    # ── dim_shop ──
    shops = pd.DataFrame()
    shops["shop_id"] = df["platform"] + "_default"  # 卖家中心只有一个店铺
    shops["shop_name"] = "我的店铺"
    shops["platform"] = df["platform"]
    shops["is_active"] = True
    shops = shops.drop_duplicates(subset=["shop_id"])

    return {"dim_product": products, "dim_shop": shops}


def normalize_sales(df: pd.DataFrame) -> pd.DataFrame:
    """
    将商品数据映射到 fact_sales 表结构

    Args:
        df: clean_products() 的输出

    Returns:
        符合 fact_sales 结构的 DataFrame
    """
    if df.empty:
        return pd.DataFrame()

    sales = pd.DataFrame()
    sales["date_id"] = df["collected_at"]
    sales["product_id"] = df["productId"].fillna(
        df["productUrl"].str.extract(r"[?&]id=(\d+)")[0]
    )
    sales["shop_id"] = df["platform"] + "_default"
    sales["sales_amount"] = 0  # 商品列表页通常没有累计销售额
    sales["sales_volume"] = df.get("sales", 0).fillna(0)
    sales["order_count"] = 0
    sales["avg_price"] = df.get("price", 0).fillna(0)
    sales["unit_price"] = df.get("price", 0).fillna(0)
    sales["data_source"] = df["platform"] + "_products"

    return sales
