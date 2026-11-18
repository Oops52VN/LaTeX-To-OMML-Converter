@echo off
setlocal
cd /d "%~dp0"
echo === QUAST LaTeX to OMML - Installing dependencies ===
where python >nul 2>nul || (echo [ERROR] Python 3.8+ was not found in PATH. & pause & exit /b 1)

python -m pip install --upgrade pip || goto :fail
python -m pip install -r requirements.txt || goto :fail

rem Optional: build the Rust accelerator (the app falls back to pure Python without it)
where cargo >nul 2>nul
if %errorlevel%==0 (
    echo Building optional Rust core quast_core ...
    python -m pip install maturin
    python -m maturin build --release -m core\pyproject.toml --out core\dist && for %%W in (core\dist\*.whl) do python -m pip install --force-reinstall "%%W"
) else (
    echo Cargo not found - skipping optional Rust core.
)

echo.
echo === Installation finished. Run run.bat to start the application. ===
pause
exit /b 0

:fail
echo [ERROR] Installation failed.
pause
exit /b 1