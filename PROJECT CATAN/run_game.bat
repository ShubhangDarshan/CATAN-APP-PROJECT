@echo off
title Settlers of Catan (DOS-Box Edition)
cd /d "%~dp0"
python main.py
if errorlevel 1 (
    echo.
    echo Game terminated with an error code.
    pause
)
