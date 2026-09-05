@echo off
setlocal EnableDelayedExpansion
title OpenShorts Full Launcher
cd /d "%~dp0"
echo ==================================================
echo  OpenShorts - FULL local project (no Docker)
echo  Backend :8000 + Renderer :3100 + Frontend :5175
echo ==================================================
echo.

REM -- .env --
if not exist ".env" (
  echo [WARN] .env not found, creating from .env.example
  if exist ".env.example" copy /Y ".env.example" ".env" >nul
)

REM -- UTF-8 for Python --
if defined PYTHONUTF8 (
  if not "%PYTHONUTF8%"=="0" if not "%PYTHONUTF8%"=="1" set "PYTHONUTF8=1"
)
if not defined PYTHONUTF8 set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

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

echo [1/5] Checking Python deps...
python -c "import fastapi, uvicorn" >nul 2>nul
if errorlevel 1 (
  echo   Installing requirements.txt...
  python -m pip install -r requirements.txt
  if errorlevel 1 (
    echo [ERROR] pip install failed
    pause
    exit /b 1
  )
)

echo [2/5] Checking frontend deps...
if not exist "dashboard\node_modules" (
  echo   Installing dashboard/node_modules...
  pushd dashboard
  call npm.cmd install
  popd
  if errorlevel 1 (
    echo [ERROR] npm install failed
    pause
    exit /b 1
  )
)

echo [3/5] Checking renderer deps + build...
if not exist "render-service\node_modules" (
  echo   Installing render-service/node_modules...
  pushd render-service
  call npm.cmd install
  popd
  if errorlevel 1 (
    echo [ERROR] renderer npm install failed
    pause
    exit /b 1
  )
)
if not exist "remotion\node_modules" (
  echo   Installing remotion/node_modules...
  pushd remotion
  call npm.cmd install
  popd
  if errorlevel 1 (
    echo [ERROR] remotion npm install failed
    pause
    exit /b 1
  )
)
if not exist "render-service\dist\server.js" (
  echo   Building render-service...
  pushd render-service
  call npm.cmd run build
  popd
  if errorlevel 1 (
    echo [ERROR] renderer build failed
    pause
    exit /b 1
  )
)

REM Kill anything already on our three ports, then start all services.

echo [4/5] Starting backend...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do (
  echo   Killing old PID %%a on :8000
  taskkill /F /PID %%a >nul 2>nul
)
start "OpenShorts Backend" cmd /k "cd /d ""%~dp0"" && set ""PYTHONUTF8=1"" && set ""PYTHONIOENCODING=utf-8"" && python -m uvicorn app:app --host 0.0.0.0 --port 8000"

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

echo   Starting renderer on http://localhost:3100 ...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3100" ^| findstr "LISTENING"') do (
  echo   Killing old PID %%a on :3100
  taskkill /F /PID %%a >nul 2>nul
)
REM OUTPUT_DIR must be absolute so served clips resolve; bundle path is ./remotion
start "OpenShorts Renderer" cmd /k "cd /d ""%~dp0\render-service"" && set ""PORT=3100"" && set ""OUTPUT_DIR=%~dp0output"" && set ""REMOTION_BUNDLE_PATH=%~dp0remotion"" && node dist/server.js"

echo [5/5] Frontend on http://localhost:5175 ...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5175" ^| findstr "LISTENING"') do (
  echo   Killing old PID %%a on :5175
  taskkill /F /PID %%a >nul 2>nul
)
start "OpenShorts Frontend" cmd /k "cd /d ""%~dp0\dashboard"" && set ""VITE_PROXY_TARGET=http://localhost:8000"" && set ""VITE_RENDER_TARGET=http://localhost:3100"" && npm.cmd run start"

timeout /t 5 /nobreak >nul 2>nul || ping -n 6 127.0.0.1 >nul
echo.
echo ==================================================
echo  Ready!
echo    Frontend: http://localhost:5175/
echo    Backend:  http://localhost:8000/health  +  /docs
echo    Renderer: http://localhost:3100/ (Remotion previews)
echo ==================================================
echo  CLI path (no server needed):
echo    python main.py -i video.mp4 --transcript video.srt
echo ==================================================
echo  Three windows opened: Backend + Renderer + Frontend
echo  Run stop.bat to stop them all.
echo.
start "" http://localhost:5175/
pause
