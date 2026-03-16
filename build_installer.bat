@echo off
cd /d "%~dp0"

powershell -ExecutionPolicy Bypass -File ".\build_windows.ps1" -AppName KoreanSTT -AppVersion 1.0.0

if %ERRORLEVEL% neq 0 (
  echo Build failed.
  pause
  exit /b %ERRORLEVEL%
)

echo Build completed.
echo Installer location: dist\installer
pause
