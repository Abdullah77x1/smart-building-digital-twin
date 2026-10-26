"""Build leakage-safe forecasting inputs and targets from Simulator V2 history.

Run from project root:
  python prepare_data.py --csv ../smart_building_simulator_v2/building_simulation_data.csv
"""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd

HORIZONS = (1, 2, 3, 6)  # Five-minute steps -> 5,10,15,30 min
TARGETS = ("hvac_power_kw", "indoor_temp_c", "occupancy_count")
OBSERVED = (
    "outdoor_temp_c", "indoor_temp_c", "occupancy_count", "hvac_power_kw",
    "hvac_setpoint_c", "hvac_level_pct", "co2_ppm",
    "lighting_power_kw", "plug_power_kw", "is_workday",
)
LAG_VARIABLES = ("indoor_temp_c", "hvac_power_kw", "occupancy_count", "outdoor_temp_c", "co2_ppm")
LAGS = (1, 3, 6, 12)  # 5,15,30,60 minutes of history
SEASON_MAP = {12: "Winter", 1: "Winter", 2: "Winter", 3: "Spring", 4: "Spring", 5: "Spring", 6: "Summer", 7: "Summer", 8: "Summer", 9: "Autumn", 10: "Autumn", 11: "Autumn"}


def load_history(csv_path):
    csv_path = Path(csv_path)
    if not csv_path.is_file():
        raise FileNotFoundError(f"Cannot find {csv_path}. Copy the four-year CSV into data/ or use --csv PATH.")
    cols = ["timestamp", "zone_id", *OBSERVED]
    df = pd.read_csv(csv_path, usecols=cols, parse_dates=["timestamp"])
    df = df.sort_values(["zone_id", "timestamp"]).reset_index(drop=True)
    if df["timestamp"].isna().any():
        raise ValueError("Invalid timestamps detected")
    if df.duplicated(["zone_id", "timestamp"]).any():
        raise ValueError("Duplicate timestamps for a zone")
    gaps = df.groupby("zone_id")["timestamp"].diff().dropna()
    if not gaps.eq(pd.Timedelta(minutes=5)).all():
        raise ValueError("Non-consecutive timestamps: model assumes exactly five-minute observations per zone")
    if df[list(OBSERVED)].isna().any().any():
        raise ValueError("Missing predictor measurements: inspect dataset instead of silently filling future information")
    return df


def make_features(df):
    """Features at time t only; NO future observed inputs or diagnostic next_indoor_temp_c."""
    out = df[["timestamp", "zone_id", *OBSERVED]].copy()
    t = out["timestamp"]
    mins = t.dt.hour * 60 + t.dt.minute
    dayofyear = t.dt.dayofyear
    dayofweek = t.dt.dayofweek
    out["hour_sin"] = np.sin(2 * np.pi * mins / 1440)
    out["hour_cos"] = np.cos(2 * np.pi * mins / 1440)
    out["weekday_sin"] = np.sin(2 * np.pi * dayofweek / 7)
    out["weekday_cos"] = np.cos(2 * np.pi * dayofweek / 7)
    out["year_sin"] = np.sin(2 * np.pi * dayofyear / 365.2425)
    out["year_cos"] = np.cos(2 * np.pi * dayofyear / 365.2425)

    # Partition lags by BOTH zone and year, so no training sample can contain
    # a lag from the previous data split's calendar year.
    group = [out["zone_id"], out["timestamp"].dt.year]
    for col in LAG_VARIABLES:
        for step in LAGS:
            out[f"{col}_lag{step}"] = out.groupby(group, sort=False)[col].shift(step)
    feature_names = list(OBSERVED) + ["hour_sin", "hour_cos", "weekday_sin", "weekday_cos", "year_sin", "year_cos"] + [f"{c}_lag{lag}" for c in LAG_VARIABLES for lag in LAGS]
    return out, feature_names


def make_examples(df):
    """Supervised samples: each output comes from the SAME zone and year."""
    xdf, feature_names = make_features(df)
    group = [df["zone_id"], df["timestamp"].dt.year]
    target_names = []
    for col in TARGETS:
        for h in HORIZONS:
            key = f"{col}_plus_{h*5}min"
            xdf[key] = df.groupby(group, sort=False)[col].shift(-h)
            target_names.append(key)
    keep = xdf[feature_names + target_names].notna().all(axis=1)
    clean = xdf.loc[keep].copy()
    print(f"Prepared {len(clean):,} samples: {len(feature_names)} features, {len(target_names)} future targets")
    return clean, feature_names, target_names


def split_years(df):
    yr = df["timestamp"].dt.year
    train = df.loc[yr.isin([2022, 2023])].copy()
    val = df.loc[yr.eq(2024)].copy()
    test = df.loc[yr.eq(2025)].copy()
    for name, part in (("train", train), ("validation", val), ("test", test)):
        if len(part) == 0:
            raise ValueError(f"No data for {name}. Expected complete 2022–2025 history")
    return train, val, test


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, default=Path(__file__).resolve().parents[1] / "data" / "building_simulation_data.csv")
    args = parser.parse_args()
    data, features, targets = make_examples(load_history(args.csv))
    for name, frame in zip(("Training", "Validation", "Test"), split_years(data)):
        print(f"{name}: {len(frame):,} rows, {frame['timestamp'].min()} to {frame['timestamp'].max()}")
    print("Features:", features)
    print("Targets:", targets)
