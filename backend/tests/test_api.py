"""
API Integration Tests — run AFTER starting uvicorn server on port 8000
Run: python -m pytest tests/test_api.py -v
"""
import pytest
import httpx

BASE = "http://localhost:8000"

def test_health():
    r = httpx.get(f"{BASE}/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"

def test_ingest_sample_data():
    r = httpx.post(f"{BASE}/api/v1/ingest/use-sample", timeout=90)
    assert r.status_code == 200
    data = r.json()
    assert data.get("projects_ingested", 0) > 0
    print(f"\n✅ Ingested: {data.get('projects_ingested')} projects")

def test_dashboard_summary():
    r = httpx.get(f"{BASE}/api/v1/dashboard/summary", timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert "total_projects" in data
    assert data["total_projects"] > 0

def test_get_projects():
    r = httpx.get(f"{BASE}/api/v1/projects/?limit=10", timeout=30)
    assert r.status_code in [200, 404]  # 404 ok if empty
    if r.status_code == 200:
        data = r.json()
        items = data.get("projects", data) if isinstance(data, dict) else data
        print(f"\n✅ Got {len(items)} projects")

def test_vendor_network():
    r = httpx.get(f"{BASE}/api/v1/dashboard/network", timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert "nodes" in data

def test_map_data():
    r = httpx.get(f"{BASE}/api/v1/dashboard/map", timeout=30)
    assert r.status_code == 200

def test_critical_projects_exist():
    r = httpx.get(f"{BASE}/api/v1/projects/?risk_level=CRITICAL&limit=100", timeout=30)
    assert r.status_code == 200
    data = r.json()
    items = data.get("projects", data) if isinstance(data, dict) else data
    assert len(items) > 0, "Must have at least 1 CRITICAL project after sample data ingestion"
    print(f"\n✅ CRITICAL projects: {len(items)}")