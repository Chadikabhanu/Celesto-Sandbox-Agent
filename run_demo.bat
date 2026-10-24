@echo off
REM ============================================================================
REM Celesto Sandbox Code Verification Agent - One-Click Video Demo Launcher
REM ============================================================================
title Celesto Sandbox Agent - Live Demo Walkthrough
color 0B
cls

echo ============================================================================
echo   CELESTO SANDBOX CODE VERIFICATION AGENT - DEMO LAUNCHER
echo ============================================================================
echo.
echo Select Demo Mode:
echo   [1] Automated Hands-Free Mode (Recommended for video recording)
echo   [2] Interactive Step-by-Step Mode (Press Enter between scenes)
echo   [3] Run Contract Test Suite (pytest tests/test_reports.py -v)
echo.
set /p mode="Enter choice (1, 2, or 3) [Default: 1]: "

if "%mode%"=="2" goto INTERACTIVE
if "%mode%"=="3" goto TESTS
goto AUTO

:AUTO
cls
echo Starting Automated Hands-Free Demo Walkthrough (Pacing: 2.0s per step)...
echo Get ready to read your voiceover script!
echo.
python scripts\demo_walkthrough.py --auto --delay 2.0
goto END

:INTERACTIVE
cls
echo Starting Interactive Demo Walkthrough...
echo Press Enter at each step when prompted.
echo.
python scripts\demo_walkthrough.py
goto END

:TESTS
cls
echo Running Phase 6 Submission Contract Test Suite...
pytest tests\test_reports.py -v
goto END

:END
echo.
echo ============================================================================
echo Demonstration finished. Press any key to exit.
echo ============================================================================
pause >nul
