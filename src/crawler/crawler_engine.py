"""
爬虫引擎 - 核心抓取逻辑
"""

import asyncio
import time
import uuid
from typing import List, Dict, Optional, Callable
from PyQt6.QtWebEngineWidgets import QWebEngineView
# from src.browser.playwright_controller import PlaywrightController
from src.browser.qwebengine_controller import QWebEngineController
from src.crawler.data_extractor import DataExtractor
from src.crawler.data_exporter import DataExporter
from ..database.models import Database, CrawlStrategy, FormConfig


class CrawlerEngine:
    """爬虫引擎"""

    def __init__(self, web_view: Optional[QWebEngineView] = None):
        """初始化爬虫引擎"""
        # 根据是否提供web_view决定使用哪种浏览器控制器
        if web_view:
            self.browser = QWebEngineController(web_view)
        
        self.extractor = DataExtractor()
        self.exporter = DataExporter()
        self.is_running = False
        self.is_paused = False
        
        # 数据库相关初始化
        self.db = Database()
        self.crawl_strategy_model = CrawlStrategy(self.db)
        self.form_config_model = FormConfig(self.db)

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
    
    def start_crawl(
        self,
        start_url: str,
        page_config: Dict,
        strategy: Dict,
        form_data: Optional[Dict] = {},
        page_config_id: Optional[int] = None,
        progress_callback: Optional[Callable] = None,
    ) -> List[Dict]:
        """
        开始基于表单查询的抓取任务（同步版本）
        
        Args:
            start_url: 起始URL
            page_config: 页面配置
            strategy: 抓取策略
            form_data: 表单数据，包含输入字段和查询按钮配置
            page_config_id: 页面配置ID，用于加载表单配置
            progress_callback: 进度回调函数
            
        Returns:
            抓取的数据列表
        """
        self.is_running = True
        self.is_paused = False
        
        all_data = []
        current_page = 1
        max_pages = strategy.get("max_pages", 100)

        try:
            # 点击查询按钮
            # 优先使用表单配置中的查询按钮选择器和JavaScript定位函数
            search_button_selector = form_data.get("search_button_selector", "")
            search_button_js_function = form_data.get("search_button_js_function")
            
            form_config = None
            if page_config_id:
                form_config = self.form_config_model.get_by_page(page_config_id)
                
            if form_config:
                if form_config.get('search_button_selector'):
                    search_button_selector = form_config['search_button_selector']
                if form_config.get('search_button_js_function'):
                    search_button_js_function = form_config['search_button_js_function']
            
            # 先实现硬编码, 故注释这里
            # if search_button_selector:
            #     click_success = self._click_search_button_sync(search_button_selector, search_button_js_function)
            #     if not click_success:
            #         print("无法点击查询按钮")
            #         return all_data
            
            # 等待查询结果加载完成
            loading_selector = form_data.get("loading_selector", ".q-loading")
            # 优先使用表单配置中的加载指示器选择器
            if form_config and form_config.get('loading_indicator_selector'):
                loading_selector = form_config['loading_indicator_selector']
                
            self._wait_for_loading_complete_sync(loading_selector)
            
            # 获取查询结果（支持分页）
            all_data = self._get_all_pages_results_sync(
                page_config, strategy, form_data, progress_callback
            )
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise Exception(f"抓取过程出错: {e}")
        finally:
            self.browser.close()
            self.is_running = False
        
        return all_data
    
    def _fill_form_field_sync(self, selector: str, value: str) -> bool:
        """填充表单字段（同步版本）"""
        try:
            # 先尝试直接填写
            if isinstance(self.browser, QWebEngineController):
                # 使用JavaScript直接设置值并触发事件
                safe_selector = selector.replace("'", "\\'")
                safe_value = value.replace("'", "\\'")
                js_code = "(function() { " \
                         "const element = document.querySelector('" + safe_selector + "'); " \
                         "if (element) { " \
                         "element.value = '" + safe_value + "'; " \
                         "element.dispatchEvent(new Event('input', { bubbles: true })); " \
                         "element.dispatchEvent(new Event('change', { bubbles: true })); " \
                         "return true; " \
                         "}" \
                         "return false; " \
                         "})()"
                
                from PyQt6.QtCore import QEventLoop
                loop = QEventLoop()
                result = [False]
                
                def on_script_result(filled):
                    result[0] = filled
                    loop.quit()
                
                self.browser.page.runJavaScript(js_code, on_script_result)
                loop.exec()
                return result[0]
            return False
        except Exception as e:
            print(f"填充表单字段失败: {e}")
            return False
    
    def _click_search_button_sync(self, selector: str, js_function: Optional[str] = None) -> bool:
        """点击查询按钮（同步版本）- 第五步实现"""
        try:
            print("\n5️⃣ 正在点击查询按钮...")
            
            # 优先使用JavaScript定位函数
            if js_function and js_function.strip():
                print("使用JavaScript定位函数查找查询按钮...")
                
                # 检查浏览器类型并执行JavaScript
                if isinstance(self.browser, QWebEngineController):
                    from PyQt6.QtCore import QEventLoop
                    loop = QEventLoop()
                    result = [False]
                    
                    def on_script_result(script_result):
                        try:
                            # 解析结果
                            if isinstance(script_result, dict) and script_result.get('success'):
                                print(f"✅ JavaScript定位函数成功找到并点击查询按钮")
                                print(f"  策略: {script_result.get('strategy')}")
                                button_info = script_result.get('buttonInfo', {})
                                print(f"  按钮信息: 文本='{button_info.get('text', '').strip()}', 类名='{button_info.get('className', '')}'")
                                result[0] = True
                            else:
                                print(f"❌ JavaScript定位函数未找到查询按钮")
                                if isinstance(script_result, dict):
                                    print(f"  错误信息: {script_result.get('message', '未知错误')}")
                                    print(f"  找到按钮数量: {script_result.get('foundButtons', 0)}")
                                result[0] = False
                        except Exception as e:
                            print(f"处理JavaScript结果时出错: {e}")
                            result[0] = False
                        finally:
                            loop.quit()
                    
                    # 执行JavaScript定位函数
                    self.browser.page.runJavaScript(js_function, on_script_result)
                    loop.exec()
                    
                    if result[0]:
                        # 等待点击后页面响应
                        from PyQt6.QtCore import QTimer
                        loop = QEventLoop()
                        QTimer.singleShot(1000, loop.quit)
                        loop.exec()
                        print("✅ 查询按钮已点击")
                        return True
                    print("JavaScript定位函数执行失败，尝试使用内置策略...")
            
            # 如果没有提供有效的JS函数或执行失败，使用内置的多策略查询按钮定位
            if not js_function or not js_function.strip():
                # 构建高级多策略定位的JavaScript代码
                advanced_js_function = """
                (function() {
                    // XPath 定位函数
                    function findByXPath(xpath) {
                        try {
                            const result = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
                            return result.singleNodeValue;
                        } catch (e) {
                            return null;
                        }
                    }
                    
                    // 多策略精确查找表单区域内的查询按钮
                    const searchButtonStrategies = [
                        // 策略1: 在表单区域内查找包含"查询"文本的按钮
                        "//form//button[.//span[normalize-space(text())='查询']]",
                        
                        // 策略2: 在申请人输入框附近的查询按钮
                        "//div[contains(@class, 'row') and .//div[normalize-space(text())='申请人：']]/following-sibling::div//button[.//span[normalize-space(text())='查询']]",
                        
                        // 策略3: 在查询条件区域内的查询按钮
                        "//div[contains(@class, 'search-condition')]//button[.//span[normalize-space(text())='查询']]",
                        
                        // 策略4: 查找包含查询图标的按钮
                        "//button[contains(@class, 'q-btn') and .//span[normalize-space(text())='查询']]",
                        
                        // 策略5: 在申请人输入框同一行的查询按钮
                        "//div[.//div[normalize-space(text())='申请人：']]//button[.//span[normalize-space(text())='查询']]",
                        
                        // 策略6: 通用查询按钮CSS选择器
                        "button:has(span:contains('查询'))",
                        
                        // 策略7: 简单包含查询文本的按钮
                        "//button[contains(normalize-space(text()), '查询')]",
                        
                        // 策略8: 提交按钮
                        "//input[@type='submit' and contains(@value, '查询')]",
                    ];
                    
                    console.log("🔍 开始查找查询按钮...");
                    
                    for (let i = 0; i < searchButtonStrategies.length; i++) {
                        const strategy = searchButtonStrategies[i];
                        let button = null;
                        
                        try {
                            if (strategy.startsWith('//')) {
                                // XPath 定位
                                button = findByXPath(strategy);
                            } else if (strategy.includes(':has')) {
                                // 特殊CSS选择器处理
                                const buttons = document.querySelectorAll('button');
                                for (let btn of buttons) {
                                    const spans = btn.querySelectorAll('span');
                                    if (Array.from(spans).some(span => span.textContent.includes('查询'))) {
                                        button = btn;
                                        break;
                                    }
                                }
                            } else {
                                // 普通CSS选择器
                                button = document.querySelector(strategy);
                            }
                            
                            if (button && button.offsetParent !== null) { // 确保按钮可见
                                console.log(`✅ 使用策略 ${i+1} 找到查询按钮:`, strategy);
                                console.log('🔍 按钮信息:', {
                                    text: button.textContent,
                                    className: button.className,
                                    tagName: button.tagName,
                                    parentHTML: button.parentElement ? button.parentElement.outerHTML.substring(0, 200) : 'no parent'
                                });
                                
                                // 点击按钮
                                button.click();
                                console.log('✅ 查询按钮已点击');
                                return {
                                    success: true,
                                    strategy: strategy,
                                    buttonInfo: {
                                        text: button.textContent,
                                        className: button.className
                                    }
                                };
                            }
                        } catch (e) {
                            console.log(`❌ 策略 ${i+1} 执行出错:`, e.message);
                        }
                        console.log(`❌ 策略 ${i+1} 未找到可见按钮:`, strategy);
                    }
                    
                    // 如果所有策略都失败，尝试查找所有包含"查询"的按钮并输出调试信息
                    console.log('🔍 备用方案：查找所有包含"查询"的按钮');
                    const allButtons = document.querySelectorAll('button');
                    const queryButtons = Array.from(allButtons).filter(btn => 
                        btn.textContent.includes('查询')
                    );
                    
                    console.log(`📊 找到 ${queryButtons.length} 个包含"查询"的按钮:`);
                    queryButtons.forEach((btn, index) => {
                        console.log(`  按钮 ${index+1}:`, {
                            text: btn.textContent.trim(),
                            className: btn.className,
                            parentText: btn.parentElement ? btn.parentElement.textContent.substring(0, 100) : 'no parent'
                        });
                    });
                    
                    return {
                        success: false,
                        message: '未找到合适的查询按钮',
                        foundButtons: queryButtons.length
                    };
                })()
                """
                
                # 执行高级定位JavaScript
                if isinstance(self.browser, QWebEngineController):
                    from PyQt6.QtCore import QEventLoop
                    loop = QEventLoop()
                    result = [False]
                    
                    def on_script_result(script_result):
                        try:
                            if isinstance(script_result, dict) and script_result.get('success'):
                                print(f"✅ 高级定位策略成功找到并点击查询按钮")
                                print(f"  策略: {script_result.get('strategy')}")
                                button_info = script_result.get('buttonInfo', {})
                                print(f"  按钮信息: 文本='{button_info.get('text', '').strip()}', 类名='{button_info.get('className', '')}'")
                                result[0] = True
                            else:
                                print(f"❌ 高级定位策略未找到查询按钮")
                                if isinstance(script_result, dict):
                                    print(f"  错误信息: {script_result.get('message', '未知错误')}")
                                    print(f"  找到按钮数量: {script_result.get('foundButtons', 0)}")
                                result[0] = False
                        except Exception as e:
                            print(f"处理JavaScript结果时出错: {e}")
                            result[0] = False
                        finally:
                            loop.quit()
                    
                    self.browser.page.runJavaScript(advanced_js_function, on_script_result)
                    loop.exec()
                    
                    if result[0]:
                        # 等待点击后页面响应
                        from PyQt6.QtCore import QTimer
                        loop = QEventLoop()
                        QTimer.singleShot(1000, loop.quit)
                        loop.exec()
                        print("✅ 查询按钮已点击")
                        return True
            
            # 最后的后备策略 - 使用简单选择器
            strategies = [
                selector,  # 使用提供的选择器
                f"button:contains('查询')",  # 包含"查询"文本的按钮
                f"input[type='submit'][value*='查询']",  # 提交按钮值包含"查询"
                f"#search",  # ID为search的元素
                f".search-btn",  # class为search-btn的元素
                f"button[type='submit']"  # 提交按钮
            ]
            
            for strategy in strategies:
                try:
                    # 尝试点击按钮
                    success = self.browser.click_sync(strategy)
                    if success:
                        print(f"✅ 成功点击查询按钮: {strategy}")
                        return True
                except Exception as e:
                    print(f"策略 {strategy} 执行出错: {e}")
            
            print("❌ 所有查询按钮定位策略都失败")
            return False
        except Exception as e:
            print(f"❌ 点击查询按钮失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _wait_for_loading_complete_sync(self, loading_selector: str):
        """等待加载完成（同步版本）- 第六步实现"""
        try:
            print("\n6️⃣ 等待查询结果加载...")
            print(f"⏳ 等待加载组件消失，监控元素: {loading_selector}")
            
            from PyQt6.QtCore import QEventLoop, QTimer
            
            # 最大等待时间
            max_wait_time = 30  # 秒
            check_interval = 500  # 毫秒
            elapsed_time = 0
            
            # 等待加载元素消失或超时
            while elapsed_time < max_wait_time * 1000 and self.is_running:
                # 构建JavaScript代码来检查加载状态
                loading_check_js = """
                (function() {
                    // 检查是否存在加载组件
                    const loadingElements = document.querySelectorAll('%s');
                    const hasLoading = loadingElements.length > 0;
                    
                    if (!hasLoading) {
                        console.log('✅ 加载组件已消失，查询结果加载完成');
                        return true;
                    } else {
                        console.log('⏳ 仍在加载中，找到 ' + loadingElements.length + ' 个加载组件');
                        // 输出加载组件的详细信息用于调试
                        loadingElements.forEach((el, index) => {
                            console.log(`  加载组件 ${index+1}:`, {
                                className: el.className,
                                parentText: el.parentElement ? el.parentElement.textContent.substring(0, 100) : 'no parent',
                                visible: el.offsetParent !== null
                            });
                        });
                        return false;
                    }
                })()
                """ % loading_selector.replace("'", "\\'")
                
                # 执行JavaScript检查加载状态
                loop = QEventLoop()
                loading_complete = [False]
                
                def on_script_result(result):
                    loading_complete[0] = result
                    loop.quit()
                
                if isinstance(self.browser, QWebEngineController):
                    self.browser.page.runJavaScript(loading_check_js, on_script_result)
                    loop.exec()
                else:
                    # 降级到简单的元素检查
                    loading_complete[0] = not self._check_element_exists_sync(loading_selector)
                
                if loading_complete[0]:
                    # 再等待一小段时间确保页面完全加载
                    loop = QEventLoop()
                    QTimer.singleShot(2000, loop.quit)
                    loop.exec()
                    print("✅ 查询结果加载完成")
                    return True
                
                # 等待下一次检查
                loop = QEventLoop()
                QTimer.singleShot(check_interval, loop.quit)
                loop.exec()
                
                elapsed_time += check_interval
            
            print("⚠️ 等待加载组件超时，继续执行...")
            return False
        except Exception as e:
            print(f"❌ 等待加载完成失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _check_element_exists_sync(self, selector: str) -> bool:
        """检查元素是否存在（同步版本）"""
        try:
            safe_selector = selector.replace("'", "\\'")
            js_code = "(function() { " \
                     "const element = document.querySelector('" + safe_selector + "'); " \
                     "return element !== null; " \
                     "})()"
            
            from PyQt6.QtCore import QEventLoop
            loop = QEventLoop()
            result = [False]
            
            def on_script_result(exists):
                result[0] = exists
                loop.quit()
            
            self.browser.page.runJavaScript(js_code, on_script_result)
            loop.exec()
            return result[0]
        except Exception as e:
            print(f"检查元素存在性失败: {e}")
            return False
    
    def _get_all_pages_results_sync(
        self,
        page_config: Dict,
        strategy: Dict,
        form_data: Dict,
        progress_callback: Optional[Callable] = None,
    ) -> List[Dict]:
        """获取所有页面的查询结果（同步版本）- 第七步完整实现"""
        print("\n7️⃣ 正在获取查询结果...")
        print("📄 开始获取所有页面数据...")
        
        all_data = []
        current_page = 1
        max_pages = strategy.get("max_pages", 100)
        result_ids = set()  # 用于去重
        
        # 数据收集统计信息
        pagination_stats = {
            'totalPages': 0,
            'currentPage': 0,
            'totalResults': 0,
            'pagesCollected': 0
        }
        
        # 获取结果ID字段名（用于去重）
        result_id_field = form_data.get("result_id_field", "申请号")
        
        while self.is_running and current_page <= max_pages:
            # 检查暂停
            while self.is_paused:
                from PyQt6.QtCore import QEventLoop, QTimer
                loop = QEventLoop()
                QTimer.singleShot(500, loop.quit)  # 等待500ms
                loop.exec()

            print(f"\n📖 正在获取第 {current_page} 页数据...")
            
            # 获取当前页数据
            page_data = self._get_query_results_sync(page_config)
            
            # 如果是第一页，获取分页信息
            if current_page == 1:
                pagination_info = self._get_pagination_info_sync()
                pagination_stats['totalPages'] = pagination_info.get('totalPages', 1)
                pagination_stats['totalResults'] = pagination_info.get('totalResults', '0')
            
            # 去重并添加到总数据
            new_records_count = 0
            for record in page_data:
                # 使用ID字段去重
                record_id = record.get(result_id_field, str(uuid.uuid4()))
                if record_id not in result_ids:
                    result_ids.add(record_id)
                    record["_page_number"] = current_page
                    all_data.append(record)
                    new_records_count += 1
            
            # 更新统计信息
            pagination_stats['pagesCollected'] = current_page
            pagination_stats['currentPage'] = current_page
            
            print(f"✅ 第 {current_page} 页数据获取成功")
            print(f"  新增数据: {new_records_count} 条")
            
            # 回调进度
            if progress_callback:
                progress_callback(
                    current_page=current_page,
                    total_pages=pagination_stats['totalPages'],
                    records_count=len(all_data),
                    message=f"已获取第 {current_page} 页，新增 {new_records_count} 条数据",
                )
            
            # 检查是否有下一页
            pagination_info = self._get_pagination_info_sync()
            has_next_page = pagination_info.get('hasNextPage', False)
            total_pages = pagination_info.get('totalPages', 1)
            
            print(f"📊 分页信息: 当前页 {current_page}/{total_pages}, 是否有下一页: {has_next_page}")
            
            if not has_next_page or current_page >= total_pages:
                print("🎯 已到达最后一页，分页收集完成")
                break
            
            # 点击下一页
            print("🔄 正在点击下一页...")
            next_result = self._click_next_page_sync()
            
            if not next_result.get('success'):
                print(f"❌ 点击下一页失败: {next_result.get('message', '未知错误')}")
                break
            
            # 等待下一页加载完成
            print("⏳ 等待下一页数据加载...")
            loading_selector = form_data.get("loading_selector", ".q-loading")

            # 设计一个超时等待，超时默认值60秒，使得load_success必须为true
            load_success = False
            timeout = 120
            start_time = time.time()
            while time.time() - start_time <= timeout:
                load_success = self._wait_for_loading_complete_sync(loading_selector)
                if not load_success:
                    print("等待loading加载完成超时, 继续等待...")
                    continue
                else:
                    break
            if not load_success:
                print("❌ 下一页加载失败")
                raise Exception("❌ 下一页加载失败")
            
            # 等待页面稳定
            from PyQt6.QtCore import QEventLoop, QTimer
            loop = QEventLoop()
            QTimer.singleShot(2000, loop.quit)  # 增加等待时间确保页面稳定
            loop.exec()
            
            current_page += 1
        
        # 显示完成统计
        print(f"\n📊 分页收集完成统计:")
        print(f"  总页数: {pagination_stats['totalPages']}")
        print(f"  已收集页数: {pagination_stats['pagesCollected']}")
        print(f"  总结果数: {pagination_stats['totalResults']}")
        print(f"  最终数据条数: {len(all_data)}")
        
        print("🎉 所有页面查询结果获取成功！")
        return all_data
    
    def _get_pagination_info_sync(self) -> Dict:
        """获取分页信息（同步版本）"""
        try:
            # 构建JavaScript代码获取分页信息
            pagination_js = """
            (function() {
                // 获取分页信息
                const paginationInfo = {
                    totalResults: document.querySelector('.total strong') ? document.querySelector('.total strong').textContent : '0',
                    currentPage: 1,
                    totalPages: 1,
                    hasNextPage: false,
                    nextPageButton: null
                };
                
                // 获取分页按钮
                const paginationContainer = document.querySelector('.q-pagination');
                if (paginationContainer) {
                    // 获取当前页码
                    const activeButton = paginationContainer.querySelector('.q-btn--standard');
                    if (activeButton) {
                        const pageText = activeButton.textContent.trim();
                        if (pageText && !isNaN(parseInt(pageText))) {
                            paginationInfo.currentPage = parseInt(pageText);
                        }
                    }
                    
                    // 获取总页数 - 查找最后一个页码按钮
                    const pageButtons = paginationContainer.querySelectorAll('.q-btn:not(.q-btn--disabled)');
                    let lastPage = 1;
                    pageButtons.forEach(btn => {
                        const text = btn.textContent.trim();
                        if (text && !isNaN(parseInt(text))) {
                            const pageNum = parseInt(text);
                            if (pageNum > lastPage) {
                                lastPage = pageNum;
                            }
                        }
                    });
                    paginationInfo.totalPages = lastPage;
                    
                    // 检查是否有下一页按钮
                    const nextButtons = Array.from(paginationContainer.querySelectorAll('.q-btn:not(.q-btn--disabled)'));
                    const nextButton = nextButtons.find(btn => {
                        const icons = btn.querySelectorAll('.material-icons');
                        return Array.from(icons).some(icon => 
                            icon.textContent.includes('keyboard_arrow_right')
                        );
                    });
                    
                    if (nextButton) {
                        paginationInfo.hasNextPage = true;
                        paginationInfo.nextPageButton = nextButton;
                    }
                }
                
                return paginationInfo;
            })()
            """
            
            # 执行JavaScript获取分页信息
            from PyQt6.QtCore import QEventLoop
            loop = QEventLoop()
            result = [{'totalResults': '0', 'currentPage': 1, 'totalPages': 1, 'hasNextPage': False}]
            
            def on_script_result(pagination_info):
                result[0] = pagination_info
                loop.quit()
            
            if isinstance(self.browser, QWebEngineController):
                self.browser.page.runJavaScript(pagination_js, on_script_result)
                loop.exec()
            
            return result[0]
        except Exception as e:
            print(f"获取分页信息失败: {e}")
            return {'totalResults': '0', 'currentPage': 1, 'totalPages': 1, 'hasNextPage': False}
    
    def _click_next_page_sync(self) -> Dict:
        """点击下一页按钮（同步版本）"""
        try:
            # 构建JavaScript代码点击下一页
            next_page_js = """
            (function() {
                // 查找下一页按钮
                const paginationContainer = document.querySelector('.q-pagination');
                if (!paginationContainer) {
                    return { success: false, message: '未找到分页容器' };
                }
                
                // 查找包含右箭头图标的按钮
                const nextButtons = Array.from(paginationContainer.querySelectorAll('.q-btn'));
                const nextButton = nextButtons.find(btn => {
                    const icons = btn.querySelectorAll('.material-icons');
                    return Array.from(icons).some(icon => 
                        icon.textContent.includes('keyboard_arrow_right')
                    );
                });
                
                if (nextButton && !nextButton.disabled) {
                    console.log('✅ 找到下一页按钮，正在点击...');
                    nextButton.click();
                    return { 
                        success: true, 
                        message: '下一页按钮已点击',
                        buttonInfo: {
                            text: nextButton.textContent,
                            className: nextButton.className
                        }
                    };
                } else {
                    console.log('❌ 未找到可用的下一页按钮');
                    return { 
                        success: false, 
                        message: '未找到可用的下一页按钮',
                        nextButtonExists: !!nextButton,
                        nextButtonDisabled: nextButton ? nextButton.disabled : false
                    };
                }
            })()
            """
            
            # 执行JavaScript点击下一页
            from PyQt6.QtCore import QEventLoop
            loop = QEventLoop()
            result = [{'success': False, 'message': '执行失败'}]
            
            def on_script_result(click_result):
                result[0] = click_result
                loop.quit()
            
            if isinstance(self.browser, QWebEngineController):
                self.browser.page.runJavaScript(next_page_js, on_script_result)
                loop.exec()
            
            return result[0]
        except Exception as e:
            print(f"点击下一页失败: {e}")
            return {'success': False, 'message': str(e)}
    
    def _parse_patent_info(self, info_html):
        """解析专利信息HTML"""
        import re
        patent_data = {}
        
        # 如果传入的是纯文本，使用更精确的纯文本解析
        if not info_html.startswith('<'):
            return self._parse_patent_info_text(info_html)
        
        # 对于HTML格式，我们使用更精确的HTML标签结构来提取字段
        # 提取申请号/专利号
        app_number_match = re.search(r'申请号/专利号：\s*</span>\s*<span[^>]*class="hover_active"[^>]*>([^<]*)</span>', info_html)
        if app_number_match:
            patent_data['专利号'] = app_number_match.group(1).strip()
        
        # 提取发明名称
        invention_name_match = re.search(r'发明名称：<span[^>]*>([^<]*)</span>', info_html)
        if invention_name_match:
            patent_data['专利名称'] = invention_name_match.group(1).strip()
        
        # 提取申请人
        applicant_match = re.search(r'申请人：([^<]*)(?=<span|</span>|$)', info_html)
        if applicant_match:
            applicant_text = applicant_match.group(1).strip()
            # 清理可能包含的HTML标签
            applicant_text = re.sub(r'<[^>]+>', '', applicant_text).strip()
            patent_data['申请人'] = applicant_text
        
        # 提取专利类型
        patent_type_match = re.search(r'专利类型：([^<]*)(?=<span|</span>|$)', info_html)
        if patent_type_match:
            patent_type_text = patent_type_match.group(1).strip()
            patent_type_text = re.sub(r'<[^>]+>', '', patent_type_text).strip()
            patent_data['专利类型'] = patent_type_text
        
        # 提取申请日
        application_date_match = re.search(r'申请日：([^<]*)(?=<span|</span>|$)', info_html)
        if application_date_match:
            application_date_text = application_date_match.group(1).strip()
            application_date_text = re.sub(r'<[^>]+>', '', application_date_text).strip()
            patent_data['申请日期'] = application_date_text
        
        # 提取发明专利申请公布号
        publication_number_match = re.search(r'发明专利申请公布号：([^<]*)(?=<span|</span>|$)', info_html)
        if publication_number_match:
            publication_number_text = publication_number_match.group(1).strip()
            publication_number_text = re.sub(r'<[^>]+>', '', publication_number_text).strip()
            patent_data['公布号'] = publication_number_text
        
        # 提取授权公告号
        grant_number_match = re.search(r'授权公告号：([^<]*)(?=<span|</span>|$)', info_html)
        if grant_number_match:
            grant_number_text = grant_number_match.group(1).strip()
            grant_number_text = re.sub(r'<[^>]+>', '', grant_number_text).strip()
            patent_data['授权公告号'] = grant_number_text
        
        # 提取案件状态
        case_status_match = re.search(r'案件状态：([^<]*)(?=<span|</span>|$)', info_html)
        if case_status_match:
            case_status_text = case_status_match.group(1).strip()
            case_status_text = re.sub(r'<[^>]+>', '', case_status_text).strip()
            patent_data['案件状态'] = case_status_text
        
        # 提取授权公告日 - 使用更通用的匹配模式
        grant_date_match = re.search(r'授权公告日：([^<]*)(?=<span|</span>|$)', info_html)
        if grant_date_match:
            grant_date_text = grant_date_match.group(1).strip()
            grant_date_text = re.sub(r'<[^>]+>', '', grant_date_text).strip()
            patent_data['授权公告日'] = grant_date_text
        
        # 提取主分类号 - 使用更通用的匹配模式
        main_class_match = re.search(r'主分类号：([^<]*)(?=<span|</span>|$)', info_html)
        if main_class_match:
            main_class_text = main_class_match.group(1).strip()
            main_class_text = re.sub(r'<[^>]+>', '', main_class_text).strip()
            patent_data['主分类号'] = main_class_text

        # 如果HTML解析失败，回退到纯文本解析
        if not patent_data:
            clean_text = re.sub(r'<[^>]+>', ' ', info_html)
            clean_text = re.sub(r'\s+', ' ', clean_text).strip()
            patent_data = self._parse_patent_info_text(clean_text)
        
        return patent_data
    
    def _parse_patent_info_text(self, info_text):
        """解析纯文本格式的专利信息"""
        import re
        patent_data = {}
        
        # 提取申请号/专利号
        app_number_match = re.search(r'申请号/专利号：\s*([^\s]+)', info_text)
        if app_number_match:
            patent_data['专利号'] = app_number_match.group(1).strip()
        
        # 提取发明名称
        invention_name_match = re.search(r'发明名称：([^申]+?)(?=\s*申请人：|\s*专利类型：|$)', info_text)
        if invention_name_match:
            patent_data['专利名称'] = invention_name_match.group(1).strip()
        
        # 提取申请人
        applicant_match = re.search(r'申请人：([^专]+?)(?=\s*专利类型：|\s*申请日：|$)', info_text)
        if applicant_match:
            patent_data['申请人'] = applicant_match.group(1).strip()
        
        # 提取专利类型
        patent_type_match = re.search(r'专利类型：([^申]+?)(?=\s*申请日：|\s*发明专利申请公布号：|$)', info_text)
        if patent_type_match:
            patent_data['专利类型'] = patent_type_match.group(1).strip()
        
        # 提取申请日
        application_date_match = re.search(r'申请日：\s*([^\s]+)', info_text)
        if application_date_match:
            patent_data['申请日期'] = application_date_match.group(1).strip()
        
        return patent_data
    
    def _extract_table_info(self, result_data):
        """从查询结果中提取table_info结构化数据"""
        import re
        table_info_list = []
        
        # 检查是否有tableInfoData字段
        if 'tableInfoData' in result_data and result_data['tableInfoData']:
            for table_info in result_data['tableInfoData']:
                info_html = table_info.get('html', '')
                patent_data = self._parse_patent_info(info_html)
                patent_data['raw_text'] = table_info.get('text', '')
                # 添加元数据
                patent_data['_source_url'] = result_data.get('url', '')
                patent_data['_page_title'] = result_data.get('pageTitle', '')
                table_info_list.append(patent_data)
        
        # 如果没有新的tableInfoData，尝试从tableContent中提取
        elif 'resultInfo' in result_data and 'tableContent' in result_data['resultInfo']:
            table_content = result_data['resultInfo']['tableContent']
            
            # 使用正则表达式从tableContent中提取table_info块
            table_info_pattern = r'<div[^>]*class="table_info"[^>]*>(.*?)</div>'
            table_info_matches = re.findall(table_info_pattern, table_content, re.DOTALL)
            
            for table_info_html in table_info_matches:
                # 提取纯文本内容
                info_text = re.sub(r'<[^>]+>', ' ', table_info_html)
                info_text = re.sub(r'\s+', ' ', info_text).strip()
                
                patent_data = self._parse_patent_info(table_info_html)
                patent_data['raw_text'] = info_text
                # 添加元数据
                patent_data['_source_url'] = result_data.get('url', '')
                patent_data['_page_title'] = result_data.get('pageTitle', '')
                table_info_list.append(patent_data)
        
        return table_info_list
    
    def _get_query_results_sync(self, page_config: Dict) -> List[Dict]:
        """获取当前页的查询结果（同步版本）"""
        print("\n🔄 正在获取查询结果...")
        
        # 构建JavaScript代码获取查询结果
        js_code = """
            (function() {
                // 获取查询结果信息
                const resultInfo = {
                    totalResults: document.querySelector('.total strong') ? document.querySelector('.total strong').textContent : '0',
                    tableContent: document.querySelector('.tableList') ? document.querySelector('.tableList').innerHTML : '',
                    pageInfo: document.querySelector('.q-pagination') ? document.querySelector('.q-pagination').innerHTML : ''
                };
                
                // 获取所有可见的表格数据
                const tableRows = document.querySelectorAll('.tableList tr, .tableList .row');
                const tableData = Array.from(tableRows).map(row => ({
                    html: row.outerHTML,
                    text: row.textContent.trim()
                }));
                
                // 获取所有table_info数据
                const tableInfoElements = document.querySelectorAll('.table_info');
                const tableInfoData = Array.from(tableInfoElements).map(info => ({
                    html: info.outerHTML,
                    text: info.textContent.trim()
                }));
                
                return {
                    resultInfo: resultInfo,
                    tableData: tableData,
                    tableInfoData: tableInfoData,
                    fullPageHTML: document.documentElement.outerHTML,
                    pageTitle: document.title,
                    url: window.location.href
                };
            })()
        """
        
        # 执行JavaScript获取结果
        try:
            from PyQt6.QtCore import QEventLoop
            loop = QEventLoop()
            result = [None]
            
            def on_script_result(script_result):
                result[0] = script_result
                loop.quit()
            
            # 检查浏览器类型并执行JavaScript
            if isinstance(self.browser, QWebEngineController):
                self.browser.page.runJavaScript(js_code, on_script_result)
                loop.exec()
            else:
                print("❌ 不支持的浏览器类型")
                return []
            
            # 获取JavaScript执行结果
            result_data = result[0]
            if not result_data:
                print("❌ JavaScript执行失败或返回空结果")
                return []
            
            # 显示JavaScript执行结果摘要
            print("\n📊 JavaScript提取结果摘要:")
            if 'resultInfo' in result_data:
                print(f"   - 查询结果数量: {result_data['resultInfo'].get('totalResults', '0')}")
            if 'tableData' in result_data:
                print(f"   - 表格数据行数: {len(result_data['tableData'])}")
            if 'tableInfoData' in result_data:
                print(f"   - 详情信息数: {len(result_data['tableInfoData'])}")
            # 提取结构化数据
            table_info_list = self._extract_table_info(result_data)
            
            # 打印提取的结构化数据信息
            print(f"\n📋 结构化数据提取结果:")
            print(f"   - 成功提取专利记录数: {len(table_info_list)}")
            
            if table_info_list:
                # 显示前几条数据预览
                for i, record in enumerate(table_info_list[:3]):
                    patent_number = record.get('专利号', 'N/A')
                    patent_name = record.get('专利名称', 'N/A')
                    print(f"   - 记录 {i+1}: {patent_number} - {patent_name[:30]}...")

            return table_info_list
            
        except Exception as e:          
            import traceback
            traceback.print_exc()
            raise(f"❌ 获取查询结果失败: {str(e)}")
