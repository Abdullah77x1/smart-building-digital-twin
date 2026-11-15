# Real-building data package (Smart Building Digital Twin)

Package v2.4 (v2.3 plus the ML benchmark): adds PLEIAData (12 rooms), ROBOD (rooms 3 and 4) and ORNL FRP-2 (cooling season), with cards and analysis scripts, and the V3 two-node simulator calibration (protocol, results, code).

Measured data from real buildings, prepared for the team. Not synthetic. Details, checks and limits are in `docs/`.

## Contents
| Path | What it is |
|---|---|
| `data/CUBEMS_2019_Floor6_Zone4_real_merged_5min.csv` | **Main file.** One zone, Bangkok, 6 Mar to 22 Oct 2019, every 5 min, with outdoor weather (66,226 rows) |
| `data/CUBEMS_2018_Floor6_Zone4_real_merged_5min.csv` | **Year-transfer test set** (different year, never used for fitting; its reference results have been seen). Same zone, 1 Jul to 14 Sep 2018 (21,888 rows) |
| `data/CUBEMS_2019_Floor6_AllZones_real_long_5min.csv` | Optional: zones Z1, Z2, Z4, Z5 stacked with `zone_id` |
| `data/FLEXLAB_2020_cellsAB_real_5min.csv` | Two small test cells, Berkeley, Jul to Aug 2020 (separate building) |
| `data/NTU_2018_2019_real_5min.csv` | Small office, Singapore, two control cases (separate building) |
| `data/PLEIAData_2021_12rooms_10min.zip` | 12 rooms (Murcia, Spain, 2021), 10-minute rows, indoor temperature, AC unit states, presence, CO2, weather. Unzip first (630,720 rows). Usable AC dynamics only in rooms A42, B12, B11, B10, B9, B16 (see its card) |
| `data/ROBOD/combined_Room3.csv`, `combined_Room4.csv` | NUS SDE4 (Singapore, 2021), two rooms, 5 min, with **camera occupant count** and measured solar. Weekdays only, in blocks (29 and 47 days) |
| `data/ORNL_FRP2/` | Oak Ridge test building, **cooling season only**: baseline, free-floating and night set-back, 1-minute, unoccupied, measured solar. Skip the unit row (row 2) when reading |
| `docs/DATA_CARD_PLEIAData_12rooms.md`, `DATA_CARD_ROBOD_Room3_Room4.md`, `DATA_CARD_ORNL_FRP2_cooling.md` | Source, licence, checks, limits and the analyses for these three |
| `data/benchmark/`, `docs/BENCHMARK.md`, `scripts/benchmark/` | **ML benchmark**: ready feature tables per building (CU-BEMS, ROBOD, PLEIAData) plus an optional pooled table, fixed splits, baselines, one scoring script (`evaluate.py`: a model file needs only `fit` and `predict`), integrity checks and four example models. Start here for model comparison |
| `docs/V3_PROTOCOL.md`, `docs/V3_RESULTS.md`, `scripts/v3/`, `reference_run/v3/` | Two-node simulator V3: protocol frozen before fitting, results, simulator code with the mass node (identical to V2 when the mass is 0), comparison scripts and outputs |
| `scripts/analyses/` | Scripts behind those cards (ORNL, ROBOD, PLEIAData). They read the packaged files; PLEIAData scripts need the unzipped CSV in the working directory (or the raw Zenodo files for the build). ORNL results re-run identically from the package |
| `data/weekday_ac_off_days.csv` | Monday-Friday days when the AC never ran (14 days): closure or holiday candidates, **not** an official holiday list |
| `data/real_operating_schedule_summary.csv`, `data/real_weekday_hourly_profile.csv` | The real AC timer schedule and hourly weekday profile (use as the baseline schedule) |
| `docs/DATA_CARD.md` | Sources, columns, checks, limits for the CU-BEMS files |
| `docs/DATA_CARD_FLEXLAB_NTU.md` | Same for FLEXLAB and NTU |
| `docs/zone_transfer_criteria_TEMPLATE.json` | **Proposed** success criteria for the reserved zones (`adopted: false`); the team edits and adopts them before the zones are run |
| `docs/ZONE_TRANSFER_PROTOCOL.md` | Frozen protocol for the reserved zones Z1, Z2, Z5 (read before running them) |
| `docs/REFERENCE_RESULTS.md`, `reference_run/` | Frozen reference results (v2), limits, changes from v1, environment and checksums |
| `scripts/check_reference.py` | Re-runs the reference forecast and lunch test and compares with `reference_run/` |
| `docs/FORECAST_TIMING_DEFINITION.md` | Timing definition, allowed inputs, baselines, split and reporting rules for the forecast experiment, with reference results |
| `scripts/forecast_reference.py` | Reference implementation of that experiment (model vs persistence vs schedule); 2018 is evaluated only with `--final` |
| `scripts/lunch_test.py` | Lunch-shutdown natural experiment: day selection, the distribution of the temperature rise (2019 and 2018) and the comparison figure |
| `scripts/build_real_data.py` | Rebuilds the three CU-BEMS files from the raw figshare files, offline (see below) |
| `scripts/fetch_external.py` | Downloads the weather and solar inputs (needs internet) |
| `external/` | The weather (Meteostat) and solar (Open-Meteo) inputs actually used |
| `figures/` | Overview, lunch-shutdown test, simulator vs real |

