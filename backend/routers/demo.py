"""
MPLAD FraudShield - Demo Mode & WebSocket Live Telemetry Router
Emits real-time forensic detection events to connected dashboard clients.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import List, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

logger = logging.getLogger("demo_ws")
router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket client connected. Total clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        logger.info(f"WebSocket client disconnected. Total clients: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        if not self.active_connections:
            return
        payload = json.dumps(message)
        dead = []
        for connection in list(self.active_connections):
            try:
                await connection.send_text(payload)
            except Exception as e:
                logger.warning(f"Error broadcasting to client: {e}")
                dead.append(connection)
        for d in dead:
            self.active_connections.discard(d)


manager = ConnectionManager()

SAMPLE_DEMO_EVENTS = [
    {
        "type": "NEW_FLAG",
        "project_id": "MPLAD-MA-2023-1018",
        "title": "Deep Borewell & Drinking Water Supply",
        "flag": "Duplicate GPS",
        "score": 94,
        "mp": "Smt. Supriya Sule",
        "amount": "₹42.50L",
        "location": "Baramati, Maharashtra",
        "risk_level": "CRITICAL",
        "detail": "GPS coordinates exactly match existing project #8841 within 0.0001°",
        "timestamp": "Just now",
        "step": 1,
    },
    {
        "type": "NEW_FLAG",
        "project_id": "MPLAD-UP-2023-4091",
        "title": "CC Road & Drainage Construction",
        "flag": "Tender Splitting (₹49.8L)",
        "score": 88,
        "mp": "Shri Ravi Kishan",
        "amount": "₹49.80L",
        "location": "Gorakhpur, Uttar Pradesh",
        "risk_level": "HIGH",
        "detail": "Sanctioned ₹49.8L — exactly ₹20,000 below statutory ₹50L tender board threshold",
        "timestamp": "Just now",
        "step": 2,
    },
    {
        "type": "NEW_FLAG",
        "project_id": "MPLAD-BI-2022-8114",
        "title": "Community Health Sub-Center",
        "flag": "Phantom Rapid Completion",
        "score": 96,
        "mp": "Shri Sanjay Jaiswal",
        "amount": "₹1.45 Cr",
        "location": "Paschim Champaran, Bihar",
        "risk_level": "CRITICAL",
        "detail": "Civil construction certified complete in 4 calendar days (benchmark: 180 days)",
        "timestamp": "Just now",
        "step": 3,
    },
    {
        "type": "NEW_FLAG",
        "project_id": "MPLAD-RJ-2023-3102",
        "title": "Solar High-Mast Street Lighting",
        "flag": "Vendor Cartel Concentration",
        "score": 91,
        "mp": "Shri Om Birla",
        "amount": "₹68.00L",
        "location": "Kota, Rajasthan",
        "risk_level": "CRITICAL",
        "detail": "Apex InfraCorp won 18 consecutive tenders in single district with 0 competing bids",
        "timestamp": "Just now",
        "step": 4,
    },
    {
        "type": "NEW_FLAG",
        "project_id": "MPLAD-KA-2023-7721",
        "title": "Anganwadi & Nutrition Center",
        "flag": "Ghost Asset (OSM Cross-Check)",
        "score": 95,
        "mp": "Shri Tejasvi Surya",
        "amount": "₹38.00L",
        "location": "Bangalore South, Karnataka",
        "risk_level": "CRITICAL",
        "detail": "OpenStreetMap building layer confirms dense vacant farmland with zero physical structures",
        "timestamp": "Just now",
        "step": 5,
    },
    {
        "type": "NEW_FLAG",
        "project_id": "MPLAD-WB-2022-5503",
        "title": "Paved Village Link Road",
        "flag": "Round Number Disbursement",
        "score": 82,
        "mp": "Dr. Kakoli Ghosh Dastidar",
        "amount": "₹50.00L",
        "location": "Barasat, West Bengal",
        "risk_level": "HIGH",
        "detail": "Disbursement exact multiple ₹50,00,000 with 0 itemized measurement book records",
        "timestamp": "Just now",
        "step": 6,
    },
    {
        "type": "NEW_FLAG",
        "project_id": "MPLAD-TN-2023-9044",
        "title": "Smart Anganwadi Learning Center",
        "flag": "Severe Citizen Sentiment Divergence",
        "score": 89,
        "mp": "Thiru Kanimozhi Karunanidhi",
        "amount": "₹55.00L",
        "location": "Thoothukkudi, Tamil Nadu",
        "risk_level": "HIGH",
        "detail": "92% of surveyed citizens reported facility remains locked with zero equipment installed",
        "timestamp": "Just now",
        "step": 7,
    },
    {
        "type": "NEW_FLAG",
        "project_id": "MPLAD-MP-2023-2287",
        "title": "Drinking Water Pipeline & Overhead Tank",
        "flag": "Fiscal Year-End Rush",
        "score": 85,
        "mp": "Shri V.D. Sharma",
        "amount": "₹74.00L",
        "location": "Khajuraho, Madhya Pradesh",
        "risk_level": "HIGH",
        "detail": "Sanctioned on March 30, disbursed 100% on March 31 to exhaust unspent funds",
        "timestamp": "Just now",
        "step": 8,
    },
    {
        "type": "NEW_FLAG",
        "project_id": "MPLAD-GJ-2023-6619",
        "title": "Veterinary Clinic & Cattle Shelter",
        "flag": "Plagiarized UC Text (NLP Plagiarism)",
        "score": 93,
        "mp": "Shri C.R. Patil",
        "amount": "₹62.00L",
        "location": "Navsari, Gujarat",
        "risk_level": "CRITICAL",
        "detail": "Utilization certificate text has 99.4% cosine similarity to project in adjacent block",
        "timestamp": "Just now",
        "step": 9,
    },
    {
        "type": "NEW_FLAG",
        "project_id": "MPLAD-DL-2023-1109",
        "title": "Public Library & Digital Lab",
        "flag": "Blacklisted Vendor Association",
        "score": 98,
        "mp": "Shri Manoj Tiwari",
        "amount": "₹85.00L",
        "location": "North East Delhi, Delhi",
        "risk_level": "CRITICAL",
        "detail": "Contractor GSTIN linked to directorship of blacklisted entity Devaraj Builders",
        "timestamp": "Just now",
        "step": 10,
    },
]

_demo_task: asyncio.Task | None = None


async def run_demo_simulation():
    """Broadcast fake real-time events every 2 seconds for 10 events, then broadcast completion."""
    logger.info("Initiating Live Demo analysis broadcast...")
    await manager.broadcast({
        "type": "DEMO_STARTED",
        "message": "🔴 LIVE ANALYSIS RUNNING... Scanning 847 national projects across 543 constituencies",
        "total_steps": len(SAMPLE_DEMO_EVENTS),
    })

    for idx, event in enumerate(SAMPLE_DEMO_EVENTS, 1):
        await asyncio.sleep(2.0)
        logger.info(f"Emitting demo flag {idx}/{len(SAMPLE_DEMO_EVENTS)}: {event['flag']} ({event['project_id']})")
        await manager.broadcast(event)

    await asyncio.sleep(1.0)
    await manager.broadcast({
        "type": "ANALYSIS_COMPLETE",
        "scanned": 847,
        "critical": 23,
        "high": 48,
        "funds_saved_estimate": "₹14.8 Cr",
        "message": "✅ Analysis Complete — 847 projects scanned, 23 CRITICAL flags raised",
    })
    logger.info("Live Demo analysis simulation complete.")


@router.post("/start")
async def start_demo_mode():
    """Trigger real-time demo mode simulation."""
    global _demo_task
    if _demo_task and not _demo_task.done():
        _demo_task.cancel()
    
    _demo_task = asyncio.create_task(run_demo_simulation())
    return {
        "status": "started",
        "message": "Live Demo simulation triggered. Events will be streamed over WebSocket.",
        "expected_events": 10,
        "interval_seconds": 2,
    }


@router.websocket("/ws/live-flags")
async def websocket_live_flags(websocket: WebSocket):
    """WebSocket endpoint for real-time live flags telemetry."""
    await manager.connect(websocket)
    try:
        await websocket.send_text(json.dumps({
            "type": "CONNECTED",
            "message": "Connected to MPLAD FraudShield Live Telemetry Engine.",
        }))
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("action") in {"start_demo", "trigger_demo"}:
                    asyncio.create_task(run_demo_simulation())
            except Exception:
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.warning(f"WebSocket error: {e}")
        manager.disconnect(websocket)
