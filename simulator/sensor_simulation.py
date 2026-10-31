"""Optional sensor faults for Simulator V2; preserves original physical values.

From repository root:
 python simulator/sensor_simulation.py --input data/building_simulation_data.csv --output data/building_with_sensor_faults.csv

The enhanced CSV adds sensor columns without modifying the original simulator
history. Faults affect observations only, not HVAC control or energy balances.
"""
from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path

NEW_COLUMNS = ("indoor_temp_sensor_c", "indoor_temp_sensor_status")


def enrich(input_csv: Path, output_csv: Path, *, seed: int = 42,
           noise_std_c: float = 0.15, dropout_probability: float = 0.005,
           stuck_start_probability: float = 0.0005,
           stuck_steps: int = 24) -> dict:
    """Add noisy, missing or stuck temperature readings at 5-minute intervals."""
    if input_csv.resolve() == output_csv.resolve():
        raise ValueError("Input and output must be different files")
    if noise_std_c < 0 or not (0 <= dropout_probability <= 1) or not (0 <= stuck_start_probability <= 1):
        raise ValueError("Invalid noise standard deviation or fault probability")
    if stuck_steps < 1:
        raise ValueError("stuck_steps must be at least one")

    rng = random.Random(seed)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    counts = {"normal": 0, "dropout": 0, "stuck": 0}
    remaining_stuck = 0
    stuck_value = None
    with input_csv.open(newline="", encoding="utf-8") as source, \
         output_csv.open("w", newline="", encoding="utf-8") as destination:
        reader = csv.DictReader(source)
        if not reader.fieldnames or "indoor_temp_c" not in reader.fieldnames:
            raise ValueError("Input must include indoor_temp_c")
        if any(c in reader.fieldnames for c in NEW_COLUMNS):
            raise ValueError("Sensor columns already exist; use original simulator CSV")
        writer = csv.DictWriter(destination, fieldnames=[*reader.fieldnames, *NEW_COLUMNS])
        writer.writeheader()
        for row in reader:
            true_temp = float(row["indoor_temp_c"])
            if remaining_stuck:
                measured, status = stuck_value, "stuck"
                remaining_stuck -= 1
            elif rng.random() < stuck_start_probability:
                stuck_value = true_temp + rng.gauss(0, noise_std_c)
                measured, status = stuck_value, "stuck"
                remaining_stuck = stuck_steps - 1
            elif rng.random() < dropout_probability:
                measured, status = None, "dropout"
            else:
                measured, status = true_temp + rng.gauss(0, noise_std_c), "normal"
            row["indoor_temp_sensor_c"] = "" if measured is None else f"{measured:.6f}"
            row["indoor_temp_sensor_status"] = status
            counts[status] += 1
            writer.writerow(row)
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path(__file__).resolve().parents[1] / "data" / "building_simulation_data.csv")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "data" / "building_with_sensor_faults.csv")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--noise-std-c", type=float, default=0.15)
    parser.add_argument("--dropout-probability", type=float, default=0.005)
    parser.add_argument("--stuck-start-probability", type=float, default=0.0005)
    parser.add_argument("--stuck-steps", type=int, default=24)
    args = parser.parse_args()
    counts = enrich(args.input, args.output, seed=args.seed,
                    noise_std_c=args.noise_std_c,
                    dropout_probability=args.dropout_probability,
                    stuck_start_probability=args.stuck_start_probability,
                    stuck_steps=args.stuck_steps)
    print(f"Sensor-enhanced CSV: {args.output}")
    print("Reading statuses:", counts)
    print("Original columns remain ground truth; sensor observations are separate.")


if __name__ == "__main__":
    main()
