"""
页面导航辅助 — 封装各电商平台卖家中心的常用导航操作
"""
import asyncio
from urllib.parse import urlparse


class PageNavigator:
    """电商卖家中心页面导航器"""

    def __init__(self, client):
        self.client = client  # CDPClient 实例

    # ─── 淘宝卖家中心（千牛）─────────────────────

    async def goto_taobao_seller_center(self):
        """导航到淘宝卖家中心首页"""
        await self.client.navigate("https://myseller.taobao.com/home.htm")
        await self._wait_stable()

    async def goto_taobao_products_on_sale(self, page: int = 1):
        """导航到淘宝 — 出售中的商品"""
        url = f"https://myseller.taobao.com/sale/item.htm?page={page}"
        await self.client.navigate(url)
        await self._wait_stable()

    async def goto_taobao_orders(self, page: int = 1):
        """导航到淘宝 — 已卖出的宝贝"""
        url = f"https://myseller.taobao.com/sale/order.htm?page={page}"
        await self.client.navigate(url)
        await self._wait_stable()

    # ─── 拼多多商家后台 ─────────────────────────

    async def goto_pdd_goods_list(self):
        """导航到拼多多 — 商品管理"""
        await self.client.navigate("https://mms.pinduoduo.com/goods/list")
        await self._wait_stable()

    async def goto_pdd_orders(self):
        """导航到拼多多 — 订单管理"""
        await self.client.navigate("https://mms.pinduoduo.com/order/list")
        await self._wait_stable()

    # ─── 京东商家后台 ───────────────────────────

    async def goto_jd_goods(self):
        """导航到京东 — 商品管理"""
        await self.client.navigate("https://shop.jd.com/goods/list")
        await self._wait_stable()

    # ─── 通用 ───────────────────────────────────

    async def detect_platform(self) -> str:
        """根据当前 URL 检测所在平台"""
        url = await self.client.evaluate("location.href")
        domain = urlparse(url).netloc

        if "taobao.com" in domain or "tmall.com" in domain:
            return "taobao"
        elif "pinduoduo.com" in domain or "yangkeduo.com" in domain:
            return "pdd"
        elif "jd.com" in domain:
            return "jd"
        elif "jinritemai.com" in domain or "douyin.com" in domain:
            return "douyin"
        return "unknown"

    async def _wait_stable(self, timeout: int = 10):
        """等待页面基本加载完成"""
        try:
            await self.client.wait_for_load("networkidle")
        except Exception:
            # networkidle 可能超时，降级为固定等待
            await asyncio.sleep(3)
