#!/usr/bin/env bash
set -e

echo "==================================================="
echo "  Starting MPLAD FraudShield Demo (Unix/Linux/macOS)"
echo "==================================================="

echo "[1/4] Launching Docker containers..."
docker-compose up -d

echo ""
echo "[2/4] Waiting 10 seconds for services to initialize..."
sleep 10

echo ""
echo "[3/4] Running demo preparation and fraud verification..."
if docker-compose exec -T backend python demo_prep.py; then
    echo "Demo database seeded successfully via Docker container."
elif [ -f "./backend/demo_prep.py" ]; then
    python3 backend/demo_prep.py || python backend/demo_prep.py
fi

echo ""
echo "[4/4] Opening dashboard in browser..."
URL="http://localhost:5173"
if command -v open > /dev/null; then
    open "$URL"
elif command -v xdg-open > /dev/null; then
    xdg-open "$URL"
else
    echo "Please open $URL in your web browser."
fi

echo ""
echo "==================================================="
echo "  MPLAD FraudShield is live!"
echo "  Frontend : http://localhost:5173"
echo "  Backend  : http://localhost:8000"
echo "  API Docs : http://localhost:8000/docs"
echo "==================================================="
