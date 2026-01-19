@echo off
setlocal enabledelayedexpansion

REM ==================================================
REM PROJECT CONFIG
REM ==================================================
set PROJECT_NAME=PyPongOnline
set ENTRY_POINT=py_client.py
set ICON_PATH=sprites\program.ico
set SRCDIR=%~dp0
set DISTDIR=build_windows
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
REM LOCATE VSDEVCMD (can override by setting VSDEVCMD env var)
REM ==================================================

set "VSDEVCMD="

if defined VSDEVCMD (
    echo [INFO] Using VSDEVCMD from environment: %VSDEVCMD%
) else (
    REM --- Common Build Tools paths (short paths to avoid parentheses issues)
    if exist "C:\PROGRA~2\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\vsdevcmd.bat" (
        set "VSDEVCMD=C:\PROGRA~2\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\vsdevcmd.bat"
    ) else if exist "C:\PROGRA~2\Microsoft Visual Studio\2019\BuildTools\Common7\Tools\vsdevcmd.bat" (
        set "VSDEVCMD=C:\PROGRA~2\Microsoft Visual Studio\2019\BuildTools\Common7\Tools\vsdevcmd.bat"
    ) else if exist "C:\PROGRA~2\Microsoft Visual Studio\18\BuildTools\Common7\Tools\vsdevcmd.bat" (
        set "VSDEVCMD=C:\PROGRA~2\Microsoft Visual Studio\18\BuildTools\Common7\Tools\vsdevcmd.bat"
    )

    REM --- Try vswhere
    if not defined VSDEVCMD (
        if exist "C:\PROGRA~2\Microsoft Visual Studio\Installer\vswhere.exe" (
            for /f "usebackq tokens=*" %%I in (`
                "C:\PROGRA~2\Microsoft Visual Studio\Installer\vswhere.exe" ^
                -latest -products * ^
                -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 ^
                -property installationPath
            `) do (
                if exist "%%I\Common7\Tools\vsdevcmd.bat" (
                    set "VSDEVCMD=%%I\Common7\Tools\vsdevcmd.bat"
                )
            )
        )
    )
)

REM ==================================================
REM INITIALISE VS ENVIRONMENT (MUST BE OUTSIDE PAREN BLOCKS)
REM ==================================================

if defined VSDEVCMD (
    echo [INFO] Found vsdevcmd: %VSDEVCMD%
    echo [INFO] Initializing Visual Studio build environment...

    REM --- Use the architecture you actually have installed
    call "%VSDEVCMD%" -arch=x86 -host_arch=x86

    if errorlevel 1 (
        echo [WARNING] vsdevcmd returned non-zero exit code; environment may not be loaded.
    ) else (
        echo [INFO] Visual Studio environment initialized.
    )
) else (
    echo [WARNING] Could not locate vsdevcmd.bat automatically.
    echo [WARNING] Build may fail without MSVC environment.
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

echo [INFO] Build version: %BUILDVER%

REM ==================================================
REM CLEAN OUTPUT
REM ==================================================
echo [INFO] Cleaning previous build...
if exist "%TARGET_EXE%" del /q "%TARGET_EXE%" 2>nul

REM ==================================================
REM PREPARE FILTERED SPRITES (exclude logo.png and logo.psd)
REM ==================================================
set "TMP_SPRITES=%TEMP%\pypong_sprites_%RANDOM%"

REM remove any leftover temp folder
if exist "%TMP_SPRITES%" rmdir /s /q "%TMP_SPRITES%"

REM Use robocopy to copy sprites to temp, excluding the two files
robocopy "%SRCDIR%sprites" "%TMP_SPRITES%" /E /XF "logo.png" "logo.psd" >nul

REM Note: robocopy returns non-zero codes for some conditions; ignore them and continue

REM ==================================================
REM NUITKA ONEFILE BUILD (persistent tempdir)
REM ==================================================
echo [INFO] Building %PROJECT_NAME%...

"%VENV_PY%" -m nuitka ^
 --onefile ^
 --onefile-tempdir-spec="{TEMP}/PyPongOnline" ^
 --output-dir="%DISTDIR%" ^
 --output-filename="%PROJECT_NAME%.exe" ^
 --windows-icon-from-ico="%ICON_PATH%" ^
 --windows-file-version=1.0.0.%BUILDVER% ^
 --windows-product-version=1.0.0.%BUILDVER% ^
 --windows-console-mode=attach ^
 --include-data-dir="%TMP_SPRITES%=sprites" ^
 --include-data-dir=audio=audio ^
 --include-data-dir=stages=stages ^
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
REM CLEANUP TEMP SPRITES
REM ==================================================
if exist "%TMP_SPRITES%" rmdir /s /q "%TMP_SPRITES%"

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
REM NOTE: No resource folders are copied into %DISTDIR% anymore
REM ==================================================
echo [INFO] Resources were packed into the onefile bundle; no folders copied to %DISTDIR%.

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