## Load it
```python
import pandas as pd
df = pd.read_csv("data/CUBEMS_2019_Floor6_Zone4_real_merged_5min.csv", parse_dates=["timestamp"])
df = df[df.good_row == 1]            # use only good rows for fitting and scoring
train = df[df.suggested_split == "train"]
```

## Rules
- Use `good_row == 1`. Do not fill or interpolate missing measured values.
- Rows are exactly 5 minutes apart. If you build lags, require **every** row in the lag window to be measured (no gaps inside the window, not only at the lags used); the reference code does this.
- Use `suggested_split` (time-based); never shuffle rows between train and test. The 2018 file is a year-transfer test only; read `docs/FORECAST_TIMING_DEFINITION.md` first.
- Do not mix buildings in one table by default. If you combine real and synthetic data (or several buildings) for training, add `building_id` and `data_origin` columns and evaluate on real data only.
- Never report simulator (synthetic) results as real-building results.

## Main findings so far
- The real AC runs on a timer: 07:45 to 11:50 and 13:00 to 16:25 on working weekdays (within about 5 minutes); about 21 to 22 C while on; off at night and on weekends.
- Lunch test: after the AC stops, the real room warms about 3.8 C in 65 min on average (138 days in 2019, 10th to 90th percentile 3.1 to 4.6 C; 3.65 C on 17 days in 2018); our simulator equation predicts about 1 C. The rise is not constant: it grows with outdoor temperature.
- Reference forecast (15 min ahead, v2): temperature MAE 0.130 C against 0.258 C for persistence on the 2019 test period; on 2018 the model is **not** better than persistence in MAE (0.352 against 0.319 C). For power, after excluding the identified closure days, model and schedule baseline both have a MAE of about 0.406 kW (0.4056 and 0.4062; this set still includes weekends). A good forecast does not prove real savings; the 8.63% saving remains a simulation result.
- Simulator reported numbers reproduce (5.90% dev week, 8.63% test week), but they come from a baseline that differs from the real one.

- Across buildings the rebound after an AC stop differs: +3.8 C in 65 min (CU-BEMS, timer), about 0 (ROBOD evening stop), +0.74 C (PLEIAData, 100 events, user-controlled units). One fixed set of thermal parameters fits none of them; calibrate per building.
- ORNL (unoccupied building): night set-back (AC off 22:00-07:00) used about 29% less cooling energy than the 24 h baseline after adjusting for weather (37% raw; 7-day baseline, different weeks, so a rough figure). A two-node (air + mass) model predicted the set-back days far better than one node (exploratory; see its card).
- The simulator's 5.90% and 8.63% are **HVAC electricity only**; whole-building they are 4.16% and 5.89%. About a third of the test-week saving comes from the baseline's simulated heating in July (6.34 kWh against 0.52 kWh with the optimizer).

- **V3 (see `docs/V3_RESULTS.md`):** a two-node (air + mass) model calibrated on CU-BEMS Zone 4 reproduces the lunch rebound (+3.7 C against +3.3 C measured on test windows; the one-node model gives +0.85 C). Put into the simulator, the optimizer's HVAC saving falls from 5.90% / 8.63% to about 2.5% / 3.1%, and the original one-step optimizer then leaves the comfort band in about 25% of occupied steps; an optimizer that knows the mass node keeps comfort and saves about 2 to 2.7% of HVAC. Simulation only.

## Not in the data
No occupancy count, setpoint or CO2 in CU-BEMS; solar radiation is modeled (reanalysis), not measured. The CU-BEMS zone is much larger than the simulated 120 m2 office, so compare shapes and behavior, not absolute kW. The real building never ran our optimizer, so real-world savings cannot be claimed.

## Credit and licences
CU-BEMS (Chulalongkorn University): https://doi.org/10.1038/s41597-020-00582-3 (data licence: CC BY 4.0, figshare record version 4). Weather: Meteostat, station 48455 (CC BY-NC 4.0). Solar radiation: Open-Meteo.com Historical Weather API (ERA5 reanalysis), CC BY 4.0 with attribution (check terms on open-meteo.com). FLEXLAB and NTU: IEA EBC Annex 81 dataset, CC BY 4.0, https://data.mendeley.com/datasets/xztfbtsgys/3

