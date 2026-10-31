'use strict';
const $ = id => document.getElementById(id);
const fmt = (value, digits = 1) => value == null || !Number.isFinite(Number(value)) ? '—' : Number(value).toLocaleString('en-US', {minimumFractionDigits: digits, maximumFractionDigits: digits});
const esc = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const state = {page:'overview', meta:null, history:null, metrics:null, forecasts:null, scenario:null, range:null, generation:0};
const colors = {hvac:'#72d7fb', lights:'#b17cf5', plugs:'#13ded3', indoor:'#13e1d3', outdoor:'#b384fa', occupancy:'#12d9d6'};
const pages = {
  overview:['Overview', 'Building performance', 'Explore energy use and indoor conditions across your simulated office.'],
  forecast:['Forecasts', 'A clearer view of what comes next.', 'Run the team’s pretrained model and compare its forecasts with simulated observations.'],
  scenarios:['Scenario lab', 'Explore the energy–comfort trade-off.', 'Test alternative operating policies under matched simulated conditions.'],
  model:['Model & data', 'Know what sits behind the numbers.', 'Inspect data provenance, connected components and the model’s saved evaluation.']
};
async function api(path, options={}) {
  const res = await fetch(path, {...options, signal:AbortSignal.timeout(120000)});
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'Request failed. Check the server terminal.');
  return data;
}
function error(id, message) { $(id).textContent = message || ''; $(id).hidden = !message; }
function busy(id, active, label) { $(id).disabled = active; if (label) $(id).textContent = label; }
function kpi(label, value, unit, note, symbol='◷') {
  return `<article class="kpi"><div class="kpi-top">${esc(label)}<span class="kpi-symbol" aria-hidden="true">${symbol}</span></div><div class="kpi-value">${value}<small>${esc(unit)}</small></div><div class="kpi-foot">${note}</div></article>`;
}
function legend(items) { return items.map(s => `<span><i style="--series:${s.color}"></i>${esc(s.label)}</span>`).join(''); }
function shortTime(t, includeDate=false) { return includeDate ? t.slice(5,10) + ' ' + t.slice(11,16) : t.slice(11,16); }

