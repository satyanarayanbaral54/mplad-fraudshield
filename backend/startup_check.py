"""
MPLAD FraudShield - Startup Health Check & Initialization Script
Ensures DB connectivity, Redis availability, AI key validation,
and auto-populates demo records if the database is unseeded.
"""
from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("startup_check")

from config import settings
from database import SessionLocal, engine, init_db
from sqlalchemy import text


BANNER = """
========================================================================
██████  MPLAD FraudShield v1.0
🇮🇳 Fighting corruption with AI | SIH 2025
========================================================================
✅ Backend ready at  : http://localhost:8000
✅ Dashboard at      : http://localhost:5173
✅ Interactive API Docs: http://localhost:8000/docs
========================================================================
"""


def check_database(max_retries: int = 5, retry_delay: float = 2.0) -> bool:
    """Check database connection with retry loop."""
    logger.info(f"Checking database connection to: {settings.database_url.split('@')[-1]}...")
    for attempt in range(1, max_retries + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("✅ Database connection established successfully.")
            return True
        except Exception as e:
            logger.warning(f"⚠️ [Attempt {attempt}/{max_retries}] Database connection failed: {e}")
            if attempt < max_retries:
                time.sleep(retry_delay)
    
    logger.error("❌ Failed to connect to database after maximum retries.")
    return False


def check_redis() -> bool:
    """Check Redis cache connection."""
    logger.info("Checking Redis connection...")
    try:
        import redis
        client = redis.from_url(settings.redis_url, socket_connect_timeout=2)
        if client.ping():
            logger.info("✅ Redis connected successfully.")
            return True
    except Exception as e:
        logger.warning(f"⚠️ Redis connection warning: {e}. (Async tasks/caching may operate in fallback mode)")
    return False


def check_gemini_key() -> bool:
    """Check if Gemini AI API key is configured."""
    key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if key and key.strip() and not key.startswith("your-"):
        logger.info("✅ GEMINI_API_KEY / GOOGLE_API_KEY is configured.")
        return True
    else:
        logger.warning("⚠️ GEMINI_API_KEY is not configured. Generative AI summaries will use rule-based fallback generators.")
        return False


def check_and_seed_database() -> None:
    """Verify tables exist and auto-run demo_prep if DB is empty."""
    init_db()
    
    from models.db_models import Project
    db = SessionLocal()
    try:
        count = db.query(Project).count()
        if count == 0:
            logger.info("🔄 Database is empty (0 projects found). Auto-running demo_prep.py...")
            import demo_prep
            demo_prep.main()
            logger.info("✅ Demo dataset generated and saved successfully.")
        else:
            logger.info(f"✅ Database contains {count} analyzed projects. Skipping demo seed.")
    except Exception as e:
        logger.warning(f"⚠️ DB inspection warning: {e}. Attempting demo prep initialization...")
        try:
            import demo_prep
            demo_prep.main()
        except Exception as err:
            logger.error(f"❌ Demo prep failed: {err}")
    finally:
        db.close()


def print_banner() -> None:
    """Print the startup banner."""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    print(BANNER)


def main() -> None:
    """Execute complete startup check sequence."""
    print("\n[MPLAD FraudShield] Initiating System Health & Startup Checks...\n")
    db_ok = check_database(max_retries=5, retry_delay=2.0)
    if not db_ok:
        logger.error("❌ Database health check failed. Halting startup.")
        sys.exit(1)

    check_redis()
    check_gemini_key()
    check_and_seed_database()
    print_banner()


if __name__ == "__main__":
    main()
