# Smart Building Digital Twin — Senior Design Project

**Team project · Simulator V2 + Multi-Task Forecasting V1**

A reproducible, **synthetic, single-zone** office-building simulator and a PyTorch multi-task forecasting model. The simulator generates five-minute building records for 2022–2025. The model forecasts **HVAC electrical power, indoor temperature, and occupancy** at **+5, +10, +15, and +30 minutes** (12 predictions).

> **Scope:** This is a student proof of concept. The building is fictional and not calibrated to real building measurements. The ML model predicts continuation of the existing simulated control policy; it has **not** been validated as a causal HVAC what-if simulator.

## Repository layout

```text
smart-building-digital-twin/
├── README.md                         # Project overview and setup
├── .gitignore                        # Keeps large/generated/local files out of Git
├── requirements.txt                  # ML Python libraries
├── simulator/
│   ├── building_config.json          # Building assumptions and parameters
│   ├── building_simulator.py         # Physics, weather, occupants, HVAC, lighting, CSV
│   └── validate_simulator.py         # Pilot and consistency tests
├── ml/
│   ├── prepare_data.py               # Past-only features and 12 future labels
│   ├── model.py                      # PyTorch 3-head neural network
│   ├── train_multitask.py            # Training 2022–23; tuning on 2024
│   ├── evaluate_model.py             # Test 2025, after model selection
│   ├── predict.py                    # Predict without retraining
│   ├── smoke_test.py                 # Small ML integration check
│   └── results/                      # Included small V1 checkpoint + experiment reports
├── data/
│   ├── sample_building_data.csv      # 8 real example rows
│   └── building_simulation_data.csv  # GENERATE locally; intentionally not on GitHub
├── docs/                             # Simulator equations, pilots, ML explanation
└── reports/                          # Your local validation reports
```

## Quick start (run commands from repository root)

**1. Create environment and install ML packages (Windows PowerShell)**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If PowerShell blocks activation, you can skip activation and call `.\.venv\Scripts\python.exe` instead of `python`. For simulation only, standard Python 3.10+ is sufficient without extra packages.

**2. Generate the four-year historical data locally**

```powershell
python simulator/building_simulator.py
```

This writes `data/building_simulation_data.csv` (approximately **79 MB**, **420,768 records**, sampled every five minutes) and a summary JSON. The `.gitignore` deliberately excludes the full CSV because it is reproducibly generated and bulky. **All teammates run the same command** to recreate it using the checked-in config and default seed 42.

To create a small experiment instead:

```powershell
python simulator/building_simulator.py --start 2023-07-10 --end 2023-07-11 --output data/one_day.csv
```

**3. Validate the simulator**

```powershell
python simulator/validate_simulator.py --csv data/building_simulation_data.csv --report reports/validation_results.json
```

**4. Inspect the ML input/target preparation**

```powershell
python ml/prepare_data.py
```

36 input features (10 current, 6 calendar, 20 lagged features), 12 targets (3 variables x 4 horizons). The diagnostic `next_indoor_temp_c` is not used to avoid information leakage.

**5. Run a forecast with the INCLUDED pretrained neural network**

```powershell
python ml/predict.py --timestamp "2025-07-15 09:00"
```

The default checkpoint is `ml/results/multitask_model.pt`, included in the repository. The historical CSV must first be generated (Step 2).

**6. Train again (optional)**

```powershell
python ml/train_multitask.py
```

The script trains on **2022–23**, chooses the best model on **2024**, and saves a new checkpoint in `ml/results/`. Retraining can change the tracked model/report files; inspect diffs before committing results. Do **not** tune based on 2025 results. A one-time final evaluation uses `python ml/evaluate_model.py`.

## File ownership / team suggestions

- **Simulator owner:** `simulator/`, simulator equations and validation.
- **ML owner:** `ml/`, forecasting, model evaluation and data leakage checks.
- **Energy/optimization owner:** proposed future `optimization/` component, comfort limits, scenario tests.
- **Integration owner:** proposed future `dashboard/` component, LLM integration and reports.

Coordinate architectural changes together. Assign one issue per task; use feature branches and pull requests instead of everyone editing `main` simultaneously.

## Data and evaluation cautions

- The generated data is **synthetic**, not real measured sensor data.
- Simulation parameters are **assumptions**, not calibrated HVAC or building values.
- `next_indoor_temp_c` is known to the simulator but **must not** be fed as a current ML input.
- A low forecasting error against synthetic simulation does not establish real-building accuracy.
- The original SDP calls for a **multi-zone** twin; this repo begins with one zone.
- Generated files, virtual environments, and passwords/API keys should not be committed.

## Documentation

Read [`docs/SIMULATOR_MODEL_AND_EQUATIONS.md`](docs/SIMULATOR_MODEL_AND_EQUATIONS.md), [`docs/SIMULATOR_PILOT_VALIDATION.md`](docs/SIMULATOR_PILOT_VALIDATION.md), and [`docs/ML_MODEL_EXPLANATION.md`](docs/ML_MODEL_EXPLANATION.md). The `*_ORIGINAL_*_README.md` files preserve instructions from each source package; **use this root README for current folder paths**.
