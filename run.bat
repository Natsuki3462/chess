@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
    echo [!] 还没安装，请先双击 install.bat
    pause
    exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" "app\main.py"
