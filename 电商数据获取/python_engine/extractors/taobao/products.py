"""
淘宝卖家中心 — 出售中的商品 数据提取器

页面: myseller.taobao.com/sale/item.htm
"""
import json
from typing import Any

from python_engine.extractors.base import BaseExtractor


# 提取用的 JavaScript — 注入到页面执行
EXTRACT_JS = r"""
(() => {
    const results = [];
    const debug = [];

    // ── 策略1: 查找 data-id 的商品行（新版千牛） ──
    const rows = document.querySelectorAll('[data-id]');
    if (rows.length > 0) {
        debug.push('策略1: 找到 ' + rows.length + ' 个 [data-id] 行');
        for (const row of rows) {
            const data = extractFromRow(row);
            if (data && data.title) results.push(data);
        }
        if (results.length > 0) {
            return JSON.stringify({ results, debug, strategy: 'data-id' });
        }
    }

    // ── 策略2: 查找 table 中的商品行 ──
    const tables = document.querySelectorAll('table');
    for (const table of tables) {
        const trs = table.querySelectorAll('tbody tr, tr');
        debug.push('策略2: table 有 ' + trs.length + ' 行');
        for (const tr of trs) {
            const data = extractFromRow(tr);
            if (data && data.title && data.price !== null) {
                results.push(data);
            }
        }
        if (results.length > 0) {
            return JSON.stringify({ results, debug, strategy: 'table' });
        }
    }

    // ── 策略3: 查找所有包含商品信息的通用容器 ──
    const containers = document.querySelectorAll(
        '.item, .goods-item, .product-item, [class*="item"], [class*="goods"], [class*="product"]'
    );
    debug.push('策略3: 找到 ' + containers.length + ' 个候选容器');
    for (const el of containers) {
        const text = (el.innerText || '').trim();
        // 商品行通常包含价格符号 ¥ 和一定长度的文本
        if (text.includes('¥') && text.length > 20) {
            const data = extractFromContainer(el);
            if (data && data.title) results.push(data);
        }
    }

    // ── 辅助函数: 从表格行提取 ──
    function extractFromRow(row) {
        const text = (row.innerText || '').trim();
        if (!text || text.length < 10) return null;

        const html = row.outerHTML || row.innerHTML || '';

        // 标题 — 通常是行内最长的文本段
        const candidates = [];
        row.querySelectorAll('a, span, div, td, p').forEach(el => {
            const t = (el.innerText || '').trim();
            if (t.length > 5 && !t.includes('编辑') && !t.includes('删除')) {
                candidates.push({ text: t, len: t.length, href: el.href || '' });
            }
        });
        candidates.sort((a, b) => b.len - a.len);
        const title = candidates[0]?.text || '';
        const productUrl = candidates[0]?.href || '';

        // 价格
        let price = null;
        const priceMatch = text.match(/¥\s*([\d.]+)/);
        if (priceMatch) price = parseFloat(priceMatch[1]);

        // 销量
        let sales = null;
        const salesMatch = text.match(/(\d+)\s*件/);
        if (salesMatch) sales = parseInt(salesMatch[1]);

        // 库存
        let stock = null;
        const stockMatch = text.match(/库存[:\s]*(\d+)/);
        if (stockMatch) stock = parseInt(stockMatch[1]);

        // 商品ID
        let productId = '';
        const idAttr = row.getAttribute('data-id') || '';
        if (idAttr) productId = idAttr;
        if (!productId && productUrl) {
            const m = productUrl.match(/[?&]id=(\d+)/);
            if (m) productId = m[1];
        }

        return { title, productUrl, price, sales, stock, productId };
    }

    // ── 辅助函数: 从通用容器提取 ──
    function extractFromContainer(el) {
        const text = (el.innerText || '').trim();
        if (!text) return null;

        // 标题
        const titleEl = el.querySelector('a[href], [class*="title"], [class*="name"]');
        let title = titleEl ? (titleEl.innerText || '').trim() : '';
        if (!title) {
            const lines = text.split('\n').filter(l => l.trim().length > 5);
            title = lines[0] || '';
        }

        // URL
        let productUrl = '';
        if (titleEl && titleEl.href) productUrl = titleEl.href;
        if (!productUrl) {
            const linkEl = el.querySelector('a[href*="item"]');
            if (linkEl) productUrl = linkEl.href;
        }

        // 价格
        let price = null;
        const priceMatch = text.match(/¥\s*([\d.]+)/);
        if (priceMatch) price = parseFloat(priceMatch[1]);

        // 销量
        let sales = null;
        const salesMatch = text.match(/(\d+)\s*件/);
        if (salesMatch) sales = parseInt(salesMatch[1]);

        // 商品ID
        let productId = '';
        const idAttr = el.getAttribute('data-id') || '';
        if (idAttr) productId = idAttr;
        if (!productId && productUrl) {
            const m = productUrl.match(/[?&]id=(\d+)/);
            if (m) productId = m[1];
        }

        return { title, productUrl, price, sales, stock: null, productId };
    }

    return JSON.stringify({ results, debug, strategy: 'fallback' });
})()
"""


class TaobaoProductExtractor(BaseExtractor):
    """淘宝 — 出售中的商品 提取器"""

    platform = "taobao"

    async def extract(self) -> list[dict[str, Any]]:
        """
        从出售中的商品页面提取数据

        Returns:
            [{
                "productId": "123456789",
                "title": "茶卡湖盐 3袋装",
                "productUrl": "https://...",
                "price": 29.90,
                "sales": 1234,
                "stock": 567,
            }, ...]
        """
        raw = await self.client.evaluate(EXTRACT_JS)

        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return []

        results = data.get("results", [])
        return results

    async def extract_with_debug(self) -> dict:
        """提取数据并返回调试信息（包括用了哪种策略）"""
        raw = await self.client.evaluate(EXTRACT_JS)

        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {"results": [], "debug": ["JSON 解析失败"], "strategy": "error"}

        return data
