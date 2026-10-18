@echo off
chcp 936 >nul
title 汉文化知识图谱 · 前端服务
cd /d "%~dp0"

echo ============================================================
echo    汉文化知识图谱 · 图谱前端
echo ============================================================
echo.

if not exist "03_图谱前端\app.py" (
    echo [错误] 找不到 03_图谱前端\app.py
    echo        请把本脚本放在项目根目录（与 03_图谱前端 同级）后运行。
    pause
    exit /b 1
)

cd "03_图谱前端"

if exist ".venv\Scripts\python.exe" goto run

echo [1/3] 正在寻找可用的 Python 解释器 ...
set "PYCMD="
py -3 -V >nul 2>nul && set "PYCMD=py -3"
if not defined PYCMD (
    python -V >nul 2>nul && set "PYCMD=python"
)
if not defined PYCMD (
    echo [错误] 未找到可用的 Python。
    echo        请先安装 Python 3.10 及以上版本，安装时勾选 Add Python to PATH，
    echo        然后重新运行本脚本。
    pause
    exit /b 1
)
echo        使用: %PYCMD%

echo [2/3] 正在创建虚拟环境 .venv ...
%PYCMD% -m venv .venv
if not exist ".venv\Scripts\python.exe" (
    echo [错误] 创建虚拟环境失败。
    echo        若系统中装有多个 Python，可能是 PATH 里靠前的解释器不受支持，
    echo        请改用系统自带的 Python 启动器： py -3 -m venv .venv
    pause
    exit /b 1
)

echo [3/3] 正在安装运行依赖（首次运行需要联网，约 1 分钟）...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install Flask py2neo==2021.2.4
if errorlevel 1 (
    echo [错误] 依赖安装失败，请检查网络连接后重试。
    pause
    exit /b 1
)
echo.
echo 依赖安装完成。
echo.

:run
echo 正在启动服务，请用浏览器打开： http://127.0.0.1:5000
echo 按 Ctrl+C 可停止服务。
echo.

".venv\Scripts\python.exe" app.py

echo.
echo 服务已停止。
echo 提示：若上方出现 Address already in use，说明 5000 端口已被别的程序占用。
pause
