"""
数据提取器基类

所有平台的提取器都继承此基类，统一接口：
  - extract() → list[dict]
  - snapshot() → str (HTML)
"""
from abc import ABC, abstractmethod
from typing import Any


class BaseExtractor(ABC):
    """平台数据提取器基类"""

    platform: str = "unknown"

    def __init__(self, client):
        """
        Args:
            client: CDPClient 实例
        """
        self.client = client

    @abstractmethod
    async def extract(self) -> list[dict[str, Any]]:
        """
        从当前页面提取数据

        Returns:
            提取到的数据列表，每条记录是一个 dict
        """
        ...

    async def snapshot(self, selector: str | None = None) -> str:
        """
        获取当前页面的 HTML 快照（开发/调试用）

        Args:
            selector: CSS 选择器，不传则获取整个页面

        Returns:
            HTML 字符串
        """
        return await self.client.get_html(selector)

    async def get_page_url(self) -> str:
        """获取当前页面 URL"""
        return await self.client.evaluate("location.href")

    async def get_page_title(self) -> str:
        """获取当前页面标题"""
        return await self.client.evaluate("document.title")
