@echo off
setlocal EnableDelayedExpansion
title OpenShorts Updater
cd /d "%~dp0"
echo ==================================================
echo  OpenShorts - updater
echo  Pulls the latest code, refreshes dependencies,
echo  models and the agent knowledge graph.
echo ==================================================
echo.

REM -- Force UTF-8 for Python (job logs use emoji) --
if defined PYTHONUTF8 (
  if not "%PYTHONUTF8%"=="0" if not "%PYTHONUTF8%"=="1" set "PYTHONUTF8=1"
)
if not defined PYTHONUTF8 set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

echo [1/6] Git pull
git fetch origin
if errorlevel 1 (
  echo [WARN] git fetch failed - offline or no remote. Skipping code update.
  goto deps
)
git status --porcelain | findstr /r /n "^" >nul 2>nul
if not errorlevel 1 (
  echo   Local changes detected - stashing them first...
  git stash push -m "update.bat auto-stash" >nul 2>nul
  set STASHED=1
)
git pull --ff-only origin
if errorlevel 1 (
  echo [WARN] git pull failed, diverged or conflicting. Staying on the current commit.
)
if defined STASHED (
  echo   Restoring your local changes from stash...
  git stash pop >nul 2>nul
  set STASHED=
)
echo   Code updated
echo.

:deps
echo [2/6] Python dependencies
python -m pip install --quiet -r requirements.txt
if errorlevel 1 (
  echo [WARN] pip install had errors - see above
) else (
  echo   requirements.txt up to date
)
echo.

echo [2b/6] CUDA torch (GPU scene detection + tracking)
where nvidia-smi >nul 2>nul
if not errorlevel 1 (
  python -m pip install --quiet "torch==2.11.0+cu130" "torchvision==0.26.0+cu130" --index-url https://download.pytorch.org/whl/cu130
  echo   torch CUDA wheel ensured
) else (
  echo   No NVIDIA GPU detected - keeping the CPU torch wheel.
)
echo.

echo [3/6] Dashboard dependencies
if not exist "dashboard\node_modules" (
  pushd dashboard
  call npm.cmd install
  popd
) else (
  pushd dashboard
  call npm.cmd install --no-audit --no-fund
  popd
)
echo   node_modules up to date
echo.

echo [4/6] Transcription runtime
set "NEMOSPEECH_BIN_DIR=%LOCALAPPDATA%\Programs\NeMoSpeech\bin"
if exist "%NEMOSPEECH_BIN_DIR%\nemo-speech.exe" (
  echo   nemo-speech present - upgrading silently if a newer release exists...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "iex ((irm 'https://github.com/NVIDIA/NeMo-Speech.cpp/raw/main/scripts/install.ps1') + ' -BinaryOnly')" >nul 2>nul
  if exist "%NEMOSPEECH_BIN_DIR%\nemo-speech.exe" (
    "%NEMOSPEECH_BIN_DIR%\nemo-speech.exe" --version
  )
) else (
  echo [WARN] nemo-speech missing - run setup.bat to install it
)
echo.

echo [5/6] Agent knowledge graph
if exist "graphify-out\graph.json" (
  where graphify >nul 2>nul
  if not errorlevel 1 (
    echo   Refreshing the code knowledge graph...
    graphify update . 2>nul || echo [WARN] graph refresh skipped - run setup.bat and re-run the graphify skill for a full rebuild
  ) else (
    echo   graphify CLI not found - install it with: uv tool install graphifyy
  )
) else (
  echo   No graph yet - first build happens via the graphify skill, not update.bat
)
echo.

echo [6/6] Cleanup
python -c "import pathlib, shutil; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('__pycache__')]"
echo   __pycache__ cleared
echo.

echo ==================================================
echo  Update complete. Restart the app with run.bat
echo  (run.bat kills the old backend and frontend first).
echo ==================================================
pause
