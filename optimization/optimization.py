import sys
import json
from pathlib import Path
from datetime import date

project_folder = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_folder))

from simulator.building_simulator import Config, simulate

config_file = project_folder / "simulator" / "building_config.json"
config_data = json.loads(config_file.read_text(encoding="utf-8"))
config = Config(**config_data)

start = date(2023, 7, 17)
end = date(2023, 7, 24)
results_folder = project_folder / "reports" / "optimization_test_week"

baseline = simulate(
    start=start,
    end=end,
    output=results_folder / "baseline.csv",
    cfg=config,
    seed=42
)

scenario = simulate(
    start=start,
    end=end,
    output=results_folder / "optimized.csv",
    cfg=config,
    seed=42,
    optimize_cooling=True
)


print("Baseline HVAC energy:", round(baseline["hvac_energy_kwh"], 2), "kWh")
print("Optimized HVAC energy:", round(scenario["hvac_energy_kwh"], 2), "kWh")

print(
    "Baseline temperature violations:",
    round(baseline["occupied_comfort_violation_pct"], 2), "%"
)

print(
    "Optimized temperature violations:",
    round(scenario["occupied_comfort_violation_pct"], 2), "%"
)

print("Baseline occupied minimum:", round(baseline["occupied_min_temp_c"], 2))
print("Baseline occupied maximum:", round(baseline["occupied_max_temp_c"], 2))

print("Scenario occupied minimum:", round(scenario["occupied_min_temp_c"], 2))
print("Scenario occupied maximum:", round(scenario["occupied_max_temp_c"], 2))

energy_saved = baseline["hvac_energy_kwh"] - scenario["hvac_energy_kwh"]
saving_percentage = energy_saved / baseline["hvac_energy_kwh"] * 100

print("HVAC energy saved:", round(energy_saved, 2), "kWh")
print("HVAC energy saving:", round(saving_percentage, 2), "%")

print("Baseline violation minutes:",
      baseline["occupied_violation_steps"] * config.step_minutes)

print("Optimized violation minutes:",
      scenario["occupied_violation_steps"] * config.step_minutes)

print("Baseline hot readings:", baseline["occupied_hot_steps"])
print("Optimized hot readings:", scenario["occupied_hot_steps"])

print("Baseline cold readings:", baseline["occupied_cold_steps"])
print("Optimized cold readings:", scenario["occupied_cold_steps"])

import csv

for filename in ["baseline.csv", "optimized.csv"]:
    print("\nHot readings in:", filename)

    with (results_folder / filename).open(newline="") as file:
        for row in csv.DictReader(file):
            if (
                int(row["occupancy_count"]) > 0
                and float(row["indoor_temp_c"]) > config.occupied_comfort_max_c
            ):
                print(row["timestamp"], row["indoor_temp_c"])


summary = {
    "start": start.isoformat(),
    "end_exclusive": end.isoformat(),
    "baseline_hvac_kwh": baseline["hvac_energy_kwh"],
    "optimized_hvac_kwh": scenario["hvac_energy_kwh"],
    "energy_saved_kwh": energy_saved,
    "saving_percentage": saving_percentage,
    "baseline_violation_minutes":
        baseline["occupied_violation_steps"] * config.step_minutes,
    "optimized_violation_minutes":
        scenario["occupied_violation_steps"] * config.step_minutes,
    "comfort_min_c": config.occupied_comfort_min_c,
    "comfort_max_c": config.occupied_comfort_max_c,
    "selection_margin_c": 0.2,
    "seed": 42,
    "data_type": "synthetic"
}

summary_file = results_folder / "comparison_summary.json"
summary_file.write_text(
    json.dumps(summary, indent=4),
    encoding="utf-8"
)

print("Summary saved:", summary_file)