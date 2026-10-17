@echo off
chcp 65001 >nul
cd /d "%~dp0"
"C:\Users\Enzo Bassot\AppData\Local\Programs\Python\Python312\python.exe" main.py %*
pause
