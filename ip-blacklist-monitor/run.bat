@echo off
echo ============================================
echo    IP Blacklist Monitor - Run
echo ============================================
echo.
set PYTHON=%LOCALAPPDATA%\Programs\Python\Python314\python.exe
if not exist "%PYTHON%" (
    echo [LOI] Khong tim thay Python 3.14!
    echo Vui long chay install_and_run.bat de cai dat.
    pause
    exit /b 1
)
echo Dang khoi dong...
"%PYTHON%" main.py
