@echo off
setlocal
cd /d "%~dp0"

echo === QUAST LaTeX to OMML - Compiling Standalone Installer ===
where python >nul 2>nul || (
    echo [ERROR] Python was not found in PATH.
    echo Please install Python 3.8+ or run install.bat.
    pause
    exit /b 1
)

python build_release.py %*
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Release packaging failed.
    pause
    exit /b %errorlevel%
)

echo.
echo === Packaging finished successfully! Check the 'releases' directory. ===
pause
exit /b 0
