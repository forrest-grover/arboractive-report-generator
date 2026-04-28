@echo off
REM Double-click entry point for Windows users. Runs install.ps1 with an
REM execution-policy bypass so users don't have to fiddle with PowerShell
REM settings before the first install.
set SCRIPT_DIR=%~dp0
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%install.ps1" %*
pause
