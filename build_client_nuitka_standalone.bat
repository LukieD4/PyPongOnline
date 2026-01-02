@echo off
setlocal enabledelayedexpansion

REM ============================
REM Project config
REM ============================
set PROJECT_NAME=PyPongOnline
set ENTRY_POINT=client.py
set ICON_PATH=sprites\program.ico
set SRCDIR=%~dp0
set DISTDIR=dist

cd /d "%SRCDIR%"

REM ============================
REM Read build version
REM ============================
if not exist buildver.txt (
    echo [ERROR] buildver.txt not found
    pause
    exit /b 1
)

set /p BUILD_VER=<buildver.txt
set BUILD_VER=%BUILD_VER: =%
set OUTPUT_DIR=%DISTDIR%\%PROJECT_NAME%-%BUILD_VER%

echo [INFO] Version: %BUILD_VER%

REM ============================
REM Python selection
REM ============================
set VENV_PY=%SRCDIR%.venv\Scripts\python.exe
if not exist "%VENV_PY%" (
    set VENV_PY=python
)

REM ============================
REM Clean output
REM ============================
if exist "%OUTPUT_DIR%" (
    rmdir /s /q "%OUTPUT_DIR%"
)

REM ============================
REM Build (STANDALONE, QUIET)
REM ============================
echo [INFO] Building standalone...

"%VENV_PY%" -m nuitka ^
 --standalone ^
 --output-dir="%OUTPUT_DIR%" ^
 --output-filename=%PROJECT_NAME%.exe ^
 --windows-icon-from-ico="%ICON_PATH%" ^
 --include-data-dir=sprites=sprites ^
 --include-data-file=buildver.txt=buildver.txt ^
 --assume-yes-for-downloads ^
 "%ENTRY_POINT%"


REM ============================
REM Verify result
REM ============================
if not exist "%OUTPUT_DIR%\client.dist\%PROJECT_NAME%.exe" (
    echo.
    echo [ERROR] Build failed — see messages above
    pause
    exit /b 1
)

REM ============================
REM UPX compression (optional)
REM ============================
set UPX_DIR=%SRCDIR%upx-5.0.2-win64
set UPX_EXE=%UPX_DIR%\upx.exe
set TARGET_EXE=%OUTPUT_DIR%\client.dist\%PROJECT_NAME%.exe

if exist "%UPX_EXE%" (
    echo [INFO] Running UPX on %PROJECT_NAME%.exe
    "%UPX_EXE%" --best --lzma "%TARGET_EXE%"
) else (
    echo [WARNING] UPX not found — skipping compression
)


echo.
echo ============================
echo BUILD SUCCESSFUL
echo ============================
echo Output: %OUTPUT_DIR%
echo.
pause
