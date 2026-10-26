# Generated building data

The full historical `building_simulation_data.csv` is **not tracked by Git** because it is approximately 79 MB and completely reproducible.

From the repository root run:

```bash
python simulator/building_simulator.py
```

This produces `data/building_simulation_data.csv` (2022–2025, 420,768 five-minute records, including leap day).

`sample_building_data.csv` is a tiny **actual excerpt** from the generated dataset for browsing the columns without generating the whole file.

All teammates should use the same `simulator/building_config.json`, default seed and simulator version to get comparable data. If any of these change, regenerate datasets and **retrain models**.