PLEIAData: Martínez Ibarra, González-Vidal, Skarmeta Gómez, Zenodo 7620136, CC BY 4.0, https://doi.org/10.5281/zenodo.7620136 . ROBOD: Tekler et al., Building Simulation 15(12), 2022, figshare 19234530 (CC BY 4.0), https://doi.org/10.1007/s12273-022-0925-9 (our copies come from the GitHub repository, which states no licence; see its card). ORNL FRP-2: Im, Jung, Yoon, figshare 20520438 v3 (CC BY 4.0), article https://doi.org/10.1038/s41597-022-01858-6 . Building 59 (CC0, Zenodo 5951008) is **not** included: its data are curated (outliers adjusted, gaps filled), which conflicts with the no-filling rule.

## Citation (CU-BEMS)

Pipattanasomporn, Manisa; Chitalia, Gopal; Songsiri, Jitkomut; Aswakul, Chaodit; Pora, Wanchalerm; Suwankawin, Surapong; et al. (2020). CUBEMS, a smart building electricity consumption and indoor environmental sensor dataset. figshare. Dataset. https://doi.org/10.6084/m9.figshare.11726517.v4

Licence: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)

## Two separate checks (do not confuse them)
| Level | What it shows | Needs | Command |
|---|---|---|---|
| **A. Results** | The forecast and the lunch-test numbers can be reproduced from the packaged data (checksums, settings, finite numbers, counts; errors within 1e-6 in the same environment) | Packaged files only (pandas, numpy, scikit-learn) | `python scripts/check_reference.py` (and `--selftest` tests the comparison itself) |
| **B. Data** | The packaged CU-BEMS files can be rebuilt from the raw figshare files | The raw files (not in the package) | `python scripts/build_real_data.py ... --verify data` (below) |
Library versions matter for Level A: re-run in Python 3.13 / pandas 3.0.5 / numpy 2.5.3 / scikit-learn 1.9.1 (frozen run: Python 3.12.3, scikit-learn 1.8.0), the checksums, the lunch test and every 2019 and temperature number pass, but the 2018 **power** model metrics differ by up to 0.06 kW (about 3%) and the check reports FAIL for them; the same happens with the previous package version, so it comes from the environment, not from the data. Use the frozen environment (`reference_run/environment.txt`) for an exact match. Level A does not prove Level B and the other way round. The FLEXLAB and NTU files are not rebuilt by any script (they come from the Mendeley files with the steps in `docs/DATA_CARD_FLEXLAB_NTU.md`).

## Rebuild from raw (reproducibility, Level B)
1. Download `2018Floor6.csv` and `2019Floor6.csv` from https://doi.org/10.6084/m9.figshare.11726517 into one folder. Expected MD5: `2019Floor6.csv` 4f2446b38b566f2c1a07bf0e44587b42 (matches the figshare record); `2018Floor6.csv` e4074802fd7973a87e620a9ea1a381b6 (our copy, not compared with the record).
2. From this package folder (needs Python with pandas and numpy):
```
python scripts/build_real_data.py --raw-dir C:\path\to\raw --external-dir external --out-dir rebuilt --verify data
```
3. The script prints rows and good rows for each file and `PASS` when the rebuilt file equals the one in `data/` (it is byte-identical).
`scripts/fetch_external.py` refreshes the weather and solar inputs from the internet (needs `pip install meteostat`); providers may change values, so the copies in `external/` are the reference. That script reuses the code run in our notebook but was not re-run when the package was assembled.

## Run the reference forecast
```
python scripts/forecast_reference.py --data-dir data --out-dir results            # train, validation and test 2019
python scripts/forecast_reference.py --data-dir data --out-dir results --final    # also 2018 (year-transfer check)
python scripts/forecast_reference.py --data-dir data --out-dir results --zone-transfer F6_Z1 F6_Z2 F6_Z5 --criteria criteria_zone_transfer.json   # reserved zones, ONCE; needs adopted success criteria (docs/ZONE_TRANSFER_PROTOCOL.md)
python scripts/check_reference.py                                                   # compare with the frozen reference run
```
```
python scripts/lunch_test.py --data-dir data --out-dir results                  # lunch-shutdown experiment (needs pandas, numpy)
```
The forecast script needs pandas, numpy and scikit-learn (matplotlib optional for the figure); it checks its own timing definition on every run. Read `docs/FORECAST_TIMING_DEFINITION.md` first.
