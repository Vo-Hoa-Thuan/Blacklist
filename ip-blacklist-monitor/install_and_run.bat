@echo off
echo ============================================
echo    IP Blacklist Monitor - Setup & Run
echo ============================================
echo.

:: Tìm Python
set PYTHON=
for %%P in (python python3) do (
    where %%P >nul 2>&1
    if not errorlevel 1 (
        set PYTHON=%%P
        goto :found
    )
)

:: Tìm trong các đường dẫn phổ biến
for %%P in (
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python39\python.exe"
    "C:\Python312\python.exe"
    "C:\Python311\python.exe"
    "C:\Python310\python.exe"
) do (
    if exist %%P (
        set PYTHON=%%P
        goto :found
    )
)

echo [LOI] Khong tim thay Python!
echo Vui long cai Python tu: https://www.python.org/downloads/
echo Khi cai, nho tick chon "Add Python to PATH"
pause
exit /b 1

:found
echo [OK] Tim thay Python: %PYTHON%
echo.
echo [1/2] Cai thu vien can thiet...
%PYTHON% -m pip install -r requirements.txt
if errorlevel 1 (
    echo [LOI] Cai thu vien that bai!
    pause
    exit /b 1
)
echo.
echo [2/2] Khoi dong ung dung...
%PYTHON% main.py
pause
