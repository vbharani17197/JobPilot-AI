@echo off
REM ===========================================================
REM run_agent.bat - invoked by Windows Task Scheduler daily.
REM Runs the JobPilot-AI agent via Poetry from the project root.
REM ===========================================================

cd /d "%~dp0.."

REM Prefer Poetry; fall back to module execution if Poetry is absent.
where poetry >nul 2>nul
if %ERRORLEVEL%==0 (
    poetry run jobpilot
) else (
    python -m jobpilot.main
)

exit /b %ERRORLEVEL%
