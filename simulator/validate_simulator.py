"""Repeatable QA tests for SDP simulator V2; stdlib only.

Run: python validate_simulator.py --csv building_simulation_data.csv
or:  python validate_simulator.py                 # pilots only

This verifies internal consistency, NOT scientific external validation.
"""
import argparse
import csv
import json
import math
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from building_simulator import Config, simulate


def as_rows(path: Path):
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def number(row, key):
    return float(row[key])


def data_checks(rows, cfg: Config, name: str, expected_count=None):
    assert rows, name + ': empty file'
    if expected_count is not None:
        assert len(rows) == expected_count, (name, len(rows), expected_count)
    last_dt, last_tnext, last_hvac_signed = None, None, None
    occupied_weekends = 0
    largest_balance_kw, largest_energy_kwh, largest_thermal_mismatch = 0, 0, 0
    count_heating, count_cooling = 0, 0
    for r in rows:
        ts = datetime.strptime(r['timestamp'], '%Y-%m-%d %H:%M')
        if last_dt is not None:
            assert ts - last_dt == timedelta(minutes=5), (name,'timestamp discontinuity', ts)
            largest_thermal_mismatch = max(largest_thermal_mismatch, abs(number(r,'indoor_temp_c')-last_tnext))
            assert abs(number(r,'indoor_temp_c') - last_tnext) < 0.0000021
        n = int(r['occupancy_count'])
        assert 0 <= n <= cfg.max_occupants
        if ts.weekday() >= 5 and n > 0:
            occupied_weekends += 1
        mode=r['hvac_mode']
        assert mode in ('cooling','heating','off')
        u = number(r, 'hvac_level_pct')
        cool=number(r,'hvac_cooling_kw_thermal')
        heat=number(r,'hvac_heating_kw_thermal')
        assert -1e-6 <= u <= 100+1e-6
        assert cool >= -1e-6 and cool <= cfg.max_cooling_kw_thermal + 1e-6
        assert heat >= -1e-6 and heat <= cfg.max_heating_kw_thermal + 1e-6
        assert cool<1e-6 or heat<1e-6
        assert (mode=='cooling') == (cool>1e-6)
        assert (mode=='heating') == (heat>1e-6)
        signed_u=u/100*(1 if mode=='cooling' else -1 if mode=='heating' else 0)
        if last_hvac_signed is not None:
            assert abs(signed_u-last_hvac_signed)<=cfg.ramp_limit_fraction+2e-6, (name, 'ramp',ts)
        count_heating += (mode=='heating')
        count_cooling += (mode=='cooling')
        tot = number(r,'total_power_kw')
        component_sum = sum(number(r,k) for k in ('hvac_power_kw','lighting_power_kw','plug_power_kw'))
        largest_balance_kw=max(largest_balance_kw,abs(tot-component_sum))
        largest_energy_kwh=max(largest_energy_kwh,abs(number(r,'energy_kwh')-tot/12))
        assert abs(tot-component_sum)<0.000003
        assert abs(number(r,'energy_kwh')-tot/12)<0.00000011
        assert math.isfinite(number(r,'indoor_temp_c')) and math.isfinite(tot)
        assert number(r,'co2_ppm') >= cfg.co2_outdoor_ppm-1e-6
        last_dt, last_tnext, last_hvac_signed=ts,number(r,'next_indoor_temp_c'),signed_u
    assert not occupied_weekends, (name, 'occupied on weekend', occupied_weekends)
    return {'rows':len(rows), 'first_timestamp':rows[0]['timestamp'],
        'last_timestamp':rows[-1]['timestamp'], 'weekend_occupied_steps':occupied_weekends,
        'heating_steps':count_heating, 'cooling_steps':count_cooling,
        'max_power_identity_error_kw':largest_balance_kw,
        'max_energy_identity_error_kwh':largest_energy_kwh,
        'max_next_temp_continuity_error_c':largest_thermal_mismatch}


