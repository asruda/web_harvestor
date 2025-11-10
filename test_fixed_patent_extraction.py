"""
测试修复后的数据提取功能
模拟在已登录页面上执行专利数据提取
"""

import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QUrl, QEventLoop, QTimer
from src.crawler.crawler_engine import CrawlerEngine


def test_crawl_on_current_page():
    """
    测试在当前已加载页面上执行数据提取
    假设页面已经登录并包含专利数据
    """
    print("开始测试修复后的数据提取功能...")
    
    # 创建应用和WebView实例
    app = QApplication(sys.argv)
    web_view = QWebEngineView()
    
    # 初始化爬虫引擎，使用现有的web_view
    engine = CrawlerEngine(web_view)
    
    # 定义页面配置（假设使用.tableList选择器）
    page_config = {
        "table_selector": ".tableList table",  # 使用更具体的选择器
        "field_mappings": {                    # 定义列索引到字段名的映射
            0: "序号",
            1: "专利名称",
            2: "申请号",
            3: "公开号",
            4: "申请人",
            5: "申请日",
            6: "公开日"
        }
    }
    
    # 定义简单的抓取策略
    strategy = {
        "max_pages": 1,  # 只抓取当前页
        "wait_time": 3   # 等待时间
    }
    
    try:
        print("📝 准备从当前页面提取数据...")
        print(f"🔍 使用表格选择器: {page_config['table_selector']}")
        print(f"📊 字段映射配置: {page_config['field_mappings']}")
        
        # 启动浏览器控制器但不重新加载页面
        if isinstance(engine.browser, QWebEngineController):
            engine.browser.start_sync()
            current_url = engine.browser.get_current_url_sync()
            print(f"🌐 当前页面URL: {current_url}")
        
        # 等待页面内容完全加载
        print("⏳ 等待页面内容加载完成...")
        loop = QEventLoop()
        QTimer.singleShot(3000, loop.quit)  # 等待3秒
        loop.exec()
        
        # 尝试直接获取页面HTML内容
        html_content = engine.browser.get_content_sync()
        print(f"📄 获取到页面HTML内容长度: {len(html_content)} 字符")
        
        # 检查是否包含.tableList元素
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, "lxml")
        table_elements = soup.select(".tableList")
        print(f"📋 发现 .tableList 元素数量: {len(table_elements)}")
        
        if table_elements:
            print("✅ 找到表格元素，准备提取数据...")
        else:
            print("⚠️ 未找到 .tableList 元素，尝试其他选择器...")
            # 尝试查找所有表格元素
            all_tables = soup.find_all("table")
            print(f"   页面中表格总数: {len(all_tables)}")
            
            # 显示前几个表格的基本信息
            for i, table in enumerate(all_tables[:3]):
                rows = table.find_all("tr")
                print(f"   表格 {i+1}: {len(rows)} 行")
        
        # 尝试使用不同的选择器提取数据
        test_selectors = [
            ".tableList table",
            ".tableList",
            "table",
            "#tableList table",
            "div.tableList"
        ]
        
        for selector in test_selectors:
            print(f"\n🔄 尝试选择器: {selector}")
            temp_config = page_config.copy()
            temp_config["table_selector"] = selector
            
            # 直接使用extractor提取数据
            page_data = engine.extractor.extract_table_data(
                html_content, 
                selector, 
                page_config["field_mappings"]
            )
            
            print(f"📈 提取到的数据行数量: {len(page_data)}")
            
            if page_data:
                print("✅ 成功提取到数据！前两行数据:")
                for i, row in enumerate(page_data[:2]):
                    print(f"   行 {i+1}: {row}")
            else:
                print("❌ 未能提取到数据")
        
        print("\n🎉 测试完成！")
        return 0
        
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        # 确保应用正常退出
        QTimer.singleShot(1000, app.quit)
        sys.exit(app.exec())


if __name__ == "__main__":
    # 导入必要的模块
    from src.browser.qwebengine_controller import QWebEngineController
    test_crawl_on_current_page()