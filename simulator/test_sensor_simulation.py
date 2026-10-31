"""Tests: python -m unittest discover -s simulator -p test_sensor_simulation.py"""
import csv
import tempfile
import unittest
from pathlib import Path
from sensor_simulation import enrich


class SensorSimulationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / "original.csv"
        self.output = Path(self.temp.name) / "sensor.csv"
        with self.source.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["timestamp", "indoor_temp_c", "hvac_power_kw"])
            writer.writeheader()
            for i in range(100):
                writer.writerow({"timestamp": str(i), "indoor_temp_c": f"{24+i/100:.6f}", "hvac_power_kw": "1.25"})

    def rows(self):
        with self.output.open(newline="") as handle:
            return list(csv.DictReader(handle))

    def test_reproducible_and_preserves_ground_truth(self):
        counts = enrich(self.source, self.output, seed=10)
        first = self.output.read_bytes()
        enrich(self.source, self.output, seed=10)
        self.assertEqual(first, self.output.read_bytes())
        self.assertEqual(sum(counts.values()), 100)
        self.assertEqual(self.rows()[0]["indoor_temp_c"], "24.000000")
        self.assertEqual(self.rows()[-1]["hvac_power_kw"], "1.25")

    def test_dropout(self):
        counts = enrich(self.source, self.output, dropout_probability=1, stuck_start_probability=0)
        self.assertEqual(counts["dropout"], 100)
        self.assertTrue(all(r["indoor_temp_sensor_c"] == "" for r in self.rows()))

    def test_stuck(self):
        counts = enrich(self.source, self.output, dropout_probability=0,
                        stuck_start_probability=1, stuck_steps=4, noise_std_c=0)
        rows = self.rows()
        self.assertEqual(counts["stuck"], 100)
        self.assertEqual(len({r["indoor_temp_sensor_c"] for r in rows[:4]}), 1)
        self.assertNotEqual(rows[0]["indoor_temp_sensor_c"], rows[4]["indoor_temp_sensor_c"])

    def test_invalid_parameters(self):
        with self.assertRaises(ValueError):
            enrich(self.source, self.source)
        with self.assertRaises(ValueError):
            enrich(self.source, self.output, dropout_probability=1.5)


if __name__ == "__main__":
    unittest.main()
