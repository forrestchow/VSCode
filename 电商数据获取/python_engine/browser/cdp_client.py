"""
CDP 协议封装 — 基于 Playwright 的 connect_over_cdp

连接到一个已运行的 Chrome 浏览器（察尔汗），通过 CDP 协议
执行 JS、获取 DOM、控制导航等。
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

    async def connect(self) -> "CDPClient":
        """连接到已运行在 debug port 的 Chrome"""
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.connect_over_cdp(self.cdp_url)

        # 使用默认 context 和第一个 page（或创建新 page）
        contexts = self._browser.contexts
        if contexts:
            self._context = contexts[0]
            pages = self._context.pages
            self._page = pages[0] if pages else await self._context.new_page()
        else:
            self._context = await self._browser.new_context()
            self._page = await self._context.new_page()

        # 隐藏 webdriver 特征（确保安全）
        await self._page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)

        return self

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
