import sys
import json
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWebEngineWidgets import QWebEngineView
from src.browser.qwebengine_controller import QWebEngineController

def main():
    # 初始化PyQt应用
    app = QApplication(sys.argv)
    
    # 创建WebEngine视图
    web_view = QWebEngineView()
    
    # 创建控制器
    controller = QWebEngineController(web_view)
    
    # 使用一个已知包含表格的测试URL
    test_url = "https://www.w3schools.com/html/html_tables.asp"
    
    print(f"正在加载页面: {test_url}")
    
    # 导航到测试页面（使用同步方法）
    success = controller.goto_sync(test_url)
    if not success:
        print("页面加载失败")
        return 1
    
    # 等待页面导航完成
    controller.wait_for_navigation_sync()
    
    # 执行JavaScript提取表格数据
    js_code = '''
        (function() {
            const data = {
                pageTitle: document.title,
                url: window.location.href,
                tables: [],
                debugInfo: {}
            };
            
            // 查找所有表格
            const tables = document.querySelectorAll('table');
            data.debugInfo.tableCount = tables.length;
            
            // 打印调试信息到控制台
            console.log('表格提取调试信息:');
            console.log('- 找到表格数量:', tables.length);
            
            tables.forEach((table, tableIndex) => {
                const rows = table.querySelectorAll('tr');
                const tableData = [];
                console.log(`- 表格 ${tableIndex}: ${rows.length} 行, 类名: '${table.className}', ID: '${table.id}'`);
                
                rows.forEach((row, rowIndex) => {
                    const cells = [];
                    const tds = row.querySelectorAll('td, th');
                    
                    tds.forEach((cell, cellIndex) => {
                        // 使用outerHTML获取完整HTML内容
                        const htmlContent = cell.outerHTML;
                        
                        // 提取原始文本内容
                        const rawTextContent = cell.textContent;
                        
                        // 提取链接信息
                        const links = [];
                        const linkElements = cell.querySelectorAll('a');
                        linkElements.forEach(link => {
                            links.push({
                                text: link.textContent,
                                href: link.getAttribute('href') || '',
                                target: link.getAttribute('target') || ''
                            });
                        });
                        
                        // 提取图片信息
                        const images = [];
                        const imgElements = cell.querySelectorAll('img');
                        imgElements.forEach(img => {
                            images.push({
                                src: img.getAttribute('src') || '',
                                alt: img.getAttribute('alt') || '',
                                title: img.getAttribute('title') || ''
                            });
                        });
                        
                        const cellData = {
                            html: htmlContent,
                            rawText: rawTextContent,
                            text: cell.textContent.trim(),
                            links: links,
                            images: images,
                            tagName: cell.tagName,
                            className: cell.className,
                            id: cell.id
                        };
                        
                        cells.push(cellData);
                    });
                    
                    if (cells.length > 0) {
                        tableData.push(cells);
                    }
                });
                
                if (tableData.length > 0) {
                    data.tables.push({
                        index: tableIndex,
                        rowCount: tableData.length,
                        columnCount: tableData[0]?.length || 0,
                        className: table.className,
                        id: table.id,
                        data: tableData
                    });
                }
            });
            
            return data;
        })();
    '''
    
    print("执行JavaScript提取表格数据...")
    
    # 使用get_content_sync方法执行JavaScript并获取结果
    # 先执行JavaScript来存储结果到页面
    controller.web_view.page().runJavaScript(f"window._extraction_result = {js_code};")
    
    # 然后获取结果
    result = []
    
    def callback(res):
        result.append(json.dumps(res))
    
    controller.web_view.page().runJavaScript("window._extraction_result;", callback)
    
    # 等待结果返回
    import time
    start_time = time.time()
    while not result and time.time() - start_time < 5:
        QApplication.processEvents()
        time.sleep(0.1)
    
    if result:
        result = result[0]
    else:
        result = None
    
    # 打印提取结果
    if result:
        result_dict = json.loads(result)
        
        print(f"\n页面标题: {result_dict.get('pageTitle', 'N/A')}")
        print(f"表格总数: {result_dict.get('debugInfo', {}).get('tableCount', 0)}")
        
        tables = result_dict.get('tables', [])
        print(f"成功提取表格数: {len(tables)}")
        
        # 详细打印每个表格的信息
        for i, table in enumerate(tables):
            print(f"\n=== 表格 {i} ===")
            print(f"行数: {table.get('rowCount', 0)}")
            print(f"列数: {table.get('columnCount', 0)}")
            
            # 打印前两行数据作为示例
            sample_rows = table.get('data', [])[:2]
            for row_idx, row in enumerate(sample_rows):
                print(f"  行 {row_idx}:")
                for cell_idx, cell in enumerate(row):
                    print(f"    单元格 {cell_idx}:")
                    print(f"      标签: {cell.get('tagName', '')}")
                    print(f"      类名: {cell.get('className', '')}")
                    # 打印单元格基本信息
                    print(f"        标签: {cell.get('tagName', '')}")
                    print(f"        类名: '{cell.get('className', '')}'")
                    print(f"        文本预览: '{cell.get('text', '')[:100]}{'...' if len(cell.get('text', '')) > 100 else ''}'")
                    
                    # 打印HTML预览（前150个字符）
                    html_preview = cell.get('html', '')[:150]
                    print(f"        HTML预览: '{html_preview}{'...' if len(cell.get('html', '')) > 150 else ''}'")
                    
                    print(f"        链接数: {len(cell.get('links', []))}")
                    print(f"        图片数: {len(cell.get('images', []))}")
                    
                    # 打印链接详情
                    if cell.get('links', []):
                        print(f"        链接详情:")
                        for link_idx, link in enumerate(cell.get('links', [])):
                            link_text = link.get('text', '')[:30]
                            link_href = link.get('href', '')[:80]
                            print(f"          [{link_idx}] '{link_text}{'...' if len(link.get('text', '')) > 30 else ''}' -> '{link_href}{'...' if len(link.get('href', '')) > 80 else ''}'")
    
    else:
        print("未获取到表格数据")
    
    print("\n测试完成")
    return 0

if __name__ == "__main__":
    sys.exit(main())