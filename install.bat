@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title ChessFloat 安装

echo ============================================
echo   ChessFloat 安装（全部内容都在本文件夹内）
echo ============================================
echo.

set "PYEXE="
where python >nul 2>nul
if not errorlevel 1 (set "PYEXE=python" & goto :havepy)
where py >nul 2>nul
if not errorlevel 1 (set "PYEXE=py -3" & goto :havepy)
if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" (set "PYEXE=%LOCALAPPDATA%\Programs\Python\Python313\python.exe" & goto :havepy)
echo [x] 未找到 Python。请先安装 Python 3.10 或更高版本，并勾选 "Add to PATH"。
pause
exit /b 1

:havepy
echo [1/3] Python: %PYEXE%

if exist ".venv\Scripts\python.exe" goto :havevenv
echo       创建虚拟环境 .venv ...
%PYEXE% -m venv .venv
if errorlevel 1 (
    echo [x] 虚拟环境创建失败。
    pause
    exit /b 1
)
:havevenv

set "PIP_CACHE_DIR=%~dp0.cache\pip"
set "TMP=%~dp0.cache\tmp"
set "TEMP=%~dp0.cache\tmp"
if not exist ".cache\tmp" mkdir ".cache\tmp" >nul 2>nul

echo [2/3] 安装依赖 PyQt6 / python-chess ...
".venv\Scripts\python.exe" -m pip install --upgrade pip --no-cache-dir -q
".venv\Scripts\python.exe" -m pip install -r requirements.txt --no-cache-dir -q
if errorlevel 1 (
    echo [x] 依赖安装失败，请检查网络。
    pause
    exit /b 1
)

echo [3/3] 检查 Stockfish ...
if exist "engine\stockfish.exe" goto :havengine
echo.
echo [!] 未找到 engine\stockfish.exe
echo     请下载官方 Stockfish Windows x64 版，解压后把 exe 改名为 stockfish.exe
echo     放到本目录的 engine\ 文件夹里，然后重新运行本脚本。
echo     下载页: https://github.com/official-stockfish/Stockfish/releases
echo.
pause
exit /b 1

:havengine
echo       引擎就绪：engine\stockfish.exe

echo.
echo 运行自检 ...
".venv\Scripts\python.exe" tools\smoke_test.py
if errorlevel 1 (
    echo.
    echo [!] 自检未全部通过，请把上面的输出反馈。
    pause
    exit /b 1
)

echo.
echo ============================================
echo   安装完成，双击 run.bat 启动
echo ============================================
pause
