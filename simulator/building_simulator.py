"""SDP smart-building simulator V2: reproducible, one-zone, 5-min synthetic office data.

No third-party dependencies. This is an illustrative single-zone thermal RC model,
NOT a calibrated or validated representation of any real Abu Dhabi building.
Heating is OPTIONAL and enabled by default to avoid cold-weather comfort failures
observed during V2 pilot tests. Use --cooling-only to restore cooling-only scope.

Examples:
    python building_simulator.py                       # 2022-2025 history
    python building_simulator.py --start 2023-07-10 --end 2023-07-18 --output pilot.csv
    python building_simulator.py --start 2023-07-10 --end 2023-07-18 --setpoint-shift-c 1

End date is exclusive. A warm-up simulation precedes the requested dates.
The CSV's measurements at time t represent the start of [t,t+5min), while
energy_kwh is consumption over that 5-minute interval. 'next_indoor_temp_c'
is DIAGNOSTIC ONLY, and must not be used as a contemporaneous ML feature.
"""
from __future__ import annotations
import argparse
import csv
import json
import math
import random
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path


@dataclass(frozen=True)
class Config:
    zone_id: str = "Office_Zone_1"
    floor_area_m2: float = 120.0
    ceiling_height_m: float = 3.0
    max_occupants: int = 15
    step_minutes: int = 5
    thermal_conductance_kw_per_k: float = 0.22
    thermal_capacitance_kwh_per_k: float = 5.0
    max_cooling_kw_thermal: float = 12.0
    max_heating_kw_thermal: float = 8.0  # optional reversible heat-pump mode
    heating_cop: float = 3.2
    thermostat_kp_kw_per_k: float = 3.0
    ramp_limit_fraction: float = 0.25
    occupied_setpoint_choices_c: tuple[float, ...] = (23.5, 24.0, 24.5, 25.0, 25.5)
    unoccupied_setpoint_c: float = 27.0
    preconditioning_hour: float = 6.5
    opening_hour: float = 8.0
    closing_hour: float = 18.0
    lights_power_kw: float = 0.90
    plug_standby_kw: float = 0.20
    plug_per_person_kw: float = 0.04
    occupant_gain_kw_thermal: float = 0.075
    lights_heat_fraction: float = 0.90
    plugs_heat_fraction: float = 0.90
    window_area_m2: float = 12.0
    window_shgc: float = 0.35
    peak_irradiance_kw_per_m2: float = 0.45
    fan_full_load_kw: float = 0.25
    hvac_standby_kw: float = 0.03
    co2_outdoor_ppm: float = 420.0
    co2_generation_m3_per_person_hour: float = 0.015
    ach_occupied_per_hour: float = 1.5
    ach_unoccupied_per_hour: float = 0.3
    occupied_comfort_min_c: float = 23.0
    occupied_comfort_max_c: float = 26.0
    initial_indoor_temp_c: float = 25.0
    warmup_days: int = 7

    def validate(self):
        assert self.step_minutes == 5, "V2 requires a five-minute time step"
        assert self.max_occupants > 0 and self.max_cooling_kw_thermal > 0 and self.max_heating_kw_thermal > 0
        assert self.thermal_capacitance_kwh_per_k > 0
        assert self.thermal_conductance_kw_per_k > 0
        assert 0 < self.ramp_limit_fraction <= 1
        assert self.warmup_days >= 0
        assert 0 <= self.window_shgc <= 1


def clamp(x, minimum, maximum):
    return max(minimum, min(maximum, x))


def seeded_rng(seed: int, day: date, stream: int) -> random.Random:
    """Stable independent randomness per calendar day and module."""
    return random.Random(seed * 1_000_003 + day.toordinal() * 1009 + stream * 10_000_019)


def year_weather_bias(seed: int, year: int) -> float:
    return random.Random(seed * 8191 + year * 2143).gauss(0, 0.6)


