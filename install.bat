@echo off
echo ===================================
echo 网页数据抓取工具 - 环境安装脚本
echo ===================================
echo.

echo [1/4] 检查Python环境...
python --version
if %errorlevel% neq 0 (
    echo 错误: 未找到Python，请先安装Python 3.9或更高版本
    pause
    exit /b 1
)

echo.
echo [2/4] 安装Python依赖包...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo 错误: 依赖包安装失败
    pause
    exit /b 1
)

echo.
echo [3/4] 安装完成 - 不再需要Playwright浏览器...

echo.
echo [4/4] 创建数据目录...
if not exist "config" mkdir config
if not exist "data" mkdir data
if not exist "data\exports" mkdir data\exports
if not exist "data\cookies" mkdir data\cookies

echo.
echo ===================================
echo 安装完成！
echo ===================================
echo.
echo 运行程序: python main.py
echo.
pause
