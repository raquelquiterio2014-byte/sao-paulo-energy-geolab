@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" goto missing
echo Open http://127.0.0.1:8001 after startup.
echo Keep this window open. Press Ctrl+C to stop.
".venv\Scripts\python.exe" app.py
pause
exit /b
:missing
echo Run INSTALL.bat first.
pause
exit /b 1
