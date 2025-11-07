"""
主窗口 - PyQt6主界面
"""

import sys
import asyncio
import os
import platform
import uuid
from typing import Any, Optional
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
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEngineSettings, QWebEnginePage
from ..database.models import Database, SiteConfig, PageConfig, CrawlStrategy, CrawlTask
from ..crawler.crawler_engine import CrawlerEngine
from ..crawler.data_exporter import DataExporter

# 创建全局自定义配置文件实例
_persistent_profile = None

# 在应用程序开始时创建自定义配置文件，确保所有QWebEngineView实例都使用正确的缓存设置
def setup_web_engine_profile():
    """创建并配置自定义的WebEngine配置文件以启用持久化存储"""
    global _persistent_profile
    
    try:
        # 创建存储目录
        app_data_dir = os.path.join(os.path.expanduser('~'), '.web_crawler_tool')
        cache_dir = os.path.join(app_data_dir, 'cache')
        data_dir = os.path.join(app_data_dir, 'data')
        
        for dir_path in [app_data_dir, cache_dir, data_dir]:
            if not os.path.exists(dir_path):
                os.makedirs(dir_path, exist_ok=True)
                print(f"[配置] 创建存储目录: {dir_path}")
        
        # 创建一个全新的自定义配置文件，而不是修改默认配置文件
        # 这是确保缓存正确工作的关键
        _persistent_profile = QWebEngineProfile("persistent_browser", None)
        
        # 设置缓存和存储路径
        _persistent_profile.setCachePath(cache_dir)
        _persistent_profile.setPersistentStoragePath(data_dir)
        
        # 强制使用持久化Cookie策略
        _persistent_profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
        
        # 设置为磁盘缓存模式
        _persistent_profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.DiskHttpCache)
        
        # 设置缓存大小限制
        _persistent_profile.setHttpCacheMaximumSize(50 * 1024 * 1024)  # 50MB
        
        # 验证配置
        print(f"[配置] 已创建并配置自定义WebEngine配置文件:")
        print(f"  - 缓存路径: {_persistent_profile.cachePath()}")
        print(f"  - 持久存储路径: {_persistent_profile.persistentStoragePath()}")
        print(f"  - Cookie策略: {_persistent_profile.persistentCookiesPolicy()}")
        print(f"  - 缓存类型: {_persistent_profile.httpCacheType()}")
        
        print("[配置] 自定义WebEngine配置文件已准备就绪")
        return True
    except Exception as e:
        print(f"[配置] 创建WebEngine配置文件时出错: {str(e)}")
        return False

def get_persistent_profile():
    """获取自定义的持久化配置文件"""
    global _persistent_profile
    return _persistent_profile


