"""
项目验证测试脚本
"""

import sys
import os

def test_imports():
    """测试模块导入"""
    print("=" * 50)
    print("测试模块导入...")
    print("=" * 50)
    
    errors = []
    
    # 测试数据库模块
    try:
        from src.database.models import Database, SiteConfig, PageConfig, CrawlTask
        print("✅ 数据库模块导入成功")
    except Exception as e:
        errors.append(f"❌ 数据库模块导入失败: {e}")
    
    # 测试数据提取器
    try:
        from src.crawler.data_extractor import DataExtractor
        print("✅ 数据提取器导入成功")
    except Exception as e:
        errors.append(f"❌ 数据提取器导入失败: {e}")
    
    # 测试数据导出器
    try:
        from src.crawler.data_exporter import DataExporter
        print("✅ 数据导出器导入成功")
    except Exception as e:
        errors.append(f"❌ 数据导出器导入失败: {e}")
    
    # 测试爬虫引擎
    try:
        from src.crawler.crawler_engine import CrawlerEngine
        print("✅ 爬虫引擎导入成功")
    except Exception as e:
        errors.append(f"❌ 爬虫引擎导入失败: {e}")
    
    # 测试Cookie管理器
    try:
        from src.browser.cookie_manager import CookieManager
        print("✅ Cookie管理器导入成功")
    except Exception as e:
        errors.append(f"❌ Cookie管理器导入失败: {e}")
    
    # 测试浏览器控制器
    try:
        from src.browser.qwebengine_controller import QWebEngineController
        print("✅ QWebEngine控制器导入成功")
    except Exception as e:
        errors.append(f"❌ QWebEngine控制器导入失败: {e}")
    
    if errors:
        print("\n错误汇总:")
        for error in errors:
            print(error)
        return False
    
    print("\n所有核心模块导入成功！")
    return True


def test_database():
    """测试数据库功能"""
    print("\n" + "=" * 50)
    print("测试数据库功能...")
    print("=" * 50)
    
    try:
        from src.database.models import Database, SiteConfig
        
        # 创建测试数据库
        db = Database("test.db")
        site_model = SiteConfig(db)
        
        # 测试创建配置
        import uuid
        test_id = str(uuid.uuid4())
        site_model.create(
            test_id,
            "测试网站",
            "https://example.com",
        )
        print("✅ 创建网站配置成功")
        
        # 测试获取配置
        site = site_model.get(test_id)
        assert site["name"] == "测试网站"
        print("✅ 获取网站配置成功")
        
        # 清理
        site_model.delete(test_id)
        db.close()
        os.remove("test.db")
        print("✅ 数据库测试通过")
        
        return True
    except Exception as e:
        print(f"❌ 数据库测试失败: {e}")
        if os.path.exists("test.db"):
            os.remove("test.db")
        return False


def test_data_extractor():
    """测试数据提取器"""
    print("\n" + "=" * 50)
    print("测试数据提取器...")
    print("=" * 50)
    
    try:
        from src.crawler.data_extractor import DataExtractor
        
        extractor = DataExtractor()
        
        # 测试HTML
        html = """
        <table>
            <tr>
                <td>商品A</td>
                <td>100</td>
                <td><a href="/detail/1">详情</a></td>
            </tr>
            <tr>
                <td>商品B</td>
                <td>200</td>
                <td><a href="/detail/2">详情</a></td>
            </tr>
        </table>
        """
        
        field_mappings = {
            0: "name",
            1: "price",
            2: "link",
        }
        
        data = extractor.extract_table_data(html, "table", field_mappings)
        assert len(data) == 2
        assert data[0]["name"] == "商品A"
        assert data[0]["price"] == "100"
        print("✅ 数据提取测试通过")
        
        return True
    except Exception as e:
        print(f"❌ 数据提取测试失败: {e}")
        return False


def test_data_exporter():
    """测试数据导出器"""
    print("\n" + "=" * 50)
    print("测试数据导出器...")
    print("=" * 50)
    
    try:
        from src.crawler.data_exporter import DataExporter
        import os
        
        exporter = DataExporter("test_exports")
        
        test_data = [
            {"name": "商品A", "price": 100},
            {"name": "商品B", "price": 200},
        ]
        
        # 测试CSV导出
        csv_file = exporter.export_to_csv(test_data, "test")
        assert os.path.exists(csv_file)
        print(f"✅ CSV导出成功: {csv_file}")
        
        # 测试JSON导出
        json_file = exporter.export_to_json(test_data, "test")
        assert os.path.exists(json_file)
        print(f"✅ JSON导出成功: {json_file}")
        
        # 清理
        import shutil
        shutil.rmtree("test_exports")
        print("✅ 数据导出测试通过")
        
        return True
    except Exception as e:
        print(f"❌ 数据导出测试失败: {e}")
        if os.path.exists("test_exports"):
            import shutil
            shutil.rmtree("test_exports")
        return False


def main():
    """主测试函数"""
    print("\n🚀 开始项目验证测试...\n")
    
    results = []
    
    # 运行各项测试
    results.append(("模块导入", test_imports()))
    results.append(("数据库功能", test_database()))
    results.append(("数据提取", test_data_extractor()))
    results.append(("数据导出", test_data_exporter()))
    
    # 汇总结果
    print("\n" + "=" * 50)
    print("测试结果汇总")
    print("=" * 50)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{name}: {status}")
    
    all_passed = all(r[1] for r in results)
    
    if all_passed:
        print("\n🎉 所有测试通过！项目基础功能正常。")
        print("\n下一步:")
        print("1. 运行 install.bat 安装依赖")
        print("2. 运行 python main.py 启动程序")
    else:
        print("\n⚠️  部分测试失败，请检查错误信息。")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
