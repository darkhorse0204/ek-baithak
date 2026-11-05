"""Loads the synthetic dataset once and exposes simple lookups."""
from __future__ import annotations

from functools import lru_cache

import pandas as pd

from .config import DATA_DIR

CITY_TIER = {
    "Ahmedabad": 1, "Bengaluru": 1, "Chennai": 1, "Delhi": 1, "Hyderabad": 1, "Kolkata": 1, "Mumbai": 1, "Pune": 1,
    "Bhopal": 2, "Coimbatore": 2, "Indore": 2, "Jaipur": 2, "Kochi": 2, "Lucknow": 2, "Ludhiana": 2, "Mysuru": 2,
    "Nagpur": 2, "Nashik": 2, "Patna": 2, "Surat": 2, "Vadodara": 2, "Visakhapatnam": 2,
}
CITY_STATE = {
    "Ahmedabad": "Gujarat", "Bengaluru": "Karnataka", "Chennai": "Tamil Nadu", "Delhi": "Delhi", "Hyderabad": "Telangana",
    "Kolkata": "West Bengal", "Mumbai": "Maharashtra", "Pune": "Maharashtra", "Bhopal": "Madhya Pradesh",
    "Coimbatore": "Tamil Nadu", "Indore": "Madhya Pradesh", "Jaipur": "Rajasthan", "Kochi": "Kerala",
    "Lucknow": "Uttar Pradesh", "Ludhiana": "Punjab", "Mysuru": "Karnataka", "Nagpur": "Maharashtra",
    "Nashik": "Maharashtra", "Patna": "Bihar", "Surat": "Gujarat", "Vadodara": "Gujarat", "Visakhapatnam": "Andhra Pradesh",
}


@lru_cache
def catalogue() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "product_catalogue.csv", dtype={"available_city_tiers": str})
    df["tiers"] = df.available_city_tiers.astype(str).str.split(";").map(lambda xs: {int(x) for x in xs})
    df["needs_one_of"] = df.requires_one_of.fillna("").map(lambda s: [p for p in s.split("|") if p])
    df["segments"] = df.target_segments.str.split(";")
    return df.set_index("product_id", drop=False)


@lru_cache
def leads() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "smb_leads.csv", dtype={"gstin": str, "udyam_number": str})


@lru_cache
def gstin_registry() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "mock_gstin_registry.csv", dtype=str).set_index("gstin", drop=False)


@lru_cache
def udyam_registry() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "mock_udyam_registry.csv", dtype=str).set_index("udyam_number", drop=False)


@lru_cache
def business_type_segment() -> dict[str, str]:
    """business_type -> segment, learned from the leads file."""
    lt = leads()[["business_type", "segment"]].drop_duplicates()
    return dict(zip(lt.business_type, lt.segment))
