import asyncio
import os
import json
import re
import csv
from playwright.async_api import async_playwright

# 可选依赖 - pandas 用于 Excel 导出
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

class PlaywrightFormCrawler:
    """
    基于 Playwright 的表单操作爬虫类
    """
    
    def __init__(self, login_url: str, target_url: str, user_data_dir: str = "./my_browser_session"):
        self.login_url = login_url
        self.target_url = target_url
        self.user_data_dir = user_data_dir
        
        # 确保会话目录存在
        os.makedirs(self.user_data_dir, exist_ok=True)
    
    async def crawl_with_form_operation(self, applicant_name: str = "青岛迈金智能科技股份有限公司"):
        """
        执行手动登录后的表单操作流程
        自动填写申请人信息并执行查询
        """
        print("=" * 60)
        print("🚀 Playwright 表单操作爬虫启动")
        print("=" * 60)
        print(f"📝 登录页面: {self.login_url}")
        print(f"🎯 目标页面: {self.target_url}")
        print(f"👤 申请人: {applicant_name}")
        print(f"💾 会话保存: {self.user_data_dir}")
        print("=" * 60)
        
        async with async_playwright() as p:
            # 使用持久化上下文
            context = await p.chromium.launch_persistent_context(
                user_data_dir=self.user_data_dir,
                headless=False,
                args=[
                    '--remote-debugging-port=9222',
                    '--disable-gpu',
                    '--disable-gpu-compositing',
                    '--disable-software-rasterizer',
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--no-first-run',
                    '--no-default-browser-check',
                    '--disable-infobars',
                    '--window-position=0,0',
                    '--ignore-certificate-errors',
                    '--ignore-certificate-errors-spki-list',
                    '--disable-blink-features=AutomationControlled',
                    '--window-position=400,0',
                    '--disable-renderer-backgrounding',
                    '--disable-ipc-flooding-protection',
                    '--force-color-profile=srgb',
                    '--mute-audio',
                    '--disable-background-timer-throttling'
                ]
            )
            
            # 获取第一个页面
            page = context.pages[0] if context.pages else await context.new_page()
            
            try:
                # 第一步：导航到登录页面
                print("\n1️⃣ 正在打开登录页面...")
                await page.goto(self.login_url, wait_until="networkidle")
                print("✅ 登录页面加载成功")
                print("👤 请在浏览器窗口中手动完成登录操作")
                print("⏳ 程序将等待您完成登录...")
                
                # 第二步：智能等待用户手动登录
                print("\n2️⃣ 等待手动登录...")
                print("💡 提示：登录完成后，请确保停留在查询页面")
                print("⏰ 智能等待中，检测到登录成功将立即继续...")
                
                # 智能等待登录完成 - 检查"欢迎你"等登录成功标识
                login_success = await self._wait_for_login_success(page)
                
                if not login_success:
                    print("⚠️ 登录等待超时")
                    return None
                else:
                    print("✅ 检测到登录成功，立即继续执行表单操作...")
                
                # 第三步：智能等待申请人输入框出现
                print("\n3️⃣ 正在等待申请人输入框出现...")
                applicant_input = await self._wait_for_applicant_input(page)
                
                if not applicant_input:
                    print("❌ 申请人输入框未找到，请检查是否已正确登录")
                    return None
                
                print("✅ 申请人输入框已找到")
                
                # 第四步：填写申请人信息
                print(f"\n4️⃣ 正在填写申请人信息: {applicant_name}")
                await page.evaluate("""
                    (name) => {
                        // XPath 定位函数
                        function findByXPath(xpath) {
                            try {
                                const result = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
                                return result.singleNodeValue;
                            } catch (e) {
                                return null;
                            }
                        }
                        
                        // 多策略定位申请人输入框
                        const xpaths = [
                            "//div[normalize-space(text())='申请人：']/following-sibling::label[contains(@class, 'q-field')]//input[@type='text']",
                            "//div[contains(@class, 'q-item__label') and normalize-space(text())='申请人：']/following-sibling::label//input",
                            "//label[preceding-sibling::div[normalize-space(text())='申请人：']]//input[@type='text']",
                            "//div[contains(@class, 'row') and .//div[normalize-space(text())='申请人：']]//input[@type='text']"
                        ];
                        
                        for (let xpath of xpaths) {
                            const input = findByXPath(xpath);
                            if (input) {
                                input.value = name;
                                input.dispatchEvent(new Event('input', { bubbles: true }));
                                input.dispatchEvent(new Event('change', { bubbles: true }));
                                return true;
                            }
                        }
                        return false;
                    }
                """, applicant_name)
                print("✅ 申请人信息已填写")
                
                # 第五步：点击查询按钮
                print("\n5️⃣ 正在点击查询按钮...")
                search_result = await self._click_search_button(page)
                
                if not search_result or not search_result.get('success'):
                    print("❌ 查询按钮未找到或点击失败")
                    if search_result:
                        print(f"📋 调试信息: {search_result.get('message', '未知错误')}")
                        print(f"📊 找到的按钮数量: {search_result.get('foundButtons', 0)}")
                    return None
                
                print("✅ 查询按钮已点击")
                print(f"💡 使用的定位策略: {search_result.get('strategy', '未知')}")
                
                # 第六步：等待查询结果加载 - 等待加载组件消失
                print("\n6️⃣ 等待查询结果加载...")
                await self._wait_for_loading_complete(page)
                
                # 第七步：获取查询结果（支持分页）
                print("\n7️⃣ 正在获取查询结果...")
                all_result_data = await self._get_all_pages_results(page, applicant_name)
                
                if all_result_data:
                    print("🎉 所有页面查询结果获取成功！")
                    self._display_results(all_result_data, applicant_name)
                    self._save_results(all_result_data, applicant_name)
                    return all_result_data
                else:
                    print("❌ 查询结果获取失败")
                    return None
                    
            except Exception as e:
                print(f"❌ 表单操作过程中出现错误: {e}")
                return None
            finally:
                await context.close()
    
    async def _wait_for_login_success(self, page, max_wait_time: int = 60000):
        """
        智能等待登录成功 - 检查"欢迎你"等登录成功标识
        """
        print("🔍 正在检测登录状态...")
        start_time = asyncio.get_event_loop().time()
        check_count = 0
        
        while (asyncio.get_event_loop().time() - start_time) * 1000 < max_wait_time:
            check_count += 1
            try:
                login_status = await page.evaluate("""
                    () => {
                        // 检查登录成功标识
                        const pageText = document.body.innerText;
                        const currentUrl = window.location.href;
                        
                        // 登录成功标识列表
                        const successIndicators = [
                            '欢迎你', '欢迎', '登录成功', '已登录', '用户中心',
                            '我的账户', '个人中心', '查询页面', '专利查询'
                        ];
                        
                        // 检查页面是否包含登录成功标识
                        for (const indicator of successIndicators) {
                            if (pageText.includes(indicator)) {
                                console.log('✅ 检测到登录成功标识: ' + indicator);
                                return {
                                    success: true,
                                    indicator: indicator,
                                    url: currentUrl,
                                    pageTitle: document.title
                                };
                            }
                        }
                        
                        // 检查URL是否跳转到查询页面
                        if (currentUrl.includes('chinesepatent') && !currentUrl.includes('login')) {
                            console.log('✅ 检测到已跳转到查询页面');
                            return {
                                success: true,
                                indicator: '页面跳转',
                                url: currentUrl,
                                pageTitle: document.title
                            };
                        }
                        
                        // 检查是否有申请人输入框（直接进入查询页面）
                        const applicantInput = document.querySelector('input[placeholder*="申请人"], input[name*="applicant"]');
                        if (applicantInput) {
                            console.log('✅ 检测到申请人输入框，已进入查询页面');
                            return {
                                success: true,
                                indicator: '申请人输入框',
                                url: currentUrl,
                                pageTitle: document.title
                            };
                        }
                        
                        return {
                            success: false,
                            currentUrl: currentUrl,
                            pageTitle: document.title,
                            hasLoginElements: pageText.includes('登录') || pageText.includes('Login')
                        };
                    }
                """)
            except Exception as e:
                # 如果页面正在导航，执行上下文可能被销毁，等待页面稳定后重试
                if "Execution context was destroyed" in str(e):
                    print("⏳ 页面正在导航，等待页面稳定...")
                    await asyncio.sleep(2)
                    continue
                else:
                    # 其他错误，重新抛出
                    raise e
            
            if login_status.get('success'):
                print(f"🎉 登录成功检测完成！")
                print(f"  标识: {login_status.get('indicator')}")
                print(f"  页面标题: {login_status.get('pageTitle')}")
                print(f"  URL: {login_status.get('url')}")
                return True
            
            # 每5次检查输出一次状态
            if check_count % 20 == 0:
                print(f"⏳ 仍在等待登录... 已等待: {check_count}")
            
            await asyncio.sleep(1)
        
        print(f"⏰ 登录等待超时，共检查 {check_count} 次")
        return False
    
    async def _wait_for_applicant_input(self, page, max_wait_time: int = 60000):
        """
        等待申请人输入框出现
        """
        start_time = asyncio.get_event_loop().time()
        
        while (asyncio.get_event_loop().time() - start_time) * 1000 < max_wait_time:
            applicant_input = await page.evaluate("""
                () => {
                    // XPath 定位函数
                    function findByXPath(xpath) {
                        try {
                            const result = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
                            return result.singleNodeValue;
                        } catch (e) {
                            return null;
                        }
                    }
                    
                    // 多策略定位申请人输入框
                    const xpaths = [
                        "//div[normalize-space(text())='申请人：']/following-sibling::label[contains(@class, 'q-field')]//input[@type='text']",
                        "//div[contains(@class, 'q-item__label') and normalize-space(text())='申请人：']/following-sibling::label//input",
                        "//label[preceding-sibling::div[normalize-space(text())='申请人：']]//input[@type='text']",
                        "//div[contains(@class, 'row') and .//div[normalize-space(text())='申请人：']]//input[@type='text']"
                    ];
                    
                    for (let xpath of xpaths) {
                        const input = findByXPath(xpath);
                        if (input) {
                            console.log('✅ 使用 XPath 找到申请人输入框:', xpath);
                            return input;
                        }
                    }
                    return null;
                }
            """)
            
            if applicant_input:
                return applicant_input
            
            await asyncio.sleep(0.5)
        
        return None
    
    async def _click_search_button(self, page):
        """
        点击查询按钮 - 精确定位表单区域内的查询按钮
        """
        return await page.evaluate("""
            () => {
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
                    
                    // 策略4: 使用CSS选择器查找特定类名的查询按钮
                    "button.q-btn--standard:has(span:contains('查询'))",
                    
                    // 策略5: 查找包含查询图标的按钮
                    "//button[contains(@class, 'q-btn') and .//span[normalize-space(text())='查询']]",
                    
                    // 策略6: 在申请人输入框同一行的查询按钮
                    "//div[.//div[normalize-space(text())='申请人：']]//button[.//span[normalize-space(text())='查询']]"
                ];
                
                console.log("🔍 开始查找查询按钮...");
                
                for (let i = 0; i < searchButtonStrategies.length; i++) {
                    const strategy = searchButtonStrategies[i];
                    let button = null;
                    
                    if (strategy.startsWith('//')) {
                        // XPath 定位
                        button = findByXPath(strategy);
                    } else {
                        // CSS 选择器定位
                        button = document.querySelector(strategy);
                    }
                    
                    if (button) {
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
                    } else {
                        console.log(`❌ 策略 ${i+1} 未找到按钮:`, strategy);
                    }
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
            }
        """)
    
    async def _wait_for_loading_complete(self, page, max_wait_time: int = 30000):
        """
        等待加载组件消失 - 检查 class=q-loading 的组件是否消失
        """
        print("⏳ 等待加载组件消失...")
        start_time = asyncio.get_event_loop().time()
        
        while (asyncio.get_event_loop().time() - start_time) * 1000 < max_wait_time:
            loading_complete = await page.evaluate("""
                () => {
                    // 检查是否存在 class=q-loading 的组件
                    const loadingElements = document.querySelectorAll('.q-loading');
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
                }
            """)
            
            if loading_complete:
                print("✅ 查询结果加载完成")
                return True
            
            await asyncio.sleep(0.5)
        
        print("⚠️ 等待加载组件超时，继续执行...")
        return False
    
    async def _get_pagination_info(self, page):
        """
        获取分页信息
        """
        return await page.evaluate("""
            () => {
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
                    
                    // 检查是否有下一页按钮 - 修复选择器
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
            }
        """)
    
    async def _click_next_page(self, page):
        """
        点击下一页按钮
        """
        return await page.evaluate("""
            () => {
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
            }
        """)
    
    async def _get_all_pages_results(self, page, applicant_name: str):
        """
        获取所有页面的查询结果
        """
        print("📄 开始获取所有页面数据...")
        
        all_results = {
            'resultInfo': {},
            'tableData': [],
            'tableInfoData': [],
            'fullPageHTML': '',
            'pageTitle': '',
            'url': '',
            'paginationStats': {
                'totalPages': 0,
                'currentPage': 0,
                'totalResults': 0,
                'pagesCollected': 0
            }
        }
        
        current_page = 1
        max_pages = 100  # 安全限制，防止无限循环
        
        while current_page <= max_pages:
            print(f"\n📖 正在获取第 {current_page} 页数据...")
            
            # 获取当前页面结果
            page_result = await self._get_query_results(page, applicant_name)
            
            if not page_result:
                print(f"❌ 第 {current_page} 页数据获取失败")
                break
            
            # 如果是第一页，初始化基础信息
            if current_page == 1:
                all_results['resultInfo'] = page_result.get('resultInfo', {})
                all_results['fullPageHTML'] = page_result.get('fullPageHTML', '')
                all_results['pageTitle'] = page_result.get('pageTitle', '')
                all_results['url'] = page_result.get('url', '')
                
                # 获取分页统计信息
                pagination_info = await self._get_pagination_info(page)
                all_results['paginationStats']['totalPages'] = pagination_info.get('totalPages', 1)
                all_results['paginationStats']['totalResults'] = pagination_info.get('totalResults', '0')
            
            # 合并数据
            if 'tableData' in page_result:
                all_results['tableData'].extend(page_result['tableData'])
            
            if 'tableInfoData' in page_result:
                all_results['tableInfoData'].extend(page_result['tableInfoData'])
            
            all_results['paginationStats']['pagesCollected'] = current_page
            all_results['paginationStats']['currentPage'] = current_page
            
            print(f"✅ 第 {current_page} 页数据获取成功")
            print(f"  表格数据: {len(page_result.get('tableData', []))} 行")
            print(f"  table_info 数据: {len(page_result.get('tableInfoData', []))} 条")
            
            # 检查是否有下一页
            pagination_info = await self._get_pagination_info(page)
            has_next_page = pagination_info.get('hasNextPage', False)
            total_pages = pagination_info.get('totalPages', 1)
            
            print(f"📊 分页信息: 当前页 {current_page}/{total_pages}, 是否有下一页: {has_next_page}")
            
            if not has_next_page or current_page >= total_pages:
                print("🎯 已到达最后一页，分页收集完成")
                break
            
            # 点击下一页
            print("🔄 正在点击下一页...")
            next_result = await self._click_next_page(page)
            
            if not next_result.get('success'):
                print(f"❌ 点击下一页失败: {next_result.get('message', '未知错误')}")
                break
            
            # 等待下一页加载
            print("⏳ 等待下一页数据加载...")
            ret = await self._wait_for_loading_complete(page)
            if not ret:
                return None
            
            # 等待页面稳定
            await asyncio.sleep(2)
            
            current_page += 1
        
        # 数据去重（基于申请号）
        if all_results['tableInfoData']:
            unique_table_info_data = self._deduplicate_table_info(all_results['tableInfoData'])
            all_results['tableInfoData'] = unique_table_info_data
        
        print(f"\n📊 分页收集完成统计:")
        print(f"  总页数: {all_results['paginationStats']['totalPages']}")
        print(f"  已收集页数: {all_results['paginationStats']['pagesCollected']}")
        print(f"  总结果数: {all_results['paginationStats']['totalResults']}")
        print(f"  表格数据行数: {len(all_results['tableData'])}")
        print(f"  table_info 数据条数: {len(all_results['tableInfoData'])}")
        
        return all_results
    
    def _deduplicate_table_info(self, table_info_data):
        """
        基于申请号去重 table_info 数据
        """
        seen_app_numbers = set()
        unique_data = []
        
        for item in table_info_data:
            app_number = None
            text = item.get('text', '')
            
            # 从文本中提取申请号
            app_number_match = re.search(r'申请号/专利号：\s*([^\s]+)', text)
            if app_number_match:
                app_number = app_number_match.group(1).strip()
            
            if app_number and app_number not in seen_app_numbers:
                seen_app_numbers.add(app_number)
                unique_data.append(item)
            elif not app_number:
                # 如果没有申请号，直接保留
                unique_data.append(item)
        
        print(f"🔍 数据去重: {len(table_info_data)} -> {len(unique_data)} 条")
        return unique_data
    
    async def _get_query_results(self, page, applicant_name: str):
        """
        获取查询结果
        """
        return await page.evaluate("""
            () => {
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
                
                // 获取所有 table_info 数据
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
            }
        """)
    
    def _display_results(self, result_data, applicant_name: str):
        """显示表单操作结果"""
        print("\n" + "=" * 50)
        print("📊 表单操作结果摘要")
        print("=" * 50)
        print(f"🔗 最终URL: {result_data.get('url', '未知')}")
        print(f"👤 申请人: {applicant_name}")
        
        if 'resultInfo' in result_data:
            print(f"📈 查询结果数量: {result_data['resultInfo'].get('totalResults', '0')}")
        
        if 'tableData' in result_data and result_data['tableData']:
            print(f"📋 表格数据行数: {len(result_data['tableData'])}")
            # 显示前几行数据预览
            for i, row in enumerate(result_data['tableData'][:3]):
                print(f"  行 {i+1}: {row['text'][:100]}...")
    
    def _extract_table_info(self, result_data):
        """
        从查询结果中提取 table_info 结构化数据
        """
        table_info_list = []
        
        # 检查是否有新的 tableInfoData 字段
        if 'tableInfoData' in result_data and result_data['tableInfoData']:
            for table_info in result_data['tableInfoData']:
                info_text = table_info.get('text', '')
                info_html = table_info.get('html', '')
                
                patent_data = self._parse_patent_info(info_html)
                patent_data['raw_text'] = info_text
                table_info_list.append(patent_data)
        
        # 如果没有新的 tableInfoData，尝试从 tableContent 中提取
        elif 'resultInfo' in result_data and 'tableContent' in result_data['resultInfo']:
            table_content = result_data['resultInfo']['tableContent']
            
            # 使用正则表达式从 tableContent 中提取 table_info 块
            table_info_pattern = r'<div[^>]*class="table_info"[^>]*>(.*?)</div>'
            table_info_matches = re.findall(table_info_pattern, table_content, re.DOTALL)
            
            for table_info_html in table_info_matches:
                # 提取纯文本内容
                info_text = re.sub(r'<[^>]+>', ' ', table_info_html)
                info_text = re.sub(r'\s+', ' ', info_text).strip()
                
                patent_data = self._parse_patent_info(info_text)
                patent_data['raw_text'] = info_text
                table_info_list.append(patent_data)
        
        return table_info_list
    
    def _parse_patent_info(self, info_html):
        """解析专利信息HTML"""
        patent_data = {}
        
        # 如果传入的是纯文本，使用更精确的纯文本解析
        if not info_html.startswith('<'):
            return self._parse_patent_info_text(info_html)
        
        # 对于HTML格式，我们使用更精确的HTML标签结构来提取字段
        # 改进的正则表达式模式，能够正确处理嵌套标签和字段边界
        
        # 提取申请号/专利号 - 精确匹配 hover_active 类
        app_number_match = re.search(r'申请号/专利号：\s*</span>\s*<span[^>]*class="hover_active"[^>]*>([^<]*)</span>', info_html)
        if app_number_match:
            patent_data['application_number'] = app_number_match.group(1).strip()
        
        # 提取发明名称 - 精确匹配嵌套的 span
        invention_name_match = re.search(r'发明名称：<span[^>]*>([^<]*)</span>', info_html)
        if invention_name_match:
            patent_data['invention_name'] = invention_name_match.group(1).strip()
        
        # 提取申请人 - 使用更通用的匹配模式，匹配到下一个 span 标签或行结束
        applicant_match = re.search(r'申请人：([^<]*)(?=<span|</span>|$)', info_html)
        if applicant_match:
            applicant_text = applicant_match.group(1).strip()
            # 清理可能包含的HTML标签
            applicant_text = re.sub(r'<[^>]+>', '', applicant_text).strip()
            patent_data['applicant'] = applicant_text
        
        # 提取专利类型 - 使用更通用的匹配模式
        patent_type_match = re.search(r'专利类型：([^<]*)(?=<span|</span>|$)', info_html)
        if patent_type_match:
            patent_type_text = patent_type_match.group(1).strip()
            patent_type_text = re.sub(r'<[^>]+>', '', patent_type_text).strip()
            patent_data['patent_type'] = patent_type_text
        
        # 提取申请日 - 使用更通用的匹配模式
        application_date_match = re.search(r'申请日：([^<]*)(?=<span|</span>|$)', info_html)
        if application_date_match:
            application_date_text = application_date_match.group(1).strip()
            application_date_text = re.sub(r'<[^>]+>', '', application_date_text).strip()
            patent_data['application_date'] = application_date_text
        
        # 提取发明专利申请公布号 - 使用更通用的匹配模式
        publication_number_match = re.search(r'发明专利申请公布号：([^<]*)(?=<span|</span>|$)', info_html)
        if publication_number_match:
            publication_number_text = publication_number_match.group(1).strip()
            publication_number_text = re.sub(r'<[^>]+>', '', publication_number_text).strip()
            patent_data['publication_number'] = publication_number_text
        
        # 提取授权公告号 - 使用更通用的匹配模式
        grant_number_match = re.search(r'授权公告号：([^<]*)(?=<span|</span>|$)', info_html)
        if grant_number_match:
            grant_number_text = grant_number_match.group(1).strip()
            grant_number_text = re.sub(r'<[^>]+>', '', grant_number_text).strip()
            patent_data['grant_number'] = grant_number_text
        
        # 提取案件状态 - 使用更通用的匹配模式
        case_status_match = re.search(r'案件状态：([^<]*)(?=<span|</span>|$)', info_html)
        if case_status_match:
            case_status_text = case_status_match.group(1).strip()
            case_status_text = re.sub(r'<[^>]+>', '', case_status_text).strip()
            patent_data['case_status'] = case_status_text
        
        # 提取授权公告日 - 使用更通用的匹配模式
        grant_date_match = re.search(r'授权公告日：([^<]*)(?=<span|</span>|$)', info_html)
        if grant_date_match:
            grant_date_text = grant_date_match.group(1).strip()
            grant_date_text = re.sub(r'<[^>]+>', '', grant_date_text).strip()
            patent_data['grant_date'] = grant_date_text
        
        # 提取主分类号 - 使用更通用的匹配模式
        main_class_match = re.search(r'主分类号：([^<]*)(?=<span|</span>|$)', info_html)
        if main_class_match:
            main_class_text = main_class_match.group(1).strip()
            main_class_text = re.sub(r'<[^>]+>', '', main_class_text).strip()
            patent_data['main_classification'] = main_class_text
        
        # 如果HTML解析失败，回退到纯文本解析
        if not patent_data:
            clean_text = re.sub(r'<[^>]+>', ' ', info_html)
            clean_text = re.sub(r'\s+', ' ', clean_text).strip()
            patent_data = self._parse_patent_info_text(clean_text)
        
        return patent_data
    
    def _parse_patent_info_text(self, info_text):
        """解析纯文本格式的专利信息（向后兼容）"""
        patent_data = {}
        
        # 使用更精确的纯文本解析，避免字段边界混淆
        # 提取申请号/专利号
        app_number_match = re.search(r'申请号/专利号：\s*([^\s]+)', info_text)
        if app_number_match:
            patent_data['application_number'] = app_number_match.group(1).strip()
        
        # 提取发明名称 - 使用更精确的边界
        invention_name_match = re.search(r'发明名称：([^申]+?)(?=\s*申请人：|\s*专利类型：|$)', info_text)
        if invention_name_match:
            patent_data['invention_name'] = invention_name_match.group(1).strip()
        
        # 提取申请人 - 使用更精确的边界
        applicant_match = re.search(r'申请人：([^专]+?)(?=\s*专利类型：|\s*申请日：|$)', info_text)
        if applicant_match:
            patent_data['applicant'] = applicant_match.group(1).strip()
        
        # 提取专利类型 - 使用更精确的边界
        patent_type_match = re.search(r'专利类型：([^申]+?)(?=\s*申请日：|\s*发明专利申请公布号：|$)', info_text)
        if patent_type_match:
            patent_data['patent_type'] = patent_type_match.group(1).strip()
        
        # 提取申请日
        application_date_match = re.search(r'申请日：([^\s]+)', info_text)
        if application_date_match:
            patent_data['application_date'] = application_date_match.group(1).strip()
        
        # 提取发明专利申请公布号
        publication_number_match = re.search(r'发明专利申请公布号：([^\s]+)', info_text)
        if publication_number_match:
            patent_data['publication_number'] = publication_number_match.group(1).strip()
        
        # 提取授权公告号
        grant_number_match = re.search(r'授权公告号：([^\s]+)', info_text)
        if grant_number_match:
            patent_data['grant_number'] = grant_number_match.group(1).strip()
        
        # 提取案件状态 - 使用更精确的边界
        case_status_match = re.search(r'案件状态：([^授]+?)(?=\s*授权公告日：|\s*主分类号：|$)', info_text)
        if case_status_match:
            patent_data['case_status'] = case_status_match.group(1).strip()
        
        # 提取授权公告日
        grant_date_match = re.search(r'授权公告日：([^\s]+)', info_text)
        if grant_date_match:
            patent_data['grant_date'] = grant_date_match.group(1).strip()
        
        # 提取主分类号
        main_class_match = re.search(r'主分类号：([^\s]+)', info_text)
        if main_class_match:
            patent_data['main_classification'] = main_class_match.group(1).strip()
        
        return patent_data
    
    def export_table_info(self, result_data, applicant_name: str, export_format: str = "csv"):
        """
        导出 table_info 数据到指定格式
        
        Args:
            result_data: 查询结果数据
            applicant_name: 申请人名称
            export_format: 导出格式，支持 'csv', 'json', 'excel'
        """
        import time
        timestamp = int(time.time())
        
        # 提取 table_info 数据
        table_info_data = self._extract_table_info(result_data)
        
        if not table_info_data:
            print("❌ 未找到 table_info 数据")
            return
        
        print(f"📊 提取到 {len(table_info_data)} 条 table_info 数据")
        
        try:
            if export_format == "csv":
                filename = f"table_info_{applicant_name}_{timestamp}.csv"
                self._export_to_csv(table_info_data, filename)
            elif export_format == "json":
                filename = f"table_info_{applicant_name}_{timestamp}.json"
                self._export_to_json(table_info_data, filename)
            elif export_format == "excel":
                filename = f"table_info_{applicant_name}_{timestamp}.xlsx"
                self._export_to_excel(table_info_data, filename)
            else:
                print(f"❌ 不支持的导出格式: {export_format}")
                return
            
            print(f"💾 table_info 数据已导出到: {filename}")
            
        except Exception as e:
            print(f"❌ 导出 table_info 数据失败: {e}")
    
    def _export_to_csv(self, table_info_data, filename):
        """导出为 CSV 格式"""
        if not table_info_data:
            return
        
        # 定义固定的字段顺序和中文列名映射
        field_mapping = {
            'sequence': '序号',
            'applicant': '专利权人',
            'application_date': '申请日',
            'invention_name': '专利名称',
            'application_number': '专利号',
            'grant_date': '授权公告日',
            'patent_type': '专利类型',
            'publication_number': '发明专利申请公布号',
            'grant_number': '授权公告号',
            'case_status': '案件状态',
            'main_classification': '主分类号'
        }
        
        # 获取所有可能的字段（排除 raw_text）
        all_fields = set()
        for item in table_info_data:
            all_fields.update(item.keys())
        all_fields.discard('raw_text')
        
        # 确保包含序号字段
        all_fields.add('sequence')
        
        # 按照指定顺序排列字段，未指定的字段放在最后
        ordered_fields = []
        for field in field_mapping.keys():
            if field in all_fields:
                ordered_fields.append(field)
        
        # 添加其他未指定的字段
        for field in sorted(all_fields):
            if field not in ordered_fields:
                ordered_fields.append(field)
        
        # 准备写入数据
        with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
            # 使用中文列名
            chinese_headers = [field_mapping.get(field, field) for field in ordered_fields]
            writer = csv.DictWriter(csvfile, fieldnames=ordered_fields)
            
            # 写入中文表头
            writer.writerow(dict(zip(ordered_fields, chinese_headers)))
            
            # 写入数据行
            for i, item in enumerate(table_info_data):
                # 过滤掉 raw_text 字段
                filtered_item = {k: v for k, v in item.items() if k != 'raw_text'}
                # 添加序号
                filtered_item['sequence'] = i + 1
                writer.writerow(filtered_item)
    
    def _export_to_json(self, table_info_data, filename):
        """导出为 JSON 格式"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(table_info_data, f, ensure_ascii=False, indent=2)
    
    def _export_to_excel(self, table_info_data, filename):
        """导出为 Excel 格式"""
        try:
            # 创建 DataFrame
            df_data = []
            for item in table_info_data:
                # 过滤掉 raw_text 字段
                filtered_item = {k: v for k, v in item.items() if k != 'raw_text'}
                df_data.append(filtered_item)
            
            df = pd.DataFrame(df_data)
            df.to_excel(filename, index=False, engine='openpyxl')
        except ImportError:
            print("❌ 未安装 pandas 库，无法导出 Excel 格式")
            print("💡 请运行: pip install pandas openpyxl")
    
    def _save_results(self, result_data, applicant_name: str):
        """保存表单操作结果到文件"""
        import time
        timestamp = int(time.time())
        filename = f"playwright_result_{applicant_name}_{timestamp}.json"
        
        try:
            result_data["applicant_name"] = applicant_name
            result_data["timestamp"] = timestamp
            
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(result_data, f, ensure_ascii=False, indent=2)
            
            print(f"💾 表单操作结果已保存到: {filename}")
            
            # 同时保存为可读的文本文件
            text_filename = f"playwright_result_{applicant_name}_{timestamp}.txt"
            with open(text_filename, "w", encoding="utf-8") as f:
                f.write(f"申请人: {applicant_name}\n")
                f.write(f"查询时间: {timestamp}\n")
                f.write(f"URL: {result_data.get('url', '未知')}\n")
                f.write("=" * 60 + "\n\n")
                
                if 'resultInfo' in result_data:
                    f.write(f"查询结果数量: {result_data['resultInfo'].get('totalResults', '0')}\n\n")
                
                if 'tableData' in result_data and result_data['tableData']:
                    f.write("表格数据:\n")
                    f.write("-" * 40 + "\n")
                    for i, row in enumerate(result_data['tableData']):
                        f.write(f"行 {i+1}: {row['text']}\n")
            
            print(f"💾 文本格式结果已保存到: {text_filename}")
            
            # 自动导出 table_info 数据
            print("\n📊 正在自动导出 table_info 数据...")
            self.export_table_info(result_data, applicant_name, "csv")
            self.export_table_info(result_data, applicant_name, "json")
            
        except Exception as e:
            print(f"❌ 保存表单操作结果失败: {e}")

async def main():
    """
    主函数 - 配置并运行 Playwright 表单爬虫
    """
    # ============================================
    # 🔧 在这里配置你的登录信息
    # ============================================
    
    # 示例配置（请根据实际需求修改）
    LOGIN_URL = "https://cpquery.cponline.cnipa.gov.cn/chinesepatent/index"    # 替换为实际的登录页面URL
    TARGET_URL = "https://cpquery.cponline.cnipa.gov.cn/chinesepatent/index"  # 替换为登录后要爬取的目标页面URL
    SESSION_DIR = "./my_browser_session"       # 会话保存目录
    
    # 创建爬虫实例
    crawler = PlaywrightFormCrawler(
        login_url=LOGIN_URL,
        target_url=TARGET_URL,
        user_data_dir=SESSION_DIR
    )
    
    # 执行表单操作
    company = "青岛迈金智能科技股份有限公司"
    # company = "鹰角"
    result = await crawler.crawl_with_form_operation(company)
    
    if result:
        print("\n✅ 任务完成！")
        print("💡 提示：下次运行时会自动使用保存的会话，无需重复登录")
    else:
        print("\n❌ 任务失败，请检查配置和网络连接")

if __name__ == "__main__":
    # 启动爬虫
    asyncio.run(main())
