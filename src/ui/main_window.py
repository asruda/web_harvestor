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
    QTextBrowser,
    QProgressBar,
    QSplitter,
    QMessageBox,
    QInputDialog,
    QDialog,
    QGroupBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QLineEdit
)
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt, QThread, QObject, pyqtSignal, QUrl
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEngineSettings, QWebEnginePage
from ..database.models import Database, SiteConfig, PageConfig, CrawlStrategy, FormConfig, CrawlTask
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
        self.page_config_id = page_config.get('id') if page_config else None
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
            data = self.engine.start_crawl(
                self.start_url,
                self.page_config,
                self.strategy,
                page_config_id = self.page_config_id,
                progress_callback = progress_callback,
            )
            
            if self.is_running:
                self.finished.emit(data)
        except Exception as e:
            self.error.emit(f"{str(e)}")
            import traceback
            error_info = f"错误: {str(e)}\n{traceback.format_exc()}"
            print(error_info)  # 同时打印到控制台以便调试

class FormConfigDialog(QDialog):
    """表单配置对话框"""
    
    def __init__(self, parent=None, form_config_model=None, page_config_id=None):
        super().__init__(parent)
        self.form_config_model = form_config_model
        self.page_config_id = page_config_id
        self.form_config = None
        self.init_ui()
    
    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("表单查询配置")
        self.resize(600, 400)
        
        # 主布局
        main_layout = QVBoxLayout(self)
        
        # 表单字段配置
        fields_group = QGroupBox("表单字段配置")
        fields_layout = QVBoxLayout()
        
        # 字段列表
        self.fields_table = QTableWidget()
        self.fields_table.setColumnCount(2)
        self.fields_table.setHorizontalHeaderLabels(["选择器", "默认值"])
        self.fields_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        fields_layout.addWidget(self.fields_table)
        
        # 按钮布局
        buttons_layout = QHBoxLayout()
        add_field_btn = QPushButton("添加字段")
        add_field_btn.clicked.connect(self.add_field)
        remove_field_btn = QPushButton("删除字段")
        remove_field_btn.clicked.connect(self.remove_field)
        buttons_layout.addWidget(add_field_btn)
        buttons_layout.addWidget(remove_field_btn)
        fields_layout.addLayout(buttons_layout)
        fields_group.setLayout(fields_layout)
        main_layout.addWidget(fields_group)
        
        # 查询按钮配置
        btn_group = QGroupBox("查询按钮配置")
        btn_layout = QVBoxLayout()
        
        # 简单选择器（向后兼容）
        simple_selector_layout = QHBoxLayout()
        simple_selector_layout.addWidget(QLabel("简单选择器:"))
        self.search_btn_selector = QLineEdit()
        self.search_btn_selector.setText(".search-button")
        simple_selector_layout.addWidget(self.search_btn_selector)
        btn_layout.addLayout(simple_selector_layout)
        
        # 高级JavaScript定位函数
        advanced_layout = QVBoxLayout()
        advanced_layout.addWidget(QLabel("高级定位函数 (JavaScript):"))
        self.search_btn_js_function = QTextEdit()
        self.search_btn_js_function.setMinimumHeight(200)
        self.search_btn_js_function.setPlaceholderText("输入JavaScript定位函数...")
        # 设置默认的多策略定位函数
        default_js_function = """
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
        console.log("✅ 使用策略 " + (i+1) + " 找到查询按钮:", strategy);
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
        console.log("❌ 策略 " + (i+1) + " 未找到按钮:", strategy);
    }
}

// 如果所有策略都失败，尝试查找所有包含"查询"的按钮并输出调试信息
console.log('🔍 备用方案：查找所有包含"查询"的按钮');
const allButtons = document.querySelectorAll('button');
const queryButtons = Array.from(allButtons).filter(btn =>
    btn.textContent.includes('查询')
);

console.log("📊 找到 " + queryButtons.length + " 个包含\"查询\"的按钮:");
queryButtons.forEach((btn, index) => {
    console.log("  按钮 " + (index+1) + ":", {
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
        """
        self.search_btn_js_function.setPlainText(default_js_function)
        btn_layout.addWidget(self.search_btn_js_function)
        
        btn_group.setLayout(btn_layout)
        main_layout.addWidget(btn_group)
        
        # 加载指示器选择器
        loading_layout = QHBoxLayout()
        loading_layout.addWidget(QLabel("加载指示器选择器:"))
        self.loading_selector = QLineEdit()
        self.loading_selector.setText(".q-loading")
        loading_layout.addWidget(self.loading_selector)
        main_layout.addLayout(loading_layout)
        
        # 结果ID字段名
        id_layout = QHBoxLayout()
        id_layout.addWidget(QLabel("结果ID字段名:"))
        self.result_id_field = QLineEdit()
        self.result_id_field.setText("申请号")
        id_layout.addWidget(self.result_id_field)
        main_layout.addLayout(id_layout)
        
        # 确认和取消按钮
        confirm_layout = QHBoxLayout()
        confirm_layout.addStretch()
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self.save_config)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        confirm_layout.addWidget(save_btn)
        confirm_layout.addWidget(cancel_btn)
        main_layout.addLayout(confirm_layout)
        
        # 加载现有配置
        self.load_config()
    
    def load_config(self):
        """加载现有配置"""
        if self.page_config_id:
            self.form_config = self.form_config_model.get_by_page(self.page_config_id)
            if self.form_config:
                # 填充表单字段
                fields = self.form_config.get("fields", {})
                self.fields_table.setRowCount(len(fields))
                row = 0
                for selector, default_value in fields.items():
                    selector_item = QTableWidgetItem(selector)
                    value_item = QTableWidgetItem(default_value)
                    self.fields_table.setItem(row, 0, selector_item)
                    self.fields_table.setItem(row, 1, value_item)
                    row += 1
                
                # 填充其他配置
                self.search_btn_selector.setText(self.form_config.get("search_button_selector", ".search-button"))
                self.search_btn_js_function.setPlainText(self.form_config.get("search_button_js_function", ""))
                self.loading_selector.setText(self.form_config.get("loading_selector", ".q-loading"))
                self.result_id_field.setText(self.form_config.get("result_id_field", "申请号"))
    
    def add_field(self):
        """添加字段"""
        row = self.fields_table.rowCount()
        self.fields_table.insertRow(row)
        selector_item = QTableWidgetItem("")
        value_item = QTableWidgetItem("")
        self.fields_table.setItem(row, 0, selector_item)
        self.fields_table.setItem(row, 1, value_item)
        self.fields_table.editItem(selector_item)
    
    def remove_field(self):
        """删除字段"""
        selected_rows = set()
        for item in self.fields_table.selectedItems():
            selected_rows.add(item.row())
        
        for row in sorted(selected_rows, reverse=True):
            self.fields_table.removeRow(row)
    
    def save_config(self):
        """保存配置"""
        # 收集表单字段
        fields = {}
        for row in range(self.fields_table.rowCount()):
            selector_item = self.fields_table.item(row, 0)
            value_item = self.fields_table.item(row, 1)
            
            if selector_item and value_item:
                selector = selector_item.text().strip()
                value = value_item.text().strip()
                if selector:
                    fields[selector] = value
        
        # 收集其他配置
        search_button_selector = self.search_btn_selector.text().strip()
        search_button_js_function = self.search_btn_js_function.toPlainText().strip()
        loading_selector = self.loading_selector.text().strip()
        result_id_field = self.result_id_field.text().strip()
        
        # 验证必要字段
        if not search_button_selector:
            QMessageBox.warning(self, "警告", "请输入查询按钮选择器")
            return
        
        if not result_id_field:
            QMessageBox.warning(self, "警告", "请输入结果ID字段名")
            return
        
        # 保存配置
        if self.form_config:
            # 更新现有配置
            self.form_config_model.update(
                self.form_config["id"],
                fields=fields,
                search_button_selector=search_button_selector,
                search_button_js_function=search_button_js_function,
                loading_selector=loading_selector,
                result_id_field=result_id_field,
            )
        else:
            # 创建新配置
            import uuid
            form_id = str(uuid.uuid4())
            self.form_config_model.create(
                form_id,
                self.page_config_id,
                fields=fields,
                search_button_selector=search_button_selector,
                search_button_js_function=search_button_js_function,
                loading_selector=loading_selector,
                result_id_field=result_id_field,
            )
        
        QMessageBox.information(self, "成功", "表单配置已保存")
        self.accept()


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.db = Database()
        self.site_config_model = SiteConfig(self.db)
        self.page_config_model = PageConfig(self.db)
        self.strategy_model = CrawlStrategy(self.db)
        self.form_config_model = FormConfig(self.db)
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
        
        # 默认全屏显示窗口
        self.showMaximized()
    
    def create_menus(self):
        """创建菜单栏"""
        menu_bar = self.menuBar()
        
        # 创建配置菜单
        config_menu = menu_bar.addMenu("配置")
        
        # 新建配置动作
        new_config_action = QAction("新建配置", self)
        new_config_action.triggered.connect(self.create_new_site_config)
        config_menu.addAction(new_config_action)

    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("网页数据抓取工具 v0.1.0")
        self.setGeometry(100, 100, 1280, 800)

        # 创建菜单栏
        self.create_menus()

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
        # 使用QTextBrowser而不是QTextEdit以支持链接点击功能
        self.log_text = QTextBrowser()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(100)  # 减少日志控件高度，为浏览器视图腾出更多空间
        # 启用富文本格式以支持HTML链接
        self.log_text.setOpenExternalLinks(False)  # 不自动打开外部链接，使用自定义处理
        # 连接anchorClicked信号到自定义槽函数
        self.log_text.anchorClicked.connect(self.on_anchor_clicked)
        
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
        # 移除最小高度限制，让浏览器视图能根据布局自由扩展
        
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
        
        # 添加组件到布局，并设置拉伸因子让浏览器视图占用更多空间
        layout.addWidget(self.browser_view, stretch=1)  # 设置拉伸因子为1，让浏览器视图优先占用额外空间

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

        # # 抓取策略
        # strategy_layout = QHBoxLayout()
        # strategy_layout.addWidget(QLabel("抓取策略:"))
        # self.strategy_label = QLabel("默认策略")
        # strategy_layout.addWidget(self.strategy_label)
        
        # # 添加编辑策略按钮
        # edit_strategy_btn = QPushButton("✏️ 编辑策略")
        # edit_strategy_btn.clicked.connect(self.edit_strategy)
        # strategy_layout.addWidget(edit_strategy_btn)
        
        # strategy_layout.addStretch()
        # layout.addLayout(strategy_layout)
        
        # 移除了表单查询配置相关选项

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
            from src.const.crawl import support_site
            if url not in support_site:
                self.log("❌ 不支持的网站URL")
                QMessageBox.critical(self, "错误", "❌ 不支持的网站URL")
                return
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
                
                # 创建默认表单配置
                form_id = str(uuid.uuid4())
                self.form_config_model.create(
                    form_id,
                    page_id,
                    fields={"input[name='applicant']": ""},
                    search_button_selector=".search-button",
                    loading_selector=".q-loading",
                    result_id_field="申请号",
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

    def open_form_config(self):
        """打开表单配置对话框"""
        if not self.current_page_config:
            QMessageBox.warning(self, "警告", "请先选择配置")
            return
        
        dialog = FormConfigDialog(
            self,
            form_config_model=self.form_config_model,
            page_config_id=self.current_page_config['id']
        )
        dialog.exec()
    
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
        
        # 使用普通抓取模式
        form_data = None
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
        # 传递页面配置ID给爬虫引擎
        if hasattr(self.crawler_engine, 'set_page_config_id'):
            self.crawler_engine.set_page_config_id(self.current_page_config['id'])
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
        self.log_text.append(f"📊 {message}")

    def on_crawl_finished(self, data: list):
        """抓取完成"""
        self.log_text.append(f"✅ 抓取完成! 共获取 {len(data)} 条数据")
        
        # 导出数据
        if data and self.current_site_id:
            site = self.site_config_model.get(self.current_site_id)
            if site:
                filename = self.exporter.generate_filename(site['name'])
                results = self.exporter.export_multi_format(
                    data, filename, ["csv", "json", "excel"]
                )
                
                for fmt, path in results.items():
                    # 确保路径可以被log方法正确识别为文件路径
                    # 如果路径不包含扩展名，添加扩展名
                    if not any(ext in path.lower() for ext in ['.csv', '.json', '.xlsx', '.txt']):
                        self.log(f"💾 已导出{fmt}格式: {path}")
                    else:
                        # 直接将完整路径传递给log方法，让它处理路径转换
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
        """添加日志，支持可点击的文件路径"""
        import datetime
        import re
        import os
        from pathlib import Path
        
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        
        # 检测消息中的文件路径并转换为可点击链接
        def replace_path(match):
            path = match.group(0)
            
            # 处理相对路径和绝对路径
            test_path = path
            
            # 检查路径是否存在
            if not os.path.exists(test_path):
                # 尝试相对于当前工作目录的路径
                current_dir = os.getcwd()
                rel_path = os.path.join(current_dir, path)
                if os.path.exists(rel_path):
                    test_path = rel_path
                else:
                    # 优先检查是否为data/exports开头的路径
                    if path.startswith('data/exports/') or path.startswith('data\\exports\\'):
                        # 相对于项目根目录构造完整路径
                        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                        # 获取相对路径部分（去掉data/exports/）
                        rel_part = path.split('exports', 1)[1].lstrip('/\\')
                        full_path = os.path.join(project_root, 'data', 'exports', rel_part)
                        if os.path.exists(full_path):
                            test_path = full_path
                    else:
                        # 尝试相对于项目根目录的data/exports路径
                        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                        exports_path = os.path.join(project_root, 'data', 'exports')
                        rel_export_path = os.path.join(exports_path, os.path.basename(path))
                        if os.path.exists(rel_export_path):
                            test_path = rel_export_path
            
            # 确保路径存在
            if os.path.exists(test_path):
                # 获取绝对路径以确保包含驱动器号
                abs_path = os.path.abspath(test_path)
                # 转换为HTML链接，使用正斜杠并确保正确的file:///格式
                file_url = f"file:///{abs_path.replace('\\', '/')}"
                # 使用更明显的样式显示可点击的文件名
                return f'<a href="{file_url}" style="color: blue; text-decoration: underline;">{os.path.basename(test_path)}</a>'
            return path
        
        # 优化的正则表达式，更宽松地匹配各种文件路径格式
        patterns = [
            # 捕获data/exports开头的路径，使用非贪婪匹配
            r'(data[\\/]exports[\\/].*?\.(csv|json|xlsx|txt|xls))(?=\s|$)',
            # 捕获任何带扩展名的文件路径，包含空格和特殊字符
            r'(\b[\\/\\w\\s\\.-]+?\.(csv|json|xlsx|txt|xls))(?=\s|$)',
            # 捕获带引号的路径
            r'["\'](.*?\.(csv|json|xlsx|txt|xls))["\']',
        ]
        
        formatted_message = message
        for pattern in patterns:
            # 使用re.MULTILINE标志确保在多行文本中也能正确匹配
            formatted_message = re.sub(pattern, replace_path, formatted_message, flags=re.MULTILINE)
        
        # 确保使用HTML格式
        self.log_text.append(f"[{timestamp}] {formatted_message}")

    def on_anchor_clicked(self, url):
        """处理QTextBrowser中的链接点击事件"""
        import os
        import sys
        import subprocess
        
        # 获取URL的字符串表示
        url_str = url.toString()
        
        # 专门处理file://链接
        if url_str.startswith('file://'):
            try:
                # 提取路径部分
                if url_str.startswith('file:///'):
                    file_path = url_str[8:]  # 处理file:///格式
                else:
                    file_path = url_str[7:]  # 处理file://格式
                
                # Windows路径特殊处理
                if os.name == 'nt':
                    # 修复Windows路径格式
                    file_path = file_path.lstrip('/').replace('/', '\\')
                
                # 尝试多种路径方式，按优先级排序
                test_paths = []
                
                # 1. 直接使用提取的路径（应该已经是绝对路径）
                if os.path.exists(file_path):
                    test_paths.append(file_path)
                
                # 2. 尝试绝对路径
                abs_path = os.path.abspath(file_path)
                if os.path.exists(abs_path) and abs_path not in test_paths:
                    test_paths.append(abs_path)
                
                # 3. 尝试相对于当前工作目录的路径
                current_dir = os.getcwd()
                rel_path = os.path.join(current_dir, file_path)
                if os.path.exists(rel_path) and rel_path not in test_paths:
                    test_paths.append(rel_path)
                
                # 4. 尝试相对于项目根目录的data/exports路径
                project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                exports_dir = os.path.join(project_root, 'data', 'exports')
                # 只取文件名部分，加入到exports目录
                file_name = os.path.basename(file_path)
                export_path = os.path.join(exports_dir, file_name)
                if os.path.exists(export_path) and export_path not in test_paths:
                    test_paths.append(export_path)
                
                # 记录尝试的路径，便于调试
                self.log(f"尝试打开文件: {file_name}")
                
                # 尝试打开找到的第一个有效路径
                if test_paths:
                    final_path = test_paths[0]
                    # self.log(f"找到文件: {final_path}")
                    
                    # Windows下使用多种方式尝试打开文件
                    if os.name == 'nt':
                        try:
                            # 方式1: 使用explorer.exe
                            # self.log(f"使用explorer.exe打开: {final_path}")
                            subprocess.run(['explorer.exe', final_path], shell=False, timeout=5)
                        except (subprocess.SubprocessError, TimeoutError):
                            try:
                                # 方式2: 使用cmd /c start命令
                                self.log(f"使用cmd /c start打开: {final_path}")
                                # 路径带引号以处理空格
                                subprocess.run(['cmd.exe', '/c', 'start', '', f'"{final_path}"'], shell=False, timeout=5)
                            except (subprocess.SubprocessError, TimeoutError):
                                # 方式3: 直接使用系统默认程序打开
                                self.log(f"直接使用系统默认程序打开: {final_path}")
                                os.startfile(final_path)
                    else:
                        # macOS和Linux
                        opener = 'open' if sys.platform == 'darwin' else 'xdg-open'
                        self.log(f"使用{opener}打开: {final_path}")
                        subprocess.Popen([opener, final_path])
                else:
                    # 所有路径都不存在时记录详细日志
                    self.log(f"无法找到文件: {file_path}")
                    self.log(f"尝试过的路径: {test_paths}")
                    self.log(f"当前工作目录: {os.getcwd()}")
                    self.log(f"项目导出目录: {exports_dir}")
            except Exception as e:
                # 异常处理，记录详细错误
                self.log(f"打开文件失败: {str(e)}")
                import traceback
                self.log(f"错误详情: {traceback.format_exc()}")
        else:
            # 非文件链接的处理
            self.log(f"不支持的链接类型: {url_str}")
    
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
