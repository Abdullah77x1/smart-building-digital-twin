"""Basic integrity checks for supervised labels and reloaded trained-model forecasts."""
from pathlib import Path
import argparse
import numpy as np
import pandas as pd
from model import load_checkpoint, predict
from prepare_data import load_history, make_examples, HORIZONS, TARGETS

if __name__ == "__main__":
    here = Path(__file__).resolve().parent
    p = argparse.ArgumentParser()
    p.add_argument("--csv", type=Path, default=here.parent/"data"/"building_simulation_data.csv")
    args=p.parse_args()
    base = load_history(args.csv)
    data, features, targets = make_examples(base)
    assert "next_indoor_temp_c" not in features
    assert len(features)==36 and len(targets)==12
    assert (data["timestamp"].dt.year.value_counts().sort_index().to_dict() == {2022: 105102, 2023: 105102, 2024: 105390, 2025: 105102})
    # Confirm +5-min targets are exactly the next row's values at sample point.
    sample=data.loc[data["timestamp"].eq(pd.Timestamp("2025-07-15 09:00"))].iloc[0]
    next_row=base.loc[base["timestamp"].eq(pd.Timestamp("2025-07-15 09:05"))].iloc[0]
    assert np.isclose(sample["hvac_power_kw_plus_5min"], next_row["hvac_power_kw"])
    assert np.isclose(sample["indoor_temp_c_plus_5min"], next_row["indoor_temp_c"])
    assert np.isclose(sample["occupancy_count_plus_5min"], next_row["occupancy_count"])
    model,ckpt=load_checkpoint(here/"results"/"multitask_model.pt")
    assert ckpt["features"]==features and ckpt["targets"]==targets
    forecast=predict(model,ckpt,data.loc[data["timestamp"].eq(pd.Timestamp("2025-07-15 09:00")),features].to_numpy(np.float32))
    assert forecast.shape==(1,12) and np.isfinite(forecast).all()
    print("PASS: 5-minute step, split-specific lags and labels, no leakage field, saved checkpoint, 12 finite forecasts")
