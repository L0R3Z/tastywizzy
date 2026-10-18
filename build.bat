@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PY=py -3
if exist ".venv\Scripts\python.exe" set PY=".venv\Scripts\python.exe"
%PY% -m pip install -q -r requirements-dev.txt || goto :err
%PY% -m PyInstaller --noconfirm --onefile --windowed --name TastyWizzy --paths src --add-data "config.example.json;." main.py || goto :err
echo.
echo Exécutable : dist\TastyWizzy.exe (copie-le avec ton config.json dans le dossier de ton choix)
pause
exit /b 0
:err
echo Échec de la construction.
pause
exit /b 1
