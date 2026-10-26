"""Train ONE shared-backbone network with HVAC, temperature and occupancy heads.

Usage:
  python train_multitask.py --csv data/building_simulation_data.csv
2025 remains untouched: this script NEVER evaluates against the test-year labels.
"""
import argparse
import copy
import json
import random
from pathlib import Path
import numpy as np
import torch
from torch.utils.data import TensorDataset, DataLoader

from model import MultiTaskModel, save_checkpoint, predict
from prepare_data import load_history, make_examples, split_years, TARGETS, HORIZONS


def set_seed(seed=42):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(min(4, torch.get_num_threads()))


def mae_by_task(y, p):
    return {target: {f"+{m*5}m": round(float(np.mean(abs(y[:, i*4+j]-p[:, i*4+j]))), 4)
                     for j, m in enumerate(HORIZONS)} for i, target in enumerate(TARGETS)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, default=Path(__file__).resolve().parents[1] / "data" / "building_simulation_data.csv")
    parser.add_argument("--epochs", type=int, default=14)
    parser.add_argument("--batch-size", type=int, default=2048)
    parser.add_argument("--learning-rate", type=float, default=0.001)
    parser.add_argument("--hidden-size", type=int, default=64)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent / "results")
    args = parser.parse_args()
    set_seed()
    args.output.mkdir(parents=True, exist_ok=True)

    prepared, features, targets = make_examples(load_history(args.csv))
    train, valid, _ = split_years(prepared)
    print(f"Train: {len(train):,} (2022–23); validation: {len(valid):,} (2024); test 2025 RESERVED")
    xtrain = train[features].to_numpy(dtype=np.float32)
    ytrain = train[targets].to_numpy(dtype=np.float32)
    xval = valid[features].to_numpy(dtype=np.float32)
    yval = valid[targets].to_numpy(dtype=np.float32)
    xmean, xstd = xtrain.mean(axis=0), xtrain.std(axis=0)
    ymean, ystd = ytrain.mean(axis=0), ytrain.std(axis=0)
    xstd = np.where(xstd < 1e-6, 1, xstd)
    ystd = np.where(ystd < 1e-6, 1, ystd)
    # Important: means/stds are fitted ONLY on train, never validation or test.
    xtrain = (xtrain-xmean)/xstd
    ytrain = (ytrain-ymean)/ystd
    xval = (xval-xmean)/xstd
    yval = (yval-ymean)/ystd
    data = TensorDataset(torch.from_numpy(xtrain), torch.from_numpy(ytrain))
    loader = DataLoader(data, batch_size=args.batch_size, shuffle=True, num_workers=0)
    model = MultiTaskModel(len(features), args.hidden_size)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.learning_rate)
    loss_fn = torch.nn.MSELoss()
    xval_t, yval_t = torch.from_numpy(xval), torch.from_numpy(yval)
    history, best, best_epoch, best_state = [], float("inf"), 0, None
    patience = 4
    for epoch in range(1, args.epochs + 1):
        model.train()
        running = 0.0
        for bx, by in loader:
            optimizer.zero_grad()
            loss = loss_fn(model(bx), by)  # scaled values keep three tasks comparable
            loss.backward()
            optimizer.step()
            running += float(loss.item()) * len(bx)
        model.eval()
        with torch.no_grad():
            pred = model(xval_t)
            val_loss = float(loss_fn(pred, yval_t).item())
        train_loss = running / len(data)
        history.append({"epoch": epoch, "train_scaled_mse": train_loss, "validation_scaled_mse": val_loss})
        print(f"Epoch {epoch:02d} | train MSE {train_loss:.5f} | validation MSE {val_loss:.5f}", flush=True)
        if val_loss < best - 1e-5:
            best, best_epoch, best_state = val_loss, epoch, copy.deepcopy(model.state_dict())
        if epoch - best_epoch >= patience:
            print("Early stopping: validation has not improved")
            break
    model.load_state_dict(best_state)
    checkpoint = args.output / "multitask_model.pt"
    save_checkpoint(checkpoint, model, features, targets, xmean, xstd, ymean, ystd, args.hidden_size)
    ckpt = {"x_mean":torch.tensor(xmean),"x_std":torch.tensor(xstd),"y_mean":torch.tensor(ymean),"y_std":torch.tensor(ystd)}
    val_pred = predict(model, ckpt, valid[features].to_numpy(np.float32))
    baseline = np.column_stack([valid[col].to_numpy(np.float32) for col in TARGETS for _ in HORIZONS])
    report = {
        "training_years": [2022, 2023], "validation_year": 2024,
        "held_out_test_year": 2025, "train_rows": len(train), "validation_rows": len(valid),
        "selected_epoch": best_epoch, "history": history,
        "validation_mae_model": mae_by_task(valid[targets].to_numpy(np.float32), val_pred),
        "validation_mae_persistence_baseline": mae_by_task(valid[targets].to_numpy(np.float32), baseline),
        "notes": "Synthetic, single-zone building; forecasts assume continuation of the simulator's ordinary control policy. Not a validated counterfactual-control model."
    }
    (args.output / "training_report.json").write_text(json.dumps(report, indent=2))
    print(f"Saved trained model to {checkpoint}")
    print("Validation MAE (model):", json.dumps(report["validation_mae_model"], indent=2))
    print("Validation MAE (current-value baseline):", json.dumps(report["validation_mae_persistence_baseline"], indent=2))
    print("2025 test has NOT been evaluated during training. Run evaluate_model.py once model selection is finalized.")


if __name__ == "__main__":
    main()
