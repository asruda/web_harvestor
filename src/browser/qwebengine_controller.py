"""
QWebEngineView浏览器控制器
"""

import asyncio
from typing import Optional, List, Dict, Callable
from PyQt6.QtCore import QUrl, pyqtSignal, QObject, QEventLoop
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile


class QWebEngineController(QObject):
    """QWebEngineView浏览器控制器"""

    page_loaded = pyqtSignal(bool)
    element_found = pyqtSignal(bool)

    def __init__(self, web_view: QWebEngineView):
        """初始化控制器"""
        super().__init__()
        self.web_view = web_view
        self.page = web_view.page()
        self.page.loadFinished.connect(self._on_page_loaded)
        self._current_url = ""
        self._load_finished = False
        self._element_found = False

    def _on_page_loaded(self, success: bool):
        """页面加载完成回调"""
        self._load_finished = success
        self._current_url = self.page.url().toString()
        self.page_loaded.emit(success)

    async def start(self):
        """启动浏览器（异步版本）"""
        # QWebEngineView已经由UI创建，这里只做初始化工作
        self._load_finished = False
        return True
    
    def start_sync(self):
        """启动浏览器（同步版本）"""
        # QWebEngineView已经由UI创建，这里只做初始化工作
        self._load_finished = False
        return True

    def close(self):
        """关闭浏览器（同步版本）"""
        # 不需要特殊关闭操作，由UI管理
        return True

    async def goto(self, url: str, wait_until: str = "domcontentloaded") -> bool:
        """导航到指定URL（异步版本）"""
        try:
            self._load_finished = False
            self.web_view.setUrl(QUrl(url))
            
            # 等待页面加载完成
            loop = asyncio.get_event_loop()
            future = loop.create_future()
            
            def on_loaded(success):
                if not future.done():
                    future.set_result(success)
            
            self.page.loadFinished.connect(on_loaded)
            result = await future
            self.page.loadFinished.disconnect(on_loaded)
            return result
        except Exception as e:
            print(f"页面导航失败: {e}")
            return False

    def goto_sync(self, url: str) -> bool:
        """导航到指定URL（同步版本）"""
        try:
            self._load_finished = False
            self.web_view.setUrl(QUrl(url))
            
            # 使用QEventLoop等待页面加载完成
            from PyQt6.QtCore import QEventLoop
            loop = QEventLoop()
            
            def on_loaded(success):
                loop.quit()
            
            self.page.loadFinished.connect(on_loaded)
            loop.exec()
            self.page.loadFinished.disconnect(on_loaded)
            return self._load_finished
        except Exception as e:
            print(f"页面导航失败(sync): {e}")
            return False

    def get_content_sync(self) -> str:
        """获取页面HTML内容（同步版本）"""
        try:
            from PyQt6.QtCore import QEventLoop
            loop = QEventLoop()
            result = [""]
            
            def on_script_result(html):
                result[0] = html
                loop.quit()
            
            self.page.runJavaScript("document.documentElement.outerHTML", on_script_result)
            loop.exec()
            return result[0]
        except Exception as e:
            print(f"获取页面内容失败(sync): {e}")
            return ""

    def get_current_url_sync(self) -> str:
        """获取当前URL（同步版本）"""
        return self.page.url().toString()

    def click_sync(self, selector: str) -> bool:
        """点击元素（同步版本）"""
        try:
            # 先处理选择器中的引号
            safe_selector = selector.replace("'", "\\'")
            # 使用原始字符串格式，避免转义问题
            js_code = "(function() { " \
                     "const element = document.querySelector('" + safe_selector + "'); " \
                     "if (element) { " \
                     "element.click(); " \
                     "return true; " \
                     "}" \
                     "return false; " \
                     "})()"
            
            from PyQt6.QtCore import QEventLoop
            loop = QEventLoop()
            result = [False]
            
            def on_script_result(clicked):
                result[0] = clicked
                loop.quit()
            
            self.page.runJavaScript(js_code, on_script_result)
            loop.exec()
            return result[0]
        except Exception as e:
            print(f"点击元素失败(sync): {e}")
            return False

    def wait_for_navigation_sync(self, timeout: int = 30000):
        """等待页面导航完成（同步版本）"""
        try:
            # 重置加载状态
            self._load_finished = False
            
            # 使用QEventLoop等待页面加载完成
            from PyQt6.QtCore import QEventLoop, QTimer
            loop = QEventLoop()
            
            # 设置超时
            if timeout > 0:
                QTimer.singleShot(timeout, loop.quit)
            
            def on_loaded(success):
                self._load_finished = success
                loop.quit()
            
            self.page.loadFinished.connect(on_loaded)
            loop.exec()
            self.page.loadFinished.disconnect(on_loaded)
            return self._load_finished
        except Exception as e:
            print(f"等待导航失败(sync): {e}")
            return False

    # 保留异步方法以保持兼容性
    async def wait_for_selector(self, selector: str, timeout: int = 10000) -> bool:
        """等待元素出现"""
        try:
            self._element_found = False
            
            # 使用JavaScript检查元素是否存在
            safe_selector = selector.replace("'", "\\'")
            js_code = "(function() { " \
                     "const element = document.querySelector('" + safe_selector + "'); " \
                     "return element !== null; " \
                     "})()"
            
            loop = asyncio.get_event_loop()
            future = loop.create_future()
            
            def on_script_result(result):
                if not future.done():
                    future.set_result(result)
            
            self.page.runJavaScript(js_code, on_script_result)
            result = await future
            
            if result:
                self._element_found = True
                self.element_found.emit(True)
            return result
        except Exception as e:
            print(f"等待元素失败: {e}")
            return False

    async def click(self, selector: str) -> bool:
        """点击元素"""
        return self.click_sync(selector)

    async def fill(self, selector: str, text: str) -> bool:
        """填充文本"""
        try:
            # 先处理选择器和文本中的引号
            safe_selector = selector.replace("'", "\\'")
            safe_text = text.replace("'", "\\'")
            js_code = "(function() { " \
                     "const element = document.querySelector('" + safe_selector + "'); " \
                     "if (element) { " \
                     "element.value = '" + safe_text + "'; " \
                     "element.dispatchEvent(new Event('input', { bubbles: true })); " \
                     "element.dispatchEvent(new Event('change', { bubbles: true })); " \
                     "return true; " \
                     "}" \
                     "return false; " \
                     "})()"
            
            loop = asyncio.get_event_loop()
            future = loop.create_future()
            
            def on_script_result(result):
                if not future.done():
                    future.set_result(result)
            
            self.page.runJavaScript(js_code, on_script_result)
            return await future
        except Exception as e:
            print(f"填充文本失败: {e}")
            return False

    async def get_content(self) -> str:
        """获取页面HTML内容"""
        return self.get_content_sync()

    async def get_cookies(self) -> List[Dict]:
        """获取当前Cookie"""
        try:
            js_code = """
            (function() {
                const cookies = document.cookie.split(';');
                const result = [];
                cookies.forEach(cookie => {
                    const parts = cookie.split('=');
                    result.push({
                        name: parts[0].trim(),
                        value: parts.slice(1).join('=').trim()
                    });
                });
                return result;
            })()
            """
            
            loop = asyncio.get_event_loop()
            future = loop.create_future()
            
            def on_script_result(result):
                if not future.done():
                    future.set_result(result)
            
            self.page.runJavaScript(js_code, on_script_result)
            return await future
        except Exception as e:
            print(f"获取Cookie失败: {e}")
            return []

    async def set_cookies(self, cookies: List[Dict]):
        """设置Cookie"""
        try:
            for cookie in cookies:
                name = cookie.get('name', '')
                value = cookie.get('value', '')
                domain = cookie.get('domain', '')
                path = cookie.get('path', '/')
                
                js_code = f"""
                document.cookie = "{name}={value}; path={path}; domain={domain}";
                """
                
                loop = asyncio.get_event_loop()
                future = loop.create_future()
                
                def on_script_result(result):
                    if not future.done():
                        future.set_result(result)
                
                self.page.runJavaScript(js_code, on_script_result)
                await future
        except Exception as e:
            print(f"设置Cookie失败: {e}")

    async def clear_cookies(self):
        """清除Cookie"""
        try:
            profile = self.page.profile()
            profile.clearAllCookies()
        except Exception as e:
            print(f"清除Cookie失败: {e}")

    async def screenshot(self, path: str) -> bool:
        """截图"""
        try:
            pixmap = self.web_view.grab()
            return pixmap.save(path)
        except Exception as e:
            print(f"截图失败: {e}")
            return False

    async def evaluate(self, script: str):
        """执行JavaScript"""
        try:
            loop = asyncio.get_event_loop()
            future = loop.create_future()
            
            def on_script_result(result):
                if not future.done():
                    future.set_result(result)
            
            self.page.runJavaScript(script, on_script_result)
            return await future
        except Exception as e:
            print(f"执行JavaScript失败: {e}")
            return None

    async def get_current_url(self) -> str:
        """获取当前URL"""
        return self.get_current_url_sync()

    async def wait_for_navigation(self, timeout: int = 30000):
        """等待页面导航完成"""
        return self.wait_for_navigation_sync(timeout)

    async def scroll_to_bottom(self):
        """滚动到页面底部"""
        try:
            js_code = "window.scrollTo(0, document.body.scrollHeight);"
            
            loop = asyncio.get_event_loop()
            future = loop.create_future()
            
            def on_script_result(result):
                if not future.done():
                    future.set_result(result)
            
            self.page.runJavaScript(js_code, on_script_result)
            await future
            await asyncio.sleep(1)  # 等待内容加载
        except Exception as e:
            print(f"滚动失败: {e}")