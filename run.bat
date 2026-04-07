@echo off
echo Installing dependencies...
pip install flask requests -q

echo Starting Football Predictor...
start "" http://localhost:5000
python app.py
