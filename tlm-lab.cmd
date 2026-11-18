@echo off
where py >nul 2>nul
if not errorlevel 1 (
    py -3 "%~dp0tlm-lab.py" %*
    exit /b
)
where python >nul 2>nul
if not errorlevel 1 (
    python "%~dp0tlm-lab.py" %*
    exit /b
)
echo Python was not found. Install Python 3.9 or newer, reopen the terminal, then run this command again.
exit /b 2
