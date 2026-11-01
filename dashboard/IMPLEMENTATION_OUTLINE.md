# Dashboard implementation outline

Prepared for component review, 31 October 2026. Component owner: Hamad.

This is a map of the implemented work and its evidence, not a timesheet or a claim that every line was manually written by the component owner. The dashboard was developed with implementation assistance. The simulator, trained ML model and their reports were already supplied by the team. Personal understanding and presentation rehearsal should be demonstrated separately.

## 1. Start with the component requirements

The original dashboard brief asked for historical building data, predicted energy/temperature, baseline-versus-improved scenarios and energy/comfort indicators. Those became four screens:

| Screen | Question it answers | Source |
| --- | --- | --- |
| Overview | What happened during the selected period? | Generated historical CSV |
| Forecasts | What does the saved model predict next? | Existing PyTorch checkpoint |
| Scenario lab | What happens under a different setpoint/lighting policy? | Two new simulator runs |
| Model & data | Where did the values come from, and how was the model evaluated? | Configuration and saved test report |

Evidence: `static/index.html` and the original dashboard brief in the upstream repository history.

## 2. Inspect the existing Python interfaces

The dashboard reuses `simulator/building_simulator.py`, `simulator/building_config.json`, `ml/prepare_data.py`, `ml/model.py` and the saved checkpoint/report. It does not replace their algorithms.

Current scope: a fictional 120 m² single-zone office; five-minute synthetic observations for 2022–2025. Real measurements, real building calibration and sensor connections are not part of this version.

Evidence: imports and `DashboardService.__init__()` in `service.py`.

## 3. Prepare and validate the history

The team's simulator generates the large CSV locally. The dashboard reads it once and checks required columns, the configured zone, consecutive five-minute timestamps, finite values, nonnegative power/energy/occupancy and consistent energy totals. It reports bad data instead of silently filling gaps.

Evidence: `DashboardService.frame()` in `service.py`; missing-data and energy tests in `tests/test_dashboard.py`.

## 4. Separate presentation from calculations

```text
User: choose dates / forecast timestamp / policy
                         |
                         v
Browser: index.html + style.css + app.js
                         |
                    HTTP / JSON
                         |
                         v
app.py: local API routes and input handling
                         |
                         v
service.py: validation, calculations and adapters
       |                 |                     |
       v                 v                     v
Historical CSV      Existing ML model     Existing simulator
Overview/export      Forecasts             Paired scenarios
```

Python was used because the team's modules are already Python. The frontend uses HTML, CSS, JavaScript and SVG charts. The server uses Python's standard library; there is no npm build, external chart CDN, cloud account or API key requirement. The server binds to the local computer at `127.0.0.1`.

Evidence: `app.py`, `service.py`, `static/app.js`.

## 5. Implement metrics and date filtering

The date range includes both selected dates. Internally, the end boundary is midnight after the final day. Chart values may be averaged into larger time bins; KPI totals and history exports retain the original five-minute records.

Two calculations to explain without reading a script:

- **Energy (kWh)** = sum of electrical power (kW) × 5/60 hours. For example, a constant 2 kW for 30 minutes consumes 1 kWh.
- **Occupied comfort compliance (%)** = occupied intervals inside 23–26°C ÷ all occupied intervals × 100. With no occupied intervals, compliance is unavailable. This temperature band is a project proxy, not a complete comfort standard.

Evidence: `summary()`, `select()`, `history()` and `chart_data()` in `service.py`.

## 6. Connect the existing forecast model

The adapter builds the team's 36 features using only observations from the previous hour through the chosen time. It checks feature order and runs the existing checkpoint. Outputs are HVAC electrical power, indoor temperature and occupancy at +5, +10, +15 and +30 minutes: 12 values altogether.

Future historical values are joined after prediction for comparison. A test changes future observations and confirms the predictions remain unchanged. This protects the dashboard adapter from feeding future observations into inference; it does not independently audit every possible issue in upstream model training.

Evidence: `forecast()` in `service.py`; forecast alignment and future-observation tests.

## 7. Add controlled scenario comparisons

The user chooses a setpoint shift and lighting policy. The adapter calls the team's simulator twice: baseline and candidate, using the same seed, weather and occupancy drivers. Each policy has its own seven-day warm-up. It compares energy and occupied-temperature violations.

This is one user-selected experiment, not automatic optimization. A lower energy total does not mean the candidate is acceptable. The ML checkpoint is not used to estimate the causal effect of changing the HVAC policy.

Evidence: `scenario()` and `_scenario_cached()` in `service.py`; identity-scenario and matched-driver tests.

## 8. Build the visual interface

The supplied design reference guided the dark navy panels, sidebar, cyan/purple accents, KPI cards and charts. The layout was adapted to building-energy content. Source Sans 3 is bundled with its license, and tabular numerals keep numbers aligned. Date controls, loading/error states and CSV downloads support a repeatable demo.

Evidence: `static/index.html`, `static/style.css`, `static/app.js` and `static/fonts/`.

## 9. Verify behavior and document limits

Run from the repository root:

```bash
python -m unittest discover -s dashboard/tests -v
```

The ten automated tests cover energy totals, inclusive dates/export, unavailable comfort when unoccupied, invalid inputs, missing/gapped data, forecasts and historical alignment, future-observation independence, identity scenarios, matched conditions and local HTTP behavior. They use temporary generated data and the existing checkpoint. They are not a real-building validation or a full browser accessibility audit.

The local browser flow was exercised during development. Before presenting on a different machine, run the demo there and confirm the font, charts and downloads display correctly.

## 10. Submit an isolated change for team review

The submission is based on the team's actual `main` history, with changes limited to `dashboard/`. The simulator, ML, optimization, root README, dependencies and existing data files are retained. Generated history, personal chats, virtual environments and presentation attachments are excluded.

Use a separate branch and a draft pull request. Teammates review it before any merge to `main`. The original local ZIP-based development history is a snapshot and should not be pushed as if it were an upstream clone.

## How this fits the current simulator/ML discussion

The components answer different questions. A physics simulator can generate trajectories under assumed policies. The present ML model learns short-horizon predictions from generated history. The dashboard displays both and identifies their sources.

The current saved model uses synthetic training data, with 2022–2023 for training, 2024 for validation and 2025 for testing. Real-plus-synthetic training is a future integration decision, not an implemented feature. Comparing ML predictions with held-out simulator values measures agreement with that simulator; it does not prove accuracy on a real building. The saved report also compares ML with a no-change baseline, which can outperform ML on some metrics.

Still pending: real-data mapping/calibration, the optimization teammate's result interface and any LLM explanation service. An LLM, if added, should explain calculated results and their limitations; it should not invent savings numbers.

## Evidence to show in a review

1. The pull request's **Files changed** tab establishes the submitted scope.
2. Open `service.py` and trace one value from CSV to KPI through `summary()`.
3. Run the tests and explain the purpose of two tests in your own words.
4. Demonstrate Overview → Forecasts → Scenario lab → Model & data.
5. Describe one limitation and the next interface needed from each teammate.

A commit is evidence of a submitted change, not evidence of unaided authorship or understanding. The strongest evidence of ownership is being able to trace, test, explain and improve the component. Be transparent about implementation assistance and follow your course's disclosure requirements.
