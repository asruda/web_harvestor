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
        
        # 按照用户要求的列顺序
        required_columns = [
            "序号", "专利权人", "申请日", "专利名称", "专利号", 
            "授权公告日", "专利类型", "发明专利申请公布号", 
            "授权公告号", "案件状态", "主分类号"
        ]
        
        # 处理数据，只保留需要的字段
        processed_data = []
        for idx, record in enumerate(data, 1):
            # 创建新字典，只包含需要的字段
            processed_record = {}
            processed_record["序号"] = idx
            
            # 映射可能的字段名变体
            field_mappings = {
                "专利权人": ["专利权人", "申请人"],
                "申请日": ["申请日", "申请日期"],
                "专利名称": ["专利名称", "名称"],
                "专利号": ["专利号", "申请号"],
                "授权公告日": ["授权公告日", "公告日期"],
                "专利类型": ["专利类型", "类型"],
                "发明专利申请公布号": ["发明专利申请公布号", "公布号"],
                "授权公告号": ["授权公告号", "公告号"],
                "案件状态": ["案件状态", "状态"],
                "主分类号": ["主分类号", "分类号"]
            }
            
            # 填充字段值
            for target_col, source_cols in field_mappings.items():
                for source_col in source_cols:
                    if source_col in record:
                        processed_record[target_col] = record[source_col]
                        break
                else:
                    # 如果所有可能的源字段都不存在，设置为空字符串
                    processed_record[target_col] = ""
            
            processed_data.append(processed_record)
        
        with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=required_columns)
            writer.writeheader()
            writer.writerows(processed_data)
        
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
            
            # 按照用户要求的列顺序
            required_columns = [
                "序号", "专利权人", "申请日", "专利名称", "专利号", 
                "授权公告日", "专利类型", "发明专利申请公布号", 
                "授权公告号", "案件状态", "主分类号"
            ]
            
            # 处理数据，只保留需要的字段（复用CSV导出的处理逻辑）
            processed_data = []
            for idx, record in enumerate(data, 1):
                # 创建新字典，只包含需要的字段
                processed_record = {}
                processed_record["序号"] = idx
                
                # 映射可能的字段名变体
                field_mappings = {
                    "专利权人": ["专利权人", "申请人"],
                    "申请日": ["申请日", "申请日期"],
                    "专利名称": ["专利名称", "名称"],
                    "专利号": ["专利号", "申请号"],
                    "授权公告日": ["授权公告日", "公告日期"],
                    "专利类型": ["专利类型", "类型"],
                    "发明专利申请公布号": ["发明专利申请公布号", "公布号"],
                    "授权公告号": ["授权公告号", "公告号"],
                    "案件状态": ["案件状态", "状态"],
                    "主分类号": ["主分类号", "分类号"]
                }
                
                # 填充字段值
                for target_col, source_cols in field_mappings.items():
                    for source_col in source_cols:
                        if source_col in record:
                            processed_record[target_col] = record[source_col]
                            break
                    else:
                        # 如果所有可能的源字段都不存在，设置为空字符串
                        processed_record[target_col] = ""
                
                processed_data.append(processed_record)
            
            # 创建DataFrame并按照指定顺序排列列
            df = pd.DataFrame(processed_data)
            df = df[required_columns]  # 重新排列列顺序
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
