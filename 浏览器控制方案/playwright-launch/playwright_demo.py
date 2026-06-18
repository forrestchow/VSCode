"""
Playwright Launch 模式 — 通用示例

用法:
    python playwright_demo.py        # 启动浏览器，打开百度，提取信息
    python playwright_demo.py <url>  # 启动浏览器，打开指定 URL

依赖:
    pip install playwright
    # 浏览器已随项目打包在 ms-playwright/ 下，无需 playwright install chromium
    # Profile 已随项目打包在 chrome_profile_full/ 下（含书签/插件/密码/登录态）
"""
import os
import sys
from pathlib import Path

# ★ 让 Playwright 使用项目内的 Chromium，而非全局安装的
os.environ.setdefault(
    "PLAYWRIGHT_BROWSERS_PATH",
    str(Path(__file__).parent / "ms-playwright")
)

import asyncio
from playwright.async_api import async_playwright

# Profile 目录 — 从 Chrome 复制过来的精简版（含书签/插件/密码/登录态）
# 和 cdp-control/chrome_profile_full 是同一来源、各自独立的副本
USER_DATA_DIR = str(Path(__file__).parent / "chrome_profile_full")
PROFILE_DIRECTORY = "Profile 2"  # 使用察尔汗 Profile


async def main():
    url = sys.argv[1] if len(sys.argv) > 1 else "https://www.baidu.com"

    print("=" * 50)
    print("  Playwright Launch 模式演示")
    print(f"  Profile: {USER_DATA_DIR}")
    print(f"  使用: {PROFILE_DIRECTORY}")
    print(f"  URL: {url}")
    print("=" * 50)

    async with async_playwright() as pw:
        # ─── 启动独立 Chromium（复用 Chrome Profile） ───
        print("\n[1] 启动 Playwright Chromium + 复用 Chrome Profile ...")
        context = await pw.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            headless=False,
            args=[
                f"--profile-directory={PROFILE_DIRECTORY}",
                "--no-first-run",
                "--no-default-browser-check",
            ],
            no_viewport=True,
        )
        page = context.pages[0] if context.pages else await context.new_page()

        # ─── 导航 ───
        print(f"[2] 导航到 {url} ...")
        await page.goto(url, wait_until="domcontentloaded")
        print(f"  标题: {await page.title()}")

        # ─── 提取信息 ───
        print("\n[3] 提取页面信息 ...")
        stats = await page.evaluate("""() => ({
            title: document.title,
            links: document.querySelectorAll('a').length,
            images: document.querySelectorAll('img').length,
            inputs: document.querySelectorAll('input').length,
            scripts: document.querySelectorAll('script').length,
        })""")
        for k, v in stats.items():
            print(f"  {k}: {v}")

        # ─── 交互演示 ───
        print("\n[4] 交互演示 ...")
        inputs = await page.evaluate("""() => {
            return Array.from(document.querySelectorAll('input')).map((el, i) => ({
                index: i,
                id: el.id,
                name: el.name,
                type: el.type,
                placeholder: el.placeholder,
            }));
        }""")
        for inp in inputs:
            print(f"  input[{inp['index']}] id={inp['id'] or '-'} "
                  f"type={inp['type']} placeholder={inp['placeholder'][:30] if inp['placeholder'] else '-'}")

        search_input = None
        for inp in inputs:
            if inp["type"] == "text" and inp["id"]:
                search_input = inp
                break

        if search_input:
            print(f"\n  尝试在 #{search_input['id']} 中输入 'hello world' ...")
            await page.fill(f"#{search_input['id']}", "hello world")
            await asyncio.sleep(1)

        # ─── 截图 ───
        screenshot_path = Path(__file__).parent / "screenshot.png"
        await page.screenshot(path=str(screenshot_path))
        print(f"\n[5] 截图保存: {screenshot_path}")

        print("\n浏览器保持打开 10 秒，可以手动操作 ...")
        await asyncio.sleep(10)

        await context.close()
        print("浏览器已关闭")


if __name__ == "__main__":
    asyncio.run(main())