def weather_anomaly(seed: int, day: date) -> float:
    """Smooth daily weather deviations from overlapping seeded innovations."""
    weights = [1, 2, 3, 4, 3, 2, 1]
    result = 0.0
    for j, w in enumerate(weights):
        d = day + timedelta(days=j - 3)
        result += w * seeded_rng(seed, d, 11).gauss(0, 1.4)
    return result / sum(weights)


def heatwave_offset(seed: int, day: date) -> float:
    """Seasonal multi-day heatwaves with reproducible locations each year."""
    rr = random.Random(seed * 3091 + day.year * 761)
    episodes = [(rr.randint(140, 260), rr.randint(3, 7), rr.uniform(2, 4))
                for _ in range(3)]
    day_num = (day - date(day.year, 1, 1)).days + 1
    return sum(mag for start, duration, mag in episodes if start <= day_num < start + duration)


def time_hours(ts: datetime) -> float:
    return ts.hour + ts.minute / 60


def workday(day: date) -> bool:
    return day.weekday() < 5


def make_daily_drivers(day: date, seed: int, cfg: Config) -> dict:
    """Occupancy is a schedule of individual people, never an independent redraw."""
    rng = seeded_rng(seed, day, 1)
    cloud = seeded_rng(seed, day, 2).uniform(0.4, 1.0)
    plug_use_factor = seeded_rng(seed, day, 4).uniform(0.85, 1.15)
    setpoint = seeded_rng(seed, day, 5).choice(cfg.occupied_setpoint_choices_c)
    closed = workday(day) and seeded_rng(seed, day, 6).random() < 0.018
    persons = []
    if workday(day) and not closed:
        for _ in range(cfg.max_occupants):
            if rng.random() < 0.80:
                arrival = clamp(rng.gauss(8.35, 0.53), 6.8, 10.2)
                departure = clamp(rng.gauss(17.2, 0.72), 15.1, 19.3)
                lunch = None
                if rng.random() < 0.80:
                    lstart = clamp(rng.gauss(12.7, 0.48), 11.3, 14.2)
                    lunch = (lstart, lstart + rng.uniform(.33, .9))
                persons.append((arrival, departure, lunch))
        # Visitors, if any, are treated like other people and never exceed capacity.
        if rng.random() < 0.33:
            n_visit = rng.choice([1, 1, 2])
            for _ in range(n_visit):
                visit_start = clamp(rng.gauss(13.9, 1.5), 9.0, 16.0)
                persons.append((visit_start, visit_start + rng.uniform(.25, 1.6), None))
    return {"persons": persons, "is_workday": bool(workday(day) and not closed),
            "cloud_factor": cloud, "plug_factor": plug_use_factor,
            "occupied_setpoint": setpoint,
            "weather_drift": weather_anomaly(seed, day),
            "year_bias": year_weather_bias(seed, day.year),
            "heatwave": heatwave_offset(seed, day)}


def count_people(drivers: dict, hour: float, cfg: Config) -> int:
    count = 0
    for arrival, departure, lunch in drivers["persons"]:
        if arrival <= hour < departure and not (lunch is not None and lunch[0] <= hour < lunch[1]):
            count += 1
    return min(cfg.max_occupants, count)


def outdoor_temp(ts: datetime, drivers: dict, weather_noise: float, offset_c: float) -> float:
    d = (ts.date() - date(ts.year, 1, 1)).days + 1
    hour = time_hours(ts)
    return (29.0 + 8.0 * math.cos(2 * math.pi * (d - 210) / 365.2425)
            + 4.0 * math.sin(2 * math.pi * (hour - 9.0) / 24.0)
            + drivers["year_bias"] + drivers["weather_drift"] + drivers["heatwave"]
            + weather_noise + offset_c)


def cooling_cop(t_out: float) -> float:
    return clamp(3.5 - 0.035 * (t_out - 30), 2.5, 4)


