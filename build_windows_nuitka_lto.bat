@echo off
setlocal enabledelayedexpansion

REM ==================================================
REM PROJECT CONFIG
REM ==================================================
set PROJECT_NAME=PyPongOnline
set ENTRY_POINT=client.py
set ICON_PATH=sprites\program.ico
set SRCDIR=%~dp0
set DISTDIR=dist_lto
set TARGET_EXE=%DISTDIR%\%PROJECT_NAME%.exe

cd /d "%SRCDIR%"

REM ==================================================
REM START TIMER
REM ==================================================
echo [%TIME%] Starting build...
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
REM DEPENDENCY CHECK
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

set /a BUILDVER+=1
echo %BUILDVER% > buildver.txt

echo [INFO] Build version: %BUILDVER%

REM ==================================================
REM CLEAN OUTPUT
REM ==================================================
echo [INFO] Cleaning previous build...
if exist "%TARGET_EXE%" del /q "%TARGET_EXE%" 2>nul

REM ==================================================
REM NUITKA ONEFILE BUILD
REM ==================================================
echo [INFO] Building %PROJECT_NAME%...

"%VENV_PY%" -m nuitka ^
 --onefile ^
 --output-dir="%DISTDIR%" ^
 --output-filename="%PROJECT_NAME%.exe" ^
 --windows-icon-from-ico="%ICON_PATH%" ^
 --windows-file-version=1.0.0.%BUILDVER% ^
 --windows-product-version=1.0.0.%BUILDVER% ^
 --windows-console-mode=disable ^
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
 --nofollow-import-to=ftplib ^
 --nofollow-import-to=telnetlib ^
 --nofollow-import-to=nntplib ^
 --nofollow-import-to=smtplib ^
 --nofollow-import-to=poplib ^
 --nofollow-import-to=imaplib ^
 --nofollow-import-to=gopherlib ^
 --nofollow-import-to=html ^
 --nofollow-import-to=html.parser ^
 --nofollow-import-to=xml ^
 --nofollow-import-to=xmlrpc ^
 --nofollow-import-to=cgi ^
 --nofollow-import-to=wsgiref ^
 --nofollow-import-to=cmd ^
 --nofollow-import-to=code ^
 --nofollow-import-to=rlcompleter ^
 --nofollow-import-to=pdb ^
 --nofollow-import-to=trace ^
 --nofollow-import-to=traceback ^
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
REM COPY RESOURCE DIRECTORIES
REM ==================================================
echo [INFO] Copying resource folders...

robocopy "%SRCDIR%sprites" "%DISTDIR%\sprites" /E /XF *.py *.pyc *.pyo >nul
robocopy "%SRCDIR%stages" "%DISTDIR%\stages" /E /XF *.py *.pyc *.pyo >nul

echo [INFO] Resource folders copied.


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
echo   BUILD SUCCESSFUL
echo ==================================================
echo   Output: %TARGET_EXE%
for %%F in ("%TARGET_EXE%") do echo   Size: %%~zF bytes
echo   Time: %ELAPSED% seconds
echo ==================================================
echo.
pause
