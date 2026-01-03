@echo off
setlocal enabledelayedexpansion

REM ==================================================
REM PROJECT CONFIG
REM ==================================================
set PROJECT_NAME=PyPongOnline
set ENTRY_POINT=client.py
set ICON_PATH=sprites\program.ico
set SRCDIR=%~dp0
set DISTDIR=dist
set TARGET_EXE=%DISTDIR%\%PROJECT_NAME%.exe

cd /d "%SRCDIR%"

REM ==================================================
REM START TIMER
REM ==================================================
echo [%TIME%] Starting MAX-COMPRESSION build...
for /f "tokens=1-4 delims=:.," %%a in ("%time%") do (
    set /a START_SEC=%%a*3600 + %%b*60 + %%c
)

REM ==================================================
REM PYTHON SELECTION
REM ==================================================
set VENV_PY=%SRCDIR%.venv\Scripts\python.exe
if not exist "%VENV_PY%" (
    echo [WARNING] .venv not found — using system Python
    set VENV_PY=python
) else (
    echo [INFO] Using venv: %VENV_PY%
)

REM ==================================================
REM DEPENDENCY CHECK (EXCLUDE NUMPY)
REM ==================================================
echo [INFO] Checking dependencies...
"%VENV_PY%" -c "import nuitka, pygame, websockets" 2>nul
if errorlevel 1 (
    echo [INFO] Installing missing dependencies...
    "%VENV_PY%" -m pip install --quiet --upgrade pip
    "%VENV_PY%" -m pip install --quiet nuitka pygame websockets imageio
) else (
    echo [INFO] All dependencies present
)

REM ==================================================
REM READ BUILD NUMBER
REM ==================================================
set BUILDVER=0
if exist buildver.txt (
    set /p BUILDVER=<buildver.txt
)

REM Increment
set /a BUILDVER+=1

REM Save back
echo %BUILDVER% > buildver.txt

echo [INFO] Build version: %BUILDVER%

REM ==================================================
REM CLEAN OUTPUT
REM ==================================================
echo [INFO] Cleaning previous build...
if exist "%TARGET_EXE%" del /q "%TARGET_EXE%" 2>nul

REM ==================================================
REM NUITKA ONEFILE — MAXIMUM COMPRESSION
REM ==================================================
echo [INFO] Building %PROJECT_NAME% (ONEFILE / MAX COMPRESSION)...

"%VENV_PY%" -m nuitka ^
 --onefile ^
 --output-dir="%DISTDIR%" ^
 --output-filename="%PROJECT_NAME%.exe" ^
 --windows-icon-from-ico="%ICON_PATH%" ^
 --windows-file-version=1.0.0.%BUILDVER% ^
 --windows-product-version=1.0.0.%BUILDVER% ^
 --include-data-dir=sprites=sprites ^
 --include-module=asyncio ^
 --include-module=websockets ^
 --include-module=websockets.asyncio ^
 --include-module=websockets.asyncio.client ^
 --nofollow-import-to=pytest ^
 --nofollow-import-to=unittest ^
 --nofollow-import-to=pydoc ^
 --nofollow-import-to=tkinter ^
 --nofollow-import-to=distutils ^
 --lto=yes ^
 --jobs=4 ^
 --assume-yes-for-downloads ^
 --remove-output ^
 "%ENTRY_POINT%"


REM ==================================================
REM VERIFY BUILD
REM ==================================================
if not exist "%TARGET_EXE%" ( 
    echo.
    echo [ERROR] Build failed — executable not created!
    pause
    exit /b 1
)

REM ==================================================
REM UPX — MAXIMUM POSSIBLE COMPRESSION
REM ==================================================
set UPX_DIR=%SRCDIR%upx-5.0.2-win64
set UPX_EXE=%UPX_DIR%\upx.exe

if exist "%UPX_EXE%" (
    echo [INFO] Attempting ULTRA UPX compression (this may take time)...
    "%UPX_EXE%" --ultra-brute --lzma "%TARGET_EXE%" 2>upx.log

    findstr /C:"NotCompressibleException" upx.log >nul
    if %errorlevel% equ 0 (
        echo [INFO] UPX: Executable already optimally packed — skipping
    ) else (
        echo [INFO] UPX compression applied successfully
    )
    del upx.log 2>nul
) else (
    echo [WARNING] UPX not found — skipping compression
)

REM ==================================================
REM TIMER END
REM ==================================================
for /f "tokens=1-4 delims=:.," %%a in ("%time%") do (
    set /a END_SEC=%%a*3600 + %%b*60 + %%c
)
set /a ELAPSED=%END_SEC%-%START_SEC%
if %ELAPSED% lss 0 set /a ELAPSED+=86400

REM ==================================================
REM SUMMARY
REM ==================================================
echo.
echo ==================================================
echo   BUILD SUCCESSFUL — MAX COMPRESSION
echo ==================================================
echo   Output: %TARGET_EXE%
for %%F in ("%TARGET_EXE%") do echo   Size: %%~zF bytes
echo   Time: %ELAPSED% seconds
echo ==================================================
echo.
pause