def pilot_checks(cfg:Config, folder:Path):
    results={}
    with tempfile.TemporaryDirectory() as tempdir:
        temp=Path(tempdir)
        summer_a=temp/'summer.csv';summer_b=temp/'summer_shift.csv';heatwave=temp/'heatwave.csv'
        winter=temp/'winter.csv';no_hvac=temp/'no_hvac.csv';cooling_only=temp/'cooling_only.csv'
        start=date(2023,7,10);end=date(2023,7,18)
        base=simulate(start,end,summer_a,cfg=cfg)
        plus=simulate(start,end,summer_b,cfg=cfg,setpoint_shift_c=1)
        hot=simulate(start,end,heatwave,cfg=cfg,outdoor_offset_c=4)
        cold=simulate(date(2023,1,2),date(2023,1,10),winter,cfg=cfg)
        cold_noheat=simulate(date(2023,1,2),date(2023,1,10),cooling_only,cfg=cfg,allow_heating=False)
        no=simulate(date(2023,7,10),date(2023,7,11),no_hvac,cfg=cfg,disable_hvac=True)
        a=as_rows(summer_a);b=as_rows(summer_b);h=as_rows(heatwave)
        results['summer']=data_checks(a,cfg,'summer',8*288)
        results['winter']=data_checks(as_rows(winter),cfg,'winter',8*288)
        data_checks(b,cfg,'summer_shift',8*288)
        data_checks(h,cfg,'heatwave',8*288)
        # --disable-hvac turns HVAC off at experiment boundary; special ramp exception.
        assert no['temp_max_c'] > base['temp_max_c']+7
        assert base['energy_kwh'] > plus['energy_kwh']
        assert hot['energy_kwh'] > base['energy_kwh']
        assert cold['occupied_cold_steps'] < cold_noheat['occupied_cold_steps']
        for r1,r2 in zip(a,b):
            for col in ('outdoor_temp_c','occupancy_count','solar_gain_kw_thermal','plug_power_kw'):
                assert r1[col] == r2[col], ('scenario independent drivers changed',col)
        # Under paired heatwave only the outdoor temperature changes as commanded.
        for r1,r2 in zip(a,h):
            assert abs(number(r2,'outdoor_temp_c')-number(r1,'outdoor_temp_c')-4)<0.000002
            assert r1['occupancy_count']==r2['occupancy_count']
        results['paired_scenario'] = {'base_energy_kwh':base['energy_kwh'],
          'setpoint_plus1_energy_kwh':plus['energy_kwh'],
          'setpoint_plus1_energy_saved_pct':100*(base['energy_kwh']-plus['energy_kwh'])/base['energy_kwh'],
          'base_comfort_violation_pct':base['occupied_comfort_violation_pct'],
          'setpoint_plus1_comfort_violation_pct':plus['occupied_comfort_violation_pct']}
        results['heating_check']={'winter_with_heating_cold_intervals':cold['occupied_cold_steps'],
          'winter_cooling_only_cold_intervals':cold_noheat['occupied_cold_steps']}
        results['no_hvac_check']={'no_hvac_max_indoor_c':no['temp_max_c'],
          'summer_baseline_max_indoor_c':base['temp_max_c']}
        results['heatwave_check']={'baseline_energy_kwh':base['energy_kwh'],
          'heatwave_energy_kwh':hot['energy_kwh']}
    return results


