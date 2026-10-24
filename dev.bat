@echo off
rem Double-clickable wrapper for the dev-mode launcher (scripts/dev.ps1).
rem %~dp0 has a trailing backslash, so Join-Path is not needed here.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\dev.ps1" %*
if errorlevel 1 pause
