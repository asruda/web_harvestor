"""
数据库模型定义
Database Models
"""

import sqlite3
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path


class Database:
    """数据库管理类"""

    def __init__(self, db_path: str = "config/sites.db"):
        """初始化数据库连接"""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn: Optional[sqlite3.Connection] = None
        self.init_database()

    def connect(self):
        """连接数据库"""
        if not self.conn:
            self.conn = sqlite3.connect(str(self.db_path))
            self.conn.row_factory = sqlite3.Row
        return self.conn

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            self.conn = None

    def init_database(self):
        """初始化数据库表结构"""
        conn = self.connect()
        cursor = conn.cursor()

        # 网站配置表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS site_configs (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                start_url TEXT NOT NULL,
                target_url_pattern TEXT,
                cookie_path TEXT,
                session_validation_rule TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_used_at TEXT
            )
        """)

        # 页面配置表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS page_configs (
                id TEXT PRIMARY KEY,
                site_config_id TEXT NOT NULL,
                name TEXT NOT NULL,
                page_identification_rule TEXT,
                table_selector TEXT,
                field_mappings TEXT,
                data_cleaning_rules TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (site_config_id) REFERENCES site_configs(id) ON DELETE CASCADE
            )
        """)

        # 抓取策略表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS crawl_strategies (
                id TEXT PRIMARY KEY,
                page_config_id TEXT NOT NULL,
                pagination_type TEXT,
                pagination_params TEXT,
                max_pages INTEGER DEFAULT 100,
                enable_link_tracking INTEGER DEFAULT 0,
                link_extraction_rule TEXT,
                link_filter_rule TEXT,
                tracking_depth INTEGER DEFAULT 1,
                dedup_strategy TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (page_config_id) REFERENCES page_configs(id) ON DELETE CASCADE
            )
        """)
        
        # 表单查询配置表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS form_configs (
                id TEXT PRIMARY KEY,
                page_config_id TEXT NOT NULL,
                fields TEXT,  -- JSON格式存储表单字段选择器和默认值
                search_button_selector TEXT,
                search_button_js_function TEXT,  -- 高级JavaScript定位函数
                loading_selector TEXT,
                result_id_field TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (page_config_id) REFERENCES page_configs(id) ON DELETE CASCADE
            )
        """)

        # 抓取任务表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS crawl_tasks (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                page_config_id TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                started_at TEXT,
                completed_at TEXT,
                pages_crawled INTEGER DEFAULT 0,
                records_crawled INTEGER DEFAULT 0,
                export_formats TEXT,
                export_path TEXT,
                error_message TEXT,
                FOREIGN KEY (page_config_id) REFERENCES page_configs(id)
            )
        """)

        # 抓取结果数据表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS crawl_results (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                source_url TEXT,
                data TEXT,
                crawled_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES crawl_tasks(id) ON DELETE CASCADE
            )
        """)

        conn.commit()

    def execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """执行SQL语句"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        return cursor

    def fetchone(self, query: str, params: tuple = ()) -> Optional[Dict]:
        """查询单条记录"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(query, params)
        row = cursor.fetchone()
        return dict(row) if row else None

    def fetchall(self, query: str, params: tuple = ()) -> List[Dict]:
        """查询多条记录"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


class SiteConfig:
    """网站配置模型"""

    def __init__(self, db: Database):
        self.db = db

    def create(
        self,
        id: str,
        name: str,
        start_url: str,
        target_url_pattern: str = "",
        cookie_path: str = "",
        session_validation_rule: str = "",
    ) -> str:
        """创建网站配置"""
        self.db.execute(
            """
            INSERT INTO site_configs 
            (id, name, start_url, target_url_pattern, cookie_path, session_validation_rule)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (id, name, start_url, target_url_pattern, cookie_path, session_validation_rule),
        )
        return id

    def get(self, id: str) -> Optional[Dict]:
        """获取网站配置"""
        return self.db.fetchone("SELECT * FROM site_configs WHERE id = ?", (id,))

    def get_all(self) -> List[Dict]:
        """获取所有网站配置"""
        return self.db.fetchall("SELECT * FROM site_configs ORDER BY last_used_at DESC")

    def update(self, id: str, **kwargs):
        """更新网站配置"""
        fields = ", ".join(f"{k} = ?" for k in kwargs.keys())
        values = tuple(kwargs.values()) + (id,)
        self.db.execute(f"UPDATE site_configs SET {fields} WHERE id = ?", values)

    def delete(self, id: str):
        """删除网站配置"""
        self.db.execute("DELETE FROM site_configs WHERE id = ?", (id,))

    def update_last_used(self, id: str):
        """更新最后使用时间"""
        self.db.execute(
            "UPDATE site_configs SET last_used_at = ? WHERE id = ?",
            (datetime.now().isoformat(), id),
        )


