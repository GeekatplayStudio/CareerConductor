@echo off
REM ============================================================================
REM  CareerConductor launcher - Windows
REM  Run from the project root:   start.bat   (double-click also works)
REM  Opens the control panel at http://localhost:8501
REM ============================================================================
setlocal
cd /d "%~dp0"

if not exist .venv\Scripts\streamlit.exe (
    echo The app is not installed yet - run install.bat first.
    pause
    exit /b 1
)
if not exist .env (
    echo Note: no .env found. Copy .env.example to .env and add your API keys,
    echo or the pipeline pages will show missing-key warnings.
)

echo Starting CareerConductor at http://localhost:8501  (Ctrl+C to stop)
.venv\Scripts\streamlit run careerconductor\ui\app.py %*
pause
