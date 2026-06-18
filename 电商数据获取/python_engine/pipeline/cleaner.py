"""
数据清洗 — 基于 pandas

处理从各平台提取的原始数据：
  - 销量文本 → 数字
  - 价格标准化
  - 去重
  - 缺失值处理
"""
import pandas as pd
from datetime import date


def clean_products(raw_data: list[dict], platform: str) -> pd.DataFrame:
    """
    清洗商品列表数据

    Args:
        raw_data: extract() 返回的原始数据列表
        platform: 平台标识 (taobao/pdd/jd/douyin)

    Returns:
        清洗后的 DataFrame
    """
    if not raw_data:
        return pd.DataFrame()

    df = pd.DataFrame(raw_data)

    # ── 1. 去重 ──
    if "productId" in df.columns and df["productId"].notna().any():
        df = df.drop_duplicates(subset=["productId"])
    elif "productUrl" in df.columns:
        df = df.drop_duplicates(subset=["productUrl"])

    # ── 2. 价格标准化 ──
    if "price" in df.columns:
        df["price"] = pd.to_numeric(df["price"], errors="coerce")

    # ── 3. 销量标准化 ──
    if "sales" in df.columns:
        df["sales"] = pd.to_numeric(df["sales"], errors="coerce").fillna(0).astype(int)

    # ── 4. 库存标准化 ──
    if "stock" in df.columns:
        df["stock"] = pd.to_numeric(df["stock"], errors="coerce").fillna(0).astype(int)

    # ── 5. 标题清理 ──
    if "title" in df.columns:
        df["title"] = df["title"].str.strip()

    # ── 6. 标记平台 ──
    df["platform"] = platform

    # ── 7. 标记采集日期 ──
    df["collected_at"] = date.today()

    # ── 8. 过滤空标题（无效行） ──
    df = df[df["title"].notna() & (df["title"] != "")]

    return df.reset_index(drop=True)


def clean_orders(raw_data: list[dict], platform: str) -> pd.DataFrame:
    """清洗订单数据（后续实现）"""
    if not raw_data:
        return pd.DataFrame()
    df = pd.DataFrame(raw_data)
    df["platform"] = platform
    df["collected_at"] = date.today()
    return df
