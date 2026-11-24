# Smart Building Digital Twin — Senior Design Project

This repository preserves the earlier Simulator V2, neural forecasting, sensor experiments, HVAC policy research and prototype dashboard. The final BOPTEST-based supervised dashboard, semester record and report are in the [central COSC14 project repository](https://github.com/Abdullah77x1/SDP-BOPTEST).

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
├── optimization/
│   └── README.md                     # Future HVAC strategy and comfort optimization work
├── dashboard/
│   └── README.md                     # Future interface, plots and LLM integration work
├── data/
│   ├── sample_building_data.csv      # 8 example simulated rows
│   └── building_simulation_data.csv  # GENERATE locally; intentionally not on GitHub
├── docs/                             # Simulator equations, pilots, ML explanation
└── reports/                          # Your local validation reports
```

## Get the project into VS Code (Windows)

Use the **GitHub website (github.com)** to view the shared repository, manage branches and pull requests, and collaborate with teammates. Use **VS Code on your computer** to edit and run Python. You do **not** need to install GitHub Desktop or repeatedly download/upload ZIP files. Clone the repository once, then pull and push changes using VS Code.

1. Open the [GitHub website](https://github.com/Abdullah77x1/smart-building-digital-twin) in your browser to access the shared repository. Install [VS Code](https://code.visualstudio.com/) and its Microsoft **Python** extension on your computer. To clone, pull, and push using VS Code on Windows, **Git** must also be installed; if `git --version` is not recognized in the VS Code terminal, install [Git for Windows](https://git-scm.com/downloads/win). **Git for Windows is the underlying Git tool, not a GitHub Desktop application**.
2. In VS Code, press **Ctrl+Shift+P**, run **Git: Clone**, and enter:
   `https://github.com/Abdullah77x1/smart-building-digital-twin.git`
3. Choose a folder on your computer, sign in to GitHub when prompted (required for this private repository), and open the cloned `smart-building-digital-twin` folder.
4. Open **Terminal → New Terminal**. All commands in this README are run from this **repository root** (the folder containing `README.md`, `simulator/` and `ml/`). You can check the location with `pwd`.
5. For everyday development, use a **feature branch** rather than editing `main` directly. In the lower-left corner of VS Code click the branch name (usually `main`), then **Create new branch**, e.g. `feature/occupancy-experiments`. Commit and push that branch as described below.

> Editing a file in VS Code changes your **local copy**. Nothing is uploaded to GitHub until you commit and push. Merely **running** the simulator never changes the shared online files.

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

**Example — generate the official historical dataset:** this command uses `simulator/building_config.json`, the default seed **42**, and the period **2022-01-01 through 2025-12-31**, at **5-minute** intervals. It writes:

- `data/building_simulation_data.csv` — about **79 MB**, **420,768 records** (including leap day).
- A companion summary JSON containing aggregate simulation results.

Open the CSV locally in a data viewer, or inspect a few rows without loading the entire file:

```powershell
python -c "import csv; f=open('data/building_simulation_data.csv', newline=''); r=csv.reader(f); print(next(r)); print(next(r)); f.close()"
```

The `.gitignore` excludes the large generated CSV and other local outputs. **All teammates can reproduce it locally** using the same checked-in configuration, code, and default seed. Do not commit the full generated dataset.

**Example — generate only one day** instead of the four-year history:

```powershell
python simulator/building_simulator.py --start 2023-07-10 --end 2023-07-11 --output data/one_day.csv
```

Here `--start` is inclusive and `--end` is exclusive, so the file contains **288 five-minute records** (July 10 only). The output is saved as `data/one_day.csv` on **your computer**, not on GitHub. To test a changed simulator without overwriting the official dataset, always choose a different `--output` filename.

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

## Everyday collaboration: VS Code + GitHub

Use this workflow when you or a teammate want to modify the simulator, ML model, optimization, or dashboard code:

1. **Pull before starting:** In VS Code, switch to `main`, then use **Source Control → … → Pull** to get teammates' latest merged changes. Create your feature branch from this updated `main`.
2. **Create a feature branch:** Click the branch name in the lower-left corner of VS Code → **Create new branch**, e.g. `feature/simulator-improvements`, `feature/optimization`, or `feature/dashboard`.
3. **Edit and test locally:** Change the relevant files, save, and run the program in the integrated terminal. For a simulator experiment, use a different CSV filename, such as:
   ```powershell
   python simulator/building_simulator.py --start 2023-07-10 --end 2023-07-11 --output data/my_experiment.csv
   ```
4. **Commit:** Open VS Code's **Source Control** view, review the changed files, stage intended changes with **+**, type a short commit message (e.g. `Improve occupancy schedule`), and select **Commit**. A commit records changes in your *local Git history*.
5. **Push:** Click **Publish Branch** the first time, or **Push / Sync Changes** afterward. This uploads commits to **your branch** on GitHub, not to `main`.
6. **Create a Pull Request (PR):** On the GitHub website, open the repository and select **Compare & pull request** (or **Pull requests → New pull request**). Set the **base** to `main` and the **compare** branch to your feature branch. Describe the changes and testing; ask a teammate to review them.
7. **Merge after review:** Merge the PR into `main` when the team agrees. Teammates can then pull the updated `main` into their local repositories.

**Where do generated files go?** Python writes them to the paths specified by the commands **in the environment where you run Python** (your local computer, or a GitHub Codespace if using one). Switching branches in the same local clone can leave ignored CSV files untouched; running the simulator again with the same output path can overwrite them. The GitHub website's ordinary code viewer cannot run Python by itself.

**Small browser-only edits:** On GitHub.com you may edit a file using its pencil icon, preferably on a feature branch. For actually running Python, use VS Code on your computer or a cloud environment such as Codespaces.

**Quick reference:** **clone** = make a connected local copy; **pull** = download teammates' commits; **commit** = record your changes locally; **push** = upload commits to GitHub; **PR** = request review before merging to `main`.

## File ownership / team suggestions

- **Simulator owner:** `simulator/`, simulator equations and validation.
- **ML owner:** `ml/`, forecasting, model evaluation and data leakage checks.
- **Energy/optimization owner:** `optimization/` (folder created; implementation to be developed), comfort limits, scenario tests.
- **Integration owner:** `dashboard/` (folder created; implementation to be developed), LLM integration and reports.

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
