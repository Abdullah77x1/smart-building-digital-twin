"""Compare a fixed trained model on clean versus faulty temperature inputs.

Use only the model's existing checkpoint; no retraining, tuning or checkpoint changes.
Missing temperatures use causal forward-fill within each zone/year, with 25 C
as the fallback before any observation. True future values remain evaluation targets.
"""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd

from model import load_checkpoint, predict
from prepare_data import load_history, make_examples, split_years, LAGS, HORIZONS, TARGETS


def prepare_paired(fault_csv):
    original = load_history(fault_csv)
    clean, features, targets = make_examples(original)
    sensor = pd.read_csv(fault_csv, usecols=[
        "timestamp", "zone_id", "indoor_temp_sensor_c", "indoor_temp_sensor_status"
    ], parse_dates=["timestamp"])
    if sensor.duplicated(["zone_id", "timestamp"]).any():
        raise ValueError("Duplicated sensor timestamps")
    if not sensor["indoor_temp_sensor_status"].isin(["normal", "dropout", "stuck"]).all():
        raise ValueError("Unknown sensor status")
    sensor = sensor.sort_values(["zone_id", "timestamp"]).reset_index(drop=True)
    group_keys = [sensor["zone_id"], sensor["timestamp"].dt.year]
    sensor["observed_temp"] = sensor.groupby(group_keys, sort=False)["indoor_temp_sensor_c"].ffill().fillna(25.0)
    # Joining by unique timestamp/zone preserves correct alignment after lag/horizon filtering.
    paired = clean.merge(sensor[["timestamp", "zone_id", "observed_temp", "indoor_temp_sensor_status"]],
                         on=["timestamp", "zone_id"], how="left", validate="one_to_one")
    if paired["observed_temp"].isna().any():
        raise ValueError("Missing sensor rows")
    noisy = paired[features].copy()
    noisy["indoor_temp_c"] = paired["observed_temp"].to_numpy()
    for lag in LAGS:
        key = f"indoor_temp_c_lag{lag}"
        lookup = sensor[["timestamp", "zone_id", "observed_temp"]].copy()
        lookup["timestamp"] += pd.Timedelta(minutes=5 * lag)
        lookup = lookup.rename(columns={"observed_temp": key})
        # Restrict lag lookup to same calendar year as sample; clean feature builder does too.
        lookup["year"] = (lookup["timestamp"] - pd.Timedelta(minutes=5 * lag)).dt.year
        query = paired[["timestamp", "zone_id"]].copy()
        query["year"] = query["timestamp"].dt.year
        joined = query.merge(lookup, on=["timestamp", "zone_id", "year"], how="left", validate="one_to_one")
        noisy[key] = joined[key].to_numpy()
    if noisy.isna().any().any():
        raise ValueError("Nonfinite/noisy feature gap; inspect alignment")
    return paired, noisy, features, targets


def evaluate(csv_path, model_path, output):
    model, ckpt = load_checkpoint(model_path)
    paired, noisy, features, targets = prepare_paired(csv_path)
    if ckpt["features"] != features or ckpt["targets"] != targets:
        raise ValueError("Checkpoint feature/target mismatch")
    _, _, test = split_years(paired)
    index = test.index
    actual = test[targets].to_numpy(np.float32)
    clean_predictions = predict(model, ckpt, test[features].to_numpy(np.float32))
    fault_predictions = predict(model, ckpt, noisy.loc[index, features].to_numpy(np.float32))
    result = []
    for i, task in enumerate(TARGETS):
        for j, h in enumerate(HORIZONS):
            k = i * len(HORIZONS) + j
            for status in ("all", "normal", "dropout", "stuck"):
                mask = np.ones(len(test), bool) if status == "all" else test["indoor_temp_sensor_status"].eq(status).to_numpy()
                if not mask.any():
                    continue
                err_clean = np.abs(actual[mask, k] - clean_predictions[mask, k])
                err_fault = np.abs(actual[mask, k] - fault_predictions[mask, k])
                result.append({"target": task, "horizon_minutes": h * 5, "sensor_status": status,
                               "rows": int(mask.sum()), "mae_clean_inputs": float(err_clean.mean()),
                               "mae_faulty_inputs": float(err_fault.mean()),
                               "mae_change": float(err_fault.mean() - err_clean.mean())})
    output.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(result).to_csv(output / "sensor_robustness_metrics.csv", index=False)
    report = {"test_year": 2025, "test_rows": len(test), "model": str(model_path),
              "missing_value_strategy": "past-only forward fill within zone/year; initial fallback 25 C",
              "status_used_only_for_metrics": True,
              "notes": "Fixed existing clean-trained model, true targets, same test timestamps. Synthetic sensor faults only.",
              "metrics": result}
    (output / "sensor_robustness_report.json").write_text(json.dumps(report, indent=2))
    print(pd.DataFrame(result).query("sensor_status == 'all'").to_string(index=False))
    print("Saved:", output / "sensor_robustness_metrics.csv")
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parents[1]
    p.add_argument("--csv", type=Path, default=root / "data" / "building_with_sensor_faults.csv")
    p.add_argument("--model", type=Path, default=root / "ml" / "results" / "multitask_model.pt")
    p.add_argument("--output", type=Path, default=root / "reports" / "sensor_robustness")
    args = p.parse_args()
    evaluate(args.csv, args.model, args.output)
