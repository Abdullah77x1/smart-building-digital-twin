@echo off
cd /d "%~dp0\.."
if exist .venv\Scripts\python.exe (
  .venv\Scripts\python.exe dashboard\app.py
) else (
  python dashboard\app.py
)
pause
