@echo off
rem Walidator XML KT-1 - uruchamianie w Windows. Uzycie: kt1-validate.cmd plik.xml [opcje]
rem Wszystkie opcje sa przekazywane do kt1_validator.py (pomoc: "kt1-validate.cmd -h").
setlocal
set "SCRIPT=%~dp0kt1_validator.py"

where python >nul 2>nul
if %ERRORLEVEL%==0 (
    python "%SCRIPT%" %*
    goto :end
)
where py >nul 2>nul
if %ERRORLEVEL%==0 (
    py -3 "%SCRIPT%" %*
    goto :end
)
echo Nie znaleziono Pythona 3. Zainstaluj go ze strony https://www.python.org/downloads/ i sprobuj ponownie.
exit /b 2

:end
exit /b %ERRORLEVEL%
