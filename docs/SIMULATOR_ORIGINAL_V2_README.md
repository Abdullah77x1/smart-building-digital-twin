# Senior Design Project — Smart Building Simulator V2

**Ready-to-run educational prototype**, not an empirical building simulation or an industrial-grade calibrated digital twin. Generates a **synthetic, one-zone office-building history** for machine-learning experimentation.

## Files

| File | Purpose |
|---|---|
| `building_simulator.py` | Pure Python simulator, configurable start/end and control scenarios |
| `building_config.json` | Editable assumed geometry, schedules, envelope, equipment, CO₂ and comfort parameters |
| `building_simulation_data.csv` | Full four-year historical data, 2022–2025, 5-minute steps |
| `building_simulation_data.summary.json` | Unrounded simulation energy, comfort and monthly statistics |
| `validate_simulator.py` | Internal physics, time-grid, scenario and full-dataset consistency tests |
| `validation_results.json` | Saved QA results including per-year statistics |
| `MODEL_AND_EQUATIONS.md` | Mathematical equations, assumptions, units, warnings and references |
| `PILOT_VALIDATION_REPORT.md` | Pilot summary, winter limitation, comfort trade-offs and next actions |
| `pilot_*.csv` / `pilot_*.summary.json` | Selected week-long scenario samples |

## Run

Python 3.10+; **no external packages required** for simulation and QA.

```bash
python building_simulator.py
```

Defaults to January 1, 2022 inclusive through January 1, 2026 exclusive, seed 42, and outputs `building_simulation_data.csv` plus a `.summary.json` file. Re-running overwrites files at those output paths.

Use a small summer example:

```bash
python building_simulator.py --start 2023-07-10 --end 2023-07-18 --output pilot_example.csv
```

Run a matched what-if scenario with an occupied setpoint **1°C higher** (off-hours setpoint unchanged):

```bash
python building_simulator.py --start 2023-07-10 --end 2023-07-18 --setpoint-shift-c 1 --output summer_setpoint_plus1.csv
```

To model a **cooling-only** unit:

```bash
python building_simulator.py --start 2023-01-02 --end 2023-01-10 --cooling-only --output winter_cooling_only.csv
```

To compare occupancy-responsive lighting against the baseline schedule:

```bash
python building_simulator.py --start 2023-07-10 --end 2023-07-18 --lighting-policy occupancy --output summer_occupancy_lights.csv
```

Validate original file against internal invariants (full scan may take seconds):

```bash
python validate_simulator.py --csv building_simulation_data.csv --report validation_results.json
```

You can edit `building_config.json` before rerunning. `step_minutes` is deliberately fixed at 5 in this V2 so the planned +5/+10/+15/+30-minute targets match row offsets 1/2/3/6.

## Data semantics

The 19 CSV fields are:

- `timestamp`: simulated **local UTC+04:00 wall clock**, no time-zone suffix in stored CSV; start of interval.
- `zone_id`, `is_workday`: zone identifier and open-workday flag (`is_workday` excludes sampled closure days).
- `outdoor_temp_c`, `indoor_temp_c`: simulated outdoor and zone temperatures.
- `occupancy_count`, `co2_ppm`: number of people and simulated indoor CO₂ concentration.
- `hvac_setpoint_c`, `hvac_level_pct`, `hvac_mode`: commanded temperature; magnitude of thermal capacity used (0–100%); `cooling`, `heating` or `off`.
- `hvac_cooling_kw_thermal`, `hvac_heating_kw_thermal`: delivered thermal output; **not** electric input power.
- `hvac_power_kw`: electrical input power (cooling+heating+fan+standby).
- `lights_on`, `lighting_power_kw`: lighting command and electric lighting power.
- `plug_power_kw`: appliance/computer electric power.
- `solar_gain_kw_thermal`: solar thermal heat gain.
- `total_power_kw`: sum of all electrical component loads.
- `energy_kwh`, `hvac_energy_kwh`: energy consumed **during the five-minute interval**.
- `next_indoor_temp_c`: internal diagnostic state at **t+5 minutes**; NEVER use directly as a time-t predictor.

No meters or real sensors were connected to produce these data. The assumptions, weather, occupant schedule and HVAC physics are programmatically created.

## Next ML development phase

1. **Freeze and review** building assumptions with your advisor, especially heating-vs-cooling scope, simulation-only validation and comfort definition. Treat this as *candidate* historical data until approved.
2. **Define prediction target semantics** for +5/+10/+15/+30 minutes: future HVAC electrical power (kW), indoor temperature (°C), and occupancy count. The four horizon offsets are `1,2,3,6` records. Total 12 outputs from a multi-task model.
3. **Construct strictly chronological features** from only past and currently known measurements, calendar features, any available forecast weather, and **proposed future controls** (known because you choose them). Do not feed future actual outdoor measurements, future realized power/occupancy/temperatures, or `next_indoor_temp_c` as a current feature. Keep target windows on the proper side of train/validation/test boundaries.
4. **Train baselines first** (last observed value, calendar/weekly seasonal baseline), then compare to models such as random forest/gradient boosting and one shared-trunk neural network with three heads. Scale each target for a joint network.
5. Evaluate 2022–2023 training, 2024 validation, untouched 2025 test. Report **MAE/RMSE for all 12 outputs**, by season and time-of-day, against baselines.
6. Build an **action-conditioned** predictive model or use the mathematical simulator itself for counterfactual setpoint comparisons. The ordinary forecasting model on fixed-policy data must not be treated as a validated causal control model.
7. Implement a simple candidate-setpoint optimizer with explicit 23–26°C occupied comfort constraints, then a Streamlit dashboard and LLM explanations. Compare scenario energy savings **and** occupied comfort violation rates.
8. Seek external calibration against real measured data or a benchmark simulator before implying the prototype predicts actual energy savings.

## Scope limitations

- One well-mixed thermal zone, simplified solar/CO₂, synthetic random weather and occupancy, illustrative heat gains, idealized thermostat control.
- Heating support was **added after a winter pilot failed the chosen 23°C minimum**. Disable with `--cooling-only` if the advisor requires cooling-only; that limitation must then appear in the comfort results.
- Temperature and power models are coupled but are not calibrated against measured buildings, ASHRAE comfort calculations, or manufacturer HVAC curves.
- The generator's thermostat sees internal modeled gains that would be unobservable in some real systems; its excellent temperature regulation can create overly easy ML data.
- A single zone is a defensible prototype, **not completion of the original proposal's multi-zone requirement**; expand only after single-zone acceptance and tests.
