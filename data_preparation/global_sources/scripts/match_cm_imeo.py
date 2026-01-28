#!/usr/bin/env python3
"""
Match Carbon Mapper plumes with IMEO plumes by timestamp and location.

This script:
1. Fetches CM plumes via API (with individual emissions per plume)
2. Loads IMEO plumes
3. Matches plumes by date (same day) and location (within 1km)
4. Compares emission rates for the same observation

Key insight: IMEO re-quantifies satellite data (including EMIT) using their MARS
algorithm, so matched plumes represent the SAME observation with DIFFERENT
quantification methods.

Usage:
    python match_cm_imeo.py              # Run full matching
    python match_cm_imeo.py --explore    # Only run exploratory analysis
"""

import argparse
import json
import os
from datetime import datetime
from math import radians, sin, cos, sqrt, atan2
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import numpy as np
import pandas as pd
import requests

# Paths
SCRIPTS_DIR = Path(__file__).parent
GLOBAL_SOURCES_DIR = SCRIPTS_DIR.parent

CM_PROCESSED_DIR = GLOBAL_SOURCES_DIR / "methane_CM_processed"
CM_RAW_DIR = GLOBAL_SOURCES_DIR / "methane_CM_raw"
IMEO_DIR = GLOBAL_SOURCES_DIR / "methane_raw_imeo" / "_downloads_unep_methanedata_detected_plumes_csv"
OUTPUT_DIR = GLOBAL_SOURCES_DIR / "methane_CM_processed"

API_BASE_URL = "https://api.carbonmapper.org/api/v1"

# Argentina bounding box
ARGENTINA_BBOX = (-73.5, -55.0, -53.6, -21.8)

