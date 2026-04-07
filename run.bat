@echo off
echo Installing dependencies...
pip install flask requests -q

echo.
echo ============================================
echo   LOCAL ACCESS:   http://localhost:5000
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i "IPv4"') do (
    set ip=%%a
    goto :found
)
:found
set ip=%ip: =%
echo   WIFI ACCESS:    http://%ip%:5000
echo   (share wifi link with anyone on same network)
echo ============================================
echo.

start "" http://localhost:5000
python app.py