class PageConfig:
    """页面配置模型"""

    def __init__(self, db: Database):
        self.db = db

    def create(
        self,
        id: str,
        site_config_id: str,
        name: str,
        table_selector: str,
        field_mappings: Dict,
        page_identification_rule: str = "",
        data_cleaning_rules: Optional[Dict] = None,
    ) -> str:
        """创建页面配置"""
        self.db.execute(
            """
            INSERT INTO page_configs 
            (id, site_config_id, name, page_identification_rule, 
             table_selector, field_mappings, data_cleaning_rules)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                id,
                site_config_id,
                name,
                page_identification_rule,
                table_selector,
                json.dumps(field_mappings),
                json.dumps(data_cleaning_rules or {}),
            ),
        )
        return id

    def get(self, id: str) -> Optional[Dict]:
        """获取页面配置"""
        config = self.db.fetchone("SELECT * FROM page_configs WHERE id = ?", (id,))
        if config:
            config["field_mappings"] = json.loads(config["field_mappings"])
            config["data_cleaning_rules"] = json.loads(config["data_cleaning_rules"])
        return config

    def get_by_site(self, site_config_id: str) -> List[Dict]:
        """获取网站下的所有页面配置"""
        configs = self.db.fetchall(
            "SELECT * FROM page_configs WHERE site_config_id = ?", (site_config_id,)
        )
        for config in configs:
            config["field_mappings"] = json.loads(config["field_mappings"])
            config["data_cleaning_rules"] = json.loads(config["data_cleaning_rules"])
        return configs

    def delete(self, id: str):
        """删除页面配置"""
        self.db.execute("DELETE FROM page_configs WHERE id = ?", (id,))


class CrawlStrategy:
    """抓取策略模型"""

    def __init__(self, db: Database):
        self.db = db

    def create(
        self,
        id: str,
        page_config_id: str,
        pagination_type: str = "button",
        pagination_params: Optional[Dict] = None,
        max_pages: int = 100,
        enable_link_tracking: bool = False,
        link_extraction_rule: str = "",
        tracking_depth: int = 1,
    ) -> str:
        """创建抓取策略"""
        self.db.execute(
            """
            INSERT INTO crawl_strategies 
            (id, page_config_id, pagination_type, pagination_params, max_pages,
             enable_link_tracking, link_extraction_rule, tracking_depth)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                id,
                page_config_id,
                pagination_type,
                json.dumps(pagination_params or {}),
                max_pages,
                1 if enable_link_tracking else 0,
                link_extraction_rule,
                tracking_depth,
            ),
        )
        return id

    def get_by_page(self, page_config_id: str) -> Optional[Dict]:
        """获取页面的抓取策略"""
        strategy = self.db.fetchone(
            "SELECT * FROM crawl_strategies WHERE page_config_id = ?", (page_config_id,)
        )
        if strategy:
            strategy["pagination_params"] = json.loads(strategy["pagination_params"])
            strategy["enable_link_tracking"] = bool(strategy["enable_link_tracking"])
        return strategy


