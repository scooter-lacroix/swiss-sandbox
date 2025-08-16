@echo off
REM Swiss Sandbox MCP Server Startup Script for Windows
REM This script provides an easy way to start the Swiss Sandbox MCP server

echo Starting Swiss Sandbox MCP Server...

REM Get the directory containing this script
set SCRIPT_DIR=%~dp0

REM Set up Python path
set PYTHONPATH=%SCRIPT_DIR%src;%PYTHONPATH%
set PYTHONUNBUFFERED=1

echo Script directory: %SCRIPT_DIR%
echo Python path: %PYTHONPATH%

REM Try to start the unified server
python -m sandbox.unified_server %*
if %ERRORLEVEL% EQU 0 (
    echo Server started successfully
) else (
    echo Failed to start unified server, trying fallback...
    python "%SCRIPT_DIR%server.py" %*
    if %ERRORLEVEL% EQU 0 (
        echo Fallback server started successfully
    ) else (
        echo Failed to start server. Please check your installation.
        exit /b 1
    )
)