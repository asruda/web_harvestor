"""
数据提取器 - 使用BeautifulSoup提取表格数据
"""

from typing import List, Dict, Optional
from bs4 import BeautifulSoup
import re


class DataExtractor:
    """数据提取器"""

    def __init__(self):
        """初始化提取器"""
        pass

    def extract_table_data(
        self,
        html: str,
        table_selector: str,
        field_mappings: Dict[int, str],
        cleaning_rules: Optional[Dict] = None,
    ) -> List[Dict]:
        """
        从HTML中提取表格数据
        
        Args:
            html: HTML内容
            table_selector: 表格CSS选择器
            field_mappings: 列索引到字段名的映射 {0: "name", 1: "price"}
            cleaning_rules: 数据清洗规则
            
        Returns:
            提取的数据列表
        """
        soup = BeautifulSoup(html, "lxml")
        results = []

        # 查找表格
        table = soup.select_one(table_selector)
        if not table:
            return results

        # 查找所有行
        rows = table.find_all("tr")
        
        for row in rows:
            cells = row.find_all(["td", "th"])
            if not cells:
                continue

            row_data = {}
            for col_index, field_name in field_mappings.items():
                if col_index < len(cells):
                    cell = cells[col_index]
                    
                    # 提取文本内容
                    text = cell.get_text(strip=True)
                    
                    # 检查是否包含链接
                    link = cell.find("a")
                    if link and link.get("href"):
                        # 如果字段名包含"链接"或"url"，保存链接地址
                        if "链接" in field_name.lower() or "url" in field_name.lower():
                            text = link.get("href")
                        # 否则同时保存文本和链接
                        row_data[f"{field_name}_url"] = link.get("href")
                    
                    # 应用清洗规则
                    if cleaning_rules and field_name in cleaning_rules:
                        text = self._apply_cleaning_rule(text, cleaning_rules[field_name])
                    
                    row_data[field_name] = text

            if row_data:
                results.append(row_data)

        return results

    def _apply_cleaning_rule(self, text: str, rule: str) -> str:
        """应用数据清洗规则"""
        text = text.strip()
        
        if rule == "extract_number":
            # 提取数字
            numbers = re.findall(r"\d+\.?\d*", text)
            return numbers[0] if numbers else text
        elif rule == "remove_spaces":
            # 移除所有空格
            return re.sub(r"\s+", "", text)
        elif rule == "lowercase":
            # 转小写
            return text.lower()
        elif rule == "uppercase":
            # 转大写
            return text.upper()
        
        return text

    def extract_links(self, html: str, selector: str) -> List[str]:
        """提取页面中的链接"""
        soup = BeautifulSoup(html, "lxml")
        links = []
        
        elements = soup.select(selector)
        for element in elements:
            link = element.get("href")
            if link:
                links.append(link)
        
        return links

    def get_table_total_count(self, html: str, total_selector: str) -> Optional[int]:
        """获取表格数据总数"""
        try:
            soup = BeautifulSoup(html, "lxml")
            total_element = soup.select_one(total_selector)
            if total_element:
                text = total_element.get_text(strip=True)
                # 尝试提取数字
                numbers = re.findall(r"\d+", text)
                if numbers:
                    return int(numbers[0])
            return None
        except Exception as e:
            print(f"获取总数失败: {e}")
            return None

    def check_element_exists(self, html: str, selector: str) -> bool:
        """检查元素是否存在"""
        soup = BeautifulSoup(html, "lxml")
        return soup.select_one(selector) is not None
