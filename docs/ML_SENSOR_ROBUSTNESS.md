# Experiment: how sensor faults affect the existing ML forecast

This experiment **does not retrain** the existing ML model. It compares forecasts from the same checkpoint on clean vs faulty temperature inputs, scored against the same simulator ground-truth future targets.

From the repository root (after `pip install -r requirements.txt`):

```powershell
git switch feature/simulator-improvements
git pull origin feature/simulator-improvements
python simulator/building_simulator.py
python simulator/sensor_simulation.py
python ml/evaluate_sensor_robustness.py
```

Output (not committed): `reports/sensor_robustness/sensor_robustness_metrics.csv` and `sensor_robustness_report.json`.

For missing readings, the observed temperature is filled using **only previously seen sensor readings** for that zone and calendar year. If an interval has no previous observation in the year, the fixed baseline of 25°C is used. Historical temperature lags are derived from these same observed/filled readings, never from simulator ground truth. Other features remain clean. The model's predicted targets and the 2025 held-out year remain unchanged.

Report rows compare mean absolute error for each predicted quantity (+5/+10/+15/+30 minutes), globally and for each *current* sensor fault status (normal, dropout, stuck). Status labels are evaluation-only; not model inputs. Since stuck faults persist and missing values can be followed by normal readings, the 'normal' group may also include lingering impacts of earlier faults. More detailed window-based analysis can be done later.

This is a first **inference-only robustness test**. It does not prove real sensor fault detection, real-building prediction accuracy, or that the model is robust to missing inputs. It also does not compare fault-aware retraining. We can decide whether retraining is worthwhile after evaluating these results.
