"""
Playwright浏览器控制器
"""

import asyncio
from typing import Optional, List, Dict, Callable
from playwright.async_api import async_playwright, Browser, Page, BrowserContext


class PlaywrightController:
    """Playwright浏览器控制器"""

    def __init__(self, headless: bool = False):
        """初始化控制器"""
        self.headless = headless
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    async def start(self):
        """启动浏览器"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=self.headless)
        self.context = await self.browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        self.page = await self.context.new_page()

    async def close(self):
        """关闭浏览器"""
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def goto(self, url: str, wait_until: str = "domcontentloaded") -> bool:
        """导航到指定URL"""
        try:
            if not self.page:
                await self.start()
            await self.page.goto(url, wait_until=wait_until, timeout=30000)
            return True
        except Exception as e:
            print(f"页面导航失败: {e}")
            return False

    async def wait_for_selector(self, selector: str, timeout: int = 10000) -> bool:
        """等待元素出现"""
        try:
            await self.page.wait_for_selector(selector, timeout=timeout)
            return True
        except Exception:
            return False

    async def click(self, selector: str) -> bool:
        """点击元素"""
        try:
            await self.page.click(selector)
            return True
        except Exception as e:
            print(f"点击元素失败: {e}")
            return False

    async def fill(self, selector: str, text: str) -> bool:
        """填充文本"""
        try:
            await self.page.fill(selector, text)
            return True
        except Exception as e:
            print(f"填充文本失败: {e}")
            return False

    async def get_content(self) -> str:
        """获取页面HTML内容"""
        if not self.page:
            return ""
        return await self.page.content()

    async def get_cookies(self) -> List[Dict]:
        """获取当前Cookie"""
        if not self.context:
            return []
        return await self.context.cookies()

    async def set_cookies(self, cookies: List[Dict]):
        """设置Cookie"""
        if self.context:
            await self.context.add_cookies(cookies)

    async def clear_cookies(self):
        """清除Cookie"""
        if self.context:
            await self.context.clear_cookies()

    async def screenshot(self, path: str) -> bool:
        """截图"""
        try:
            if self.page:
                await self.page.screenshot(path=path)
                return True
            return False
        except Exception as e:
            print(f"截图失败: {e}")
            return False

    async def evaluate(self, script: str):
        """执行JavaScript"""
        if self.page:
            return await self.page.evaluate(script)
        return None

    async def get_current_url(self) -> str:
        """获取当前URL"""
        if self.page:
            return self.page.url
        return ""

    async def wait_for_navigation(self, timeout: int = 30000):
        """等待页面导航完成"""
        if self.page:
            try:
                await self.page.wait_for_load_state("domcontentloaded", timeout=timeout)
            except Exception as e:
                print(f"等待导航失败: {e}")

    async def scroll_to_bottom(self):
        """滚动到页面底部"""
        if self.page:
            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1)  # 等待内容加载