COLUMNS = [
    "timestamp", "zone_id", "is_workday", "outdoor_temp_c", "indoor_temp_c",
    "occupancy_count", "co2_ppm", "hvac_setpoint_c", "hvac_level_pct",
    "hvac_cooling_kw_thermal", "hvac_heating_kw_thermal", "hvac_mode",
    "hvac_power_kw", "lights_on", "lighting_power_kw",
    "plug_power_kw", "solar_gain_kw_thermal", "total_power_kw", "energy_kwh",
    "hvac_energy_kwh", "next_indoor_temp_c",
]


def simulate(start: date, end: date, output: Path, seed: int = 42,
             cfg: Config = Config(), setpoint_shift_c: float = 0.0,
             lighting_policy: str = "scheduled", disable_hvac: bool = False,
             allow_heating: bool = True, outdoor_offset_c: float = 0.0,
             scenario_id: str = "historical",
              fixed_cooling_fraction: float | None = None,
             optimize_cooling: bool = False) -> dict:
    """Write [start,end) CSV and return unrounded diagnostic summary."""
    cfg.validate()
    if end <= start:
        raise ValueError("End must be after start (end is exclusive)")
    if abs(setpoint_shift_c) > 3:
        raise ValueError("Setpoint shift must be within +/- 3 deg C")
    if lighting_policy not in ("scheduled", "occupancy"):
        raise ValueError("Lighting policy must be scheduled or occupancy")
    output.parent.mkdir(parents=True, exist_ok=True)
    dt_h = cfg.step_minutes / 60
    ts = datetime.combine(start - timedelta(days=cfg.warmup_days), datetime.min.time())
    stop_ts = datetime.combine(end, datetime.min.time())
    start_ts = datetime.combine(start, datetime.min.time())
    indoor = cfg.initial_indoor_temp_c
    co2 = cfg.co2_outdoor_ppm
    prior_hvac_signed = 0.0
    weather_noise = 0.0
    empty_intervals = 0
    day = None
    inputs = None
    rng = None
    stats = {"rows": 0, "energy_kwh": 0.0, "hvac_energy_kwh": 0.0,
             "occupied_steps": 0, "occupied_violation_steps": 0,
             "occupied_cold_steps": 0, "occupied_hot_steps": 0,
             "occupied_temp_sum": 0.0, "occupied_max_temp_c": -math.inf,
             "occupied_min_temp_c": math.inf, "temp_min_c": math.inf,
             "temp_max_c": -math.inf, "max_hvac_level_pct": 0.0,
             "hvac_at_capacity_steps": 0, "max_electrical_power_balance_error_kw": 0.0,
             "max_interval_energy_balance_error_kwh": 0.0,
             "max_thermal_balance_error_c": 0.0, "nonfinite_steps": 0,
             "outdoor_min_c": math.inf, "outdoor_max_c": -math.inf,
             "monthly": {}}

    with output.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=COLUMNS)
        writer.writeheader()
        while ts < stop_ts:
            d = ts.date()
            if d != day:
                day = d
                inputs = make_daily_drivers(d, seed, cfg)
                rng = seeded_rng(seed, d, 3)
            h = time_hours(ts)
            weather_noise = 0.96 * weather_noise + rng.gauss(0, 0.035)
            tout = outdoor_temp(ts, inputs, weather_noise, outdoor_offset_c)
            people = count_people(inputs, h, cfg)
            is_workday = inputs["is_workday"]
            scheduled_lighting = is_workday and cfg.opening_hour <= h < cfg.closing_hour
            if people == 0:
                empty_intervals += 1
            else:
                empty_intervals = 0
            lights = int(scheduled_lighting if lighting_policy == "scheduled" else
                         scheduled_lighting and (people > 0 or empty_intervals <= 2))
            # The baseline thermostat preconditions from 06:30 on open days.
            occupied_policy = is_workday and cfg.preconditioning_hour <= h < cfg.closing_hour
            setpoint = (inputs["occupied_setpoint"] + setpoint_shift_c
                        if occupied_policy else cfg.unoccupied_setpoint_c)
            solar_irradiance = (cfg.peak_irradiance_kw_per_m2 *
                                max(0.0, math.sin(math.pi * (h - 6) / 12)) *
                                inputs["cloud_factor"])
            solar = cfg.window_area_m2 * cfg.window_shgc * solar_irradiance
            pl = cfg.plug_standby_kw + cfg.plug_per_person_kw * people * inputs["plug_factor"]
            light_p = cfg.lights_power_kw * lights
            gains = (solar + cfg.occupant_gain_kw_thermal * people +
                     cfg.lights_heat_fraction * light_p + cfg.plugs_heat_fraction * pl)
            # Signed heat-balance controller: + is cooling, - is optional heating.
            # An occupied-zone setpoint below the calculated free-floating temp
            # requests cooling; cold conditions can request heat. The thermostat
            # is ramp-limited to avoid instantaneous full-capacity transitions.
            needed_kw = (cfg.thermal_conductance_kw_per_k * (tout - setpoint)
                         + gains + cfg.thermostat_kp_kw_per_k * (indoor - setpoint))
            desired_signed = (needed_kw / cfg.max_cooling_kw_thermal if needed_kw >= 0
                              else needed_kw / cfg.max_heating_kw_thermal if allow_heating else 0.0)
            desired_signed = clamp(desired_signed, -1.0 if allow_heating else 0.0, 1.0)
            # HVAC shutdown applies only to the selected experiment, NOT the
            # preceding warm-up. Ensures baseline and no-HVAC comparison starts
            # from the same simulated thermal state.
            if disable_hvac and ts >= start_ts:
                signed_level = 0.0
            else:
                signed_level = clamp(desired_signed,
                    max(-1.0, prior_hvac_signed - cfg.ramp_limit_fraction),
                    min(1.0, prior_hvac_signed + cfg.ramp_limit_fraction))
                if not allow_heating:
                    signed_level = max(0.0, signed_level)
            if fixed_cooling_fraction is not None and ts >= start_ts:
                if not 0 <= fixed_cooling_fraction <= 1:
                    raise ValueError("Cooling fraction must be between 0 and 1")
                signed_level = fixed_cooling_fraction

            if optimize_cooling and ts >= start_ts and people > 0 and not disable_hvac:
                options = []

                for fraction in [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]:
                    if abs(fraction - prior_hvac_signed) > cfg.ramp_limit_fraction:
                        continue

                    cooling_kw = cfg.max_cooling_kw_thermal * fraction

                    predicted_temp = indoor + dt_h * (
                        cfg.thermal_conductance_kw_per_k * (tout - indoor)
                        + gains - cooling_kw
                    ) / cfg.thermal_capacitance_kwh_per_k

                    violation = max(
                        cfg.occupied_comfort_min_c - predicted_temp,
                        predicted_temp - (cfg.occupied_comfort_max_c - 0.2),
                        0.0
                    )

                    power_kw = (
                        cooling_kw / cooling_cop(tout)
                        + cfg.fan_full_load_kw * fraction
                        + cfg.hvac_standby_kw
                    )

                    options.append((violation, power_kw, fraction))

                if options:
                    signed_level = min(options)[2]

            level = abs(signed_level)
            cooling = cfg.max_cooling_kw_thermal * max(0.0, signed_level)
            heating = cfg.max_heating_kw_thermal * max(0.0, -signed_level)
            hvac_mode = "cooling" if cooling > 0 else "heating" if heating > 0 else "off"
            hvac_power = (cooling / cooling_cop(tout) + heating / cfg.heating_cop
                          + cfg.fan_full_load_kw * level + cfg.hvac_standby_kw)
            total_power = hvac_power + light_p + pl
            energy = total_power * dt_h
            hvac_energy = hvac_power * dt_h
            net_heat = (cfg.thermal_conductance_kw_per_k * (tout - indoor)
                        + gains - cooling + heating)
            next_temp = indoor + dt_h * net_heat / cfg.thermal_capacitance_kwh_per_k
            ach = cfg.ach_occupied_per_hour if people else cfg.ach_unoccupied_per_hour
            source_co2 = 1e6 * cfg.co2_generation_m3_per_person_hour * people / (cfg.floor_area_m2 * cfg.ceiling_height_m)
            next_co2 = max(cfg.co2_outdoor_ppm, co2 + dt_h * (source_co2 + ach * (cfg.co2_outdoor_ppm - co2)))
            if ts >= start_ts:
                writer.writerow({
                    "timestamp": ts.strftime("%Y-%m-%d %H:%M"),
                    "zone_id": cfg.zone_id, "is_workday": int(is_workday),
                    "outdoor_temp_c": f"{tout:.6f}", "indoor_temp_c": f"{indoor:.6f}",
                    "occupancy_count": people, "co2_ppm": f"{co2:.6f}",
                    "hvac_setpoint_c": f"{setpoint:.6f}", "hvac_level_pct": f"{100*level:.6f}",
                    "hvac_cooling_kw_thermal": f"{cooling:.6f}",
                    "hvac_heating_kw_thermal": f"{heating:.6f}", "hvac_mode": hvac_mode,
                    "hvac_power_kw": f"{hvac_power:.6f}", "lights_on": lights,
                    "lighting_power_kw": f"{light_p:.6f}", "plug_power_kw": f"{pl:.6f}",
                    "solar_gain_kw_thermal": f"{solar:.6f}",
                    "total_power_kw": f"{total_power:.6f}",
                    "energy_kwh": f"{energy:.8f}", "hvac_energy_kwh": f"{hvac_energy:.8f}",
                    "next_indoor_temp_c": f"{next_temp:.6f}"})
                stats["rows"] += 1
                stats["energy_kwh"] += energy
                stats["hvac_energy_kwh"] += hvac_energy
                stats["temp_min_c"] = min(stats["temp_min_c"], indoor)
                stats["temp_max_c"] = max(stats["temp_max_c"], indoor)
                stats["outdoor_min_c"] = min(stats["outdoor_min_c"], tout)
                stats["outdoor_max_c"] = max(stats["outdoor_max_c"], tout)
                stats["max_hvac_level_pct"] = max(stats["max_hvac_level_pct"], 100*level)
                stats["hvac_at_capacity_steps"] += (level > .99999)
                stats["max_electrical_power_balance_error_kw"] = max(stats["max_electrical_power_balance_error_kw"], abs(total_power - hvac_power - light_p - pl))
                stats["max_interval_energy_balance_error_kwh"] = max(stats["max_interval_energy_balance_error_kwh"], abs(energy - total_power * dt_h))
                stats["max_thermal_balance_error_c"] = max(stats["max_thermal_balance_error_c"], abs(next_temp - indoor - dt_h * net_heat / cfg.thermal_capacitance_kwh_per_k))
                if not all(map(math.isfinite, (indoor, next_temp, total_power, energy, co2, tout))):
                    stats["nonfinite_steps"] += 1
                if people > 0:
                    stats["occupied_steps"] += 1
                    stats["occupied_temp_sum"] += indoor
                    stats["occupied_max_temp_c"] = max(stats["occupied_max_temp_c"], indoor)
                    stats["occupied_min_temp_c"] = min(stats["occupied_min_temp_c"], indoor)
                    violation = not (cfg.occupied_comfort_min_c <= indoor <= cfg.occupied_comfort_max_c)
                    stats["occupied_violation_steps"] += int(violation)
                    stats["occupied_cold_steps"] += int(indoor < cfg.occupied_comfort_min_c)
                    stats["occupied_hot_steps"] += int(indoor > cfg.occupied_comfort_max_c)
                else:
                    violation = False
                key = ts.strftime("%Y-%m")
                month = stats["monthly"].setdefault(key, {"energy_kwh": 0.0, "hvac_energy_kwh": 0.0,
                    "occupied_steps": 0, "occupied_violations": 0, "min_temp_c": math.inf,
                    "max_temp_c": -math.inf, "hvac_at_capacity_steps": 0})
                month["energy_kwh"] += energy
                month["hvac_energy_kwh"] += hvac_energy
                month["occupied_steps"] += int(people>0)
                month["occupied_violations"] += int(violation)
                month["min_temp_c"] = min(month["min_temp_c"], indoor)
                month["max_temp_c"] = max(month["max_temp_c"], indoor)
                month["hvac_at_capacity_steps"] += int(level > .99999)
            indoor, co2, prior_hvac_signed = next_temp, next_co2, signed_level
            ts += timedelta(minutes=cfg.step_minutes)
    stats["from"] = start.isoformat()
    stats["to_exclusive"] = end.isoformat()
    stats["interval_minutes"] = cfg.step_minutes
    stats["scenario_id"] = scenario_id
    stats["setpoint_shift_c"] = setpoint_shift_c
    stats["lighting_policy"] = lighting_policy
    stats["heating_enabled"] = allow_heating
    stats["outdoor_offset_c"] = outdoor_offset_c
    stats["seed"] = seed
    stats["occupied_comfort_violation_pct"] = 100*stats["occupied_violation_steps"]/max(1,stats["occupied_steps"])
    stats["occupied_mean_temp_c"] = stats["occupied_temp_sum"]/max(1,stats["occupied_steps"])
    for month in stats["monthly"].values():
        month["occupied_violation_pct"] = 100*month["occupied_violations"]/max(1,month["occupied_steps"])
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path,
                        default=Path(__file__).with_name("building_config.json"),
                        help="Optional JSON file containing editable building parameters")
    parser.add_argument("--start", default="2022-01-01", help="First day, inclusive")
    parser.add_argument("--end", default="2026-01-01", help="Last day, exclusive")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "data" / "building_simulation_data.csv")
    parser.add_argument("--summary", type=Path, default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--setpoint-shift-c", type=float, default=0)
    parser.add_argument("--lighting-policy", choices=["scheduled", "occupancy"], default="scheduled")
    parser.add_argument("--disable-hvac", action="store_true")
    parser.add_argument("--cooling-only", action="store_true",
                        help="Disable optional reversible heating; cold weather may violate comfort constraints")
    parser.add_argument("--outdoor-offset-c", type=float, default=0)
    args = parser.parse_args()
    if args.config.exists():
        cfg_data = json.loads(args.config.read_text(encoding="utf-8"))
        cfg = Config(**cfg_data)
    else:
        cfg = Config()
    result = simulate(date.fromisoformat(args.start), date.fromisoformat(args.end),
                      output=args.output, seed=args.seed, cfg=cfg,
                      setpoint_shift_c=args.setpoint_shift_c,
                      lighting_policy=args.lighting_policy,
                      disable_hvac=args.disable_hvac, allow_heating=not args.cooling_only,
                      outdoor_offset_c=args.outdoor_offset_c)
    summary = args.summary or args.output.with_suffix(".summary.json")
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text(json.dumps({"config": asdict(cfg), "results": result}, indent=2, allow_nan=False))
    print(f"CSV saved: {args.output} ({result['rows']:,} rows)")
    print(f"Summary saved: {summary}")
    print(f"Total electricity: {result['energy_kwh']:,.1f} kWh")
    print(f"Occupied comfort violations: {result['occupied_comfort_violation_pct']:.2f}%")
    print(f"Indoor temperature range: {result['temp_min_c']:.2f} .. {result['temp_max_c']:.2f} C")


if __name__ == "__main__":
    main()
