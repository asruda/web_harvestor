#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据库迁移脚本 - 添加缺失的search_button_js_function列
"""

import sqlite3
import os
from pathlib import Path

def migrate_database():
    """执行数据库迁移"""
    # 获取数据库路径
    db_path = Path("config/sites.db")
    
    # 检查数据库文件是否存在
    if not db_path.exists():
        print("数据库文件不存在，无需迁移")
        return
    
    print(f"开始迁移数据库: {db_path}")
    
    try:
        # 连接数据库
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # 检查列是否存在
        cursor.execute("PRAGMA table_info(form_configs)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if "search_button_js_function" not in columns:
            print("添加search_button_js_function列...")
            cursor.execute("""
                ALTER TABLE form_configs 
                ADD COLUMN search_button_js_function TEXT
            """)
            conn.commit()
            print("✓ 成功添加search_button_js_function列")
        else:
            print("✓ search_button_js_function列已存在")
        
    except Exception as e:
        print(f"✗ 迁移失败: {e}")
        return False
    finally:
        if conn:
            conn.close()
    
    print("✓ 数据库迁移完成")
    return True

if __name__ == "__main__":
    migrate_database()