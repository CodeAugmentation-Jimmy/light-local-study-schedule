@echo off
cd /d "%~dp0"
for %%f in (*.py) do (
    py -3 "%%f"
    goto :finished
)
:finished
if errorlevel 1 pause
