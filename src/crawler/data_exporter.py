"""
数据导出器 - 支持多种格式导出
"""

import csv
import json
from pathlib import Path
from typing import List, Dict
from datetime import datetime


class DataExporter:
    """数据导出器"""

    def __init__(self, export_dir: str = "data/exports"):
        """初始化导出器"""
        self.export_dir = Path(export_dir)
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def export_to_csv(self, data: List[Dict], filename: str) -> str:
        """导出为CSV格式"""
        if not data:
            return ""

        filepath = self.export_dir / f"{filename}.csv"
        
        # 获取所有字段
        fieldnames = list(data[0].keys())
        
        with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
        
        return str(filepath)

    def export_to_json(self, data: List[Dict], filename: str) -> str:
        """导出为JSON格式"""
        filepath = self.export_dir / f"{filename}.json"
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return str(filepath)

    def export_to_text(self, data: List[Dict], filename: str) -> str:
        """导出为纯文本格式"""
        filepath = self.export_dir / f"{filename}.txt"
        
        with open(filepath, "w", encoding="utf-8") as f:
            for i, record in enumerate(data, 1):
                f.write(f"=== 记录 {i} ===\n")
                for key, value in record.items():
                    f.write(f"{key}: {value}\n")
                f.write("\n")
        
        return str(filepath)

    def export_to_excel(self, data: List[Dict], filename: str) -> str:
        """导出为Excel格式"""
        try:
            import pandas as pd
            
            filepath = self.export_dir / f"{filename}.xlsx"
            df = pd.DataFrame(data)
            df.to_excel(filepath, index=False, engine="openpyxl")
            
            return str(filepath)
        except ImportError:
            # 如果pandas不可用，降级为CSV
            print("pandas未安装，使用CSV格式替代")
            return self.export_to_csv(data, filename)

    def export_multi_format(
        self, data: List[Dict], base_filename: str, formats: List[str]
    ) -> Dict[str, str]:
        """导出多种格式"""
        results = {}
        
        for fmt in formats:
            if fmt.lower() == "csv":
                results["csv"] = self.export_to_csv(data, base_filename)
            elif fmt.lower() == "json":
                results["json"] = self.export_to_json(data, base_filename)
            elif fmt.lower() == "excel" or fmt.lower() == "xlsx":
                results["excel"] = self.export_to_excel(data, base_filename)
            elif fmt.lower() == "text" or fmt.lower() == "txt":
                results["text"] = self.export_to_text(data, base_filename)
        
        return results

    def generate_filename(self, task_name: str) -> str:
        """生成带时间戳的文件名"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # 清理任务名称中的特殊字符
        safe_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in task_name)
        return f"{safe_name}_{timestamp}"
