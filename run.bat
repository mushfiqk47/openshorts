@echo off
setlocal EnableDelayedExpansion
title OpenShorts Launcher
cd /d "%~dp0"
echo ==================================================
echo  OpenShorts - Local Clips-Only + OpenRouter Free
echo ==================================================
echo.

REM -- Check .env exists --
if not exist ".env" (
  echo [WARN] .env not found, creating from .env.example
  if exist ".env.example" copy /Y ".env.example" ".env" >nul
)
if exist ".env" (
  for /f "usebackq eol=# tokens=1,* delims==" %%A in (".env") do (
    if /i "%%A"=="OPENROUTER_MODEL" set "OPENROUTER_MODEL=%%B"
  )
)

REM -- Force UTF-8 for Python (fixes transcription emoji crash) --
REM Sanitize inherited PYTHONUTF8 - Python fatals on any value other than 0/1 at preinit
if defined PYTHONUTF8 (
  if not "%PYTHONUTF8%"=="0" if not "%PYTHONUTF8%"=="1" set "PYTHONUTF8=1"
)
if not defined PYTHONUTF8 set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

REM -- Backend proxy target for Vite (must be localhost when running outside docker) --
set VITE_PROXY_TARGET=http://localhost:8000
set VITE_RENDER_TARGET=http://localhost:3100

REM -- Checks --
where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] python not found in PATH
  pause
  exit /b 1
)
where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo [ERROR] ffmpeg not found in PATH - install from https://ffmpeg.org/
  pause
  exit /b 1
)
where node >nul 2>nul
if errorlevel 1 (
  echo [ERROR] node not found in PATH - install Node.js 18+
  pause
  exit /b 1
)

echo [1/4] Checking Python deps...
python -c "import fastapi, uvicorn, openai" >nul 2>nul
if errorlevel 1 (
  echo   Installing requirements.txt...
  python -m pip install -r requirements.txt
  if errorlevel 1 (
    echo [ERROR] pip install failed
    pause
    exit /b 1
  )
)
python -c "import google.genai" >nul 2>nul
if errorlevel 1 (
  echo   Installing google-genai for Gemini fallback...
  python -m pip install google-genai --quiet
)

echo [2/4] Checking frontend deps...
if not exist "dashboard\node_modules" (
  echo   Installing dashboard/node_modules - first run about 10 seconds...
  pushd dashboard
  call npm.cmd install
  popd
  if errorlevel 1 (
    echo [ERROR] npm install failed
    pause
    exit /b 1
  )
)

echo [3/4] Starting backend on http://localhost:8000 ...
REM Kill any old backend on 8000
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do (
  echo   Killing old PID %%a on :8000
  taskkill /F /PID %%a >nul 2>nul
)

REM Start backend in new window - uses .env for DISABLE_YOUTUBE_URL, OPENROUTER_*, WHISPER_*
start "OpenShorts Backend" cmd /k "cd /d ""%~dp0"" && set ""PYTHONUTF8=1"" && set ""PYTHONIOENCODING=utf-8"" && python -m uvicorn app:app --host 0.0.0.0 --port 8000"

REM Wait for backend health
echo   Waiting for backend...
set /a tries=0
:wait_backend
set /a tries+=1
timeout /t 2 /nobreak >nul 2>nul || ping -n 3 127.0.0.1 >nul
curl -s http://localhost:8000/health >nul 2>nul
if errorlevel 1 (
  if %tries% GEQ 15 (
    echo [ERROR] backend did not start in 30s - check the Backend window
    pause
    exit /b 1
  )
  goto wait_backend
)
echo   Backend OK

echo [4/4] Starting frontend on http://localhost:5175 ...
REM Kill old frontend on 5175
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5175" ^| findstr "LISTENING"') do (
  echo   Killing old PID %%a on :5175
  taskkill /F /PID %%a >nul 2>nul
)
REM Start frontend in new window - inherits VITE_PROXY_TARGET
start "OpenShorts Frontend" cmd /k "cd /d ""%~dp0\dashboard"" && set ""VITE_PROXY_TARGET=http://localhost:8000"" && set ""VITE_RENDER_TARGET=http://localhost:3100"" && npm.cmd run dev -- --host 0.0.0.0 --port 5175"

timeout /t 5 /nobreak >nul 2>nul || ping -n 6 127.0.0.1 >nul
echo.
echo ==================================================
echo  Ready!
echo    Frontend: http://localhost:5175/
echo    Backend:  http://localhost:8000/health  +  /api/config
echo    API docs: http://localhost:8000/docs
echo ==================================================
echo  Settings - in the UI paste your OpenRouter key:
echo    sk-or-v1-... from https://openrouter.ai/keys
echo    Pick a free model e.g. google/gemma-4-26b-a4b-it:free
echo    Your .env already has: %OPENROUTER_MODEL%
echo  Mode: DISABLE_YOUTUBE_URL=true (upload file only, no YouTube)
echo  Test clip: uploads/speech80.mp4 (80s, 17 segments)
echo ==================================================
echo  Two windows opened: "OpenShorts Backend" + "OpenShorts Frontend"
echo  Close them or run stop.bat to stop.
echo.
REM Open browser
start "" http://localhost:5175/
pause
