@echo off
setlocal
cd /d "%~dp0"

:: 1. Ensure Python is installed and accessible
where python >nul 2>nul || (
    echo [ERROR] Python was not found in PATH.
    echo Please install Python 3.8+ or run install.bat.
    pause
    exit /b 1
)

:: 2. Dynamically resolve the corresponding windowless Python binary (pythonw)
::    matching the exact active Python interpreter environment
for /f "delims=" %%I in ('python -c "import sys, os; d=os.path.dirname(sys.executable); c=[os.path.join(d,x) for x in ('pythonw.exe','pythonw3.exe','pythonw3.13.exe') if os.path.exists(os.path.join(d,x))]; print(c[0] if c else '')" 2^>nul') do set "PYTHONW_EXE=%%I"

:: 3. Launch the application silently without keeping a console window open
if defined PYTHONW_EXE if exist "%PYTHONW_EXE%" (
    start "" "%PYTHONW_EXE%" app\app.py %*
    exit /b 0
)

:: Fallback if pythonw binary was not found directly in python directory
where pythonw3 >nul 2>nul && (
    start "" pythonw3 app\app.py %*
    exit /b 0
)

where pythonw >nul 2>nul && (
    start "" pythonw app\app.py %*
    exit /b 0
)

:: Standard fallback to python
start "" python app\app.py %*
exit /b 0
