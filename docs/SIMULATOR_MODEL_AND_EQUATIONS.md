# Smart Building Simulator V2 — Implemented Model and Equations

**Scope:** Fictional 120 m² single-zone office in a synthetic Abu Dhabi-like climate. Five-minute time step; data from 2022–2025. **All parameter values are illustrative design assumptions, not calibrated field measurements.** The physical model is a simple lumped resistance–capacitance (RC) model rather than an engineering-grade HVAC simulation.

## 1. Space and numerical integration

- Floor area = 120 m²; ceiling height = 3 m; volume = 360 m³.
- Maximum headcount = 15; weekdays Mon–Fri, usually 08:00–18:00.
- Start of office HVAC preconditioning = 06:30 on open days.
- Occupied thermostat target = one value drawn daily from 23.5, 24, 24.5, 25, or 25.5 °C, plus optional scenario offset.
- Off-hours target = 27 °C. Cooling and optional heating use a common setpoint.
- Numerical time step `dt = 5 / 60 = 1/12` hour.
- Thermal conductance `H = 0.22 kW/K`; effective capacitance `C = 5.0 kWh/K` (passive time constant `C/H ≈ 22.7 hours`).

Timestamp `t` refers to building conditions at **the start of interval [t, t+5 min)**. Energy fields refer to energy spent *during* that interval; `next_indoor_temp_c` refers to the state at the *end* of that interval and is solely an engineering diagnostic or future label.

## 2. Synthetic outside temperature

At local hour `h` and day number `d`:

\[
T_{out,t} = 29+8\cos(2\pi(d-210)/365.2425)
           +4\sin(2\pi(h-9)/24)
           +B_{year}+W_{day}+S_t+HW_{day}+\Delta T_{scenario}.
\]

- `B_year`: reproducibly generated yearly offset, Gaussian standard deviation 0.6 °C.
- `W_day`: seven-day weighted average of seeded Gaussian innovations, creating slowly varying weather.
- `S_t = 0.96*S_(t-1)+Normal(0, 0.035)` °C (five-minute weather variation).
- `HW_day`: three randomly positioned multiday warm-season episodes each year, +2 to +4 °C.
- Cloud factor: once daily random 0.4–1.0, held fixed within each day.

Weather is **not actual recorded Abu Dhabi weather**. Deterministic seeds are keyed to calendar days so the exogenous forcing can be replayed for scenario comparisons.

## 3. Daily occupancy

For each open workday, independently sample attendance for each of 15 possible employees, with attendance probability 0.80. For each attending employee `i`, draw arrival `a_i` near 08:21, departure `l_i` near 17:12, and an optional lunch interval `[b_i, c_i)` near 12:42. Occasional visitors are added, respecting the occupancy cap.

\[
N_t = \min\left(15,\sum_i\mathbf{1}[a_i\leq h<l_i]\,\mathbf{1}[h\notin[b_i,c_i)]+N_{visitors,t}\right).
\]

Approximately 1.8% of otherwise open weekdays are selected as fictitious closure days. All weekends have zero office occupancy. Occupants are **not re-sampled at each five-minute interval**.

## 4. Solar radiation, lighting, plugs, internal heat gains

\[
I_t = 0.45\max(0,\sin(\pi(h-6)/12))\,F_{cloud}\ \mathrm{kW/m^2},
\quad Q_{solar,t} = 12(0.35)I_t.
\]

Lighting schedule (baseline): `L_t=1` from 08:00 to 18:00 on open workdays, otherwise `L_t=0`. Occupancy-responsive **scenario option** turns lights off after 10 minutes of zero occupancy; do not use the responsive policy without explicitly selecting it.

\[
P_{light,t}=0.90L_t,\quad
P_{plug,t}=0.20+0.04N_tF_{plug,day},
\]

with daily plug variation factor `F_plug,day` from 0.85 to 1.15.

\[
Q_{gains,t}=Q_{solar,t}+0.075N_t+0.90P_{light,t}+0.90P_{plug,t}.
\]

Electrical loads (kW) and sensible heat gains (kW thermal) are distinct quantities.

## 5. Controller: cooling plus optional reversible heating

**Reason for extension:** An initial cooling-only winter pilot produced a significant number of temperatures below the declared 23°C comfort proxy. The code therefore enables illustrative reversible heating by default, and has a `--cooling-only` switch to reproduce cooling-only behavior. Confirm the scope with the advisor.

The approximate signed thermal requirement (positive means cooling, negative heating) is:

