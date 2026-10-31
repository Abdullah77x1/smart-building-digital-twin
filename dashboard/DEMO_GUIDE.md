# Hamad's dashboard demo and explanation guide

## Your contribution in one sentence

“My assigned component is the dashboard. It connects our existing simulator and ML model, displays energy and indoor conditions, runs forecasts, and compares simulated policies with their comfort trade-offs. I used Codex to assist with the implementation.”

The team has changed direction since the older CU-BEMS slides. The current GitHub implementation uses a fictional **120 m², single-zone office**, synthetic 2022–2025 data, five-minute intervals and up to 15 occupants. Say this explicitly. Do not describe the current dashboard as showing live sensors or actual CU-BEMS measurements.

## A four-minute demonstration

1. **Overview, about 60 seconds.** Open the dashboard with both dates set to **15 July 2025**. Explain that the values are simulated. Point out total electricity (about **49.7 kWh**), HVAC electricity (about **31.0 kWh**), peak occupancy (**13**) and occupied comfort (**91.2%**, with **60 minutes** outside the project band). Hover over the power chart. Explain kW versus kWh, then point out the temperature and occupancy charts. These numbers were checked against the repository's default seed/configuration, not real measurements.
2. **Forecasts, about 60 seconds.** Select **15 July 2025 at 09:00** and click **Run forecast**. Current HVAC power is about **2.125 kW**. The included model predicts about **2.171 kW at +15 minutes**, compared with the historical simulated value of **2.159 kW**. Scroll to temperature and occupancy. Explain that the model outputs 12 values: three targets at four horizons. Actual future observations are displayed for evaluation but never passed into the forecast inputs.
3. **Scenario lab, about 75 seconds.** Keep the same analysis day. Use **+1°C** and **occupancy-aware lighting**, then click **Run comparison**. The checked run saves about **1.0 kWh (2.1%)**, but raises occupied time outside 23–26°C from **60 to 685 minutes**. Point to the warning: this candidate does not maintain the project's comfort proxy. Explain that both runs use the same weather and occupant drivers, and each policy has its own seven-day warm-up. The candidate is not a validated recommendation.
4. **Model & data, about 45 seconds.** Show the 2025 evaluation report, the model/no-change comparison, and source provenance. Explain that the optimizer and LLM are not connected yet. Your dashboard already provides a place for their results, while the current summary uses arithmetic. Finish by exporting the history or scenario summary CSV.

If asked to change dates, choose another day within 2022–2025 and click **Apply period**. A weekend is a useful edge case: if nobody is present, comfort compliance displays a dash instead of a misleading 100%. Scenario requests over 31 days show an explanatory error.

## Questions you should be ready to answer

**What is included in your assigned component?**
The AI-assisted dashboard implementation includes the frontend, local HTTP server, Python adapters, date filters, charts, KPI calculations, CSV exports, model-result presentation, scenario comparison interface and integration tests. The simulator equations, generator and trained neural network are the team's existing work and were not rewritten. Explain the assistance used and distinguish the work you have personally reviewed or tested. Do not claim to have manually authored or independently validated work you have not done. Read IMPLEMENTATION_OUTLINE.md, trace the code and demonstrate the component you submit.

**Why a Python backend and browser frontend?**
The team already works in Python. The backend directly imports its simulator and ML functions, while the browser presents results without needing Node, npm, a database, or external web services. A single Python command starts the dashboard. The service layer keeps model logic separate from presentation.

**Where does each value come from?**
Overview values come from the generated CSV. Forecasts come from the saved PyTorch checkpoint. Scenario values come from new calls to the physics simulator. Model accuracy comes from the repository's saved test report. The UI identifies those sources instead of mixing them.

**Why not call this a real building digital twin?**
It is an offline synthetic proof of concept of a single zone. The equations and assumptions are not calibrated against a real building. The dashboard does not create real-world validity; it displays the validity limits alongside the numbers.

**How do you calculate energy?**
Power in kW multiplied by time in hours gives energy in kWh. For five-minute records, integrate each power value over 5/60 hours, then sum. The dashboard sums interval energies and checks consistency with this calculation. Thermal HVAC power is different from electrical demand.

**What exactly does “comfort” mean here?**
The project's indoor-temperature proxy is 23–26°C while occupancy is above zero. Compliance counts occupied five-minute intervals within that band. Humidity, air speed, clothing and occupant preferences are not included, so it is not a complete thermal comfort assessment or a regulatory certification.

**Does the forecast model determine scenario temperatures?**
No. The neural network forecasts continuation of the baseline policy. The scenario lab runs the team's physics simulator with a changed setpoint policy. This avoids claiming that a correlational forecast is a validated causal model of HVAC interventions.

**What prevents future-data leakage?**
The adapter supplies only observations from the previous hour through the selected timestamp to feature construction. The team's feature function uses current values, calendar features and backward lags. Future actuals are looked up after inference. A test deliberately changes future temperature values and verifies that predictions stay unchanged.

**Why might the no-change model win?**
A slowly changing variable can be forecast well by carrying the current value forward, especially over five minutes. We show both baselines. For example, the saved report has lower five-minute temperature MAE for no-change than for the neural network. It would be misleading to claim the neural network always wins.

**Why are there fractional people in forecasts?**
The model is a regressor, so occupancy is a continuous estimate. The observed simulator occupancy is an integer. Averaging chart bins over longer periods can also produce fractional occupancy. The UI distinguishes these interpretations.

**Is the scenario with lower energy “optimal”?**
No. It is one user-selected candidate. Optimization would require a search objective, constraints and a comparison across feasible candidates. The team's optimization module is still pending. Savings alone cannot establish comfort feasibility.

**Why can a scenario baseline differ from the historical chart?**
The scenario reruns the selected dates with a fresh seven-day warm-up. The official history carries state continuously over its four-year run. A custom CSV may also use different assumptions. Compare the candidate to the paired scenario baseline, not automatically to an unrelated history total.

**What is the LLM doing?**
Nothing yet. The current overview sentence is a calculation-based summary, labeled “no LLM connected.” Future LLM explanations should receive the calculated results and limitations rather than invent numbers. This boundary is ready for integration but not implemented as a functioning LLM.

## Where to look in the code

- `dashboard/service.py`: dataset validation, energy/comfort calculations, ML adapter and matched simulations.
- `dashboard/app.py`: local server and API route allowlist.
- `dashboard/static/app.js`: UI state, charts, requests and displayed results.
- `dashboard/static/index.html` and `style.css`: structure and responsive styling.
- `dashboard/tests/test_dashboard.py`: integration tests.

## Before the meeting

Run the dashboard once, rehearse the four steps, and read the calculation and limitation sections. Keep the terminal and browser open. Test the room's display if possible. Bring the source package and the guide, and show working behavior rather than claiming that future integrations are complete.
