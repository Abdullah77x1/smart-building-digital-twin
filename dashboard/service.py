"""Read-only history/ML adapter and isolated matched simulator experiments."""
from __future__ import annotations

import io
import json
import math
import sys
import tempfile
import threading
from dataclasses import asdict
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ml'))
sys.path.insert(0, str(ROOT))
from simulator.building_simulator import Config, simulate
from prepare_data import HORIZONS, OBSERVED, TARGETS, make_features

NUMERIC = list(dict.fromkeys([*OBSERVED, 'total_power_kw', 'energy_kwh', 'hvac_energy_kwh']))
PLOT_COLUMNS = ['hvac_power_kw', 'total_power_kw', 'lighting_power_kw', 'plug_power_kw',
                'indoor_temp_c', 'outdoor_temp_c', 'hvac_setpoint_c', 'occupancy_count', 'co2_ppm']


class ModelUnavailable(RuntimeError):
    pass


def parse_day(value):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError('Use a valid date in YYYY-MM-DD format.') from None


def records(frame):
    return json.loads(frame.to_json(orient='records', date_format='iso'))


def summary(frame, cfg):
    occupied = frame['occupancy_count'] > 0
    violation = occupied & ~frame['indoor_temp_c'].between(cfg.occupied_comfort_min_c, cfg.occupied_comfort_max_c)
    count = int(occupied.sum())
    return {
        'rows': len(frame), 'hours': len(frame) * cfg.step_minutes / 60,
        'total_energy_kwh': float(frame.energy_kwh.sum()),
        'hvac_energy_kwh': float(frame.hvac_energy_kwh.sum()),
        'lighting_energy_kwh': float(frame.lighting_power_kw.sum() * cfg.step_minutes / 60),
        'plug_energy_kwh': float(frame.plug_power_kw.sum() * cfg.step_minutes / 60),
        'peak_power_kw': float(frame.total_power_kw.max()),
        'peak_occupancy': int(frame.occupancy_count.max()),
        'occupied_hours': count * cfg.step_minutes / 60,
        'comfort_violation_minutes': int(violation.sum()) * cfg.step_minutes,
        'comfort_compliance_pct': (100 * (1 - int(violation.sum()) / count)) if count else None,
        'occupied_mean_temp_c': float(frame.loc[occupied, 'indoor_temp_c'].mean()) if count else None,
        'min_temp_c': float(frame.indoor_temp_c.min()), 'max_temp_c': float(frame.indoor_temp_c.max()),
    }


def chart_data(frame):
    # Aggregate chart values only. KPIs and CSV downloads always use original five-minute rows.
    minutes = max(5, math.ceil(len(frame) / 650) * 5)
    plot = frame.set_index('timestamp')[PLOT_COLUMNS].resample(f'{minutes}min', origin='start_day').mean().dropna(how='all').reset_index()
    return records(plot), minutes


