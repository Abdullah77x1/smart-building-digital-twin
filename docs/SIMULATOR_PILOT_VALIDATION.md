# SDP V2 — Pilot Validation and Full Historical Data Report

**Model status:** Internally tested synthetic prototype; NOT calibrated or independently validated against real building data.

## A. Implementation checklist

- **PASS:** 5-minute time step, 19 documented CSV fields, editable building configuration.
- **PASS:** People-based daily arrival, departure, lunch and visitor schedules; no five-minute random re-draw.
- **PASS:** Signed HVAC controller, capacity limits and ramp rates; cooling and optional heating.
- **PASS:** One-zone RC temperature and electric/thermal power and energy equations.
- **PASS:** Pilot summer, winter, high-temperature, HVAC-off and matched thermostat-shift cases.
- **PASS:** Four-year chronological dataset generated *after* pilot tests.

## B. Pilot findings

| Scenario | Simulated electricity | Occupied comfort failure | Finding |
|---|---:|---:|---|
| Summer baseline, 8 days | 394.22 kWh | 1.37% | Standard configuration |
| Same 8 days, occupied setpoint +1°C | 380.35 kWh | 20.90% | 3.52% lower electricity, but comfort degrades markedly |
| Same 8 days, outdoor temperature +4°C | 459.37 kWh | — | Energy demand increases under matched occupancy |

- A no-HVAC summer-day intervention reached **40.35°C**, compared with **27.00°C** as the baseline summer-week maximum. Heating/cooling disabled only after the same warm-up conditions; powered standby electricity remains.
- Winter cold-temperature violations fell from **116 occupied five-minute records** (cooling only) to **0** when an optional heating mode was enabled. This is a deliberate model extension, subject to advisor review.
- Weather, occupancy, plug electrical load and solar heat gains were identical between the two paired summer setpoint scenarios. The difference in calculated electricity is therefore attributable to the changed operating policy within this simulator.

## C. Complete historical dataset

- Rows: **420,768**; 2022-01-01 00:00 through 2025-12-31 23:55.
- All time increments are 5 minutes. Leap day 2024 is present. Weekend occupancy is zero.
- Calculated total energy: **52,353.94 kWh**, of which HVAC electrical energy is **31,923.11 kWh**.
- Occupied comfort failure (outside project 23–26°C proxy): **2.03%** of occupied five-minute intervals.
- Unrounded physical temperature extremes: **23.50–27.00°C**.

| Year | Records | Electricity (kWh) | HVAC energy (kWh) | Mean outdoor temp (°C) | Occupied comfort failures |
|---|---:|---:|---:|---:|---:|
| 2022 | 105,120 | 13,197.45 | 8,059.99 | 29.24 | 2.11% |
| 2023 | 105,120 | 13,050.44 | 7,978.95 | 28.88 | 1.99% |
| 2024 | 105,408 | 13,020.73 | 7,916.06 | 28.72 | 2.16% |
| 2025 | 105,120 | 13,085.33 | 7,968.11 | 28.70 | 1.86% |

## D. Numerical / structural consistency

- Maximum component electrical-power reconciliation discrepancy: **0.000001000 kW**, consistent with decimal rounding.
- Maximum five-minute energy arithmetic discrepancy: **0.0000000433 kWh**.
- Maximum discrepancy between one row’s next-temperature diagnostic and the next row’s current temperature: **0.000000000°C**.
- CSV has consistent time grid and continuous indoor state across every calendar-year boundary.
- HVAC cooling ≤12 kW thermal, heating ≤8 kW thermal; no simultaneous heat and cool; ramp and comfort counts checked.

## E. Interpretation / what is not validated

**PASS means computational consistency, not real-world accuracy.** The equations and coefficients are a proposed educational model. The simulator does not model latent humidity loads, ventilation thermal loads, complete solar radiation geometry, real equipment cycling, thermostatic sensor imperfections, or actual weather records.

In particular, an unusually narrow 23.5–27°C temperature range across four years results partly from idealized thermostat access to heat gains; a more realistic controller/sensor model, parameters calibrated to real observations and richer building dynamics should be considered before claiming robust performance.

The synthetic data are suitable for a proof-of-concept predicting the behavior of **this generator** and illustrating energy–comfort trade-offs. They are NOT independent proof of future real-building savings.

## F. Next actions

1. Send this specification, code and pilot report to the advisor for approval, especially whether heating is in scope.
2. Freeze generator version/seed/config as the baseline and preserve the untouched 2025 test year.
3. Design the +5/+10/+15/+30-minute targets and leak-free historical input features for HVAC power, indoor temperature, occupancy.
4. Train simple baselines, then compare a multi-task model with separate regressors; report metrics by horizon and season.
5. Evaluate a what-if control policy using matched conditions, constraining occupied temperatures, then integrate dashboard/LLM.
6. Validate against external building/weather data or a recognized simulator before presenting real-world performance claims.
