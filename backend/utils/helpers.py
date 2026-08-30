"""
MPLAD FraudShield - Data Ingestion & Forensic Preprocessing Utilities
Includes synthetic data generator, feature engineering, and end-to-end preprocessing pipeline.
"""
import os
import sys
import random
import string
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple, Union, Optional

import numpy as np
import pandas as pd

# Ensure module path resolution works under all execution contexts
_current_dir = os.path.dirname(os.path.abspath(__file__))
_parent_dir = os.path.abspath(os.path.join(_current_dir, ".."))
for p in [_current_dir, _parent_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from benchmark_data import benchmark_costs, get_state_benchmark
except ImportError:
    try:
        from utils.benchmark_data import benchmark_costs, get_state_benchmark
    except ImportError:
        from backend.utils.benchmark_data import benchmark_costs, get_state_benchmark


# ---------------------------------------------------------------------------
# District GPS Lookup Dictionary (~50 Major Indian Districts)
# ---------------------------------------------------------------------------
DISTRICT_GPS_LOOKUP: Dict[str, Tuple[float, float]] = {
    "Prayagraj": (25.4358, 81.8463),
    "Varanasi": (25.3176, 82.9739),
    "Lucknow": (26.8467, 80.9462),
    "Gorakhpur": (26.7606, 83.3732),
    "Kanpur Nagar": (26.4499, 80.3319),
    "Agra": (27.1767, 78.0081),
    "Patna": (25.5941, 85.1376),
    "Gaya": (24.7914, 85.0002),
    "Muzaffarpur": (26.1209, 85.3647),
    "Darbhanga": (26.1542, 85.8918),
    "Bhagalpur": (25.2425, 86.9842),
    "Jaipur": (26.9124, 75.7873),
    "Jodhpur": (26.2389, 73.0243),
    "Kota": (25.2138, 75.8648),
    "Udaipur": (24.5854, 73.7125),
    "Ajmer": (26.4499, 74.6399),
    "Indore": (22.7196, 75.8577),
    "Bhopal": (23.2599, 77.4126),
    "Gwalior": (26.2183, 78.1828),
    "Jabalpur": (23.1815, 79.9864),
    "Ujjain": (23.1765, 75.7885),
    "Pune": (18.5204, 73.8567),
    "Nagpur": (21.1458, 79.0882),
    "Nashik": (19.9975, 73.7898),
    "Thane": (19.2183, 72.9781),
    "Aurangabad": (19.8762, 75.3433),
    "Bengaluru Urban": (12.9716, 77.5946),
    "Mysuru": (12.2958, 76.6394),
    "Belagavi": (15.8497, 74.4977),
    "Dharwad": (15.4589, 75.0078),
    "Mangaluru": (12.9141, 74.8560),
    "Ahmedabad": (23.0225, 72.5714),
    "Surat": (21.1702, 72.8311),
    "Vadodara": (22.3072, 73.1812),
    "Rajkot": (22.3039, 70.8022),
    "Bhavnagar": (21.7645, 72.1519),
    "Chennai": (13.0827, 80.2707),
    "Coimbatore": (11.0168, 76.9558),
    "Madurai": (9.9252, 78.1198),
    "Tiruchirappalli": (10.7905, 78.7047),
    "Salem": (11.6643, 78.1460),
    "Kolkata": (22.5726, 88.3639),
    "Howrah": (22.5958, 88.2636),
    "North 24 Parganas": (22.7210, 88.4810),
    "South 24 Parganas": (22.1950, 88.1900),
    "Hooghly": (22.9042, 88.3912),
    "Puri": (19.8135, 85.8312),
    "Cuttack": (20.4625, 85.8828),
    "Khordha": (20.1809, 85.6200),
    "Ranchi": (23.3441, 85.3096),
    "Dhanbad": (23.7957, 86.4304),
    "Raipur": (21.2514, 81.6296),
    "Durg": (21.1904, 81.2849),
}

# ---------------------------------------------------------------------------
# Predefined Master Lists
# ---------------------------------------------------------------------------
STATES_DISTRICTS = {
    "Uttar Pradesh": ["Prayagraj", "Varanasi", "Lucknow", "Gorakhpur", "Kanpur Nagar", "Agra"],
    "Bihar": ["Patna", "Gaya", "Muzaffarpur", "Darbhanga", "Bhagalpur"],
    "Rajasthan": ["Jaipur", "Jodhpur", "Kota", "Udaipur", "Ajmer"],
    "Madhya Pradesh": ["Indore", "Bhopal", "Gwalior", "Jabalpur", "Ujjain"],
    "Maharashtra": ["Pune", "Nagpur", "Nashik", "Thane", "Aurangabad"],
    "Karnataka": ["Bengaluru Urban", "Mysuru", "Belagavi", "Dharwad", "Mangaluru"],
    "Gujarat": ["Ahmedabad", "Surat", "Vadodara", "Rajkot", "Bhavnagar"],
    "Tamil Nadu": ["Chennai", "Coimbatore", "Madurai", "Tiruchirappalli", "Salem"],
    "West Bengal": ["Kolkata", "Howrah", "North 24 Parganas", "South 24 Parganas", "Hooghly"],
    "Odisha": ["Puri", "Cuttack", "Khordha"],
    "Jharkhand": ["Ranchi", "Dhanbad"],
    "Chhattisgarh": ["Raipur", "Durg"],
}

MP_CONSTITUENCIES = [
    ("Shri Ramesh Kumar", "Phoolpur (UP-52)", "Uttar Pradesh", "Prayagraj"),
    ("Smt. Priya Sharma", "Allahabad (UP-53)", "Uttar Pradesh", "Prayagraj"),
    ("Shri Arvind Singh", "Patna Sahib (BR-30)", "Bihar", "Patna"),
    ("Smt. Meena Devi", "Jaipur Rural (RJ-06)", "Rajasthan", "Jaipur"),
    ("Shri Suresh Patel", "Indore (MP-26)", "Madhya Pradesh", "Indore"),
    ("Shri Pinaki Mishra", "Puri (OD-17)", "Odisha", "Puri"),
    ("Shri Ramakant Yadav", "Azamgarh (UP-69)", "Uttar Pradesh", "Gorakhpur"),
    ("Smt. Ananya Sen", "Diamond Harbour (WB-21)", "West Bengal", "South 24 Parganas"),
    ("Shri Rajesh Patil", "Pune (MH-34)", "Maharashtra", "Pune"),
    ("Shri D. Kathir Anand", "Vellore (TN-08)", "Tamil Nadu", "Salem"),
    ("Shri Tejasvi Surya", "Bengaluru South (KA-26)", "Karnataka", "Bengaluru Urban"),
    ("Smt. Darshana Jardosh", "Surat (GJ-24)", "Gujarat", "Surat"),
    ("Shri Sanjay Seth", "Ranchi (JH-08)", "Jharkhand", "Ranchi"),
    ("Shri Sunil Soni", "Raipur (CG-08)", "Chhattisgarh", "Raipur"),
    ("Shri Ravi Shankar", "Varanasi (UP-77)", "Uttar Pradesh", "Varanasi"),
]

WORK_TYPES = [
    "Road Construction & Culverts",
    "School Classroom & Lab Building",
    "Solar High-Mast Street Lighting",
    "Deep Borewell & Drinking Water Supply",
    "Community Health Center Expansion",
    "Anganwadi & Nutritious Meal Center",
    "Public Sanitation Complex & Toilets",
    "Drainage Canal Paving",
    "Community Hall & Cyclone Shelter",
    "Model Digital Library & Smart Class",
]

VENDORS_POOL = [
    ("Apex Infra Buildtech Pvt Ltd", "REG-UP-98213", "AABCA1234F"),
    ("Shree Balaji Constructions", "REG-BR-45210", "BCDEF2345G"),
    ("National Highway Contractors", "REG-MH-11209", "CDEFG3456H"),
    ("Pioneer Civil Works", "REG-RJ-77412", "DEFGH4567J"),
    ("Sai Krupa Water Solutions", "REG-MP-88321", "EFGHI5678K"),
    ("Bharat Engineering Associates", "REG-TN-66543", "FGHIJ6789L"),
    ("Green Valley Infrastructure", "REG-KA-55432", "GHIJK7890M"),
    ("Om Shakti Roadways", "REG-GJ-99120", "HIJKL8901N"),
    ("Trimurti Civil Developers", "REG-WB-33219", "IJKLM9012P"),
    ("Eastern Shelter Builders", "REG-OD-22104", "JKLMN0123Q"),
    ("Surya Power & Solar Ltd", "REG-DL-44321", "KLMNO1234R"),
    ("Durga Infratech Projects", "REG-JH-77651", "LMNOP2345S"),
]

REQUIRED_COLUMNS = [
    "project_id", "mp_name", "constituency", "state", "district",
    "work_type", "latitude", "longitude", "recommended_date",
    "sanction_date", "completion_date", "status", "allocated_amount",
    "sanctioned_amount", "expenditure_reported", "unspent_balance",
    "vendor_name", "vendor_reg_no", "vendor_pan", "vendor_registration_date",
    "contract_amount", "has_photo", "photo_urls", "uc_text"
]


# ---------------------------------------------------------------------------
# Synthetic Dataset Generator
# ---------------------------------------------------------------------------
def generate_sample_mplad_dataset(n_records: int = 500) -> pd.DataFrame:
    """
    Generates a realistic synthetic MPLAD dataset with 500 records as a pandas DataFrame.
    Includes deliberate fraud anomalies for forensic demo and ML training.
    """
    random.seed(42)
    np.random.seed(42)

    records: List[Dict[str, Any]] = []

    def random_date(start_year: int = 2021, end_year: int = 2024) -> datetime:
        start = datetime(start_year, 1, 1)
        end = datetime(end_year, 12, 31)
        return start + timedelta(days=random.randint(0, (end - start).days))

    for i in range(1, n_records + 1):
        mp_info = random.choice(MP_CONSTITUENCIES)
        mp_name, constituency, state, district = mp_info
        work_type = random.choice(WORK_TYPES)
        vendor = random.choice(VENDORS_POOL)

        base_gps = DISTRICT_GPS_LOOKUP.get(district, (25.0, 82.0))
        lat = round(base_gps[0] + random.uniform(-0.08, 0.08), 6)
        lon = round(base_gps[1] + random.uniform(-0.08, 0.08), 6)

        rec_date = random_date(2021, 2023)
        sanc_date = rec_date + timedelta(days=random.randint(15, 90))
        duration_days = random.randint(60, 300)
        comp_date = sanc_date + timedelta(days=duration_days)

        status = random.choices(["Completed", "Ongoing", "Sanctioned", "Stalled"], weights=[0.65, 0.20, 0.10, 0.05])[0]

        # Financials in ₹
        allocated = round(random.uniform(500000, 7500000), 2)
        sanctioned = round(allocated * random.uniform(0.90, 1.0), 2)
        if status == "Completed":
            expenditure = round(sanctioned * random.uniform(0.92, 1.05), 2)
        elif status == "Ongoing":
            expenditure = round(sanctioned * random.uniform(0.30, 0.70), 2)
        else:
            expenditure = round(sanctioned * random.uniform(0.0, 0.25), 2)

        unspent = max(0.0, round(sanctioned - expenditure, 2))
        contract_amt = round(sanctioned * random.uniform(0.95, 1.0), 2)

        has_photo = True if status == "Completed" and random.random() > 0.10 else False
        photo_urls = f"https://mplad-portal.gov.in/photos/geo_proof_{i}.jpg" if has_photo else ""

        vendor_reg_date = rec_date - timedelta(days=random.randint(300, 2500))

        clean_uc_text = (
            f"Karya '{work_type}' at Gram Panchayat {district} successfully completed. "
            f"Total expenditure Rs {expenditure:,.2f} verified against Sanction Order {rec_date.strftime('%Y')}/MPLAD/{i}. "
            f"Site inspection conducted by Junior Engineer PWD on {comp_date.strftime('%d-%b-%Y')}. "
            f"All quality benchmarks, MB book entries, and muster rolls found satisfactory. Upayogita Praman Patra niyamit hai."
        )

        records.append({
            "project_id": f"MPLAD-{state[:2].upper()}-{2021 + (i % 4)}-{1000 + i}",
            "mp_name": mp_name,
            "constituency": constituency,
            "state": state,
            "district": district,
            "work_type": work_type,
            "latitude": lat,
            "longitude": lon,
            "recommended_date": rec_date.strftime("%Y-%m-%d"),
            "sanction_date": sanc_date.strftime("%Y-%m-%d"),
            "completion_date": comp_date.strftime("%Y-%m-%d") if status == "Completed" else "",
            "status": status,
            "allocated_amount": allocated,
            "sanctioned_amount": sanctioned,
            "expenditure_reported": expenditure,
            "unspent_balance": unspent,
            "vendor_name": vendor[0],
            "vendor_reg_no": vendor[1],
            "vendor_pan": vendor[2],
            "vendor_registration_date": vendor_reg_date.strftime("%Y-%m-%d"),
            "contract_amount": contract_amt,
            "has_photo": has_photo,
            "photo_urls": photo_urls,
            "uc_text": clean_uc_text,
        })

    df = pd.DataFrame(records)

    # 1. 15 projects with duplicate GPS coordinates (< 50m)
    dup_center_lat, dup_center_lon = 25.435800, 81.846300
    for idx in range(10, 25):
        df.at[idx, "latitude"] = round(dup_center_lat + random.uniform(-0.0002, 0.0002), 6)
        df.at[idx, "longitude"] = round(dup_center_lon + random.uniform(-0.0002, 0.0002), 6)
        df.at[idx, "uc_text"] = "Work completed as per norms, funds utilized properly as sanctioned. Karya niyamanoosar sampann hua."

    # 2. 20 projects where same vendor won 4+ projects from same MP (Collusion)
    collusion_mp = "Shri Ramakant Yadav"
    collusion_constituency = "Azamgarh (UP-69)"
    collusion_vendor = ("Apex Infra Buildtech Pvt Ltd", "REG-UP-98213", "AABCA1234F")
    for idx in range(40, 60):
        df.at[idx, "mp_name"] = collusion_mp
        df.at[idx, "constituency"] = collusion_constituency
        df.at[idx, "vendor_name"] = collusion_vendor[0]
        df.at[idx, "vendor_reg_no"] = collusion_vendor[1]
        df.at[idx, "vendor_pan"] = collusion_vendor[2]
        df.at[idx, "uc_text"] = "Work completed as per norms, funds utilized properly as sanctioned. Rashi ka upayog uchit paya gaya."

    # 3. 25 projects with cost_per_unit / expenditure 3x state average (Inflated Bills)
    for idx in range(80, 105):
        orig_alloc = df.at[idx, "allocated_amount"]
        inflated_alloc = round(orig_alloc * 3.2, 2)
        df.at[idx, "allocated_amount"] = inflated_alloc
        df.at[idx, "sanctioned_amount"] = inflated_alloc
        df.at[idx, "expenditure_reported"] = round(inflated_alloc * 1.15, 2)
        df.at[idx, "contract_amount"] = inflated_alloc
        df.at[idx, "uc_text"] = "Work completed as per norms, funds utilized properly as sanctioned. Bil prastut kiya gaya aur bhugtan sampann hua."

    # 4. 10 projects completed in under 15 days (Physically Impossible)
    for idx in range(130, 140):
        s_date = datetime.strptime(df.at[idx, "sanction_date"], "%Y-%m-%d")
        impossible_comp = s_date + timedelta(days=random.randint(4, 11))
        df.at[idx, "status"] = "Completed"
        df.at[idx, "completion_date"] = impossible_comp.strftime("%Y-%m-%d")
        df.at[idx, "work_type"] = "Road Construction & Culverts"
        df.at[idx, "expenditure_reported"] = df.at[idx, "sanctioned_amount"]
        df.at[idx, "uc_text"] = "Work completed as per norms, funds utilized properly as sanctioned in record time."

    # 5. 30 projects with utilization rate > 0.95 in February-March (Year-End Rush)
    for idx in range(160, 190):
        rush_year = 2023
        rush_month = random.choice([2, 3])
        rush_day = random.randint(15, 28 if rush_month == 2 else 30)
        s_date = datetime(rush_year, rush_month, rush_day)
        c_date = s_date + timedelta(days=random.randint(3, 10))
        sanc_val = df.at[idx, "sanctioned_amount"]

        df.at[idx, "sanction_date"] = s_date.strftime("%Y-%m-%d")
        df.at[idx, "completion_date"] = c_date.strftime("%Y-%m-%d")
        df.at[idx, "status"] = "Completed"
        df.at[idx, "expenditure_reported"] = round(sanc_val * random.uniform(0.96, 0.999), 2)
        df.at[idx, "unspent_balance"] = round(sanc_val - df.at[idx, "expenditure_reported"], 2)
        df.at[idx, "uc_text"] = "Work completed as per norms, funds utilized properly as sanctioned before fiscal year ending March 31."

    # 6. 8 projects marked 'Completed' with NO photo proof (Phantom Completion)
    for idx in range(210, 218):
        df.at[idx, "status"] = "Completed"
        df.at[idx, "has_photo"] = False
        df.at[idx, "photo_urls"] = ""
        df.at[idx, "expenditure_reported"] = df.at[idx, "sanctioned_amount"]
        df.at[idx, "uc_text"] = "Work completed as per norms, funds utilized properly as sanctioned. Photo proof awaiting portal upload."

    return df


# ---------------------------------------------------------------------------
# Data Cleaning & Normalization Functions
# ---------------------------------------------------------------------------
def validate_dataset_schema(df: pd.DataFrame) -> Tuple[bool, List[str]]:
    """
    Checks if all required columns exist in the DataFrame.
    Returns (is_valid, missing_columns_list).
    """
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    return (len(missing) == 0, missing)


def normalize_amounts(df: pd.DataFrame, to_lakhs: bool = True) -> pd.DataFrame:
    """
    Normalizes all monetary columns to ₹ Lakhs.
    If already in Lakhs, preserves scale; otherwise converts raw Rupees to Lakhs.
    """
    df_clean = df.copy()
    money_cols = ["allocated_amount", "sanctioned_amount", "expenditure_reported", "unspent_balance", "contract_amount"]

    for col in money_cols:
        if col in df_clean.columns:
            if df_clean[col].dropna().median() > 10000:
                df_clean[col] = df_clean[col].apply(lambda x: round(float(x) / 1e5, 4) if pd.notnull(x) else 0.0)
            else:
                df_clean[col] = df_clean[col].astype(float).round(4)

    return df_clean


def parse_dates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Converts all date columns to standard datetime objects.
    """
    df_clean = df.copy()
    date_cols = ["recommended_date", "sanction_date", "completion_date", "vendor_registration_date"]

    for col in date_cols:
        if col in df_clean.columns:
            df_clean[col] = pd.to_datetime(df_clean[col], errors="coerce")

    return df_clean


def fill_missing_gps(df: pd.DataFrame) -> pd.DataFrame:
    """
    Fills missing or invalid latitude/longitude using the district GPS lookup dictionary.
    """
    df_clean = df.copy()

    for idx, row in df_clean.iterrows():
        lat = row.get("latitude")
        lon = row.get("longitude")
        district = str(row.get("district", "")).strip()

        if pd.isnull(lat) or pd.isnull(lon) or lat == 0 or lon == 0:
            if district in DISTRICT_GPS_LOOKUP:
                base_lat, base_lon = DISTRICT_GPS_LOOKUP[district]
                df_clean.at[idx, "latitude"] = round(base_lat + random.uniform(-0.02, 0.02), 6)
                df_clean.at[idx, "longitude"] = round(base_lon + random.uniform(-0.02, 0.02), 6)

    return df_clean


def load_csv_dataset(filepath: str) -> pd.DataFrame:
    """
    Loads, validates, cleans, and standardizes an MPLAD CSV dataset.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Dataset file not found at: {filepath}")

    df = pd.read_csv(filepath)
    is_valid, missing = validate_dataset_schema(df)
    if not is_valid:
        raise ValueError(f"CSV schema invalid. Missing required columns: {missing}")

    df = fill_missing_gps(df)
    df = parse_dates(df)
    df = normalize_amounts(df)
    return df


# ---------------------------------------------------------------------------
# Feature Engineering Pipeline
# ---------------------------------------------------------------------------
def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes forensic and operational audit features on the cleaned MPLAD dataset.
    """
    df_feat = df.copy()

    date_cols = ["recommended_date", "sanction_date", "completion_date", "vendor_registration_date"]
    for col in date_cols:
        if col in df_feat.columns and not pd.api.types.is_datetime64_any_dtype(df_feat[col]):
            df_feat[col] = pd.to_datetime(df_feat[col], errors="coerce")

    # 1. utilization_rate = expenditure_reported / allocated_amount (clip 0 to 1.5)
    alloc = df_feat["allocated_amount"].replace(0, np.nan)
    exp = df_feat["expenditure_reported"].fillna(0.0)
    df_feat["utilization_rate"] = (exp / alloc).fillna(0.0).clip(lower=0.0, upper=1.5).round(4)

    # 2. days_to_completion = (completion_date - sanction_date).dt.days (negative/uncompleted = -1)
    if "completion_date" in df_feat.columns and "sanction_date" in df_feat.columns:
        diff_days = (df_feat["completion_date"] - df_feat["sanction_date"]).dt.days
        df_feat["days_to_completion"] = diff_days.apply(lambda x: int(x) if pd.notnull(x) and x >= 0 else -1)
    else:
        df_feat["days_to_completion"] = -1

    # 3. cost_per_unit = sanctioned_amount / 1.0 (or length/area field if present, else 1)
    df_feat["cost_per_unit"] = df_feat["sanctioned_amount"].astype(float).round(4)

    # 4. completion_month = completion_date.dt.month (or sanction month as fallback)
    comp_month = df_feat["completion_date"].dt.month
    sanc_month = df_feat["sanction_date"].dt.month
    df_feat["completion_month"] = comp_month.combine_first(sanc_month).fillna(0).astype(int)

    # 5. year_end_rush_flag = 1 if completion_month in [2, 3] else 0
    df_feat["year_end_rush_flag"] = df_feat["completion_month"].apply(lambda m: 1 if m in [2, 3] else 0)

    # 6. vendor_project_count = count of how many times each vendor_name appears
    if "vendor_name" in df_feat.columns:
        df_feat["vendor_project_count"] = df_feat.groupby("vendor_name")["project_id"].transform("count")
    else:
        df_feat["vendor_project_count"] = 1

    # 7. mp_avg_utilization = mean utilization_rate per mp_name across all their projects
    if "mp_name" in df_feat.columns:
        df_feat["mp_avg_utilization"] = df_feat.groupby("mp_name")["utilization_rate"].transform("mean").round(4)
    else:
        df_feat["mp_avg_utilization"] = df_feat["utilization_rate"]

    # 8. days_recommend_to_sanction = (sanction_date - recommended_date).dt.days
    if "sanction_date" in df_feat.columns and "recommended_date" in df_feat.columns:
        rec_diff = (df_feat["sanction_date"] - df_feat["recommended_date"]).dt.days
        df_feat["days_recommend_to_sanction"] = rec_diff.fillna(-1).astype(int)
    else:
        df_feat["days_recommend_to_sanction"] = -1

    # 9. vendor_days_before_contract = (sanction_date - vendor_registration_date).dt.days
    if "sanction_date" in df_feat.columns and "vendor_registration_date" in df_feat.columns:
        v_diff = (df_feat["sanction_date"] - df_feat["vendor_registration_date"]).dt.days
        df_feat["vendor_days_before_contract"] = v_diff.fillna(-1).astype(int)
    else:
        df_feat["vendor_days_before_contract"] = -1

    # 10. is_phantom = 1 if status == 'completed' AND has_photo == False else 0
    status_series = df_feat["status"].astype(str).str.strip().str.lower()
    has_photo_series = df_feat["has_photo"].fillna(False).astype(bool)
    photo_urls_series = df_feat["photo_urls"].fillna("").astype(str).str.strip()

    is_phantom_mask = (status_series == "completed") & (~has_photo_series | (photo_urls_series == ""))
    df_feat["is_phantom"] = is_phantom_mask.astype(int)

    # 11. state_benchmark = lookup from benchmark_costs[state][work_type]
    benchmarks = []
    for _, row in df_feat.iterrows():
        st = str(row.get("state", "DEFAULT")).strip()
        wt = str(row.get("work_type", "")).strip()
        benchmarks.append(get_state_benchmark(st, wt))
    df_feat["state_benchmark"] = benchmarks

    # 12. cost_deviation_pct = (cost_per_unit - state_benchmark) / state_benchmark * 100
    st_bench = df_feat["state_benchmark"].replace(0, np.nan)
    df_feat["cost_deviation_pct"] = (((df_feat["cost_per_unit"] - st_bench) / st_bench) * 100).fillna(0.0).round(2)

    return df_feat


def preprocess_pipeline(filepath_or_df: Union[str, pd.DataFrame]) -> pd.DataFrame:
    """
    End-to-end processing pipeline:
    Loads / accepts DataFrame -> Validates -> Imputes GPS -> Parses Dates -> Normalizes -> Engineers Features.
    Returns analysis-ready DataFrame.
    """
    if isinstance(filepath_or_df, str):
        df = pd.read_csv(filepath_or_df)
    elif isinstance(filepath_or_df, pd.DataFrame):
        df = filepath_or_df.copy()
    else:
        raise TypeError("Expected file path string or pandas DataFrame.")

    # 1. Validate Schema
    is_valid, missing = validate_dataset_schema(df)
    if not is_valid:
        raise ValueError(f"Dataset schema invalid. Missing required columns: {missing}")

    # 2. Impute GPS
    df = fill_missing_gps(df)

    # 3. Parse Dates
    df = parse_dates(df)

    # 4. Normalize Amounts to ₹ Lakhs
    df = normalize_amounts(df, to_lakhs=True)

    # 5. Feature Engineering
    df_engineered = engineer_features(df)

    return df_engineered


# ---------------------------------------------------------------------------
# Legacy and Common Utilities
# ---------------------------------------------------------------------------
def generate_ref_id(prefix: str = "MPLAD") -> str:
    """Generate a short unique reference ID."""
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
    return f"{prefix}-{suffix}"


def crore_to_rupees(crore: float) -> float:
    return crore * 1e7


def rupees_to_crore(rupees: float) -> float:
    return rupees / 1e7


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    if denominator == 0:
        return default
    return numerator / denominator


def date_diff_months(start: datetime, end: datetime) -> float:
    delta = end - start
    return delta.days / 30.44


def format_risk_badge(risk_level: str) -> Dict[str, str]:
    mapping = {
        "LOW": {"color": "green", "label": "Low Risk"},
        "MEDIUM": {"color": "yellow", "label": "Medium Risk"},
        "HIGH": {"color": "orange", "label": "High Risk"},
        "CRITICAL": {"color": "red", "label": "Critical Risk"},
    }
    return mapping.get(risk_level, {"color": "gray", "label": "Unknown"})


# ---------------------------------------------------------------------------
# Main Execution: Generate & Save Dataset
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(current_dir, "..", "data")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "sample_dataset.csv")

    print("[*] Generating synthetic MPLAD dataset with 500 records & forensic fraud signals...")
    df_sample = generate_sample_mplad_dataset(500)
    df_sample.to_csv(output_path, index=False, encoding="utf-8")

    print(f"[OK] Saved {len(df_sample)} records to {os.path.abspath(output_path)}")
    print(f"     - Columns count: {len(df_sample.columns)}")
    print(f"     - Fraud patterns injected: duplicate GPS (15), cartel vendor (20), cost overruns (25), impossible completion (10), year-end rush (30), phantom completion (8).")

    print("\n[*] Testing Preprocessing & Feature Engineering Pipeline...")
    df_ready = preprocess_pipeline(output_path)
    print(f"[OK] Pipeline execution successful! Analysis-ready shape: {df_ready.shape}")
    print(f"     - Engineered Features Added: {[c for c in df_ready.columns if c not in df_sample.columns]}")