# Matching parameters
DISTANCE_THRESHOLD_KM = 1.0  # 1 km spatial matching
DATE_TOLERANCE_DAYS = 0  # Same day only (for plume matching)


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate Haversine distance between two points in km."""
    R = 6371.0  # Earth radius in km

    lat1_rad = radians(lat1)
    lat2_rad = radians(lat2)
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)

    a = sin(dlat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return R * c


def fetch_cm_plumes(
    bbox: Tuple[float, float, float, float],
    sectors: List[str] = ["1B2"],
    plume_gas: str = "CH4",
) -> pd.DataFrame:
    """
    Fetch Carbon Mapper plumes from API with individual emission rates.
    """
    print("\n📡 Fetching CM plumes from API...")

    url = f"{API_BASE_URL}/catalog/plumes/annotated"
    all_plumes = []
    offset = 0
    limit = 1000

    while True:
        params = {
            "bbox": list(bbox),
            "sectors": sectors,
            "plume_gas": plume_gas,
            "status": "published",
            "limit": limit,
            "offset": offset,
        }

        response = requests.get(url, params=params, timeout=60)
        response.raise_for_status()
        data = response.json()

        plumes = data.get("items", [])
        if not plumes:
            break

        all_plumes.extend(plumes)
        print(f"   Retrieved {len(plumes)} plumes (total: {len(all_plumes)})")

        if len(plumes) < limit:
            break
        offset += limit

    print(f"   ✅ Total CM plumes: {len(all_plumes)}")

    # Convert to DataFrame
    records = []
    for p in all_plumes:
        # Extract coordinates from geometry
        geom = p.get("geometry_json", {})
        coords = geom.get("coordinates", [None, None]) if geom else [None, None]

        # Parse timestamp
        ts = p.get("scene_timestamp")

        records.append({
            "cm_plume_id": p.get("plume_id"),
            "cm_scene_id": p.get("scene_id"),
            "cm_timestamp": ts,
            "cm_longitude": coords[0],
            "cm_latitude": coords[1],
            "cm_emission_kg_hr": p.get("emission_auto"),
            "cm_emission_uncertainty_kg_hr": p.get("emission_uncertainty_auto"),
            "cm_instrument": p.get("instrument"),
            "cm_platform": p.get("platform"),
        })

    df = pd.DataFrame(records)

    # Parse timestamps
    df["cm_timestamp"] = pd.to_datetime(df["cm_timestamp"], format="mixed", utc=True)
    df["cm_date"] = df["cm_timestamp"].dt.date

    return df


def load_imeo_plumes() -> pd.DataFrame:
    """Load IMEO plume data for Argentina Oil & Gas."""
    print("\n📊 Loading IMEO plumes...")

    imeo_plumes_file = IMEO_DIR / "unep_methanedata_detected_plumes.csv"
    if not imeo_plumes_file.exists():
        raise FileNotFoundError(f"IMEO plumes not found: {imeo_plumes_file}")

    df = pd.read_csv(imeo_plumes_file)

    # Filter for Argentina O&G
    df = df[
        (df["country"] == "Argentina") &
        (df["sector"] == "Oil and Gas")
    ].copy()

    # Parse dates
    df["tile_date"] = pd.to_datetime(df["tile_date"], format="mixed", utc=True)
    df["imeo_date"] = df["tile_date"].dt.date

    # Rename columns for clarity
    df = df.rename(columns={
        "id_plume": "imeo_plume_id",
        "source_name": "imeo_source_name",
        "satellite": "imeo_satellite",
        "lat": "imeo_latitude",
        "lon": "imeo_longitude",
        "ch4_fluxrate": "imeo_emission_kg_hr",
        "ch4_fluxrate_std": "imeo_emission_uncertainty_kg_hr",
        "tile": "imeo_tile",
        "detection_institution": "imeo_detection_institution",
        "quantification_institution": "imeo_quantification_institution",
    })

    print(f"   IMEO Argentina O&G plumes: {len(df)}")

    return df


def match_plumes(
    cm_plumes: pd.DataFrame,
    imeo_plumes: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Match CM plumes to IMEO plumes by date and location.

    For same-day, same-location plumes, this likely represents the SAME
    satellite observation quantified by different methods.
    """
    print("\n" + "=" * 60)
    print("PLUME-TO-PLUME MATCHING")
    print("=" * 60)
    print(f"Distance threshold: {DISTANCE_THRESHOLD_KM} km")
    print(f"Date tolerance: {DATE_TOLERANCE_DAYS} days (same day)")

    matched = []
    cm_matched_ids = set()
    imeo_matched_ids = set()

    for _, cm_row in cm_plumes.iterrows():
        cm_date = cm_row["cm_date"]
        cm_lat = cm_row["cm_latitude"]
        cm_lon = cm_row["cm_longitude"]

        if pd.isna(cm_lat) or pd.isna(cm_lon):
            continue

        best_match = None
        best_dist = float("inf")

        for _, imeo_row in imeo_plumes.iterrows():
            imeo_date = imeo_row["imeo_date"]

            # Check date match
            if cm_date != imeo_date:
                continue

            imeo_lat = imeo_row["imeo_latitude"]
            imeo_lon = imeo_row["imeo_longitude"]

            # Check spatial proximity
            dist = haversine_distance(cm_lat, cm_lon, imeo_lat, imeo_lon)

            if dist <= DISTANCE_THRESHOLD_KM and dist < best_dist:
                best_dist = dist
                best_match = imeo_row

        if best_match is not None:
            matched.append({
                # CM plume data
                "cm_plume_id": cm_row["cm_plume_id"],
                "cm_timestamp": cm_row["cm_timestamp"],
                "cm_date": str(cm_row["cm_date"]),
                "cm_longitude": cm_row["cm_longitude"],
                "cm_latitude": cm_row["cm_latitude"],
                "cm_emission_kg_hr": cm_row["cm_emission_kg_hr"],
                "cm_emission_uncertainty_kg_hr": cm_row["cm_emission_uncertainty_kg_hr"],
                "cm_instrument": cm_row["cm_instrument"],
                "cm_platform": cm_row["cm_platform"],
                # IMEO plume data
                "imeo_plume_id": best_match["imeo_plume_id"],
                "imeo_source_name": best_match["imeo_source_name"],
                "imeo_date": str(best_match["imeo_date"]),
                "imeo_longitude": best_match["imeo_longitude"],
                "imeo_latitude": best_match["imeo_latitude"],
                "imeo_emission_kg_hr": best_match["imeo_emission_kg_hr"],
                "imeo_emission_uncertainty_kg_hr": best_match["imeo_emission_uncertainty_kg_hr"],
                "imeo_satellite": best_match["imeo_satellite"],
                "imeo_tile": best_match["imeo_tile"],
                "imeo_detection_institution": best_match["imeo_detection_institution"],
                "imeo_quantification_institution": best_match["imeo_quantification_institution"],
                # Match metadata
                "match_distance_km": best_dist,
            })
            cm_matched_ids.add(cm_row["cm_plume_id"])
            imeo_matched_ids.add(best_match["imeo_plume_id"])

    matched_df = pd.DataFrame(matched)

    # Calculate emission ratio
    if not matched_df.empty:
        valid = matched_df["cm_emission_kg_hr"].notna() & matched_df["imeo_emission_kg_hr"].notna()
        matched_df["emission_ratio_cm_imeo"] = np.where(
            valid & (matched_df["imeo_emission_kg_hr"] > 0),
            matched_df["cm_emission_kg_hr"] / matched_df["imeo_emission_kg_hr"],
            np.nan
        )

    print(f"\n✅ Matched plumes: {len(matched_df)}")

    # Unmatched plumes
    cm_only = cm_plumes[~cm_plumes["cm_plume_id"].isin(cm_matched_ids)].copy()
    imeo_only = imeo_plumes[~imeo_plumes["imeo_plume_id"].isin(imeo_matched_ids)].copy()

    print(f"   CM-only plumes: {len(cm_only)}")
    print(f"   IMEO-only plumes: {len(imeo_only)}")

    return matched_df, cm_only, imeo_only


