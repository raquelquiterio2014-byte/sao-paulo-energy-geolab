@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 goto missing
if not exist ".venv\Scripts\python.exe" py -3 -m venv .venv
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
echo Installation complete. Run START.bat next.
pause
exit /b 0
:missing
echo Python launcher not found. Install Python 3.11 or 3.12 with the Windows launcher.
pause
exit /b 1
:failed
echo Installation failed. Copy the error displayed above.
pause
exit /b 1
