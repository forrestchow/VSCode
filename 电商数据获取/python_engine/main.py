"""
电商数据获取 — 主入口

用法:
    python -m python_engine.main                    # 采集当前页面
    python -m python_engine.main --snapshot         # 仅保存 HTML 快照
    python -m python_engine.main --snapshot --save-db  # 快照 + 采集 + 入库
"""
import asyncio
import argparse
from datetime import datetime
from pathlib import Path

# 将项目根目录加入 path（供直接运行）
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from python_engine.config import SNAPSHOT_DIR
from python_engine.browser.manager import connect_or_launch
from python_engine.browser.navigator import PageNavigator
from python_engine.extractors.taobao.products import TaobaoProductExtractor
from python_engine.pipeline.cleaner import clean_products
from python_engine.pipeline.normalizer import normalize_products, normalize_sales
from python_engine.pipeline.loader import (
    upsert_dim_product,
    upsert_dim_shop,
    upsert_fact_sales,
)
from python_engine.db.connection import get_engine


async def run_extraction(save_db: bool = False):
    """
    主流程：连接 Chrome → 检测平台 → 提取数据 → 清洗 → 入库
    """
    # 1. 连接浏览器
    print("=" * 50)
    print("  电商数据获取")
    print("=" * 50)

    client, is_new = await connect_or_launch()
    nav = PageNavigator(client)
    print(f"[Main] Chrome {'新启动' if is_new else '已有实例'}，已连接\n")

    # 2. 检测当前页面
    platform = await nav.detect_platform()
    url = await client.evaluate("location.href")
    title = await client.evaluate("document.title")
    print(f"[Main] 当前页面: {title}")
    print(f"[Main] URL: {url}")
    print(f"[Main] 检测平台: {platform}\n")

    # 3. 提取数据
    if platform == "taobao":
        extractor = TaobaoProductExtractor(client)
        result = await extractor.extract_with_debug()
    else:
        print(f"[Main] 平台 '{platform}' 暂不支持，仅保存 HTML 快照")
        html = await client.get_html()
        save_snapshot(html, platform)
        await client.close()
        return

    items = result.get("results", [])
    print(f"[Main] 提取策略: {result.get('strategy', 'unknown')}")
    print(f"[Main] 调试信息: {result.get('debug', [])}")
    print(f"[Main] 提取到 {len(items)} 个商品\n")

    if not items:
        print("[Main] [WARN] 未提取到数据。保存 HTML 快照以便分析...")
        html = await client.get_html()
        save_snapshot(html, platform)
        await client.close()
        return

    # 打印前 3 条预览
    print("[Main] 数据预览 (前3条):")
    for item in items[:3]:
        print(f"  {item.get('title', '-')[:50]}")
        print(f"    价格: ¥{item.get('price', '?')}  销量: {item.get('sales', '?')}件  ID: {item.get('productId', '?')}")
    print()

    # 4. 清洗 + 归一化
    df = clean_products(items, platform)
    print(f"[Cleaner] 清洗后: {len(df)} 行")

    normalized = normalize_products(df)
    sales_df = normalize_sales(df)

    # 5. 入库
    if save_db:
        engine = get_engine()
        n_prod = upsert_dim_product(engine, normalized["dim_product"])
        n_shop = upsert_dim_shop(engine, normalized["dim_shop"])
        n_sales = upsert_fact_sales(engine, sales_df)
        print(f"[Loader] 入库: {n_prod} 产品, {n_shop} 店铺, {n_sales} 销售记录")
        print("[Main] [OK] 数据已写入 PostgreSQL")
    else:
        print("[Main] (试运行模式，未写入数据库。加 --save-db 参数启用入库)")

    # 6. 断开
    await client.close()
    print(f"\n[Main] 完成。共采集 {len(items)} 个商品。")


def save_snapshot(html: str, platform: str, label: str = ""):
    """保存 HTML 快照到 html_snapshots/"""
    SNAPSHOT_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = f"{platform}_{label}_{ts}.html" if label else f"{platform}_{ts}.html"
    path = SNAPSHOT_DIR / name
    path.write_text(html, encoding="utf-8")
    print(f"[Snapshot] HTML 已保存: {path}")
    return path


async def snapshot_only():
    """仅保存当前页面的 HTML 快照（开发分析用）"""
    client, _ = await connect_or_launch()
    nav = PageNavigator(client)

    url = await client.evaluate("location.href")
    platform = await nav.detect_platform()
    html = await client.get_html()

    path = save_snapshot(html, platform)
    print(f"[Snapshot] 页面: {url}")
    print(f"[Snapshot] 大小: {len(html)} 字符")

    await client.close()
    return path


def main():
    parser = argparse.ArgumentParser(description="电商数据获取")
    parser.add_argument(
        "--snapshot", action="store_true",
        help="仅保存当前页面 HTML 快照（不提取数据）"
    )
    parser.add_argument(
        "--save-db", action="store_true",
        help="将采集结果写入 PostgreSQL"
    )
    args = parser.parse_args()

    if args.snapshot:
        asyncio.run(snapshot_only())
    else:
        asyncio.run(run_extraction(save_db=args.save_db))


if __name__ == "__main__":
    main()
