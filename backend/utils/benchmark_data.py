"""
Benchmark data generator and CPWD cost reference tables for MPLAD FraudShield.
"""
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any

STATES = [
    "Uttar Pradesh", "Maharashtra", "Bihar", "Rajasthan", "Madhya Pradesh",
    "Tamil Nadu", "Karnataka", "Gujarat", "West Bengal", "Odisha",
    "Jharkhand", "Chhattisgarh", "Andhra Pradesh", "Telangana", "Kerala",
    "Punjab", "Haryana", "Assam", "Delhi"
]

PROJECT_CATEGORIES = [
    "Construction of school building",
    "Road development and widening",
    "Community water supply project",
    "Construction of rural hospital",
    "Solar street light installation",
    "Bridge construction",
    "Drainage system improvement",
    "Public toilet complex",
    "Anganwadi center construction",
    "Rainwater harvesting structure",
]

VENDOR_NAMES = [
    "Bharat Construction Co.", "Sunrise Infrastructure Ltd.",
    "National Builders Pvt. Ltd.", "Apex Engineering Works",
    "Pioneer Civil Contractors", "Green Valley Developers",
    "Om Sai Constructions", "Shree Ram Infrastructure",
    "Jai Hind Projects", "Trimurti Civil Works",
]

MP_NAMES = [
    "Shri Ramesh Kumar", "Smt. Priya Sharma", "Shri Arvind Singh",
    "Smt. Meena Devi", "Shri Suresh Patel",
]

# ---------------------------------------------------------------------------
# CPWD-based State-wise Cost Benchmarks (in ₹ Lakhs per project/unit)
# ---------------------------------------------------------------------------
BASE_CPWD_RATES = {
    "Road Construction & Culverts": 35.0,
    "School Classroom & Lab Building": 25.0,
    "Solar High-Mast Street Lighting": 5.0,
    "Deep Borewell & Drinking Water Supply": 8.0,
    "Community Health Center Expansion": 45.0,
    "Anganwadi & Nutritious Meal Center": 12.0,
    "Public Sanitation Complex & Toilets": 7.5,
    "Drainage Canal Paving": 18.0,
    "Community Hall & Cyclone Shelter": 55.0,
    "Model Digital Library & Smart Class": 15.0,
}

STATE_COST_MULTIPLIERS = {
    "Uttar Pradesh": 0.95,
    "Bihar": 0.90,
    "Rajasthan": 1.05,
    "Madhya Pradesh": 0.95,
    "Maharashtra": 1.15,
    "Karnataka": 1.10,
    "Gujarat": 1.08,
    "Tamil Nadu": 1.05,
    "West Bengal": 0.98,
    "Odisha": 0.92,
    "Jharkhand": 0.90,
    "Chhattisgarh": 0.92,
    "Andhra Pradesh": 1.02,
    "Telangana": 1.06,
    "Kerala": 1.20,
    "Punjab": 1.05,
    "Haryana": 1.08,
    "Assam": 1.12,
    "Delhi": 1.25,
    "DEFAULT": 1.00,
}

# Generate state-wise benchmark dictionary
benchmark_costs: Dict[str, Dict[str, float]] = {}
for state, mult in STATE_COST_MULTIPLIERS.items():
    benchmark_costs[state] = {
        work_type: round(base_rate * mult, 2)
        for work_type, base_rate in BASE_CPWD_RATES.items()
    }


def get_state_benchmark(state: str, work_type: str) -> float:
    """Returns the CPWD cost benchmark in ₹ Lakhs for a given state & work type."""
    state_table = benchmark_costs.get(state, benchmark_costs["DEFAULT"])
    return state_table.get(work_type, BASE_CPWD_RATES.get(work_type, 20.0))


def generate_sample_vendors(n: int = 20) -> List[Dict[str, Any]]:
    vendors = []
    for i in range(n):
        contracts = random.randint(1, 15)
        avg_val = random.uniform(500000, 5000000)
        vendors.append({
            "name": random.choice(VENDOR_NAMES) + f" #{i+1}",
            "registration_number": f"REG{random.randint(100000, 999999)}",
            "pan_number": f"AAAAB{random.randint(1000, 9999)}C",
            "blacklisted": random.random() < 0.05,
            "risk_score": round(random.uniform(0, 100), 2),
            "total_contracts": contracts,
            "total_contract_value": round(contracts * avg_val, 2),
        })
    return vendors


def generate_sample_projects(n: int = 50) -> List[Dict[str, Any]]:
    projects = []
    for i in range(n):
        allocated = round(random.uniform(500000, 10000000), 2)
        disbursed = round(allocated * random.uniform(0.3, 1.1), 2)
        expenditure = round(allocated * random.uniform(0.2, 1.3), 2)
        start = datetime.now() - timedelta(days=random.randint(60, 1000))
        projects.append({
            "title": random.choice(PROJECT_CATEGORIES) + f" - {random.choice(STATES)} #{i+1}",
            "description": "Development project sanctioned under MPLAD scheme.",
            "mp_constituency": f"Constituency-{random.randint(1, 543)}",
            "mp_name": random.choice(MP_NAMES),
            "state": random.choice(STATES),
            "district": f"District-{random.randint(1, 50)}",
            "allocated_amount": allocated,
            "disbursed_amount": min(disbursed, allocated * 1.05),
            "expenditure": expenditure,
            "status": random.choice(["PROPOSED", "SANCTIONED", "ONGOING", "COMPLETED", "STALLED"]),
            "latitude": round(random.uniform(8.0, 35.0), 6),
            "longitude": round(random.uniform(68.0, 97.0), 6),
            "start_date": start.isoformat(),
        })
    return projects
