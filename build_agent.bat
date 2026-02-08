@echo off
echo Building Windows Agent...

:: Ensure PyInstaller is installed
pip install pyinstaller

:: Clean previous builds
rmdir /s /q build dist

:: Build the agent
pyinstaller --noconfirm --onefile --windowed ^
    --name "ControllerAgent" ^
    --hidden-import=win32timezone ^
    --hidden-import=mss ^
    --hidden-import=pynput.keyboard._win32 ^
    --hidden-import=pynput.mouse._win32 ^
    --add-data "g:\Code\Windows\Controller Agent\agent\.env;." ^
    "g:\Code\Windows\Controller Agent\agent\main.py"

echo Build complete! Executable is in dist/ControllerAgent.exe
pause