// Dependency-free SVG plots. Values retain true timestamp spacing and unrounded API data.
function chart(id, points, series, options={}) {
  const host = $(id); if (!host || !points.length || host.closest('[hidden]')) return;
  const W=Math.max(160,host.clientWidth), H=host.clientHeight || 180, left=39, right=12, top=12, bottom=29;
  const plotW=W-left-right, plotH=H-top-bottom;
  const values=points.flatMap(p=>series.map(s=>p[s.key])).filter(v=>v!=null&&Number.isFinite(v));
  if(!values.length){host.innerHTML='<div class="empty-state">No values available.</div>';return;}
  let lo=options.zero?0:Math.min(...values), hi=Math.max(...values);
  if(options.band){lo=Math.min(lo,options.band[0]);hi=Math.max(hi,options.band[1]);}
  if(options.max!=null) hi=Math.max(hi,options.max);
  let pad=(hi-lo)*.12||1; if(!options.zero)lo-=pad;hi+=pad;
  const times=points.map(p=>Date.parse(p.timestamp)), minT=times[0], maxT=times[times.length-1];
  const x=t=>left+(t-minT)/(maxT-minT||1)*plotW, y=v=>top+(hi-v)/(hi-lo)*plotH;
  const tickDigits=Math.max(0,Math.min(4,Math.ceil(-Math.log10((hi-lo)/4))));
  const unit=options.unit||'', sameDay=points[0].timestamp.slice(0,10)===points.at(-1).timestamp.slice(0,10);
  let svg=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(options.label||'Time series chart')}"><title>${esc(options.label||'Time series chart')}</title>`;
  if(options.band) svg+=`<rect x="${left}" y="${y(options.band[1])}" width="${plotW}" height="${y(options.band[0])-y(options.band[1])}" fill="#194c49" opacity=".25"/>`;
  for(let i=0;i<5;i++){const v=lo+(hi-lo)*i/4, yy=y(v);svg+=`<line x1="${left}" y1="${yy}" x2="${W-right}" y2="${yy}" stroke="#364057" stroke-dasharray="2 3"/><text x="${left-8}" y="${yy+3}" text-anchor="end" font-size="10" fill="#a3abc2">${fmt(v,tickDigits)}</text>`;}
  const ticks=W<380?3:5;
  for(let i=0;i<ticks;i++){const idx=Math.round(i*(points.length-1)/(ticks-1)), xx=x(times[idx]);svg+=`<text x="${xx}" y="${H-7}" text-anchor="${i===0?'start':i===ticks-1?'end':'middle'}" font-size="10" fill="#a3abc2">${esc(shortTime(points[idx].timestamp,!sameDay))}</text>`;}
  // Use gradients only for visual encoding; timestamps and numeric values are unchanged.
  svg+=`<defs><linearGradient id="${id}-bar" x1="0" x2="0" y1="0" y2="1"><stop stop-color="#03e1cd"/><stop offset="1" stop-color="#7b58d7"/></linearGradient>`+series.map((s,i)=>`<linearGradient id="${id}-fill-${i}" x1="0" x2="0" y1="0" y2="1"><stop stop-color="${s.color}" stop-opacity=".38"/><stop offset="1" stop-color="${s.color}" stop-opacity=".01"/></linearGradient>`).join('')+'</defs>';
  series.forEach((s,si)=>{
    if(options.bars){
      const barWidth=Math.max(2,plotW/points.length*.58);
      points.forEach((p,i)=>{if(p[s.key]!=null)svg+=`<rect x="${(left+(i+.5)/points.length*plotW-barWidth/2).toFixed(2)}" y="${y(p[s.key]).toFixed(2)}" width="${barWidth.toFixed(2)}" height="${Math.max(0,y(0)-y(p[s.key])).toFixed(2)}" rx="1" fill="url(#${id}-bar)"/>`;});
      return;
    }
    let path='', segment=false;
    points.forEach((p,i)=>{if(p[s.key]==null){segment=false;return;}path+=`${segment?'L':'M'}${x(times[i]).toFixed(2)},${y(p[s.key]).toFixed(2)} `;segment=true;});
    if(options.area&&(si===0||options.multiArea)&&points.every(p=>p[s.key]!=null)) svg+=`<path d="${path}L${x(maxT)},${options.zero?y(0):top+plotH} L${x(minT)},${options.zero?y(0):top+plotH} Z" fill="url(#${id}-fill-${si})"/>`;
    svg+=`<path d="${path}" fill="none" stroke="${s.color}" stroke-width="${s.dashed?1.8:2}" ${s.dashed?'stroke-dasharray="5 4"':''} stroke-linejoin="round" stroke-linecap="round"/>`;
    if(points.length<=8) points.forEach((p,i)=>{if(p[s.key]!=null)svg+=`<circle cx="${x(times[i])}" cy="${y(p[s.key])}" r="3" fill="${s.color}" stroke="#20273f" stroke-width="1.5"/>`;});
  });
  svg+='</svg>';host.innerHTML=svg;
  host.onpointermove=e=>{
    const rect=host.getBoundingClientRect(), fraction=Math.max(0,Math.min(1,(e.clientX-rect.left-left)/plotW));
    const target=minT+fraction*(maxT-minT);let idx=0;for(let i=1;i<times.length;i++)if(Math.abs(times[i]-target)<Math.abs(times[idx]-target))idx=i;
    const p=points[idx];$('chart-tooltip').textContent=p.timestamp.slice(0,16).replace('T',' ')+'\n'+series.map(s=>`${s.label}: ${fmt(p[s.key],unit==='people'?1:2)} ${unit}`).join('\n');
    $('chart-tooltip').hidden=false;$('chart-tooltip').style.left=Math.min(e.clientX+14,window.innerWidth-235)+'px';$('chart-tooltip').style.top=Math.max(8,Math.min(e.clientY+15,window.innerHeight-135))+'px';
  };
  host.onpointerleave=()=>{$('chart-tooltip').hidden=true;};
}

