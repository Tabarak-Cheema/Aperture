@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"

echo.
echo === Aperture ===
echo Working dir: %CD%
echo.

REM --- 1. Ensure uv is available (auto-install via the official script) ----
REM  uv is Astral's fast Python manager. It downloads Python 3.12 if your
REM  system Python is missing / too new / too old, creates the venv in
REM  milliseconds and only ever installs pre-built wheels.
set "UV_INSTALL_DIR=%USERPROFILE%\.local\bin"
set "PATH=%UV_INSTALL_DIR%;%PATH%"

where uv >nul 2>&1
if errorlevel 1 (
  echo Installing uv ^(one-time, ~15 MB^)...
  powershell -ExecutionPolicy Bypass -NoProfile -Command "irm https://astral.sh/uv/install.ps1 | iex"
  if errorlevel 1 (
    echo [ERROR] Failed to install uv. Check your network connection.
    pause
    exit /b 1
  )
  REM Pick up the new PATH entry inside this session
  set "PATH=%USERPROFILE%\.local\bin;%PATH%"
)

where uv >nul 2>&1
if errorlevel 1 (
  echo [ERROR] uv installed but not on PATH. Open a new terminal and retry.
  pause
  exit /b 1
)

echo uv ready.
echo.

REM --- 2. Make sure uv has a Python 3.12 available ------------------------
echo Checking for Python 3.12 ^(will download via uv if missing^)...
uv python install 3.12 2>nul

REM --- 3. Create venv against Python 3.12 ---------------------------------
REM  If an old / broken venv exists (e.g. created against Python 3.14 earlier),
REM  move it aside so we start clean.
if exist .venv (
  for /f "tokens=1,2 delims=." %%a in ('.venv\Scripts\python -c "import sys;print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2^>nul') do (
    set VENV_MAJOR=%%a
    set VENV_MINOR=%%b
  )
  if not defined VENV_MAJOR goto :recreate_venv
  if !VENV_MAJOR! NEQ 3 goto :recreate_venv
  if !VENV_MINOR! LSS 10 goto :recreate_venv
  if !VENV_MINOR! GEQ 14 goto :recreate_venv
  goto :venv_ok
  :recreate_venv
  echo Existing .venv uses an incompatible Python ^(!VENV_MAJOR!.!VENV_MINOR!^) -- recreating.
  if exist _venv_old rmdir /s /q _venv_old >nul 2>&1
  ren .venv _venv_old >nul 2>&1
)
echo Creating .venv with Python 3.12...
uv venv --python 3.12 .venv
if errorlevel 1 (
  echo [ERROR] Failed to create venv.
  pause
  exit /b 1
)
:venv_ok

REM --- 4. Install Python requirements (wheels only, no source builds) -----
echo.
echo === Installing Python requirements ===
uv pip install --python .venv\Scripts\python.exe --only-binary=:all: -r requirements.txt
if errorlevel 1 (
  echo [ERROR] pip install failed. See messages above.
  pause
  exit /b 1
)

REM --- 5. Node + web deps --------------------------------------------------
where node >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Node 20+ not on PATH. Install from https://nodejs.org/
  pause
  exit /b 1
)
where npm >nul 2>&1
if errorlevel 1 (
  echo [ERROR] npm not on PATH
  pause
  exit /b 1
)

pushd apps\web
if not exist node_modules (
  echo.
  echo === Installing web dependencies ===
  call npm install --legacy-peer-deps
  if errorlevel 1 (
    echo [ERROR] npm install failed.
    popd
    pause
    exit /b 1
  )
)
popd

REM --- 6. PYTHONPATH ------------------------------------------------------
set PYTHONPATH=packages\aqir;packages\catalog;packages\llm_gateway;services\compile;services\query;services\ingest;services\insight;apps\server

REM --- 7. Launch server + web --------------------------------------------
echo.
echo === Launching ===
start "aperture-server" cmd /k ".venv\Scripts\python.exe -m uvicorn apps.server.aperture_server.main:app --port 8000 --reload"
timeout /t 2 /nobreak >nul

pushd apps\web
start "aperture-web" cmd /k "npm run dev"
popd

timeout /t 5 /nobreak >nul
start "" http://localhost:5173

:status_loop
cls
echo ============================================================
echo    Aperture is up.
echo.
echo    Open:        http://localhost:5173
echo    API docs:    http://localhost:8000/docs
echo.
echo    Everything runs locally. No account, no sign-in.
echo    Create your first project in the UI, then upload files and ask.
echo.
echo    Two service windows are open - close them to stop.
echo    Ctrl+C in this window to stop the status refresh.
echo    Last refresh: %date% %time%
echo ============================================================
timeout /t 10 /nobreak >nul
goto status_loop