def analyze_matches(matched_df: pd.DataFrame) -> Dict:
    """Analyze matched plumes and generate statistics."""
    if matched_df.empty:
        return {}

    print("\n" + "=" * 60)
    print("MATCH ANALYSIS")
    print("=" * 60)

    stats = {}

    # Emission comparison
    valid = matched_df.dropna(subset=["cm_emission_kg_hr", "imeo_emission_kg_hr"])
    if len(valid) > 0:
        mean_ratio = valid["emission_ratio_cm_imeo"].mean()
        median_ratio = valid["emission_ratio_cm_imeo"].median()

        print(f"\n📊 Emission Rate Comparison (n={len(valid)})")
        print(f"   Mean CM emission: {valid['cm_emission_kg_hr'].mean():.0f} kg/hr")
        print(f"   Mean IMEO emission: {valid['imeo_emission_kg_hr'].mean():.0f} kg/hr")
        print(f"   Mean CM/IMEO ratio: {mean_ratio:.2f}")
        print(f"   Median CM/IMEO ratio: {median_ratio:.2f}")

        stats["emission_comparison"] = {
            "n_valid": len(valid),
            "cm_mean_emission": float(valid["cm_emission_kg_hr"].mean()),
            "cm_median_emission": float(valid["cm_emission_kg_hr"].median()),
            "imeo_mean_emission": float(valid["imeo_emission_kg_hr"].mean()),
            "imeo_median_emission": float(valid["imeo_emission_kg_hr"].median()),
            "mean_ratio": float(mean_ratio),
            "median_ratio": float(median_ratio),
        }

        # Categorize by ratio
        low_ratio = (valid["emission_ratio_cm_imeo"] < 0.5).sum()
        high_ratio = (valid["emission_ratio_cm_imeo"] > 2.0).sum()
        mid_ratio = len(valid) - low_ratio - high_ratio

        print(f"\n   Ratio distribution:")
        print(f"   CM << IMEO (ratio < 0.5): {low_ratio}")
        print(f"   CM ≈ IMEO (0.5 ≤ ratio ≤ 2): {mid_ratio}")
        print(f"   CM >> IMEO (ratio > 2): {high_ratio}")

        stats["ratio_distribution"] = {
            "low": int(low_ratio),
            "mid": int(mid_ratio),
            "high": int(high_ratio),
        }

    # Instrument breakdown
    if "cm_instrument" in matched_df.columns:
        print(f"\n📊 By CM Instrument:")
        for inst, group in matched_df.groupby("cm_instrument"):
            valid_group = group.dropna(subset=["cm_emission_kg_hr", "imeo_emission_kg_hr"])
            if len(valid_group) > 0:
                ratio = valid_group["emission_ratio_cm_imeo"].mean()
                print(f"   {inst}: n={len(valid_group)}, mean ratio={ratio:.2f}")

    # IMEO satellite breakdown
    if "imeo_satellite" in matched_df.columns:
        print(f"\n📊 By IMEO Satellite:")
        for sat, group in matched_df.groupby("imeo_satellite"):
            valid_group = group.dropna(subset=["cm_emission_kg_hr", "imeo_emission_kg_hr"])
            if len(valid_group) > 0:
                ratio = valid_group["emission_ratio_cm_imeo"].mean()
                print(f"   {sat}: n={len(valid_group)}, mean ratio={ratio:.2f}")

    # Show individual matches
    print(f"\n📋 All Matched Plumes:")
    for _, row in matched_df.iterrows():
        cm_em = row["cm_emission_kg_hr"]
        imeo_em = row["imeo_emission_kg_hr"]
        ratio = row["emission_ratio_cm_imeo"]

        cm_str = f"{cm_em:.0f}" if pd.notna(cm_em) else "N/A"
        imeo_str = f"{imeo_em:.0f}" if pd.notna(imeo_em) else "N/A"
        ratio_str = f"{ratio:.2f}" if pd.notna(ratio) else "N/A"

        print(f"   {row['cm_date']} | {row['cm_plume_id']}")
        print(f"      CM: {cm_str} kg/hr ({row['cm_instrument']})")
        print(f"      IMEO: {imeo_str} kg/hr ({row['imeo_satellite']})")
        print(f"      Ratio: {ratio_str}, Distance: {row['match_distance_km']:.3f} km")

    return stats