class FormConfig:
    """表单查询配置模型"""

    def __init__(self, db: Database):
        self.db = db

    def create(
        self,
        id: str,
        page_config_id: str,
        fields: Optional[Dict] = None,
        search_button_selector: str = ".search-button",
        search_button_js_function: Optional[str] = None,
        loading_selector: str = ".q-loading",
        result_id_field: str = "申请号",
    ) -> str:
        """创建表单查询配置"""
        self.db.execute(
            """
            INSERT INTO form_configs 
            (id, page_config_id, fields, search_button_selector, 
             search_button_js_function, loading_selector, result_id_field)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                id,
                page_config_id,
                json.dumps(fields or {}),
                search_button_selector,
                search_button_js_function,
                loading_selector,
                result_id_field,
            ),
        )
        return id

    def get_by_page(self, page_config_id: str) -> Optional[Dict]:
        """获取页面的表单查询配置"""
        config = self.db.fetchone(
            "SELECT * FROM form_configs WHERE page_config_id = ?", (page_config_id,)
        )
        if config:
            config["fields"] = json.loads(config["fields"])
        return config

    def update(
        self,
        id: str,
        fields: Optional[Dict] = None,
        search_button_selector: Optional[str] = None,
        search_button_js_function: Optional[str] = None,
        loading_selector: Optional[str] = None,
        result_id_field: Optional[str] = None,
    ):
        """更新表单查询配置"""
        update_fields = {}
        if fields is not None:
            update_fields["fields"] = json.dumps(fields)
        if search_button_selector is not None:
            update_fields["search_button_selector"] = search_button_selector
        if search_button_js_function is not None:
            update_fields["search_button_js_function"] = search_button_js_function
        if loading_selector is not None:
            update_fields["loading_selector"] = loading_selector
        if result_id_field is not None:
            update_fields["result_id_field"] = result_id_field
        
        if update_fields:
            fields_str = ", ".join(f"{k} = ?" for k in update_fields.keys())
            values = tuple(update_fields.values()) + (id,)
            self.db.execute(f"UPDATE form_configs SET {fields_str} WHERE id = ?", values)


class CrawlTask:
    """抓取任务模型"""

    def __init__(self, db: Database):
        self.db = db

    def create(
        self, id: str, name: str, page_config_id: str, export_formats: List[str], export_path: str
    ) -> str:
        """创建抓取任务"""
        self.db.execute(
            """
            INSERT INTO crawl_tasks 
            (id, name, page_config_id, export_formats, export_path, status)
            VALUES (?, ?, ?, ?, ?, 'pending')
            """,
            (id, name, page_config_id, json.dumps(export_formats), export_path),
        )
        return id

    def get(self, id: str) -> Optional[Dict]:
        """获取任务"""
        task = self.db.fetchone("SELECT * FROM crawl_tasks WHERE id = ?", (id,))
        if task and task["export_formats"]:
            task["export_formats"] = json.loads(task["export_formats"])
        return task

    def get_all(self, limit: int = 50) -> List[Dict]:
        """获取所有任务"""
        tasks = self.db.fetchall(
            "SELECT * FROM crawl_tasks ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        for task in tasks:
            if task["export_formats"]:
                task["export_formats"] = json.loads(task["export_formats"])
        return tasks

    def update_status(
        self, id: str, status: str, pages_crawled: int = 0, records_crawled: int = 0
    ):
        """更新任务状态"""
        update_fields = {"status": status, "pages_crawled": pages_crawled, "records_crawled": records_crawled}
        
        task = self.get(id)
        if status == "running" and task and not task.get("started_at"):
            update_fields["started_at"] = datetime.now().isoformat()
        elif status in ["completed", "failed"]:
            update_fields["completed_at"] = datetime.now().isoformat()

        fields = ", ".join(f"{k} = ?" for k in update_fields.keys())
        values = tuple(update_fields.values()) + (id,)
        self.db.execute(f"UPDATE crawl_tasks SET {fields} WHERE id = ?", values)

    def add_result(self, task_id: str, result_id: str, source_url: str, data: Dict):
        """添加抓取结果"""
        self.db.execute(
            """
            INSERT INTO crawl_results (id, task_id, source_url, data)
            VALUES (?, ?, ?, ?)
            """,
            (result_id, task_id, source_url, json.dumps(data)),
        )

    def get_results(self, task_id: str) -> List[Dict]:
        """获取任务的所有结果"""
        results = self.db.fetchall(
            "SELECT * FROM crawl_results WHERE task_id = ? ORDER BY crawled_at", (task_id,)
        )
        for result in results:
            result["data"] = json.loads(result["data"])
        return results
