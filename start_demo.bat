@echo off
echo.
echo  ██████  MPLAD FraudShield v1.0
echo  Fighting Corruption with AI - SIH 2025
echo.

echo [1/4] Starting Backend...
start "MPLAD Backend" cmd /k "cd /d C:\Users\SATYA\.gemini\antigravity\scratch\mplad-fraudshield\backend && python -m uvicorn main:app --reload --port 8000"

echo [2/4] Waiting for backend to start...
timeout /t 5 /nobreak > nul

echo [3/4] Starting Frontend...
start "MPLAD Frontend" cmd /k "cd /d C:\Users\SATYA\.gemini\antigravity\scratch\mplad-fraudshield\frontend && npm run dev"

echo [4/4] Waiting for frontend to start...
timeout /t 5 /nobreak > nul

echo.
echo  ✅ Backend  → http://localhost:8000
echo  ✅ Docs     → http://localhost:8000/docs
echo  ✅ Dashboard → http://localhost:5173
echo.

start "" "http://localhost:5173"
echo  Dashboard opened in browser!
pause