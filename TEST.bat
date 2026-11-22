@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" goto missing
".venv\Scripts\python.exe" -m unittest -v
set "TEST_EXIT=%ERRORLEVEL%"
pause
exit /b %TEST_EXIT%
:missing
echo Run INSTALL.bat first.
pause
exit /b 1
