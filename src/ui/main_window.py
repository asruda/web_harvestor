"""
主窗口 - PyQt6主界面
"""

from src.crawler.crawler_engine import CrawlerEngine
import sys
import asyncio
from typing import Any, Optional
import uuid
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QListWidget,
    QTextEdit,
    QProgressBar,
    QSplitter,
    QMessageBox,
    QInputDialog,
)
from PyQt6.QtCore import Qt, QThread, QObject, pyqtSignal, QUrl
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtGui import QCloseEvent
from ..database.models import Database, SiteConfig, PageConfig, CrawlStrategy, CrawlTask
from ..crawler.crawler_engine import CrawlerEngine
from ..crawler.data_exporter import DataExporter


class CrawlWorker(QObject):
    """爬虫工作器，用于在主线程中执行爬虫操作"""
    progress = pyqtSignal(dict)
    finished = pyqtSignal(list)
    error = pyqtSignal(str)
    
    def __init__(self, engine: CrawlerEngine, start_url: str, page_config: dict, strategy: dict):
        super().__init__()
        self.engine = engine
        self.start_url = start_url
        self.page_config = page_config
        self.strategy = strategy
        self.is_running = True
    
    def stop(self):
        """停止爬虫"""
        self.is_running = False
        if self.engine:
            self.engine.stop()
    
    def crawl(self):
        """执行爬虫操作（在主线程中调用）"""
        try:
            def progress_callback(**kwargs):
                if not self.is_running:
                    raise Exception("爬虫已停止")
                self.progress.emit(kwargs)
            
            # 直接在主线程中调用start_crawl方法
            data = self.engine.start_crawl(
                self.start_url,
                self.page_config,
                self.strategy,
                progress_callback,
            )
            if self.is_running:
                self.finished.emit(data)
        except Exception as e:
            import traceback
            error_info = f"错误: {str(e)}\n{traceback.format_exc()}"
            self.error.emit(error_info)
            print(error_info)  # 同时打印到控制台以便调试

