# SDP Multi-task Forecasting Model V1

## What it does

Trains **one PyTorch model** with shared layers and **three prediction heads**. Each head forecasts four horizons (+5, +10, +15, +30 minutes) based on the current and previous hour of recorded building conditions:

- HVAC **electrical** power (`hvac_power_kw`, kW)
- Indoor temperature (`indoor_temp_c`, °C)
- Occupancy (`occupancy_count`, people; regression output, rounded for display)

There are **12 outputs from one model**. It learns from the V2 **synthetic** simulator CSV. It is a **forecasting model for continuation of the original operating policy**, NOT yet a validated model of what happens if you change tomorrow's thermostat setting.

## Folder layout

```text
sdp_multitask_ml_v1/
├── data/
│   └── building_simulation_data.csv       # Copy from Simulator V2, not duplicated in this ML ZIP
├── prepare_data.py                        # Load, create past-only input features and future targets
├── model.py                               # One shared neural network + 3 output heads
├── train_multitask.py                     # Train on 2022–23, select epoch on 2024
├── evaluate_model.py                      # Final one-time test on 2025
├── predict.py                             # Load the saved model; predict at one timestamp
├── results/
│   ├── multitask_model.pt                 # Trained weights + feature order + train-only normalization
│   ├── training_report.json               # Training history and 2024 comparison with baseline
│   ├── test_metrics_by_season.csv         # 2025 errors, each task/horizon/season
│   ├── test_report.json                   # Overall 2025 metrics
│   └── example_2025_predictions.csv       # Example forecasts vs simulated truth
└── requirements.txt
```

## Run in VS Code (Windows or macOS)

1. Install Python 3.10 or newer, open this directory in VS Code, and create a virtual environment if preferred.
2. From the **V2 simulator package**, copy `building_simulation_data.csv` into this package's `data/` folder.
3. Install libraries:

   ```bash
   python -m pip install -r requirements.txt
   ```

4. Inspect how rows and targets are prepared:

   ```bash
   python prepare_data.py
   ```

5. Train (2022–23 data and 2024 validation):

   ```bash
   python train_multitask.py
   ```

6. Inspect forecasts from the **already-trained model** (no training required):

   ```bash
   python predict.py --timestamp "2025-07-15 09:00"
   ```

7. **Once** you have decided on your final architecture using 2024 validation, evaluate 2025:

   ```bash
   python evaluate_model.py
   ```

All three scripts accept `--csv PATH` so you can leave the CSV in the existing V2 folder instead of copying it. `train_multitask.py` supports `--epochs` and `--hidden-size` for experiments; **choose hyperparameters using 2024 validation only**.

## Data and leakage safeguards

- Each recorded row is five minutes apart; shift -1/-2/-3/-6 produces the targets.
- A full preceding **60-minute observation history** is available via lags (5, 15, 30, 60 minutes).
- Features include current observable temperatures, occupancy, HVAC power and settings, indoor CO₂, lights, plugs, current workday flag, and calendar features. **No future measured inputs.**
- The V2 diagnostic `next_indoor_temp_c` is deliberately **excluded** because it reveals a future state.
- Lags and future targets are computed separately *within each year*, preventing crossing training/validation/test boundaries; the first 12 and last 6 rows of each year are excluded.
- Input and target standardization are computed only from 2022–2023. A shared model uses loss on scaled outputs so different units have comparable weight.
- The test year 2025 is not used to train or select hyperparameters. `evaluate_model.py` is intentionally separate.
- The evaluation includes a `no change` baseline that predicts each future value equals its current value. Important because the five-minute horizon is easy when temperatures change slowly.
- Data are **synthetic**. Results reflect the simulator's assumptions; they do not prove accuracy on a real building.

## How the model learns

`fit`/training here is the loop that feeds `X` and `y` into a neural network, computes differences between its predictions and correct future values, and adjusts internal weights using the Adam optimizer. `results/multitask_model.pt` is the trained model, so you can later load it from the dashboard to make forecasts without retraining.

## Important next project steps

1. Discuss the simulator's realism, synthetic-data acceptability, one-zone scope, and optional heating with your advisor.
2. Compare the 12 model errors with the `no change` baseline; inspect errors at occupancy transitions and by season.
3. Add **known future control plans** and a validated control-response model if you want credible thermostat what-if forecasts. The current model only forecasts the simulator's policy.
4. Build a simple candidate-setpoint optimizer and separate real-time dashboard. Never attribute real building savings to purely synthetic predictions.
