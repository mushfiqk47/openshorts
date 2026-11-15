@echo off
setlocal EnableDelayedExpansion
title OpenShorts Setup
cd /d "%~dp0"
echo ==================================================
echo  OpenShorts - first-time setup
echo  Prepares a new machine: runtime, models, dependencies.
echo  After this, run.bat starts the app.
echo ==================================================
echo.

REM -- Force UTF-8 for Python (fixes emoji output in job logs) --
REM Sanitize inherited PYTHONUTF8 - Python fatals on any value other than 0/1 at preinit
if defined PYTHONUTF8 (
  if not "%PYTHONUTF8%"=="0" if not "%PYTHONUTF8%"=="1" set "PYTHONUTF8=1"
)
if not defined PYTHONUTF8 set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

REM -- Prerequisite checks --
echo [check] prerequisites
where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] python not found in PATH - install Python 3.11 from https://www.python.org/downloads/
  echo         On the installer, tick "Add python.exe to PATH".
  pause
  exit /b 1
)
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python 3.11+ is required - install it from https://www.python.org/downloads/
  pause
  exit /b 1
)
where node >nul 2>nul
if errorlevel 1 (
  echo [ERROR] node not found in PATH - install Node.js 18+ from https://nodejs.org/
  pause
  exit /b 1
)
where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo [ERROR] ffmpeg not found in PATH - install from https://ffmpeg.org/download.html or: winget install Gyan.FFmpeg
  pause
  exit /b 1
)
echo   python, node, ffmpeg OK

where nvidia-smi >nul 2>nul
if errorlevel 1 (
  echo [WARN] nvidia-smi not found - no NVIDIA GPU or driver visible.
  echo        Transcription is GPU-only and needs CUDA. AI Shorts and YouTube
  echo        Studio still work, but Clip Generator needs a speech track.
) else (
  echo   NVIDIA GPU detected
)
echo.

REM -- NeMo-Speech.cpp: the CUDA transcription runtime --
echo [1/5] NeMo-Speech.cpp runtime (parakeet-tdt-0.6b-v3 GGUF on CUDA)
set "NEMOSPEECH_BIN_DIR=%LOCALAPPDATA%\Programs\NeMoSpeech\bin"
if exist "%NEMOSPEECH_BIN_DIR%\nemo-speech.exe" goto nemo_found
where nemo-speech >nul 2>nul
if not errorlevel 1 goto nemo_found_path
if exist ".env" (
  for /f "usebackq eol=# tokens=1,* delims==" %%A in (".env") do (
    if /i "%%A"=="NEMO_SPEECH_BIN" if exist "%%~B" goto nemo_env
  )
)
echo   Installing the prebuilt release (no compiler needed)...
powershell -NoProfile -ExecutionPolicy Bypass -Command "iex ((irm 'https://github.com/NVIDIA/NeMo-Speech.cpp/raw/main/scripts/install.ps1') + ' -BinaryOnly')"
if not exist "%NEMOSPEECH_BIN_DIR%\nemo-speech.exe" (
  echo [WARN] nemo-speech.exe still not found after install attempt.
  echo        Install manually, then re-run setup.bat:
  echo          powershell -Command "irm https://github.com/NVIDIA/NeMo-Speech.cpp/raw/main/scripts/install.ps1 | iex"
  echo        Or set NEMO_SPEECH_BIN in .env to an existing binary path.
  goto nemo_done
)
:nemo_found
set "NEMOBIN=%NEMOSPEECH_BIN_DIR%\nemo-speech.exe"
goto nemo_version
:nemo_found_path
set "NEMOBIN=nemo-speech"
goto nemo_version
:nemo_env
echo   Using NEMO_SPEECH_BIN from .env
set "NEMOBIN="
goto nemo_done
:nemo_version
for /f "delims=" %%V in ('%NEMOBIN% --version 2^>nul') do echo   %%V
echo   Pulling the Parakeet model, about 714 MB, skipped if already cached...
if exist "%LOCALAPPDATA%\NeMoSpeech\models\nvidia\parakeet-tdt-0.6b-v3" (
  echo   Model already cached
) else (
  %NEMOBIN% pull parakeet-tdt
)
:nemo_done
echo.

REM -- .env --
echo [2/5] .env configuration
if exist ".env" (
  echo   .env exists, keeping it
) else if exist ".env.example" (
  copy /Y ".env.example" ".env" >nul
  echo   Created .env from .env.example. API keys can be pasted in the app
  echo   Settings UI or filled into the file directly.
) else (
  echo [WARN] .env.example missing - the app will create defaults on first run.
)
echo.

REM -- Python deps --
echo [3/5] Python dependencies
python -m pip install --quiet -r requirements.txt
if errorlevel 1 (
  echo [ERROR] pip install failed - check the output above
  pause
  exit /b 1
)
echo   requirements.txt installed

REM torch: pip's Windows default wheel is CPU-only. A GPU machine needs the
REM CUDA build from the pytorch index. PEP 440 gotcha: a plain ==2.11.0 pin
REM matches the installed +cpu wheel and installs nothing, so the local
REM version is pinned explicitly.
where nvidia-smi >nul 2>nul
if not errorlevel 1 (
  echo   Installing CUDA torch for TransNetV2 and YOLO...
  python -m pip install --quiet "torch==2.11.0+cu130" "torchvision==0.26.0+cu130" --index-url https://download.pytorch.org/whl/cu130
) else (
  echo   No NVIDIA GPU detected - keeping the CPU torch wheel.
)
echo.

REM -- Dashboard deps --
echo [4/5] Dashboard dependencies
if exist "dashboard\node_modules" (
  echo   node_modules already present
) else (
  pushd dashboard
  call npm.cmd install
  popd
  if errorlevel 1 (
    echo [ERROR] npm install failed - check the output above
    pause
    exit /b 1
  )
)
echo.

REM -- Final verification --
echo [5/5] Final checks
python -c "import fastapi, uvicorn, transcribe_backends" >nul 2>nul
if errorlevel 1 (
  echo [ERROR] backend imports failed - the app will not start. Check the pip output above.
  pause
  exit /b 1
)
echo   backend imports OK
echo.
echo ==================================================
echo  Setup complete.
echo  Next: run run.bat to start the app, then open
echo    http://localhost:5175
echo  Paste your API keys in Settings, or pick the AI
echo  provider there (auto / custom / gemini / openrouter
echo  / ollama). Keep this install fresh with update.bat.
echo ==================================================
pause