def full_checks(path:Path,cfg:Config):
    expected=(date(2026,1,1)-date(2022,1,1)).days*288
    yearly={}
    last_dt, prior_next, previous_signed=None,None,None
    max_power_err,max_energy_err,max_temp_err=0,0,0
    total=0
    with path.open(newline='',encoding='utf8') as f:
        for row in csv.DictReader(f):
            total+=1
            t=datetime.strptime(row['timestamp'],'%Y-%m-%d %H:%M')
            if last_dt:
                assert t-last_dt==timedelta(minutes=5), ('time gap', t)
                max_temp_err=max(max_temp_err,abs(float(row['indoor_temp_c'])-prior_next))
                assert abs(float(row['indoor_temp_c'])-prior_next) <0.0000021
            if not last_dt: assert t==datetime(2022,1,1)
            assert int(row['occupancy_count'])<=cfg.max_occupants
            assert not (t.weekday()>=5 and int(row['occupancy_count'])>0)
            y=yearly.setdefault(str(t.year),{'rows':0,'energy_kwh':0,'hvac_energy_kwh':0,
                       'occupied_steps':0,'violations':0,'outdoor_sum':0,'max_occupancy':0})
            y['rows']+=1
            y['energy_kwh']+=float(row['energy_kwh'])
            y['hvac_energy_kwh']+=float(row['hvac_energy_kwh'])
            y['outdoor_sum']+=float(row['outdoor_temp_c'])
            people=int(row['occupancy_count'])
            y['max_occupancy']=max(y['max_occupancy'],people)
            if people:
                y['occupied_steps']+=1
                y['violations']+=int(not 23<=float(row['indoor_temp_c'])<=26)
            mode=row['hvac_mode']; u=float(row['hvac_level_pct']); cool=float(row['hvac_cooling_kw_thermal']); heat=float(row['hvac_heating_kw_thermal'])
            assert mode in ('cooling','heating','off') and 0<=u<=100.00001
            assert 0<=cool<=cfg.max_cooling_kw_thermal +1e-6
            assert 0<=heat<=cfg.max_heating_kw_thermal+1e-6
            assert not (cool>0 and heat>0)
            signed=u/100*(1 if mode=='cooling' else -1 if mode=='heating' else 0)
            if previous_signed is not None:
                assert abs(signed-previous_signed)<cfg.ramp_limit_fraction+0.000002
            power_components=sum(float(row[k]) for k in ('hvac_power_kw','lighting_power_kw','plug_power_kw'))
            max_power_err=max(max_power_err,abs(float(row['total_power_kw'])-power_components))
            max_energy_err=max(max_energy_err,abs(float(row['energy_kwh'])-float(row['total_power_kw'])/12))
            assert max_power_err <0.000003 and max_energy_err <1.1e-7
            prior_next=float(row['next_indoor_temp_c']); last_dt=t; previous_signed=signed
    assert total==expected
    assert last_dt==datetime(2025,12,31,23,55)
    assert yearly['2024']['rows']==105408
    assert len(yearly)==4
    year_weather=[]
    for y,vals in yearly.items():
        vals['mean_outdoor_temp_c']=vals.pop('outdoor_sum')/vals['rows']
        vals['comfort_violation_pct']=100*vals['violations']/max(1,vals['occupied_steps'])
        year_weather.append(round(vals['mean_outdoor_temp_c'],4))
    assert len(set(year_weather))==4, 'No interannual weather differences'
    return {'rows':total,'start':'2022-01-01 00:00','end':'2025-12-31 23:55',
           'leap_day_present':True,'yearly':yearly,'max_power_balance_error_kw':max_power_err,
           'max_energy_balance_error_kwh':max_energy_err,'max_temp_continuity_error_c':max_temp_err}


def main():
    args=argparse.ArgumentParser()
    args.add_argument('--csv',type=Path)
    args.add_argument('--config',type=Path,default=Path(__file__).with_name('building_config.json'))
    args.add_argument('--report',type=Path,default=Path('validation_results.json'))
    args=args.parse_args()
    cfg=Config(**json.loads(args.config.read_text())) if args.config.exists() else Config()
    results={'pilot_tests':pilot_checks(cfg,Path('.'))}
    if args.csv: results['full_dataset']=full_checks(args.csv,cfg)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(results,indent=2)+'\n')
    print('PASS: pilot consistency, seasonal HVAC, paired scenarios, heatwave, no-HVAC')
    if args.csv: print(f"PASS: full dataset, {results['full_dataset']['rows']:,} rows, leap year, time grid, balance identities")
    print('Report:',args.report)

if __name__=='__main__': main()
