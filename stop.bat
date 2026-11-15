@echo off
cd /d "%~dp0"
echo Stopping OpenShorts...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do (
  echo Killing PID %%a on :8000
  taskkill /F /PID %%a >nul 2>nul
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5175" ^| findstr "LISTENING"') do (
  echo Killing PID %%a on :5175
  taskkill /F /PID %%a >nul 2>nul
)
REM Also kill window titles if netstat missed
taskkill /FI "WINDOWTITLE eq OpenShorts Backend*" /F >nul 2>nul
taskkill /FI "WINDOWTITLE eq OpenShorts Frontend*" /F >nul 2>nul
echo Done.
pause
