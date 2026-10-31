"""End-to-end small sensor robustness test without touching saved model results."""
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "simulator"))
sys.path.insert(0, str(ROOT / "ml"))
from building_simulator import simulate
from sensor_simulation import enrich
from evaluate_sensor_robustness import prepare_paired, evaluate
from model import MultiTaskModel, save_checkpoint
from prepare_data import split_years


class SensorRobustnessSmokeTest(unittest.TestCase):
    def test_end_to_end(self):
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            # Short 2022 and 2025 segments are sufficient for smoke testing
            # feature alignment and the reserved test-year evaluation.
            parts = []
            for year in (2022, 2024, 2025):
                path = work / f"{year}.csv"
                simulate(date(year, 7, 10), date(year, 7, 13), path)
                parts.append(path)
            import csv
            combined = work / "combined.csv"
            with combined.open("w", newline="") as out:
                writer = None
                for part in parts:
                    with part.open(newline="") as source:
                        reader = csv.DictReader(source)
                        if writer is None:
                            writer = csv.DictWriter(out, fieldnames=reader.fieldnames)
                            writer.writeheader()
                        writer.writerows(reader)

            faulty = work / "faulty.csv"
            stats = enrich(combined, faulty, seed=42, dropout_probability=0.03,
                           stuck_start_probability=0.02, stuck_steps=6)
            self.assertEqual(sum(stats.values()), 3 * 3 * 288)
            paired, noisy, features, targets = prepare_paired(faulty)
            self.assertEqual(len(paired), len(noisy))
            self.assertFalse(noisy.isna().any().any())
            self.assertTrue((noisy["indoor_temp_c"] != paired["indoor_temp_c"]).any())
            _, _, test = split_years_with_short_fixture(paired)

            # Randomly initialized checkpoint tests I/O and indexing only.
            # No performance claims are made from this smoke test.
            model = MultiTaskModel(len(features))
            checkpoint = work / "untrained_smoke_checkpoint.pt"
            save_checkpoint(checkpoint, model, features, targets,
                            np.zeros(len(features), dtype=np.float32),
                            np.ones(len(features), dtype=np.float32),
                            np.zeros(len(targets), dtype=np.float32),
                            np.ones(len(targets), dtype=np.float32), 64)
            # evaluate() uses the original split_years helper, which requires
            # 2024 validation samples; include a short 2024 fixture instead.
            report = evaluate(faulty, checkpoint, work / "report")
            self.assertEqual(report["test_year"], 2025)
            self.assertGreater(report["test_rows"], 0)
            self.assertTrue((work / "report/sensor_robustness_metrics.csv").exists())


if __name__ == "__main__":
    unittest.main()
