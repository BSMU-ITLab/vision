@echo off
:: This script allows to run exe with debug logging level

:: Get the directory of the batch script
set "script_dir=%~dp0"

:: Find the first file with name ending in "-c.exe"
:: And run the exe-file with "--log-level=debug" argument
for /r "%script_dir%" %%F in (*-c.exe) do (
    "%%F" --log-level=debug
    exit /b
)

echo No exe-file found ending in "-c.exe" in the script's directory.
