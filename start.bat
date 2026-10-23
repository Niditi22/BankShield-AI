@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
 echo Follow README.md to complete the initial setup first.
 pause
 exit /b 1
)
.venv\Scripts\python.exe app.py
pause
