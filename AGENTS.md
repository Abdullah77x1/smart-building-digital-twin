# AGENTS.md — Smart Building Digital Twin SDP

Instructions for coding agents (including Codex) working in this repository. Read `README.md` and relevant `docs/` files before editing. When documentation and code differ, inspect the code, report the discrepancy, and do not silently invent behavior.

## Project mission and boundaries
- Khalifa University Senior Design Project: data-driven, offline proof of concept for smart-building energy management, energy/temperature forecasting, and HVAC what-if analysis.
- Team of four students (three CS, one ESM); coordinate changes through branches and review. The advisor critiques decisions; students are responsible for design and implementation.
- **Current implemented baseline:** one fictional 120 m² office zone, maximum 15 occupants, five-minute interval, synthetic Abu Dhabi-like weather, 2022–2025 history. This is a **single-zone foundation**, not the full envisioned multi-zone building digital twin.
- No physical sensors or live building actuation. No connection to actual BMS controls. Treat all coefficients, comfort limits and behavior rules as assumptions, not as calibrated field measurements.
- Target applications: show building state, predict near-future HVAC electrical power/indoor temperature/occupancy, compare energy and comfort under controlled what-if scenarios. The equation-based simulator, not the observational forecast model, is currently the mechanism for HVAC-policy interventions.

## Architecture: source of truth
- `simulator/building_simulator.py`: deterministic seeded synthetic building drivers, weekday arrival/departure occupancy, simplified RC thermal dynamics, optional heating, thermostat and HVAC, electricity and CO2 calculations, CSV and summary output.
- `simulator/building_config.json`: baseline parameters. Step = 5 minutes; original defaults and baseline behavior should remain stable unless explicitly requested.
- `simulator/validate_simulator.py`: pilot and consistency checks (thermal/electrical balances, time grid, seasonal scenarios).
- `simulator/sensor_simulation.py`: **optional post-processing** of simulator CSV. Adds `indoor_temp_sensor_c` and `indoor_temp_sensor_status` (`normal`, `dropout`, `stuck`). Retains true `indoor_temp_c` and all physics/power fields unchanged. Noise/fault rates are illustrative, not hardware-calibrated.
- `ml/prepare_data.py`: supervised feature/label construction; 36 inputs including past lags; targets are future `hvac_power_kw`, `indoor_temp_c`, and `occupancy_count` at +5/+10/+15/+30 min (12 total).
- `ml/model.py`, `ml/train_multitask.py`, `ml/evaluate_model.py`: PyTorch shared-backbone, three-head forecasting and evaluation.
- `ml/evaluate_sensor_robustness.py`: compare the existing clean-trained model on clean versus faulty observed temperature inputs while scoring against **true future simulator outputs**; causal past-only fill for missing readings. It does not retrain or establish real-world validity.
- `optimization/` and `dashboard/` are proposed or may be evolving separately; inspect what exists before treating them as implemented.

## Dataset decisions and research background
- Initial foundation explored CU-BEMS (Chulalongkorn University building, 2018–2019), focusing on 2019 Floor 6 Zone 4 and possibly outdoor temperature. Data-quality gaps, missing HVAC control commands, and limited ability to make causal what-if claims constrained that approach.
- Other candidate sources included UCI Occupancy Detection and Oak Ridge building data. **Do not claim that UCI observations, CU-BEMS measurements, or Oak Ridge data are currently fused into Simulator V2 unless code and provenance show it.** An UCI-derived occupancy integration was explored, but is not part of this repository's established baseline.
- Synthetic data, synthetic-with-real-derived-drivers data, and actual sensor measurements must be labeled distinctly. A model tested on synthetic values is not validated on actual buildings.
- The instructor suggested combining real and simulated data; treat the meaning and implementation as an open design question, not an accomplished requirement.

## Scientific and evaluation rules
- Preserve timestamps: records at t are start-of-interval state; `energy_kwh` is energy over [t, t+5min). `next_indoor_temp_c` is a **future diagnostic**: never include it as a current predictor.
- Default data split: train on 2022–2023, choose/tune on 2024, reserve 2025 for held-out final evaluation. Avoid fitting transformations on validation/test years. Do not use future sensor readings for imputation, lag features, or online inference.
- Fault-status labels are synthetic ground truth for evaluation, **not a real-time feature available to a deployed fault detector**.
- For fair paired scenarios, hold weather/occupancy seeds constant and vary only the intended intervention; preserve energy balance and indoor-state continuity.
- Report MAE/RMSE by target and horizon, compare to baselines, identify sample counts and assumptions. Avoid claiming a lower synthetic test error demonstrates real-building performance.
- Comfort proxy is occupied indoor temperature 23–26°C, **not** a certification of ASHRAE 55 compliance.

## Working safely with Git and Codex
- Default development branch for the simulator/sensor work: `feature/simulator-improvements`. **Do not push, merge, force-push, delete branches, or edit `main` without explicit user permission.** Check `git status` and current branch first.
- Keep teammates' dashboard/other feature branches intact. Do not automatically merge unrelated code.
- Review diffs and report modified files and test results. Avoid destructive cleanup of user work or changing tracked model checkpoints unintentionally.
- Do not commit generated four-year datasets, local environment directories, credentials, confidential building information, or large ML artifacts without specific permission.
- Prefer Python stdlib for simulator additions. Keep dependencies minimal and reproducibility controlled by explicit seeds. For ML, use existing requirements and tested PyTorch/Pandas/Numpy setup.
- **Do not assert tests passed unless executed**. State blockers and distinguish hypothetical/sample results from actual evaluated results.

## Useful commands (repository root)
```powershell
git status
git switch feature/simulator-improvements
python -m pip install -r requirements.txt
python simulator/building_simulator.py
python simulator/validate_simulator.py --csv data/building_simulation_data.csv --report reports/validation_results.json
python simulator/sensor_simulation.py
python -m unittest discover -s simulator -p test_sensor_simulation.py -v
python -m unittest discover -s ml -p test_sensor_robustness.py -v
python ml/evaluate_sensor_robustness.py
```

Regenerate local baseline data before robustness runs. Existing `ml/results/multitask_model.pt` is a clean-trained checkpoint; do not overwrite it as part of a sensor-robustness baseline. Full training and final evaluation are separate deliberate actions.

## Documentation and open questions
Refer to `docs/SIMULATOR_MODEL_AND_EQUATIONS.md`, `docs/SIMULATOR_PILOT_VALIDATION.md`, `docs/ML_MODEL_EXPLANATION.md`, `docs/SENSOR_FAULTS.md`, and `docs/ML_SENSOR_ROBUSTNESS.md`.
Open items: quantify robustness experimentally; consider whether sensor-fault-aware retraining is justified; determine credible real-data integration/validation; eventually evaluate multi-zone scope, realistic weather and thermal calibration, fault detection, and dashboard integration. Do not present these as completed features.
