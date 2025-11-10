#!/usr/bin/env python3
"""
测试表格数据提取的独立脚本
直接测试JavaScript提取功能，专注于HTML标签数据提取
"""

import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWebEngineWidgets import QWebEngineView
from src.ui.main_window import setup_web_engine_profile
import json

def test_tables_extraction():
    """测试表格数据提取"""
    print("=== 开始测试表格数据提取 ===")
    
    # 初始化应用程序和WebEngine
    app = QApplication(sys.argv)
    setup_web_engine_profile()
    
    # 创建浏览器视图
    web_view = QWebEngineView()
    
    # 直接测试JavaScript提取
    test_js = '''
    (function() {
        // 提取页面信息
        const data = {
            pageTitle: document.title,
            url: window.location.href,
            bodyText: document.body.innerText.substring(0, 500),
            tables: [],
            debugInfo: {}
        };
        
        // 获取所有表格
        const tables = document.querySelectorAll('table');
        data.debugInfo.tableCount = tables.length;
        
        // 尝试直接获取专利表格
        const patentTable = document.querySelector('.tableList table, .table_info');
        if (patentTable) {
            data.debugInfo.foundPatentTable = true;
            data.debugInfo.patentTableClass = patentTable.className;
            data.debugInfo.patentTableId = patentTable.id;
        }
        
        // 尝试获取表格列表元素
        const tableList = document.querySelector('.tableList');
        if (tableList) {
            data.debugInfo.hasTableList = true;
            data.debugInfo.tableListInnerHTML = tableList.innerHTML.substring(0, 300);
        }
        
        // 提取每个表格的数据
        tables.forEach((table, idx) => {
            const rows = table.querySelectorAll('tr');
            const tableData = {
                index: idx,
                className: table.className,
                id: table.id,
                rowCount: rows.length,
                data: []
            };
            
            rows.forEach((row, rowIdx) => {
                const cells = [];
                const tds = row.querySelectorAll('td, th');
                
                tds.forEach((cell) => {
                    cells.push({
                        text: cell.textContent.trim(),
                        html: cell.outerHTML
                    });
                });
                
                if (cells.length > 0) {
                    tableData.data.push(cells);
                }
            });
            
            if (tableData.data.length > 0) {
                data.tables.push(tableData);
            }
        });
        
        return JSON.stringify(data);
    })();
    '''
    
    # 用于存储JavaScript执行结果
    js_result = None
    
    # 结果回调函数
    def handle_js_result(result):
        nonlocal js_result
        try:
            js_result = json.loads(result)
            print("✅ JavaScript执行成功并返回数据")
        except Exception as e:
            print(f"❌ 解析JavaScript结果失败: {str(e)}")
            print(f"原始结果: {result}")
            js_result = {"error": str(e), "raw_result": result}
    
    # 加载URL并执行JavaScript
    test_url = "https://cpquery.cponline.cnipa.gov.cn/chinesepatent/index"
    print(f"📄 加载测试URL: {test_url}")
    
    # 页面加载完成信号
    def on_load_finished(ok):
        print(f"✅ 页面加载完成: {ok}")
        if ok:
            print("📊 执行JavaScript提取...")
            # 延迟执行JavaScript以确保页面完全加载
            web_view.page().runJavaScript("setTimeout(() => { /* 等待页面稳定 */ }, 3000)", lambda: 
                web_view.page().runJavaScript(test_js, handle_js_result)
            )
        else:
            print("❌ 页面加载失败")
            app.quit()
    
    # 连接信号
    web_view.loadFinished.connect(on_load_finished)
    
    # 加载URL
    web_view.load(test_url)
    
    # 运行应用程序直到JavaScript执行完成
    def check_result():
        if js_result is not None:
            # 显示结果
            print("\n📋 JavaScript提取结果详情:")
            print(f"  - 页面标题: {js_result.get('pageTitle', 'N/A')}")
            print(f"  - 表格数量: {js_result['debugInfo'].get('tableCount', 0)}")
            print(f"  - 找到专利表格: {js_result['debugInfo'].get('foundPatentTable', False)}")
            print(f"  - 包含表格列表: {js_result['debugInfo'].get('hasTableList', False)}")
            
            # 显示表格数据
            if js_result.get('tables'):
                print(f"\n📊 提取到 {len(js_result['tables'])} 个表格:")
                for i, table in enumerate(js_result['tables']):
                    print(f"\n  表格 {i+1}:")
                    print(f"    - 类名: {table.get('className', '')}")
                    print(f"    - ID: {table.get('id', '')}")
                    print(f"    - 行数: {table.get('rowCount', 0)}")
                    print(f"    - 数据行数: {len(table.get('data', []))}")
                    
                    # 显示前2行数据
                    for j, row in enumerate(table['data'][:2]):
                        print(f"\n      行 {j+1}:")
                        for k, cell in enumerate(row):
                            print(f"        列 {k+1}: {cell.get('text', '')[:100]}...")
                            if len(cell.get('html', '')) < 200:
                                print(f"            HTML: {cell.get('html', '')}")
                            else:
                                print(f"            HTML: {cell.get('html', '')[:100]}...")
            else:
                print("❌ 未提取到表格数据")
            
            # 退出应用程序
            app.quit()
        else:
            # 继续检查
            QTimer.singleShot(1000, check_result)
    
    # 导入QTimer并启动检查
    from PyQt6.QtCore import QTimer
    QTimer.singleShot(5000, check_result)  # 5秒后开始检查
    
    # 运行应用程序
    sys.exit(app.exec())

if __name__ == "__main__":
    test_tables_extraction()