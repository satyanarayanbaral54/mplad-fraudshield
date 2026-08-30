@echo off
echo ===================================================
echo   Starting MPLAD FraudShield Demo (Windows)
echo ===================================================
echo [1/4] Launching Docker containers...
docker-compose up -d

echo.
echo [2/4] Waiting 10 seconds for services to initialize...
timeout /t 10 /nobreak >nul

echo.
echo [3/4] Running demo preparation and fraud verification...
docker-compose exec -T backend python demo_prep.py 2>nul || python backend/demo_prep.py

echo.
echo [4/4] Opening dashboard in browser...
start http://localhost:5173

echo.
echo ===================================================
echo   MPLAD FraudShield is live!
echo   Frontend : http://localhost:5173
echo   Backend  : http://localhost:8000
echo   API Docs : http://localhost:8000/docs
echo ===================================================
pause