function overview() {
  if(!state.history) return;
  const h=state.history,s=h.summary, hvacShare=s.total_energy_kwh?100*s.hvac_energy_kwh/s.total_energy_kwh:0;
  $('kpis').innerHTML=kpi('Total electricity',fmt(s.total_energy_kwh),'kWh',`${fmt(s.hours,0)} hours · ${s.rows.toLocaleString()} observations`,'ϟ')+
    kpi('HVAC electricity',fmt(s.hvac_energy_kwh),'kWh',`<b>${fmt(hvacShare)}%</b> of total electricity`,'◈')+
    kpi('Occupied comfort',fmt(s.comfort_compliance_pct),'%',s.comfort_compliance_pct==null?'No occupied intervals in this period':`${s.comfort_violation_minutes} minutes outside 23–26°C`,'◉')+
    kpi('Peak occupancy',fmt(s.peak_occupancy,0),'people',`${fmt(s.occupied_hours,1)} occupied hours · capacity 15`,'♧');
  const power=[{key:'hvac_power_kw',label:'HVAC',color:colors.hvac},{key:'lighting_power_kw',label:'Lighting',color:colors.lights},{key:'plug_power_kw',label:'Plug loads',color:colors.plugs}];
  $('power-legend').innerHTML=legend(power);
  chart('power-chart',h.points,power,{zero:true,area:true,unit:'kW',label:'HVAC, lighting and plug electrical power over the selected period'});
  chart('temperature-chart',h.points,[{key:'indoor_temp_c',label:'Indoor',color:colors.indoor},{key:'outdoor_temp_c',label:'Outdoor',color:colors.outdoor}],{band:[23,26],area:true,multiArea:true,unit:'°C',label:'Indoor and outdoor temperatures with the project comfort band'});
  const binSize=Math.max(1,Math.ceil(h.points.length/24));
  const occupancyBins=[];
  for(let i=0;i<h.points.length;i+=binSize){const bin=h.points.slice(i,i+binSize);occupancyBins.push({timestamp:bin[0].timestamp,occupancy_count:bin.reduce((sum,p)=>sum+p.occupancy_count,0)/bin.length});}
  chart('occupancy-chart',occupancyBins,[{key:'occupancy_count',label:'Average occupancy',color:colors.occupancy}],{zero:true,max:15,bars:true,unit:'people',label:'Average simulated occupancy over time'});
  $('chart-resolution').textContent=`${h.chart_interval_minutes}-minute ${h.chart_interval_minutes>5?'averages':'observations'}`;
  $('comfort-note').textContent=`Comfort is evaluated only while occupied. ${s.comfort_violation_minutes} minutes outside the project proxy.`;
  $('occupancy-note').textContent=`${h.chart_interval_minutes*binSize}-minute averages · ${fmt(s.peak_occupancy,0)} peak occupants in original data`;
  const mix=[['HVAC',s.hvac_energy_kwh,colors.hvac],['Lighting',s.lighting_energy_kwh,colors.lights],['Plug loads',s.plug_energy_kwh,colors.plugs]];
  const a=hvacShare,b=a+(s.total_energy_kwh?s.lighting_energy_kwh/s.total_energy_kwh*100:0);
  $('energy-donut').innerHTML=`<div class="donut" role="img" aria-label="Energy breakdown: ${mix.map(m=>`${m[0]} ${fmt(m[1])} kWh`).join(', ')}" style="background:conic-gradient(${colors.hvac} 0% ${a}%, ${colors.lights} ${a}% ${b}%, ${colors.plugs} ${b}% 100%)"><div class="donut-hole"><strong>${fmt(s.total_energy_kwh)}</strong><span>kWh total</span></div></div>`;
  const compliance=s.comfort_compliance_pct;
  $('comfort-donut').innerHTML=`<div class="donut comfort-ring" role="img" aria-label="${compliance==null?'No occupied intervals':fmt(compliance)+' percent of occupied intervals within comfort band'}" style="background:${compliance==null?'#32384e':`conic-gradient(from -75deg,#c235ee 0%,#e32bc7 ${compliance}%,#39415a ${compliance}% 100%)`}"><div class="donut-hole"><span>Occupied comfort</span><strong>${fmt(compliance)}${compliance==null?'':'%'}</strong><span>${s.comfort_violation_minutes} min outside band</span></div></div>`;
  $('energy-breakdown').innerHTML=mix.map(m=>`<div class="breakdown-row"><i style="--series:${m[2]}"></i>${m[0]}<b>${fmt(m[1])} kWh</b><span>${fmt(s.total_energy_kwh?100*m[1]/s.total_energy_kwh:0,0)}%</span></div>`).join('');
  $('insight-text').textContent=`HVAC accounts for ${fmt(hvacShare)}% of electricity in this period. ${s.comfort_compliance_pct==null?'There were no occupied intervals to evaluate comfort.':`${fmt(s.comfort_compliance_pct)}% of occupied intervals are within the 23–26°C proxy.`} Compare a policy change to see whether an energy saving comes with more comfort violations.`;
}
function setPage(page) {
  state.page=page;window.scrollTo({top:0});
  document.querySelectorAll('.page').forEach(el=>el.hidden=el.id!==page||!state.history);
  document.querySelectorAll('[data-page]').forEach(el=>{el.classList.toggle('active',el.dataset.page===page);if(el.dataset.page===page)el.setAttribute('aria-current','page');else el.removeAttribute('aria-current');});
  $('breadcrumb').textContent=pages[page][0];$('page-title').textContent=pages[page][1];$('page-description').textContent=pages[page][2];
  $('chart-tooltip').hidden=true;
  requestAnimationFrame(redraw);
}
function redraw(){if(state.page==='overview')overview();if(state.page==='forecast'&&state.forecasts)renderForecast();if(state.page==='scenarios'&&state.scenario)renderScenario();}
async function loadRange() {
  state.generation++;error('error','');busy('apply',true,'Loading…');$('loading').hidden=false;
  document.querySelectorAll('.page').forEach(el=>el.hidden=true);
  const generation=state.generation;const range={start:$('start').value,end:$('end').value};
  try {
    const result=await api('/api/history?'+new URLSearchParams(range));
    if(generation!==state.generation)return;state.history=result;state.range=range;state.forecasts=null;state.scenario=null;
    $('record-count').textContent=result.summary.rows.toLocaleString()+' records · 5 min';
    $('export').href='/api/export?'+new URLSearchParams(range);$('export').removeAttribute('aria-disabled');
    const preferred=range.start+'T09:00';$('forecast-time').value=preferred;
    $('forecast-time').min=state.meta.first_date+'T00:00';$('forecast-time').max=state.meta.last_date+'T23:55';
    $('forecast-content').innerHTML='<div class="empty-state">Select a timestamp and run the model.</div>';
    $('scenario-results').innerHTML='<article class="panel empty-state tall"><span class="empty-symbol">⇄</span><h2>Every saving has a trade-off.</h2><p>Run a matched comparison to see the energy difference<br>and occupied time outside the comfort proxy.</p><span class="pill">Physics-based simulation · not an optimizer</span></article>';
    error('forecast-error','');error('scenario-error','');setPage(state.page);
  } catch(e) {state.history=null;$('export').setAttribute('aria-disabled','true');error('error',e.message);}
  finally{busy('apply',false,'Apply period');$('loading').hidden=true;}
}
function forecastTable(f,target,unit) {
 return `<div class="table-wrap"><table><thead><tr><th>Horizon</th><th>Predicted · ${unit}</th><th>Actual · ${unit}</th><th>Absolute error</th></tr></thead><tbody>${f.forecasts.map(p=>`<tr><td>+${p.minutes} min</td><td><strong>${fmt(p.predicted[target],target==='occupancy_count'?1:3)}</strong></td><td>${fmt(p.actual?.[target],target==='occupancy_count'?0:3)}</td><td>${p.actual?fmt(Math.abs(p.actual[target]-p.predicted[target]),3):'Unavailable'}</td></tr>`).join('')}</tbody></table></div>`;
}
function renderForecast() {
 const f=state.forecasts;if(!f)return;
 const targets=[['hvac_power_kw','HVAC electrical power','kW',colors.hvac],['indoor_temp_c','Indoor temperature','°C',colors.indoor],['occupancy_count','Occupancy','people',colors.occupancy]];
 $('forecast-content').innerHTML=`<div class="snapshot"><strong>Observation at ${esc(f.timestamp.slice(0,16).replace('T',' '))}</strong><br>${fmt(f.current.hvac_power_kw,3)} kW HVAC · ${fmt(f.current.indoor_temp_c,2)}°C indoors · ${fmt(f.current.occupancy_count,0)} people. Model uses ${f.input_features} past/current features.</div>`+targets.map(([key,title,unit])=>`<div class="forecast-target"><h3>${title}<small>${unit}</small></h3><div class="legend"><span><i style="--series:#72d7fb"></i>Prediction</span><span><i style="--series:#a3afbd"></i>Historical actual</span></div><div id="forecast-${key}" class="chart"></div>${forecastTable(f,key,unit)}</div>`).join('')+`<div class="note">${esc(f.note)} Occupancy outputs are continuous estimates, so fractional people represent a model estimate rather than a measured count.</div>`;
 targets.forEach(([key,title,unit,color])=>{const points=[{timestamp:f.timestamp,predicted:f.current[key],actual:f.current[key]},...f.forecasts.map(p=>({timestamp:p.timestamp,predicted:p.predicted[key],actual:p.actual?.[key]??null}))];chart('forecast-'+key,points,[{key:'predicted',label:'Prediction',color:colors.hvac},{key:'actual',label:'Actual',color:'#a3afbd',dashed:true}],{unit,label:title+' forecast compared with historical actuals'});});
}
function renderScenario() {
 const r=state.scenario;if(!r)return;const b=r.baseline.summary,c=r.candidate.summary;
 const verdict=r.comfort_pass==null?'No occupied intervals':r.comfort_pass?'Inside comfort proxy':'Comfort trade-off';
 $('scenario-results').innerHTML=`<div class="scenario-results-head"><div><span class="eyebrow">${esc(r.start)} THROUGH ${esc(r.end)}</span><h2>Baseline vs candidate</h2></div><button class="button secondary" id="export-scenario">↓ Results CSV</button></div><div class="scenario-kpis">${kpi('Energy difference',fmt(r.energy_saved_kwh),'kWh',r.energy_saved_kwh>=0?`${fmt(r.energy_saved_pct)}% less than baseline`:`${fmt(Math.abs(r.energy_saved_pct))}% more than baseline`)}${kpi('Candidate electricity',fmt(c.total_energy_kwh),'kWh',`Baseline: ${fmt(b.total_energy_kwh)} kWh`)}${kpi('Outside comfort band',fmt(c.comfort_violation_minutes,0),'min',`Baseline: ${b.comfort_violation_minutes} occupied minutes`)}</div><article class="panel scenario-result-panel"><div class="panel-head"><div><span class="eyebrow">PAIRED SIMULATION</span><h2>Total electrical power</h2></div><span class="status ${r.comfort_pass===true?'good':'warn'}">${verdict}</span></div><div class="legend"><span><i style="--series:#9aa9bd"></i>Baseline</span><span><i style="--series:#72d7fb"></i>Candidate</span></div><div id="scenario-power" class="chart"></div></article><article class="panel scenario-result-panel"><div class="panel-head"><h2>Indoor temperature</h2><span class="unit-label">23–26°C comfort proxy</span></div><div id="scenario-temperature" class="chart"></div><div class="note">${r.comfort_pass===false?'The candidate spends occupied time outside the comfort proxy. An energy reduction alone does not make this policy acceptable.':r.comfort_pass===null?'Comfort cannot be assessed because this period contains no occupied intervals.':'The candidate stays inside the occupied comfort proxy for this experiment. This is not evidence of real-building comfort.'}</div></article><article class="panel"><h2>Experiment assumptions</h2><p class="small muted">Setpoint shift: ${r.shift_c>0?'+':''}${fmt(r.shift_c)}°C. Lighting: ${esc(r.lighting_policy)}. ${esc(r.note)}</p><div class="note">This is a user-selected candidate, not an automatically optimized solution. The team’s optimization module is not connected.</div></article>`;
 const points=r.baseline.points.map((p,i)=>({timestamp:p.timestamp,base_power:p.total_power_kw,candidate_power:r.candidate.points[i].total_power_kw,base_temp:p.indoor_temp_c,candidate_temp:r.candidate.points[i].indoor_temp_c}));
 chart('scenario-power',points,[{key:'base_power',label:'Baseline',color:'#9aa9bd',dashed:true},{key:'candidate_power',label:'Candidate',color:colors.hvac}],{zero:true,unit:'kW',label:'Baseline and candidate total electrical power'});
 chart('scenario-temperature',points,[{key:'base_temp',label:'Baseline',color:'#9aa9bd',dashed:true},{key:'candidate_temp',label:'Candidate',color:colors.hvac}],{band:[23,26],unit:'°C',label:'Baseline and candidate indoor temperatures'});
 $('export-scenario').onclick=()=>{
  const rows=[['metric','baseline','candidate','unit'],['total_energy',b.total_energy_kwh,c.total_energy_kwh,'kWh'],['hvac_energy',b.hvac_energy_kwh,c.hvac_energy_kwh,'kWh'],['comfort_violation',b.comfort_violation_minutes,c.comfort_violation_minutes,'occupied minutes'],['occupied_hours',b.occupied_hours,c.occupied_hours,'hours'],['setpoint_shift',0,r.shift_c,'deg C'],['lighting_policy','scheduled',r.lighting_policy,'policy'],['start',r.start,r.start,'inclusive'],['end',r.end,r.end,'inclusive'],['seed',42,42,''],['source','Simulator V2','Simulator V2','synthetic'],['warmup','7 days baseline policy','7 days candidate policy','separate warmups']];
  download(rows.map(row=>row.join(',')).join('\r\n'),'scenario-comparison.csv','text/csv');
 };
}
function download(text,filename,type){const url=URL.createObjectURL(new Blob([text],{type}));const a=document.createElement('a');a.href=url;a.download=filename;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function metrics() {
 if(!state.metrics)return;const target=$('metric-target').value;
 $('metrics-table').innerHTML=`<table><thead><tr><th>Horizon</th><th>Model MAE</th><th>No-change MAE</th><th>Model RMSE</th><th>No-change RMSE</th><th>Test samples</th></tr></thead><tbody>${state.metrics.test_metrics.filter(m=>m.target===target).map(m=>`<tr><td>+${m.horizon_minutes} min</td><td><strong>${fmt(m.mae_model,4)}</strong></td><td>${fmt(m.mae_no_change,4)}</td><td>${fmt(m.rmse_model,4)}</td><td>${fmt(m.rmse_no_change,4)}</td><td>${m.n.toLocaleString()}</td></tr>`).join('')}</tbody></table>`;
}
async function init() {
 $('export').setAttribute('aria-disabled','true');
 try {
  const [meta,report]=await Promise.all([api('/api/meta'),api('/api/metrics')]);state.meta=meta;state.metrics=report;
  ['start','end'].forEach(id=>{$(id).min=meta.first_date;$(id).max=meta.last_date;$(id).value=meta.default_date;});
  const facts=[['Source','Simulator V2 · synthetic'],['Zone',meta.zone],['History',`${meta.first_date} to ${meta.last_date}`],['Rows',meta.rows.toLocaleString()],['Interval','5 minutes'],['Dataset',meta.filename],['Time basis','Simulator local clock'],['Comfort proxy','23–26°C while occupied'],['Evaluation source','ml/results/test_report.json']];
  $('provenance').innerHTML=facts.map(([k,v])=>`<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('');
  $('model-status').textContent=meta.model_present?'Checkpoint found':'Checkpoint missing';metrics();await loadRange();
 } catch(e){error('error',e.message);$('loading').hidden=true;document.querySelectorAll('.page').forEach(el=>el.hidden=true);}
}
document.querySelectorAll('[data-page]').forEach(el=>el.onclick=()=>setPage(el.dataset.page));
document.querySelectorAll('[data-open]').forEach(el=>el.onclick=()=>{setPage(el.dataset.open);window.scrollTo({top:0,behavior:'smooth'});});
$('range-form').onsubmit=e=>{e.preventDefault();loadRange();};
$('export').onclick=e=>{if(!state.history||$('export').hasAttribute('aria-disabled'))e.preventDefault();};
$('forecast-form').onsubmit=async e=>{e.preventDefault();const generation=state.generation;error('forecast-error','');state.forecasts=null;$('forecast-content').innerHTML='<div class="empty-state">Running the pretrained model…</div>';busy('predict',true,'Predicting…');try{const forecastResult=await api('/api/forecast?'+new URLSearchParams({timestamp:$('forecast-time').value}));if(generation!==state.generation)return;state.forecasts=forecastResult;renderForecast();$('model-status').textContent='Inference verified';$('model-status').classList.add('good');}catch(err){$('forecast-content').innerHTML='';error('forecast-error',err.message);}finally{busy('predict',false,'Run forecast ↗');}};
$('scenario-form').onsubmit=async e=>{e.preventDefault();if(!state.range)return;if($('start').value!==state.range.start||$('end').value!==state.range.end){error('scenario-error','Apply the changed analysis period before running a scenario.');return;}const generation=state.generation;error('scenario-error','');state.scenario=null;busy('run-scenario',true,'Simulating both policies…');$('shift').disabled=true;$('lighting').disabled=true;$('scenario-results').innerHTML='<article class="panel empty-state tall">Running baseline and candidate with matched conditions…</article>';try{const scenarioResult=await api('/api/scenario',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...state.range,shift:Number($('shift').value),lighting:$('lighting').value})});if(generation!==state.generation)return;state.scenario=scenarioResult;renderScenario();}catch(err){$('scenario-results').innerHTML='';error('scenario-error',err.message);}finally{busy('run-scenario',false,'Run comparison ↗');$('shift').disabled=false;$('lighting').disabled=false;}};
$('shift').oninput=()=>{const v=Number($('shift').value);$('shift-value').textContent=(v>0?'+':'')+fmt(v)+'°C';};
for(const id of ['shift','lighting'])$(id).addEventListener('change',()=>{if(state.scenario){state.scenario=null;$('scenario-results').innerHTML='<article class="panel empty-state tall">Settings changed. Run comparison to update results.</article>';}});
for(const id of ['start','end'])$(id).addEventListener('change',()=>{if(state.range&&($(id).value!==state.range[id]))$('record-count').textContent='Dates changed · apply period';});
$('metric-target').onchange=metrics;
let resizeTimer;window.addEventListener('resize',()=>{clearTimeout(resizeTimer);resizeTimer=setTimeout(redraw,150);});
init();

// Recalculate SVG label layout after the bundled font finishes loading.
document.fonts.ready.then(redraw);
