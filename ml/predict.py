"""Load the saved network to forecast 3 targets at +5, +10, +15 and +30 min."""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
from model import load_checkpoint, predict
from prepare_data import load_history, make_features, HORIZONS, TARGETS


def main():
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, default=here.parent / "data" / "building_simulation_data.csv")
    parser.add_argument("--model", type=Path, default=here / "results" / "multitask_model.pt")
    parser.add_argument("--timestamp", type=str, default="2025-07-15 09:00")
    args = parser.parse_args()
    frame = load_history(args.csv)
    data, features = make_features(frame)
    model, ckpt = load_checkpoint(args.model)
    if ckpt["features"] != features:
        raise ValueError("The model expects a different feature order; regenerate/retrain first")
    row = data.loc[data["timestamp"].eq(pd.Timestamp(args.timestamp))]
    if len(row) != 1:
        raise ValueError(f"Expected one row at {args.timestamp}, got {len(row)}")
    if row[features].isna().any().any():
        raise ValueError("This timestamp lacks 60 minutes of historical inputs; select a later time")
    pred = predict(model, ckpt, row[features].to_numpy(np.float32))[0]
    print(f"\nCURRENT OBSERVATIONS at {args.timestamp}:")
    for col in TARGETS:
        print(f"  {col:20s} {float(row.iloc[0][col]):8.3f}")
    print("\nFUTURE FORECASTS (one model, 12 outputs):")
    for idx, mins in enumerate(HORIZONS):
        print(f"  +{mins*5:2d} minutes: power={pred[idx]:.3f} kW | temperature={pred[4+idx]:.2f} °C | occupancy={pred[8+idx]:.1f} people (~{round(pred[8+idx])})")
    print("\nThese are predictions, not observations. Future thermostat changes are not supplied to this version of the model.")

if __name__ == "__main__":
    main()
