"""Final evaluation on unseen 2025 history. Run only after choosing the model on 2024."""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
from model import load_checkpoint, predict
from prepare_data import load_history, make_examples, split_years, HORIZONS, TARGETS, SEASON_MAP


def main():
    p = argparse.ArgumentParser()
    here = Path(__file__).resolve().parent
    p.add_argument("--csv", type=Path, default=here.parent / "data" / "building_simulation_data.csv")
    p.add_argument("--model", type=Path, default=here / "results" / "multitask_model.pt")
    p.add_argument("--output", type=Path, default=here / "results")
    args = p.parse_args()
    args.output.mkdir(exist_ok=True, parents=True)
    model, ckpt = load_checkpoint(args.model)
    samples, features, targets = make_examples(load_history(args.csv))
    if ckpt["features"] != features or ckpt["targets"] != targets:
        raise ValueError("Feature/target schema mismatch between trained model and data")
    _, _, test = split_years(samples)
    actual = test[targets].to_numpy(dtype=np.float32)
    predicted = predict(model, ckpt, test[features].to_numpy(dtype=np.float32))
    current = np.column_stack([test[col].to_numpy(np.float32) for col in TARGETS for _ in HORIZONS])
    seasons = test["timestamp"].dt.month.map(SEASON_MAP).to_numpy()
    table = []
    for i, target in enumerate(TARGETS):
        for j, horizon in enumerate(HORIZONS):
            k = 4*i+j
            for season in ("All", "Winter", "Spring", "Summer", "Autumn"):
                choose = np.ones(len(test), dtype=bool) if season == "All" else seasons == season
                a, pr, base = actual[choose, k], predicted[choose, k], current[choose, k]
                table.append({"target":target,"horizon_minutes":horizon*5,"season":season,
                              "n":int(len(a)),"mae_model":float(np.mean(np.abs(a-pr))),
                              "rmse_model":float(np.sqrt(np.mean((a-pr)**2))),
                              "mae_no_change":float(np.mean(np.abs(a-base))),
                              "rmse_no_change":float(np.sqrt(np.mean((a-base)**2)))})
    metric_frame = pd.DataFrame(table)
    metric_frame.to_csv(args.output / "test_metrics_by_season.csv", index=False)
    print("\n2025 TEST: MAE, model versus 'no change' baseline")
    print(metric_frame[metric_frame["season"]=="All"][["target","horizon_minutes","mae_model","mae_no_change"]].to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    examples = test.loc[test["timestamp"].isin(pd.to_datetime([
        "2025-01-15 09:00", "2025-04-15 09:00", "2025-07-15 09:00", "2025-10-15 09:00"
    ])), ["timestamp", "zone_id", *TARGETS]].copy()
    idx = test.index.isin(examples.index)
    for k, target in enumerate(targets):
        examples[f"predicted_{target}"] = predicted[idx, k]
        examples[f"actual_{target}"] = actual[idx, k]
    examples.to_csv(args.output / "example_2025_predictions.csv", index=False)
    overall = metric_frame[metric_frame["season"] == "All"]
    report = {"test_year":2025,"test_rows":len(test),"test_metrics":overall.to_dict(orient="records"),
              "caution":"Results only quantify predictive fidelity to the simulator, not real-world accuracy."}
    (args.output / "test_report.json").write_text(json.dumps(report, indent=2))
    print("\nSaved test metrics and example 2025 predictions in results/")

if __name__ == "__main__":
    main()