class DashboardService:
    def __init__(self, csv_path=None, model_path=None):
        self.csv_path = Path(csv_path or ROOT / 'data/building_simulation_data.csv')
        self.model_path = Path(model_path or ROOT / 'ml/results/multitask_model.pt')
        self.cfg = Config(**json.loads((ROOT / 'simulator/building_config.json').read_text()))
        self._frame = None
        self._model = None
        self._lock = threading.RLock()

    def frame(self):
        with self._lock:
            if self._frame is None:
                if not self.csv_path.is_file():
                    raise FileNotFoundError('History is missing. Run: python simulator/building_simulator.py, then restart the dashboard.')
                frame = pd.read_csv(self.csv_path)
                missing = set(['timestamp', 'zone_id', *NUMERIC]) - set(frame.columns)
                if missing:
                    raise ValueError('CSV is missing columns: ' + ', '.join(sorted(missing)))
                frame['timestamp'] = pd.to_datetime(frame.timestamp, errors='raise')
                if frame.empty or frame.timestamp.isna().any():
                    raise ValueError('CSV has no usable timestamps.')
                if frame.timestamp.dt.tz is not None:
                    raise ValueError('Use the simulator local timestamps without a timezone offset.')
                if frame.zone_id.nunique() != 1 or frame.zone_id.iloc[0] != self.cfg.zone_id:
                    raise ValueError('This version supports the configured single zone only.')
                frame = frame.sort_values('timestamp').reset_index(drop=True)
                if not frame.timestamp.diff().dropna().eq(pd.Timedelta(minutes=5)).all():
                    raise ValueError('History must have unique, consecutive five-minute timestamps. Do not fill gaps silently.')
                for col in NUMERIC:
                    frame[col] = pd.to_numeric(frame[col], errors='raise')
                if not np.isfinite(frame[NUMERIC].to_numpy()).all():
                    raise ValueError('History contains missing or non-finite measurements.')
                if (frame[['hvac_power_kw', 'lighting_power_kw', 'plug_power_kw', 'energy_kwh', 'hvac_energy_kwh', 'occupancy_count']] < 0).any().any():
                    raise ValueError('Power, energy and occupancy must be nonnegative.')
                if not np.allclose(frame.total_power_kw, frame.hvac_power_kw + frame.lighting_power_kw + frame.plug_power_kw, atol=3e-6, rtol=0):
                    raise ValueError('Total power does not match HVAC + lighting + plugs.')
                if not np.allclose(frame.energy_kwh, frame.total_power_kw / 12, atol=1e-6, rtol=0) or not np.allclose(frame.hvac_energy_kwh, frame.hvac_power_kw / 12, atol=1e-6, rtol=0):
                    raise ValueError('Interval energy does not match five-minute power integration.')
                self._frame = frame
            return self._frame

    def select(self, start, end):
        first, last = parse_day(start), parse_day(end)
        if last < first:
            raise ValueError('End date must be on or after start date.')
        if (last - first).days >= 366:
            raise ValueError('Select no more than 366 days at once.')
        frame = self.frame()
        if first < frame.timestamp.iloc[0].date() or last > frame.timestamp.iloc[-1].date():
            raise ValueError('Selected dates are outside the loaded history.')
        selected = frame.loc[(frame.timestamp >= pd.Timestamp(first)) & (frame.timestamp < pd.Timestamp(last + timedelta(days=1)))]
        if selected.empty:
            raise ValueError('No data for the selected dates.')
        return selected

    def metadata(self):
        frame = self.frame()
        return {'zone': self.cfg.zone_id, 'config': asdict(self.cfg), 'source': 'Simulator V2 · synthetic data',
                'filename': self.csv_path.name, 'rows': len(frame), 'first_date': str(frame.timestamp.iloc[0].date()),
                'last_date': str(frame.timestamp.iloc[-1].date()), 'interval_minutes': 5,
                'default_date': '2025-07-15' if frame.timestamp.iloc[0] <= pd.Timestamp('2025-07-15') <= frame.timestamp.iloc[-1] else str(frame.timestamp.iloc[0].date()),
                'model_present': self.model_path.is_file(), 'llm_connected': False,
                'optimization_connected': False, 'time_basis': 'Simulator local clock; no timezone conversion'}

    def history(self, start, end):
        selected = self.select(start, end)
        points, interval = chart_data(selected)
        return {'summary': summary(selected, self.cfg), 'points': points, 'chart_interval_minutes': interval,
                'start': start, 'end': end, 'first': records(selected.head(1))[0], 'last': records(selected.tail(1))[0]}

    def export(self, start, end):
        return self.select(start, end).to_csv(index=False)

    def forecast(self, timestamp):
        try:
            ts = pd.Timestamp(timestamp)
            if pd.isna(ts) or ts.tzinfo is not None:
                raise ValueError()
        except Exception:
            raise ValueError('Select a valid simulator timestamp without a timezone offset.') from None
        frame = self.frame()
        # Deliberately pass only observations through t to feature construction.
        history = frame.loc[(frame.timestamp >= ts - pd.Timedelta(minutes=60)) & (frame.timestamp <= ts)]
        features_frame, features = make_features(history)
        row = features_frame.loc[features_frame.timestamp.eq(ts)]
        if len(row) != 1:
            raise ValueError('Choose a timestamp present in the five-minute history.')
        if row[features].isna().any().any():
            raise ValueError('Forecast requires 60 minutes of preceding history within the same calendar year.')
        with self._lock:
            try:
                from model import load_checkpoint, predict
                if self._model is None:
                    self._model = load_checkpoint(self.model_path)
                model, ckpt = self._model
                if ckpt['features'] != features:
                    raise ValueError('Model feature order differs from the current data adapter.')
                pred = predict(model, ckpt, row[features].to_numpy(np.float32))[0]
            except (ImportError, FileNotFoundError) as exc:
                raise ModelUnavailable('Forecast unavailable. Install requirements.txt and confirm ml/results/multitask_model.pt exists.') from exc
        if not np.isfinite(pred).all():
            raise ModelUnavailable('The model returned non-finite values; no forecast is shown.')
        result = []
        for i, step in enumerate(HORIZONS):
            future_ts = ts + pd.Timedelta(minutes=step * 5)
            actual = frame.loc[frame.timestamp.eq(future_ts)]
            result.append({'minutes': step * 5, 'timestamp': future_ts.isoformat(),
                           'predicted': {target: float(pred[j * 4 + i]) for j, target in enumerate(TARGETS)},
                           'actual': {target: float(actual.iloc[0][target]) for target in TARGETS} if len(actual) else None})
        current = frame.loc[frame.timestamp.eq(ts)]
        return {'timestamp': ts.isoformat(), 'current': records(current)[0], 'forecasts': result,
                'model': 'Multi-task neural network V1', 'input_features': len(features),
                'note': 'Predicts continuation of the baseline policy. Actuals are historical simulator values revealed for comparison, never model inputs.'}

    def metrics(self):
        report = json.loads((ROOT / 'ml/results/test_report.json').read_text())
        return {**report, 'source_file': 'ml/results/test_report.json', 'training_years': '2022–2023', 'validation_year': 2024}

    def scenario(self, start, end, shift=1.0, lighting='occupancy'):
        first, last = parse_day(start), parse_day(end)
        if not date(2022, 1, 1) <= first <= last <= date(2025, 12, 31):
            raise ValueError('Scenario dates must be within 2022–2025, with end on or after start.')
        if (last - first).days >= 31:
            raise ValueError('Scenario experiments are limited to 31 days.')
        try:
            shift = float(shift)
        except (TypeError, ValueError):
            raise ValueError('Setpoint shift must be a number.') from None
        if not math.isfinite(shift) or not -3 <= shift <= 3:
            raise ValueError('Setpoint shift must be between -3 and +3°C.')
        if lighting not in ('scheduled', 'occupancy'):
            raise ValueError('Choose scheduled or occupancy lighting.')
        return self._scenario_cached(str(first), str(last), shift, lighting)

    @lru_cache(maxsize=12)
    def _scenario_cached(self, start, end, shift, lighting):
        first, stop = parse_day(start), parse_day(end) + timedelta(days=1)
        result = {'start': start, 'end': end, 'shift_c': shift, 'lighting_policy': lighting, 'seed': 42}
        with tempfile.TemporaryDirectory(prefix='sdp-scenario-') as tmp:
            for label, adjustment, policy in [('baseline', 0.0, 'scheduled'), ('candidate', shift, lighting)]:
                path = Path(tmp) / (label + '.csv')
                simulate(first, stop, path, cfg=self.cfg, seed=42, setpoint_shift_c=adjustment, lighting_policy=policy)
                frame = pd.read_csv(path, parse_dates=['timestamp'])
                points, interval = chart_data(frame)
                result[label] = {'summary': summary(frame, self.cfg), 'points': points, 'chart_interval_minutes': interval}
        base, candidate = result['baseline']['summary'], result['candidate']['summary']
        result['energy_saved_kwh'] = base['total_energy_kwh'] - candidate['total_energy_kwh']
        result['energy_saved_pct'] = 100 * result['energy_saved_kwh'] / base['total_energy_kwh'] if base['total_energy_kwh'] else None
        result['comfort_pass'] = candidate['comfort_violation_minutes'] == 0 if candidate['occupied_hours'] else None
        result['note'] = ('Paired Simulator V2 runs with seed 42 and the same weather/occupancy drivers. '
                          'Each policy also applies during its own seven-day warm-up, so initial indoor temperatures can differ. '
                          'This is a steady-policy experiment, not a switch at the selected history timestamp. '
                          'The 23–26°C band is a project comfort proxy. Savings apply only to this uncalibrated simulator.')
        return result
