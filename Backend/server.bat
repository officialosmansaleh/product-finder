@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
  set "PY=.venv\Scripts\python.exe"
) else (
  set "PY=python"
)

echo Checking backend dependencies...
%PY% -c "import fastapi,uvicorn,pandas,openpyxl,multipart,pydantic,reportlab" >nul 2>&1
if errorlevel 1 (
  echo Installing missing dependencies from requirements.txt...
  %PY% -m pip install -r requirements.txt
  if errorlevel 1 (
    echo.
    echo Failed to install dependencies.
    goto :fail
  )
)

%PY% -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
if errorlevel 1 goto :fail
goto :end

:fail
echo.
echo Server failed to start. Press any key to close this window.
pause >nul

:end

