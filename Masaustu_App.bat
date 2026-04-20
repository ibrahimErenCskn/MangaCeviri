@echo off
title Manhwa Masaustu Ceviri Araci
echo Manhwa Masaustu Ceviri Asistani Baslatiliyor...
cd /d "%~dp0"
call backend\venv\Scripts\activate.bat
python desktop_app.py
pause
