@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set "API_PORT=8011"
set "WEB_PORT=5211"

where uv.exe >nul 2>&1 || goto no_uv
where pnpm.cmd >nul 2>&1 || goto no_pnpm

rem This launcher is for local development. Keep it independent from a
rem production backend/.env (PostgreSQL/RabbitMQ may not be running).
set "DATABASE_URL=sqlite+pysqlite:///./data/ops_workbench.db"
set "DATABASE_AUTO_CREATE=true"
set "CELERY_TASK_ALWAYS_EAGER=true"
set "CELERY_TASK_EAGER_PROPAGATES=true"
set "VITE_API_PROXY_TARGET=http://127.0.0.1:%API_PORT%"

set "API_READY="
set "WEB_READY="
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "try { Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:%API_PORT%/health' -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }" >nul 2>&1
if not errorlevel 1 set "API_READY=1"
if not defined API_READY powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "if (Get-NetTCPConnection -State Listen -LocalPort %API_PORT% -ErrorAction SilentlyContinue) { exit 1 }; exit 0"
if errorlevel 1 goto api_port_busy
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "try { Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:%WEB_PORT%/' -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }" >nul 2>&1
if not errorlevel 1 set "WEB_READY=1"
if not defined WEB_READY powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "if (Get-NetTCPConnection -State Listen -LocalPort %WEB_PORT% -ErrorAction SilentlyContinue) { exit 1 }; exit 0"
if errorlevel 1 goto web_port_busy

if not exist "backend\.venv\Scripts\python.exe" (
  echo [SETUP] Installing backend dependencies...
  pushd "backend"
  uv sync --dev
  if errorlevel 1 (popd & goto failed)
  popd
)

if not exist "frontend\node_modules" (
  echo [SETUP] Installing frontend dependencies...
  pushd "frontend"
  call pnpm.cmd install
  if errorlevel 1 (popd & goto failed)
  popd
)

echo [SETUP] Applying database migrations (SQLite)...
pushd "backend"
".venv\Scripts\python.exe" -m alembic upgrade head
if errorlevel 1 (popd & goto failed)
popd

if not defined API_READY echo [START] Starting API on http://127.0.0.1:%API_PORT% ...
if not defined API_READY start "Ecommerce API" /D "%~dp0backend" cmd.exe /k ""%~dp0backend\.venv\Scripts\python.exe" -m uvicorn app.main:app --reload --host 127.0.0.1 --port %API_PORT%"
if not defined WEB_READY echo [START] Starting web app on http://127.0.0.1:%WEB_PORT% ...
if not defined WEB_READY start "Ecommerce Web" /D "%~dp0frontend" cmd.exe /k "pnpm.cmd dev --host 127.0.0.1 --port %WEB_PORT% --strictPort"

echo [WAIT] Checking services...
for /l %%I in (1,1,30) do (
  if not defined API_READY (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "try { Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:%API_PORT%/health' -TimeoutSec 1 | Out-Null; exit 0 } catch { exit 1 }" >nul 2>&1
    if not errorlevel 1 set "API_READY=1"
  )
  if not defined WEB_READY (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "try { Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:%WEB_PORT%/' -TimeoutSec 1 | Out-Null; exit 0 } catch { exit 1 }" >nul 2>&1
    if not errorlevel 1 set "WEB_READY=1"
  )
  if defined API_READY if defined WEB_READY goto ready
  timeout /t 1 /nobreak >nul
)

echo [ERROR] Services did not become ready within 30 seconds.
echo         Check the two service windows for the first error.
pause
exit /b 1

:ready
start "" "http://127.0.0.1:%WEB_PORT%"
echo [OK] Services are ready. Web: http://127.0.0.1:%WEB_PORT%
exit /b 0

:no_uv
echo [ERROR] uv was not found. Install uv and add it to PATH.
pause
exit /b 1

:no_pnpm
echo [ERROR] pnpm was not found. Install pnpm and add it to PATH.
pause
exit /b 1

:api_port_busy
echo [ERROR] API port %API_PORT% is occupied by another service.
pause
exit /b 1

:web_port_busy
echo [ERROR] Web port %WEB_PORT% is occupied by another service.
pause
exit /b 1

:failed
echo [ERROR] Dependency setup failed. Review the output above.
pause
exit /b 1