def save_results(
    matched_df: pd.DataFrame,
    cm_only: pd.DataFrame,
    imeo_only: pd.DataFrame,
    analysis_stats: Dict,
) -> None:
    """Save matching results to files."""
    print("\n" + "=" * 60)
    print("SAVING RESULTS")
    print("=" * 60)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Save matched plumes
    if not matched_df.empty:
        path = OUTPUT_DIR / f"matched_plumes_cm_imeo_{timestamp}.csv"
        matched_df.to_csv(path, index=False)
        print(f"   ✅ {path.name}")

    # Save CM-only plumes
    if not cm_only.empty:
        path = OUTPUT_DIR / f"cm_only_plumes_{timestamp}.csv"
        cm_only.to_csv(path, index=False)
        print(f"   ✅ {path.name}")

    # Save IMEO-only plumes
    if not imeo_only.empty:
        path = OUTPUT_DIR / f"imeo_only_plumes_{timestamp}.csv"
        imeo_only.to_csv(path, index=False)
        print(f"   ✅ {path.name}")

    # Save summary
    summary = {
        "timestamp": timestamp,
        "matching_params": {
            "distance_threshold_km": DISTANCE_THRESHOLD_KM,
            "date_tolerance_days": DATE_TOLERANCE_DAYS,
            "region": "Argentina",
            "sector": "Oil and Gas (1B2)",
        },
        "results": {
            "matched_plumes": len(matched_df),
            "cm_only_plumes": len(cm_only),
            "imeo_only_plumes": len(imeo_only),
        },
        "analysis": analysis_stats,
        "notes": {
            "matching_logic": "Same date + within 1km = same observation, different quantification",
            "cm_quantification": "Carbon Mapper algorithm",
            "imeo_quantification": "UNEP IMEO MARS algorithm (re-quantifies satellite data)",
        },
    }

    path = OUTPUT_DIR / f"plume_match_summary_{timestamp}.json"
    with open(path, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"   ✅ {path.name}")


def main():
    parser = argparse.ArgumentParser(description="Match CM and IMEO plumes")
    parser.add_argument("--explore", action="store_true", help="Only print stats, don't save")
    args = parser.parse_args()

    print("=" * 60)
    print("CARBON MAPPER - IMEO PLUME MATCHING")
    print("=" * 60)
    print(f"Distance threshold: {DISTANCE_THRESHOLD_KM} km")
    print(f"Date tolerance: {DATE_TOLERANCE_DAYS} days")
    print("Note: Same-day matches likely represent SAME observation,")
    print("      different quantification methods (CM vs IMEO MARS)")

    # Fetch/load data
    cm_plumes = fetch_cm_plumes(ARGENTINA_BBOX, sectors=["1B2"], plume_gas="CH4")
    imeo_plumes = load_imeo_plumes()

    # Match plumes
    matched_df, cm_only, imeo_only = match_plumes(cm_plumes, imeo_plumes)

    # Analyze matches
    analysis_stats = analyze_matches(matched_df)

    # Save results (unless explore-only mode)
    if not args.explore:
        save_results(matched_df, cm_only, imeo_only, analysis_stats)

    print("\n" + "=" * 60)
    print("COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
