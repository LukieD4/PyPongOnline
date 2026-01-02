@echo off
setlocal enabledelayedexpansion
REM -----------------------------
REM Project config
REM -----------------------------
set PROJECT_NAME=PyPongOnline
set ENTRY_POINT=client.py
set ICON_PATH=sprites\cell.png
REM location of this script (project root)
set SRCDIR=%~dp0
cd /d "%SRCDIR%"
REM -----------------------------
REM Choose Python interpreter:
REM Prefer .venv\Scripts\python.exe if it exists, otherwise fall back to `python`
REM -----------------------------
set VENV_PY=%SRCDIR%.venv\Scripts\python.exe
if not exist "%VENV_PY%" (
    echo ".venv\\Scripts\\python.exe not found — falling back to system python"
    set VENV_PY=python
) else (
    echo "Using venv Python: %VENV_PY%"
)
REM Show which python will be used
"%VENV_PY%" -c "import sys; print('PYTHON:', sys.executable)"
REM -----------------------------
REM Ensure pip + necessary packages are installed into the chosen python
REM -----------------------------
echo Installing/ensuring dependencies into %VENV_PY%...
"%VENV_PY%" -m pip install --upgrade pip
"%VENV_PY%" -m pip install --upgrade pyinstaller pygame numpy websockets
REM -----------------------------
REM Clean previous builds
REM -----------------------------
echo Cleaning old builds...
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul
del *.spec 2>nul
REM -----------------------------
REM Run PyInstaller using the selected Python interpreter
REM - Using -m PyInstaller ensures the correct Python env is used
REM - collect options for pygame/numpy included
REM -----------------------------
echo Building %PROJECT_NAME%...
"%VENV_PY%" -m PyInstaller ^
 --onefile ^
 --windowed ^
 --name "%PROJECT_NAME%" ^
 --collect-all pygame ^
 --collect-submodules pygame ^
 --collect-all numpy ^
 --hidden-import websockets ^
 --hidden-import asyncio ^
 --add-data "sprites;sprites" ^
 --add-data "sprites\font;sprites\font" ^
 --add-data "sprites\missing.png;sprites" ^
 --upx-dir "C:\Users\melsm\Documents\_PROJECTS\PyPongOnline\upx-5.0.2-win64" ^
 "%ENTRY_POINT%"
REM -----------------------------
REM Done / show where the exe landed
REM -----------------------------
echo.
echo Build complete!
echo Output located in: dist\%PROJECT_NAME%.exe
pause