class CrawlWorker(QObject):
    """爬虫工作器，用于在主线程中执行爬虫操作"""
    progress = pyqtSignal(dict)
    finished = pyqtSignal(list)
    error = pyqtSignal(str)
    
    def __init__(self, engine: CrawlerEngine, start_url: str, page_config: dict, strategy: dict, form_data: dict = None):
        super().__init__()
        self.engine = engine
        self.start_url = start_url
        self.page_config = page_config
        self.strategy = strategy
        self.form_data = form_data  # 表单数据，用于表单查询
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
            
            # 根据是否有表单数据选择不同的抓取方法
            if self.form_data:
                # 使用表单查询抓取
                data = self.engine.start_crawl_with_form(
                    self.start_url,
                    self.page_config,
                    self.strategy,
                    self.form_data,
                    progress_callback,
                )
            else:
                # 使用普通抓取
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
        
        # 获取自定义配置文件
        self.profile = get_persistent_profile()
        print("📋 WebEngine配置文件关联状态:")
        print(f"  - 配置文件状态: {'已准备就绪' if self.profile else '未设置'}")
        
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

        # 先创建日志控件，确保log方法可用
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        
        # 浏览器视图 - 使用 QWebEngineView，应用自定义配置文件
        if self.profile:
            # 创建一个与自定义配置文件关联的页面
            page = QWebEnginePage(self.profile, self)
            # 创建浏览器视图
            self.browser_view = QWebEngineView()
            # 将自定义页面设置到浏览器视图
            self.browser_view.setPage(page)
            print("✅ 已成功将自定义配置文件应用到浏览器视图")
        else:
            # 如果自定义配置文件不可用，使用默认方式创建
            self.browser_view = QWebEngineView()
            print("⚠️ 使用默认配置创建浏览器视图")
            
        self.browser_view.setFixedWidth(1440)
        self.browser_view.setMinimumHeight(300)
        
        # 添加错误处理和调试信号连接
        self.browser_view.loadStarted.connect(lambda: self.log("🌐 页面开始加载"))
        self.browser_view.loadFinished.connect(lambda success: 
            self.log(f"🌐 页面加载完成: {'成功' if success else '失败'}, 浏览器宽度: {self.browser_view.width()}px")
        )
        self.browser_view.loadProgress.connect(lambda progress: 
            self.log(f"🌐 加载进度: {progress}%") if progress % 20 == 0 else None
        )
        
        # 捕获URL变化
        self.browser_view.urlChanged.connect(lambda url: 
            self.log(f"🌐 URL变化: {url.toString()}")
        )
        
        # 增强的浏览器设置，特别是针对政府网站访问
        from PyQt6.QtWebEngineCore import QWebEngineSettings, QWebEngineProfile
        settings = self.browser_view.page().settings()
        
        # 只设置基本必要的属性，避免使用可能不存在的属性
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.ErrorPageEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.AllowRunningInsecureContent, True)
        
        # 设置持久化存储路径以保持登录状态
        import os
        import platform
        app_data_dir = os.path.join(os.path.expanduser('~'), '.web_crawler_tool')
        cache_dir = os.path.join(app_data_dir, 'cache')
        data_dir = os.path.join(app_data_dir, 'data')
        
        print(f"🖥️  操作系统: {platform.system()}, Python版本: {platform.python_version()}")
        
        # 检查存储目录状态
        try:
            for dir_path in [app_data_dir, cache_dir, data_dir]:
                if os.path.exists(dir_path):
                    print(f"✅ 确认存储目录存在: {dir_path}")
                    if os.access(dir_path, os.W_OK):
                        print(f"🔓 目录可写: {dir_path}")
                    else:
                        print(f"🔒 目录不可写: {dir_path}")
                else:
                    print(f"❌ 目录不存在: {dir_path}")
            
            # 验证浏览器视图使用的配置
            profile = self.browser_view.page().profile()
            print(f"📋 当前浏览器视图配置:")
            print(f"  - 缓存路径: {profile.cachePath()}")
            print(f"  - 持久存储路径: {profile.persistentStoragePath()}")
            print(f"  - Cookie策略: {profile.persistentCookiesPolicy()}")
            print(f"  - 缓存类型: {profile.httpCacheType()}")
            print(f"  - 配置文件名称: {profile.storageName()}")
            
            # 尝试在缓存目录中创建一个临时文件来测试写入权限
            try:
                test_file_path = os.path.join(profile.cachePath(), '.test_write')
                with open(test_file_path, 'w') as f:
                    f.write('test')
                os.remove(test_file_path)
                print(f"✅ 成功验证缓存目录写入权限: {profile.cachePath()}")
            except Exception as write_error:
                print(f"🔴 验证缓存目录写入权限失败: {str(write_error)}")
            
            self.log("✅ 浏览器已使用全局配置文件，将保持登录状态")
        except Exception as e:
            print(f"⚠️  检查浏览器配置时出错: {str(e)}")
            self.log(f"⚠️  检查浏览器配置时出错: {str(e)}")
            
        # 为当前视图启用必要的设置
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.ErrorPageEnabled, True)
        
        # 设置用户代理（使用现代浏览器标识）
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36"
        profile.setHttpUserAgent(user_agent)
        
        self.log("✅ 浏览器持久化存储已配置，将保持登录状态")
        # 添加SSL证书错误处理
        def handle_certificate_error(web_engine_page, certificate_error):
            # 记录证书错误但继续加载（仅用于测试，生产环境应谨慎处理）
            error_str = certificate_error.errorDescription()
            self.log(f"⚠️ SSL证书错误: {error_str}")
            certificate_error.ignoreCertificateError()
            return True
        
        self.browser_view.page().certificateError.connect(handle_certificate_error)
        
        # 添加页面错误处理
        self.browser_view.page().loadStarted.connect(lambda: self.log("🌐 页面开始加载"))
        self.browser_view.page().loadFinished.connect(lambda success: 
            self.log(f"🌐 页面加载完成: {'成功' if success else '失败'}")
        )
        
        # 添加组件到布局
        layout.addWidget(self.browser_view)

        # 控制面板
        control_panel = self.create_control_panel()
        layout.addWidget(control_panel)

        # 进度条
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)
        
        # 添加日志控件到布局
        layout.addWidget(self.log_text)

        return panel
    
    def handle_js_console_message(self, level, message, line_number, source_id):
        """处理JavaScript控制台消息"""
        level_str = "信息"
        if level == self.browser_view.page().JavaScriptConsoleMessageLevel.InfoMessageLevel:
            level_str = "信息"
        elif level == self.browser_view.page().JavaScriptConsoleMessageLevel.WarningMessageLevel:
            level_str = "警告"
        elif level == self.browser_view.page().JavaScriptConsoleMessageLevel.ErrorMessageLevel:
            level_str = "错误"
        
        self.log(f"📜 JS {level_str} ({source_id}:{line_number}): {message}")

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
        
        # 表单查询配置（简化版）
        form_layout = QVBoxLayout()
        form_layout.addWidget(QLabel("📝 表单查询配置:"))
        
        # 表单字段配置（灵活版）
        field_layout = QHBoxLayout()
        field_layout.addWidget(QLabel("字段选择器:"))
        from PyQt6.QtWidgets import QLineEdit
        self.field_selector = QLineEdit()
        self.field_selector.setText("input[name='applicant']")
        self.field_selector.setPlaceholderText("例如: input[name='applicant'] 或 #search-input")
        field_layout.addWidget(self.field_selector)
        form_layout.addLayout(field_layout)
        
        # 字段值
        value_layout = QHBoxLayout()
        value_layout.addWidget(QLabel("字段值:"))
        self.field_value = QLineEdit()
        self.field_value.setPlaceholderText("输入要查询的值")
        value_layout.addWidget(self.field_value)
        form_layout.addLayout(value_layout)
        
        # 查询按钮选择器
        search_btn_layout = QHBoxLayout()
        search_btn_layout.addWidget(QLabel("查询按钮选择器:"))
        self.search_btn_selector = QLineEdit()
        self.search_btn_selector.setText(".search-button")
        self.search_btn_selector.setPlaceholderText("例如: .search-button 或 #search")
        search_btn_layout.addWidget(self.search_btn_selector)
        form_layout.addLayout(search_btn_layout)
        
        # 加载指示器选择器
        loading_layout = QHBoxLayout()
        loading_layout.addWidget(QLabel("加载指示器选择器:"))
        self.loading_selector = QLineEdit()
        self.loading_selector.setText(".q-loading")
        self.loading_selector.setPlaceholderText("例如: .loading 或 #loading-indicator")
        loading_layout.addWidget(self.loading_selector)
        form_layout.addLayout(loading_layout)
        
        # 结果ID字段名
        result_id_layout = QHBoxLayout()
        result_id_layout.addWidget(QLabel("结果ID字段名:"))
        self.result_id_field = QLineEdit()
        self.result_id_field.setText("申请号")
        self.result_id_field.setPlaceholderText("用于去重的字段名")
        result_id_layout.addWidget(self.result_id_field)
        form_layout.addLayout(result_id_layout)
        
        form_layout.addWidget(QLabel("提示: 留空字段值将使用普通抓取模式"))
        layout.addLayout(form_layout)

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
        
        # 检查是否使用表单查询模式
        form_data = None
        if hasattr(self, 'field_value') and self.field_value.text().strip():
            # 使用表单查询模式
            field_value = self.field_value.text().strip()
            field_selector = self.field_selector.text().strip() or "input[name='applicant']"
            search_btn_selector = self.search_btn_selector.text().strip()
            loading_selector = self.loading_selector.text().strip()
            result_id_field = self.result_id_field.text().strip()
            
            # 构建表单数据
            form_data = {
                "fields": {
                    field_selector: field_value,  # 使用用户配置的字段选择器
                },
                "search_button_selector": search_btn_selector or ".search-button",
                "loading_selector": loading_selector or ".q-loading",
                "result_id_field": result_id_field or "申请号"
            }
            
            self.log(f"🔍 开始表单查询抓取 - 字段: {field_selector}, 值: {field_value}")
        else:
            self.log("🚀 开始普通抓取任务...")
        
        self.start_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        
        # 使用已创建的爬虫引擎（已关联到browser_view）
        if not self.crawler_engine:
            self.crawler_engine = CrawlerEngine(self.browser_view)
        
        # 创建爬虫工作器（在主线程中执行）
        self.crawl_worker = CrawlWorker(
            self.crawler_engine, site['start_url'], self.current_page_config, strategy, form_data
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
