"""
爬虫引擎 - 核心抓取逻辑
"""

import asyncio
import uuid
from typing import List, Dict, Optional, Callable
from PyQt6.QtWebEngineWidgets import QWebEngineView
from src.browser.playwright_controller import PlaywrightController
from src.browser.qwebengine_controller import QWebEngineController
from src.crawler.data_extractor import DataExtractor
from src.crawler.data_exporter import DataExporter


class CrawlerEngine:
    """爬虫引擎"""

    def __init__(self, web_view: Optional[QWebEngineView] = None):
        """初始化爬虫引擎"""
        # 根据是否提供web_view决定使用哪种浏览器控制器
        if web_view:
            self.browser = QWebEngineController(web_view)
        else:
            # 保留对Playwright的兼容，但优先使用QWebEngineView
            self.browser = PlaywrightController(headless=False)
        
        self.extractor = DataExtractor()
        self.exporter = DataExporter()
        self.is_running = False
        self.is_paused = False

    def start_crawl(
        self,
        start_url: str,
        page_config: Dict,
        strategy: Dict,
        progress_callback: Optional[Callable] = None,
    ) -> List[Dict]:
        """
        开始抓取任务（同步版本）
        
        Args:
            start_url: 起始URL
            page_config: 页面配置
            strategy: 抓取策略
            progress_callback: 进度回调函数
            
        Returns:
            抓取的数据列表
        """
        self.is_running = True
        self.is_paused = False
        
        all_data = []
        current_page = 1
        max_pages = strategy.get("max_pages", 100)
        visited_urls = set()
        
        try:
            # 启动浏览器
            if isinstance(self.browser, QWebEngineController):
                # 使用同步方式启动浏览器
                from PyQt6.QtCore import QEventLoop
                loop = QEventLoop()
                self.browser.start_sync()
            else:
                self.browser.start()
            
            # 导航到起始页
            success = self.browser.goto_sync(start_url)
            if not success:
                print("页面导航失败")
                return all_data
            
            # 使用QEventLoop处理等待
            from PyQt6.QtCore import QEventLoop, QTimer
            loop = QEventLoop()
            QTimer.singleShot(2000, loop.quit)  # 等待2秒
            loop.exec()
            
            while self.is_running and current_page <= max_pages:
                # 检查暂停
                while self.is_paused:
                    loop = QEventLoop()
                    QTimer.singleShot(500, loop.quit)  # 等待500ms
                    loop.exec()
                
                # 获取当前页面内容
                html = self.browser.get_content_sync()
                current_url = self.browser.get_current_url_sync()
                
                # 提取表格数据
                table_selector = page_config.get("table_selector", "")
                field_mappings = page_config.get("field_mappings", {})
                
                page_data = self.extractor.extract_table_data(
                    html, table_selector, field_mappings
                )
                
                # 记录数据来源URL
                for record in page_data:
                    record["_source_url"] = current_url
                    record["_page_number"] = current_page
                
                all_data.extend(page_data)
                
                # 回调进度
                if progress_callback:
                    progress_callback(
                        current_page=current_page,
                        total_pages=max_pages,
                        records_count=len(all_data),
                        message=f"已抓取第 {current_page} 页，共 {len(page_data)} 条数据",
                    )
                
                # 检查是否有下一页
                has_next = self._check_and_navigate_next_page_sync(strategy)
                if not has_next:
                    break
                
                current_page += 1
                # 控制抓取速度
                loop = QEventLoop()
                QTimer.singleShot(1000, loop.quit)
                loop.exec()
            
            # 处理链接跟踪（简化版）
            if strategy.get("enable_link_tracking"):
                link_data = self._crawl_links_sync(
                    all_data, page_config, strategy, progress_callback
                )
                all_data.extend(link_data)
            
        except Exception as e:
            print(f"抓取过程出错: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.browser.close()
            self.is_running = False
        
        return all_data

    def _check_and_navigate_next_page_sync(self, strategy: Dict) -> bool:
        """检查并导航到下一页（同步版本）"""
        pagination_type = strategy.get("pagination_type", "button")
        pagination_params = strategy.get("pagination_params", {})
        
        if pagination_type == "button":
            # 按钮点击翻页
            next_button_selector = pagination_params.get("next_button_selector", ".next-page")
            
            # 检查按钮是否存在且可点击
            html = self.browser.get_content_sync()
            if not self.extractor.check_element_exists(html, next_button_selector):
                return False
            
            # 点击下一页按钮
            success = self.browser.click_sync(next_button_selector)
            if success:
                # 等待导航完成
                self.browser.wait_for_navigation_sync()
                # 等待页面加载
                from PyQt6.QtCore import QEventLoop, QTimer
                loop = QEventLoop()
                QTimer.singleShot(1000, loop.quit)
                loop.exec()
            return success
        
        elif pagination_type == "url":
            # URL参数翻页 - 暂不实现
            return False
        
        return False

    def _crawl_links_sync(
        self,
        main_data: List[Dict],
        page_config: Dict,
        strategy: Dict,
        progress_callback: Optional[Callable] = None,
    ) -> List[Dict]:
        """抓取链接页面数据（同步版本）"""
        link_data = []
        
        # 从主数据中提取链接
        links = []
        for record in main_data:
            # 查找包含URL的字段
            for key, value in record.items():
                if "url" in key.lower() and value:
                    links.append(value)
        
        # 访问链接
        for i, link in enumerate(links[:10]):  # 限制数量以加快速度
            if not self.is_running:
                break
            
            try:
                self.browser.goto_sync(link)
                
                # 等待页面加载
                from PyQt6.QtCore import QEventLoop, QTimer
                loop = QEventLoop()
                QTimer.singleShot(1000, loop.quit)
                loop.exec()
                
                html = self.browser.get_content_sync()
                
                # 提取子页面数据
                sub_data = self.extractor.extract_table_data(
                    html,
                    page_config.get("table_selector", ""),
                    page_config.get("field_mappings", {}),
                )
                
                for record in sub_data:
                    record["_source_url"] = link
                    record["_link_depth"] = 1
                
                link_data.extend(sub_data)
                
                if progress_callback:
                    progress_callback(
                        current_page=i + 1,
                        total_pages=len(links),
                        records_count=len(link_data),
                        message=f"正在抓取链接 {i+1}/{len(links)}",
                    )
            except Exception as e:
                print(f"抓取链接失败 {link}: {e}")
                continue
        
        return link_data

    def pause(self):
        """暂停抓取"""
        self.is_paused = True

    def resume(self):
        """恢复抓取"""
        self.is_paused = False

    def stop(self):
        """停止抓取"""
        self.is_running = False