\[
Q_{req,t}=H(T_{out,t}-T_{set,t})+Q_{gains,t}+K_p(T_{in,t}-T_{set,t}),
\qquad K_p=3.0\ \mathrm{kW/K}.
\]

Normalize by the available capacity (`Q_cool,max=12 kW thermal`, `Q_heat,max=8 kW thermal`):

\[
q_t=\begin{cases}
Q_{req,t}/12,&Q_{req,t}\ge0\\
Q_{req,t}/8,&Q_{req,t}<0\ \text{and heating enabled}\\
0,&Q_{req,t}<0\ \text{and cooling-only}.
\end{cases}
\]

\[
q_{target,t}=\mathrm{clip}(q_t,-1,1),\quad
q_{t}=\mathrm{clip}(q_{target,t},q_{t-1}-0.25,q_{t-1}+0.25).
\]

In cooling-only mode, additionally impose `q_t≥0`. Magnitude `|q_t|` is the fraction of rated cooling/heating capacity. Negative values are *not* negative electrical power: `hvac_mode` records which operating mode is active.

\[
Q_{cool,t}=12\max(q_t,0),\quad Q_{heat,t}=8\max(-q_t,0).
\]

The COP assumptions are:

\[
COP_{cool,t}=\mathrm{clip}(3.5-0.035(T_{out,t}-30),2.5,4.0),\quad
COP_{heat}=3.2.
\]

\[
P_{HVAC,t}=Q_{cool,t}/COP_{cool,t}+Q_{heat,t}/3.2+0.25|q_t|+0.03.
\]

The final 0.03 kW is modeled as powered-standby consumption; with `--disable-hvac` the system produces no heating/cooling but retains 0.03 kW standby draw. The controller is an idealized feedforward-plus-proportional controller, not a commercial unit's actual firmware.

## 6. Thermal balance

\[
T_{in,t+1}=T_{in,t}+\frac{dt}{C}
\left[H(T_{out,t}-T_{in,t})+Q_{gains,t}-Q_{cool,t}+Q_{heat,t}\right].
\]

This is explicit Euler integration at 5-minute resolution. Heating is injected as a thermal gain. **Unmodeled**: latent humidity and dehumidification, ventilation heat transfer, multiple wall temperatures, moisture transport, shading geometry, infiltration variation, explicit lighting illuminance, equipment faults and room-to-room conduction.

## 7. CO₂ — occupancy-related sensor signal

\[
CO2_{t+1}=\max\Big(420,\ CO2_t+dt\big[10^6\,(0.015N_t/360)+ACH_t(420-CO2_t)\big]\Big),
\]

where `ACH = 1.5/hour` with occupants and `0.3/hour` otherwise. In the implemented model, the ventilation rate influences the CO₂ calculation **but not the indoor thermal equation**; this decoupling is a known simplification.

## 8. Electrical power and interval energy

\[
P_{total,t}=P_{HVAC,t}+P_{light,t}+P_{plug,t},\qquad
E_{5min,t}=P_{total,t}/12,\qquad E_{HVAC,t}=P_{HVAC,t}/12.
\]

Values are internally computed using full precision, then rounded only when written to the CSV. Validation allows tight numerical tolerances for rounding.

## 9. Reproducibility, sample splits and disclosure

- Full history: 2022–2025, including Feb 29, 2024, **420,768 rows**.
- One continuous indoor temperature and CO₂ state across the year boundaries.
- Train 2022–2023; validate 2024; test 2025.
- All models evaluated on these data learn to approximate **this synthetic generator**, not necessarily real buildings.
- The controller has direct access to actual simulated heat gains, which is **more information than a real thermostat might have**. Expect near-setpoint thermal regulation and possibly unusually easy prediction; study robustness with more imperfect control, disturbances and calibration before claiming real-world significance.
- Comfort is a project-specific indoor temperature proxy of 23–26°C when occupants are present, **not ASHRAE Standard 55 compliance**.

**Background references for structure (NOT calibration of assumed coefficients):**
- EnergyPlus Engineering Reference: https://energyplus.readthedocs.io/en/latest/guides/engineering-reference/3.6-inside-heat-balance.html
- EnergyPlus Essentials: https://energyplus.readthedocs.io/en/latest/essentials/essentials.html
- ASHRAE Standard 55 overview: https://www.ashrae.org/technical-resources/bookstore/standard-55-thermal-environmental-conditions-for-human-occupancy