class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.db = Database()
        self.site_config_model = SiteConfig(self.db)
        self.page_config_model = PageConfig(self.db)
        self.strategy_model = CrawlStrategy(self.db)
        self.task_model = CrawlTask(self.db)
        self.exporter = DataExporter()
        
        self.current_site_id = None
        self.current_page_config = None
        self.crawl_thread = None
        self.browser_view = None
        self.crawler_engine = None  # 存储爬虫引擎实例
        
        self.init_ui()
        self.load_site_configs()

    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("网页数据抓取工具 v0.1.0")
        self.setGeometry(100, 100, 1280, 800)

        # 创建中心部件
        central_widget: Any = QWidget()
        self.setCentralWidget(central_widget)

        # 主布局 - 水平分割器
        main_splitter: Any = QSplitter(Qt.Orientation.Horizontal)

        # 左侧面板 - 配置列表
        left_panel = self.create_left_panel()
        main_splitter.addWidget(left_panel)

        # 右侧面板 - 工作区
        right_panel = self.create_right_panel()
        main_splitter.addWidget(right_panel)

        # 设置分割比例
        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 3)

        # 主布局
        layout = QVBoxLayout(central_widget)
        layout.addWidget(main_splitter)
        layout.setContentsMargins(5, 5, 5, 5)

    def create_left_panel(self) -> QWidget:
        """创建左侧面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # 标题
        title_label = QLabel("📋 网站配置")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; padding: 5px;")
        layout.addWidget(title_label)

        # 新建配置按钮
        new_config_btn = QPushButton("➕ 新建网站配置")
        new_config_btn.clicked.connect(self.create_new_site_config)
        layout.addWidget(new_config_btn)

        # 配置列表
        self.site_list = QListWidget()
        self.site_list.itemClicked.connect(self.on_site_selected)
        layout.addWidget(self.site_list)

        # 操作按钮
        btn_layout = QHBoxLayout()
        edit_btn = QPushButton("✏️ 编辑")
        edit_btn.clicked.connect(self.edit_site_config)
        delete_btn = QPushButton("🗑️ 删除")
        delete_btn.clicked.connect(self.delete_site_config)
        btn_layout.addWidget(edit_btn)
        btn_layout.addWidget(delete_btn)
        layout.addLayout(btn_layout)

        return panel

    def create_right_panel(self) -> QWidget:
        """创建右侧面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # 工具栏
        toolbar_layout = QHBoxLayout()
        self.current_site_label = QLabel("当前: 未选择")
        self.current_site_label.setStyleSheet("font-weight: bold;")
        toolbar_layout.addWidget(self.current_site_label)
        toolbar_layout.addStretch()
        layout.addLayout(toolbar_layout)

        # 浏览器视图 - 使用 QWebEngineView
        self.browser_view = QWebEngineView()
        self.browser_view.setMinimumHeight(300)
        layout.addWidget(self.browser_view)

        # 控制面板
        control_panel = self.create_control_panel()
        layout.addWidget(control_panel)

        # 进度和日志
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        layout.addWidget(self.log_text)

        return panel

    def create_control_panel(self) -> QWidget:
        """创建控制面板"""
        panel = QWidget()
        panel.setStyleSheet("background-color: #ffffff; border: 1px solid #ddd; padding: 10px;")
        layout = QVBoxLayout(panel)

        # 抓取策略
        strategy_layout = QHBoxLayout()
        strategy_layout.addWidget(QLabel("抓取策略:"))
        self.strategy_label = QLabel("默认策略")
        strategy_layout.addWidget(self.strategy_label)
        
        # 添加编辑策略按钮
        edit_strategy_btn = QPushButton("✏️ 编辑策略")
        edit_strategy_btn.clicked.connect(self.edit_strategy)
        strategy_layout.addWidget(edit_strategy_btn)
        
        strategy_layout.addStretch()
        layout.addLayout(strategy_layout)

        # 控制按钮
        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("🎯 开始抓取")
        self.start_btn.clicked.connect(self.start_crawl)
        self.start_btn.setEnabled(False)
        
        self.pause_btn = QPushButton("⏸️ 暂停")
        self.pause_btn.clicked.connect(self.pause_crawl)
        self.pause_btn.setEnabled(False)
        
        self.stop_btn = QPushButton("⏹️ 停止")
        self.stop_btn.clicked.connect(self.stop_crawl)
        self.stop_btn.setEnabled(False)

        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.pause_btn)
        btn_layout.addWidget(self.stop_btn)
        layout.addLayout(btn_layout)

        return panel

    def load_site_configs(self):
        """加载网站配置列表"""
        self.site_list.clear()
        configs = self.site_config_model.get_all()
        for config in configs:
            item_text = f"{config['name']}\n{config['start_url'][:50]}..."
            self.site_list.addItem(item_text)
            # 保存配置ID到item
            item = self.site_list.item(self.site_list.count() - 1)
            if item:  # 添加空值检查
                item.setData(Qt.ItemDataRole.UserRole, config['id'])

    def create_new_site_config(self):
        """创建新网站配置"""
        name, ok = QInputDialog.getText(self, "新建配置", "请输入网站名称:")
        if ok and name:
            url, ok = QInputDialog.getText(self, "新建配置", "请输入起始URL:")
            if ok and url:
                site_id = str(uuid.uuid4())
                self.site_config_model.create(site_id, name, url)
                
                # 创建默认页面配置
                page_id = str(uuid.uuid4())
                self.page_config_model.create(
                    page_id,
                    site_id,
                    "默认页面",
                    "table",  # 默认表格选择器
                    {0: "列1", 1: "列2", 2: "列3"},  # 默认字段映射
                )
                
                # 创建默认策略
                strategy_id = str(uuid.uuid4())
                self.strategy_model.create(
                    strategy_id,
                    page_id,
                    pagination_type="button",
                    pagination_params={"next_button_selector": ".next-page"},
                )
                
                self.load_site_configs()
                self.log("✅ 创建配置成功: " + name)

    def on_site_selected(self, item):
        """选择网站配置"""
        site_id = item.data(Qt.ItemDataRole.UserRole)
        self.current_site_id = site_id
        
        # 获取配置
        site = self.site_config_model.get(site_id)
        if site:
            self.current_site_label.setText(f"当前: {site['name']}")
            
            # 在浏览器视图中加载页面
            if self.browser_view:
                self.browser_view.setUrl(QUrl(site['start_url']))
                self.log(f"🌐 正在加载网站: {site['start_url']}")
            
            # 获取页面配置
            pages = self.page_config_model.get_by_site(site_id)
            if pages:
                self.current_page_config = pages[0]
                self.start_btn.setEnabled(True)
                self.log(f"✅ 已选择配置: {site['name']}")

    def edit_site_config(self):
        """编辑网站配置"""
        current_item = self.site_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "警告", "请先选择一个配置")
            return
        
        QMessageBox.information(self, "提示", "编辑功能正在开发中...")

    def delete_site_config(self):
        """删除网站配置"""
        current_item = self.site_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "警告", "请先选择一个配置")
            return
        
        site_id = current_item.data(Qt.ItemDataRole.UserRole)
        reply = QMessageBox.question(
            self, "确认删除", "确定要删除此配置吗？", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.site_config_model.delete(site_id)
            self.load_site_configs()
            self.log("✅ 已删除配置")

    def edit_strategy(self):
        """编辑抓取策略"""
        if not self.current_page_config:
            QMessageBox.warning(self, "警告", "请先选择一个网站配置")
            return
        
        QMessageBox.information(self, "提示", "编辑策略功能正在开发中...\n\n当前策略信息将在此显示并允许编辑。")

    def start_crawl(self):
        """开始抓取"""
        if not self.current_page_config or not self.current_site_id:
            QMessageBox.warning(self, "警告", "请先选择配置")
            return
        
        # 获取配置和策略
        site = self.site_config_model.get(self.current_site_id)
        if not site:
            QMessageBox.warning(self, "警告", "未找到网站配置")
            return
            
        strategy = self.strategy_model.get_by_page(self.current_page_config['id'])
        
        if not strategy:
            QMessageBox.warning(self, "警告", "未找到抓取策略")
            return
        
        
        self.log("🚀 开始抓取任务...")
        self.start_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        
        # 使用已创建的爬虫引擎（已关联到browser_view）
        if not self.crawler_engine:
            self.crawler_engine = CrawlerEngine(self.browser_view)
        
        # 创建爬虫工作器（在主线程中执行）
        self.crawl_worker = CrawlWorker(
            self.crawler_engine, site['start_url'], self.current_page_config, strategy
        )
        self.crawl_worker.progress.connect(self.on_crawl_progress)
        self.crawl_worker.finished.connect(self.on_crawl_finished)
        self.crawl_worker.error.connect(self.on_crawl_error)
        
        # 在主线程中启动爬虫（使用QTimer确保不会阻塞UI）
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(100, self.crawl_worker.crawl)

    def pause_crawl(self):
        """暂停抓取"""
        if self.crawler_engine:
            if self.crawler_engine.is_paused:
                self.crawler_engine.resume()
                self.pause_btn.setText("⏸️ 暂停")
                self.log("▶️ 恢复抓取")
            else:
                self.crawler_engine.pause()
                self.pause_btn.setText("▶️ 继续")
                self.log("⏸️ 暂停抓取")

    def stop_crawl(self):
        """停止抓取"""
        if hasattr(self, 'crawl_worker'):
            self.crawl_worker.stop()
        if self.crawler_engine:
            self.crawler_engine.stop()
        self.log("⏹️ 停止抓取")

    def on_crawl_progress(self, progress: dict):
        """抓取进度更新"""
        current = progress.get("current_page", 0)
        total = progress.get("total_pages", 100)
        message = progress.get("message", "")
        
        percentage = int((current / total) * 100) if total > 0 else 0
        self.progress_bar.setValue(percentage)
        self.log(f"📊 {message}")

    def on_crawl_finished(self, data: list):
        """抓取完成"""
        self.log(f"✅ 抓取完成! 共获取 {len(data)} 条数据")
        
        # 导出数据
        if data and self.current_site_id:
            site = self.site_config_model.get(self.current_site_id)
            if site:
                filename = self.exporter.generate_filename(site['name'])
                results = self.exporter.export_multi_format(
                    data, filename, ["csv", "json", "excel"]
                )
                
                for fmt, path in results.items():
                    self.log(f"💾 已导出{fmt}格式: {path}")
        
        self.start_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setValue(100)
        
        QMessageBox.information(self, "完成", f"抓取完成! 共 {len(data)} 条数据")

    def on_crawl_error(self, error: str):
        """抓取错误"""
        self.log(f"❌ 错误: {error}")
        self.start_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        
        QMessageBox.critical(self, "错误", f"抓取失败: {error}")

    def log(self, message: str):
        """添加日志"""
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")

    def closeEvent(self, a0):  # type: ignore
        """关闭窗口事件"""
        if not a0:
            return
            
        if self.crawl_thread and self.crawl_thread.isRunning():
            reply = QMessageBox.question(
                self,
                "确认退出",
                "爬虫任务正在运行,确定要退出吗?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.stop_crawl()
                self.crawl_thread.wait()
                a0.accept()
            else:
                a0.ignore()
        else:
            self.db.close()
            a0.accept()
