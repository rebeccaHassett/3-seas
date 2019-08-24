@echo off
REM Batch command install pyinstaller
REM Runs on Windows

REM set the python version here

pyinstaller --windowed --add-data "creds.json;." --onefile victim.py

PAUSE