@echo off
REM ============================================================================
REM  CareerConductor installer - Windows
REM  Run from the project root:   install.bat   (double-click also works)
REM  Safe to re-run any time; it reuses the existing environment.
REM ============================================================================
setlocal
cd /d "%~dp0"

echo.
echo [1/4] Checking Python (3.11 or newer required)
where python >nul 2>nul
if errorlevel 1 (
    echo   Python was not found. Install it from https://www.python.org/downloads/
    echo   IMPORTANT: check "Add python.exe to PATH" in the installer, then re-run install.bat
    pause
    exit /b 1
)
python -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)"
if errorlevel 1 (
    echo   Your Python is older than 3.11. Install a newer one from python.org and re-run.
    pause
    exit /b 1
)
for /f "tokens=2" %%v in ('python --version') do echo   OK: Python %%v

echo.
echo [2/4] Creating virtual environment (.venv)
if exist .venv (
    echo   .venv already exists - reusing it.
) else (
    python -m venv .venv
    echo   Created .venv
)

echo.
echo [3/4] Installing CareerConductor and dependencies (may take a minute)
.venv\Scripts\python -m pip install --quiet --upgrade pip
.venv\Scripts\python -m pip install --quiet -e .
echo   Dependencies installed.

echo.
echo [4/4] Preparing configuration
if exist .env (
    echo   .env already exists - keeping your settings.
) else (
    copy /y .env.example .env >nul
    echo   Created .env from the template.
)

echo.
echo Done. Next steps:
echo   1. Open .env in Notepad and add your ANTHROPIC_API_KEY (console.anthropic.com)
echo      and optionally GEMINI_API_KEY (aistudio.google.com).
echo   2. Launch the app:   start.bat
echo.
pause
