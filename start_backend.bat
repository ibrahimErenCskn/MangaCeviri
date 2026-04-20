@echo off
echo ===================================
echo   Manhwa Ceviri Backend Baslat
echo ===================================
echo.

cd /d "%~dp0backend"

REM Virtual environment kontrolu
if not exist "venv" (
    echo [*] Virtual environment olusturuluyor...
    python -m venv venv
    echo [*] Kurulum tamamlandi.
)

echo [*] Virtual environment aktif ediliyor...
call venv\Scripts\activate.bat

echo [*] Bagimliliklar yukleniyor...
pip install -r requirements.txt --quiet

echo.
echo [*] Backend baslatiliyor (port 8899)...
echo [*] Durdurmak icin Ctrl+C basin
echo.
python main.py
