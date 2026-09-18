@echo off
setlocal EnableExtensions EnableDelayedExpansion
title Pix2Vec - raster to vector
color 0B

set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"

echo.
echo   =====================================================
echo     Pix2Vec - raster to vector converter
echo   =====================================================
echo.

rem ---------------------------------------------------------------
rem  Step 1: find Python
rem ---------------------------------------------------------------
set "PYTHON_EXE="

where python >nul 2>&1
if not errorlevel 1 set "PYTHON_EXE=python"

if not defined PYTHON_EXE (
    where py >nul 2>&1
    if not errorlevel 1 set "PYTHON_EXE=py"
)

rem local (Microsoft Store style) installs
if not defined PYTHON_EXE (
    for /f "delims=" %%P in ('dir /b /s "%LOCALAPPDATA%\Python\pythoncore-*" 2^>nul') do (
        if exist "%%P\python.exe" if not defined PYTHON_EXE set "PYTHON_EXE=%%P\python.exe"
    )
    for /f "delims=" %%P in ('dir /b /s "%LOCALAPPDATA%\Microsoft\WindowsApps\python*.exe" 2^>nul') do (
        if not defined PYTHON_EXE set "PYTHON_EXE=%%P"
    )
)
if not defined PYTHON_EXE (
    for /f "delims=" %%P in ('dir /b /s "C:\Python*\python.exe" 2^>nul') do (
        if not defined PYTHON_EXE set "PYTHON_EXE=%%P"
    )
)
if not defined PYTHON_EXE (
    for /f "delims=" %%P in ('dir /b /s "C:\Program Files\Python*\python.exe" 2^>nul') do (
        if not defined PYTHON_EXE set "PYTHON_EXE=%%P"
    )
)

if not defined PYTHON_EXE (
    echo   [!] Python is not found.
    echo       Install Python 3.10+ from https://www.python.org/downloads/
    echo       and tick "Add python.exe to PATH" during setup.
    echo.
    pause
    exit /b 1
)

"%PYTHON_EXE%" -c "import sys;print(sys.version.split()[0])" > "%TEMP%\p2s_version.txt" 2>nul
set /p PYVER=<"%TEMP%\p2s_version.txt"
echo   [*] Python found: !PYVER!

rem ---------------------------------------------------------------
rem  Step 2: make virtual environment if needed
rem ---------------------------------------------------------------
set "VENV=%PROJECT_DIR%.venv"
set "VENV_PY=%VENV%\Scripts\python.exe"

if not exist "%VENV_PY%" (
    echo   [*] Creating virtual environment...
    "%PYTHON_EXE%" -m venv "%VENV%"
    if errorlevel 1 (
        echo   [!] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

rem ---------------------------------------------------------------
rem  Step 3: install dependencies if needed
rem ---------------------------------------------------------------
"%VENV_PY%" -c "import vtracer, PIL" >nul 2>&1
if errorlevel 1 (
    echo   [*] Installing dependencies ^(vtracer, pillow^)...
    "%VENV_PY%" -m pip install --disable-pip-version-check -r "%~dp0requirements.txt" >nul 2>&1
    if errorlevel 1 (
        echo   [!] pip install failed. Check internet connection.
        pause
        exit /b 1
    )
)

rem ---------------------------------------------------------------
rem  Step 4: run the converter (drag ^& drop a folder onto .bat works)
rem ---------------------------------------------------------------
chcp 65001 >nul
echo   [*] Starting...
echo.
if "%~1"=="" (
    "%VENV_PY%" -m pix2vec.main
) else (
    "%VENV_PY%" -m pix2vec.main %*
)

echo.
pause
endlocal
