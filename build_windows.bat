@echo off
REM Build a standalone Trident Dental Imaging .exe for Windows.
REM Run this ONCE on a Windows PC (the clinic PC or any Windows machine).
REM Output: dist\TridentDentalImaging.exe — copy that to the clinic PC.

echo === Trident Dental Imaging — Windows build ===

where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed.
    echo Download Python 3.11+ from https://www.python.org/downloads/windows/
    echo During install, check "Add Python to PATH".
    pause
    exit /b 1
)

if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)

call venv\Scripts\activate.bat

echo Installing dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller twain

echo Building executable...
pyinstaller --noconfirm --clean trident.spec

echo.
echo === Build complete ===
echo Output: dist\TridentDentalImaging\TridentDentalImaging.exe
echo Copy the entire 'dist\TridentDentalImaging' folder to the clinic PC.
pause
