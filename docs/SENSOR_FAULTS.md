# Optional sensor-noise and malfunction experiment

Simulator V2 still produces the original physically consistent **ground-truth** CSV. This optional step adds an observed indoor temperature, leaving original columns and HVAC dynamics untouched.

From the repository root:

```powershell
python simulator/building_simulator.py --start 2023-07-10 --end 2023-07-12 --output data/pilot.csv
python simulator/sensor_simulation.py --input data/pilot.csv --output data/pilot_sensors.csv
python -m unittest discover -s simulator -p test_sensor_simulation.py
```

To process full 2022–2025 history, run `python simulator/sensor_simulation.py` after generating the baseline CSV.

## Extra output columns

- `indoor_temp_sensor_c`: noisy observed temperature, blank for a missing reading.
- `indoor_temp_sensor_status`: `normal`, `dropout`, or `stuck`.

Existing `indoor_temp_c` is the simulator's ground-truth state (not a faulty measurement). Other columns, including energy and HVAC power, remain unchanged. Defaults: normal noise standard deviation 0.15°C, per-step dropout probability 0.005, per-step stuck-fault start probability 0.0005, and stuck duration 24 steps (2 hours). Parameters are illustrative, not calibrated against actual sensor specifications. Use the same seed for reproducibility. Example:

```powershell
python simulator/sensor_simulation.py --input data/pilot.csv --output data/pilot_sensors.csv --noise-std-c 0.2 --dropout-probability 0.01 --stuck-start-probability 0.001 --stuck-steps 36
```

**Important:** This is a separate measurement dataset. Existing `ml/prepare_data.py` still uses ideal `indoor_temp_c` and rejects missing predictor values. Training on faulty sensor measurements requires an explicit, leakage-safe preprocessing choice; do not silently replace target/ground-truth columns. The added status is simulated ground truth for evaluation, not information automatically available to a real fault detector.
