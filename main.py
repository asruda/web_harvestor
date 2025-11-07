"""
主程序入口
Web Data Crawler Tool
"""

import sys
from PyQt6.QtWidgets import QApplication
from src.ui.main_window import MainWindow, setup_web_engine_profile


def main():
    """主函数"""
    print("1. 开始初始化应用程序...")

    # 创建应用程序实例
    app = QApplication(sys.argv)
    
    # 设置应用程序信息
    app.setApplicationName("网页数据抓取工具")
    app.setApplicationVersion("0.1.0")
    app.setOrganizationName("WebCrawler")
    
    # 配置WebEngine，确保在创建任何Web视图之前执行
    print("1.1 配置WebEngine环境...")
    setup_web_engine_profile()
    
    # 添加异常捕获
    try:
        print("2. 创建主窗口实例...")
        # 创建并显示主窗口
        window = MainWindow()
        print("3. 主窗口实例创建完成，准备显示...")
        window.show()
        print("4. 主窗口已显示，开始运行应用程序事件循环...")
        
        # 运行应用程序
        sys.exit(app.exec())
    except Exception as e:
        import traceback
        error_info = f"程序崩溃: {str(e)}\n{traceback.format_exc()}"
        print(error_info)
        # 尝试显示错误对话框
        try:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(None, "错误", error_info)
        except:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
