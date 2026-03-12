@echo off
echo ============================================
echo    IP Blacklist Monitor - WEB SERVER
echo ============================================
echo.
set PYTHON=%LOCALAPPDATA%\Programs\Python\Python314\python.exe
if not exist "%PYTHON%" (
    echo [LOI] Khong tim thay Python 3.14!
    pause
    exit /b 1
)

echo Dang cai dat Flask...
"%PYTHON%" -m pip install Flask requests --quiet

echo.
echo Dang khoi dong Web Server...
"%PYTHON%" app.py
pause
