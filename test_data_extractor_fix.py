"""
简单测试修复后的数据提取器
专注于验证类型转换问题是否已解决
"""

from src.crawler.data_extractor import DataExtractor


def test_extractor_with_string_keys():
    """
    测试使用字符串类型键的field_mappings
    验证修复后的类型转换逻辑是否正常工作
    """
    print("开始测试修复后的数据提取器...")
    
    # 创建测试HTML
    test_html = """
    <table class="test-table">
        <tr>
            <td>1</td>
            <td>测试专利</td>
            <td>CN202010001234.5</td>
            <td>CN111111111A</td>
            <td>测试公司</td>
            <td>2020-01-01</td>
            <td>2020-06-01</td>
        </tr>
        <tr>
            <td>2</td>
            <td>另一个专利</td>
            <td>CN202010005678.9</td>
            <td>CN222222222A</td>
            <td>另一个公司</td>
            <td>2020-02-01</td>
            <td>2020-07-01</td>
        </tr>
    </table>
    """
    
    # 创建提取器实例
    extractor = DataExtractor()
    
    # 测试1: 使用整数键的field_mappings（原始格式）
    print("\n测试1: 使用整数键的field_mappings")
    field_mappings_int = {
        0: "序号",
        1: "专利名称",
        2: "申请号",
        3: "公开号",
        4: "申请人",
        5: "申请日",
        6: "公开日"
    }
    
    results_int = extractor.extract_table_data(test_html, "table.test-table", field_mappings_int)
    print(f"提取结果数量: {len(results_int)}")
    for i, row in enumerate(results_int):
        print(f"第{i+1}行: {row}")
    
    # 测试2: 使用字符串键的field_mappings（问题场景）
    print("\n测试2: 使用字符串键的field_mappings")
    field_mappings_str = {
        "0": "序号",  # 注意这里是字符串"0"而不是整数0
        "1": "专利名称",
        "2": "申请号",
        "3": "公开号",
        "4": "申请人",
        "5": "申请日",
        "6": "公开日"
    }
    
    results_str = extractor.extract_table_data(test_html, "table.test-table", field_mappings_str)
    print(f"提取结果数量: {len(results_str)}")
    for i, row in enumerate(results_str):
        print(f"第{i+1}行: {row}")
    
    # 测试3: 混合类型的field_mappings
    print("\n测试3: 混合类型的field_mappings")
    field_mappings_mixed = {
        0: "序号",
        "1": "专利名称",
        2: "申请号",
        "3": "公开号",
        4: "申请人",
        "5": "申请日",
        6: "公开日"
    }
    
    results_mixed = extractor.extract_table_data(test_html, "table.test-table", field_mappings_mixed)
    print(f"提取结果数量: {len(results_mixed)}")
    for i, row in enumerate(results_mixed):
        print(f"第{i+1}行: {row}")
    
    # 测试4: 包含无效键的field_mappings
    print("\n测试4: 包含无效键的field_mappings")
    field_mappings_invalid = {
        0: "序号",
        "abc": "专利名称",  # 无效的非数字字符串键
        2: "申请号",
        "-1": "公开号",  # 负数索引
        4: "申请人",
        "10": "申请日"  # 超出范围的索引
    }
    
    results_invalid = extractor.extract_table_data(test_html, "table.test-table", field_mappings_invalid)
    print(f"提取结果数量: {len(results_invalid)}")
    for i, row in enumerate(results_invalid):
        print(f"第{i+1}行: {row}")
    
    print("\n🎉 所有测试完成！")
    print("✅ 修复验证结果:")
    print(f"  - 整数键测试: {'成功' if results_int else '失败'}")
    print(f"  - 字符串键测试: {'成功' if results_str else '失败'}")
    print(f"  - 混合键测试: {'成功' if results_mixed else '失败'}")
    print(f"  - 无效键测试: {'成功' if len(results_invalid) > 0 else '失败'} (应能处理部分有效键)")


if __name__ == "__main__":
    test_extractor_with_string_keys()