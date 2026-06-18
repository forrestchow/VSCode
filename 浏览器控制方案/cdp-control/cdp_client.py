"""
CDP 客户端 — 独立版

通过 Playwright 的 connect_over_cdp 连接到一个已运行的 Chrome 浏览器
（带 --remote-debugging-port=9222 启动的 Debug 模式），执行 JS、获取 DOM、控制导航等。

用法:
    from cdp_client import CDPClient
    client = CDPClient(port=9222)
    await client.connect()
    title = await client.evaluate("document.title")
    await client.close()

依赖:
    pip install playwright
    # 不需要 playwright install chromium
"""
import asyncio
import json
from typing import Any
from playwright.async_api import async_playwright, Browser, Page, BrowserContext


class CDPClient:
    """Chrome DevTools Protocol 客户端"""

    def __init__(self, port: int = 9222):
        self.port = port
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    @property
    def cdp_url(self) -> str:
        return f"http://localhost:{self.port}"

    @property
    def page(self) -> Page:
        if not self._page:
            raise RuntimeError("未连接。请先调用 connect()")
        return self._page

    async def connect(self, url_pattern: str | None = None) -> "CDPClient":
        """连接到已运行在 debug port 的 Chrome

        Args:
            url_pattern: 可选，匹配 URL 中包含该字符串的 page（不传则连激活标签页）
        """
        import urllib.request
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.connect_over_cdp(self.cdp_url)

        # 通过 /json 端点获取激活标签页的 URL（第一个 type:page）
        active_url = None
        try:
            resp = urllib.request.urlopen(f"http://localhost:{self.port}/json")
            targets = json.loads(resp.read().decode())
            for t in targets:
                if t.get('type') == 'page':
                    active_url = t.get('url', '')
                    break
        except Exception:
            pass

        contexts = self._browser.contexts
        if contexts:
            self._context = contexts[0]
            pages = self._context.pages
            target_url = url_pattern or active_url
            if target_url:
                for p in pages:
                    if target_url in (p.url or ''):
                        self._page = p
                        break
            if not self._page:
                self._page = pages[0] if pages else await self._context.new_page()
        else:
            self._context = await self._browser.new_context()
            self._page = await self._context.new_page()

        await self._page.bring_to_front()

        # 隐藏 webdriver 特征
        await self._page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)

        return self

    @property
    def pages(self):
        """返回所有 page 列表"""
        if not self._context:
            return []
        return self._context.pages

    async def use_page(self, page):
        """切换到指定 page"""
        self._page = page
        await page.bring_to_front()

    async def evaluate(self, js: str, *args) -> Any:
        """在页面中执行 JavaScript 并返回结果"""
        return await self._page.evaluate(js, *args)

    async def get_html(self, selector: str | None = None) -> str:
        """获取页面 HTML"""
        if selector:
            return await self.evaluate(
                "(sel) => document.querySelector(sel)?.outerHTML || ''",
                selector
            )
        return await self.evaluate("() => document.documentElement.outerHTML")

    async def get_text(self, selector: str) -> str:
        """获取元素文本"""
        return await self.evaluate(
            "(sel) => document.querySelector(sel)?.innerText || ''",
            selector
        )

    async def navigate(self, url: str, wait_until: str = "domcontentloaded"):
        """导航到 URL"""
        await self._page.goto(url, wait_until=wait_until)

    async def wait_for_selector(self, selector: str, timeout: int = 15000):
        """等待元素出现"""
        await self._page.wait_for_selector(selector, timeout=timeout)

    async def wait_for_load(self, state: str = "networkidle"):
        """等待页面加载状态"""
        await self._page.wait_for_load_state(state)

    async def click(self, selector: str):
        """点击元素"""
        await self._page.click(selector)

    async def type_text(self, selector: str, text: str):
        """在输入框键入文字"""
        await self._page.fill(selector, text)

    async def screenshot(self, path: str):
        """截屏"""
        await self._page.screenshot(path=path)

    async def close(self):
        """断开 CDP 连接（不关闭浏览器）"""
        if self._playwright:
            await self._playwright.stop()
        self._browser = None
        self._page = None
        self._context = None
        self._playwright = None

    def is_connected(self) -> bool:
        return self._browser is not None and self._browser.is_connected()


# ─── CLI 测试 ───
if __name__ == "__main__":
    async def main():
        print("=== CDP Client 测试 ===")
        client = CDPClient(port=9222)
        try:
            await client.connect()
            print(f"[OK] 已连接到 Chrome")
            title = await client.evaluate("document.title")
            url = await client.evaluate("location.href")
            print(f"  Title: {title}")
            print(f"  URL: {url}")
        except Exception as e:
            print(f"[FAIL] 连接失败: {e}")
            print("请确保 Chrome 已以 Debug 模式启动：")
            print('  --remote-debugging-port=9222 --user-data-dir="<非默认路径>"')
        finally:
            await client.close()

    asyncio.run(main())
