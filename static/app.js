const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const state = {
  spot: document.querySelector('.spot-chip')?.dataset.spot || 'silvaplana',
  controller: null,
  historyController: null,
  historyData: null,
  historyView: 'month',
  historyDate: new Date(),
  measurementController: null,
  measurementData: null,
  measurementDay: null,
  liveData: null,
  forecastView: 'day',
  spotStats: {},
};

function text(selector, value) { $(selector).textContent = value ?? '–'; }
function value(value, suffix = '') { return Number.isFinite(value) ? `${value}${suffix}` : '–'; }
function dateTime(raw, timeZone = null) {
  if (!raw) return 'Unbekannt';
  const parsed = new Date(raw);
  if (Number.isNaN(parsed.getTime())) return raw;
  try { return new Intl.DateTimeFormat('de-CH', { dateStyle: 'short', timeStyle: 'short', ...(timeZone ? { timeZone } : {}) }).format(parsed); }
  catch (_) { return new Intl.DateTimeFormat('de-CH', { dateStyle: 'short', timeStyle: 'short' }).format(parsed); }
}
function timeLabel(raw, timeZone = null) {
  const parsed = new Date(raw);
  if (Number.isNaN(parsed.getTime())) return '–';
  try { return new Intl.DateTimeFormat('de-CH', { hour: '2-digit', minute: '2-digit', ...(timeZone ? { timeZone } : {}) }).format(parsed); }
  catch (_) { return new Intl.DateTimeFormat('de-CH', { hour: '2-digit', minute: '2-digit' }).format(parsed); }
}
function isoWithOffset(raw, offsetSeconds = 0) {
  if (!raw || /(?:Z|[+-]\d\d:\d\d)$/.test(raw)) return raw;
  const sign = offsetSeconds >= 0 ? '+' : '-';
  const absolute = Math.abs(offsetSeconds);
  const hours = String(Math.floor(absolute / 3600)).padStart(2, '0');
  const minutes = String(Math.floor((absolute % 3600) / 60)).padStart(2, '0');
  return `${raw}${sign}${hours}:${minutes}`;
}
function cacheLabel(source) {
  if (!source.available) return 'Nicht verfügbar';
  return source.cache_status === 'stale' ? 'Letzter gültiger Wert' : 'Aktuell';
}
function preferred(data) { return data.station.available && Number.isFinite(data.station.wind_kn) ? data.station : data.model; }
function compass(degrees) {
  if (!Number.isFinite(degrees)) return '–';
  const names = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW'];
  return names[Math.round(degrees / 22.5) % 16];
}

function localDayKey(raw, timeZone = 'Europe/Zurich') {
  const parts = new Intl.DateTimeFormat('en-CA', { timeZone, year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date(raw));
  const get = type => parts.find(item => item.type === type)?.value;
  return `${get('year')}-${get('month')}-${get('day')}`;
}

function circularDirection(records) {
  const values = records.map(item => item.direction_deg).filter(Number.isFinite);
  if (!values.length) return null;
  const radians = values.map(item => item * Math.PI / 180);
  const angle = Math.atan2(radians.reduce((sum, item) => sum + Math.sin(item), 0), radians.reduce((sum, item) => sum + Math.cos(item), 0)) * 180 / Math.PI;
  return Math.round((angle + 360) % 360);
}

function measurementPaths(records, key, maxValue) {
  const width = 1000; const height = 165;
  const groups = []; let group = [];
  records.forEach((item, index) => {
    const number = item[key];
    const previous = index ? new Date(records[index - 1].time).getTime() : null;
    const current = new Date(item.time).getTime();
    if (!Number.isFinite(number) || (previous && current - previous > 21 * 60 * 1000)) {
      if (group.length) groups.push(group);
      group = [];
    }
    if (Number.isFinite(number)) {
      const x = records.length > 1 ? index / (records.length - 1) * width : 0;
      const y = height - number / maxValue * (height - 12);
      group.push(`${x.toFixed(1)},${y.toFixed(1)}`);
    }
  });
  if (group.length) groups.push(group);
  return groups.map(points => `<polyline class="${key === 'wind_kn' ? 'wind-line' : 'gust-line'}" points="${points.join(' ')}"/>`).join('');
}

function renderMeasurementHistory() {
  const data = state.measurementData;
  if (!data?.records?.length) return;
  const records = data.records;
  const winds = records.map(item => item.wind_kn).filter(Number.isFinite);
  const gusts = records.map(item => item.gust_kn).filter(Number.isFinite);
  const direction = circularDirection(records);
  const maxValue = Math.max(10, ...winds, ...gusts);
  const weeklyPeak = records.filter(item => Number.isFinite(item.gust_kn)).sort((a, b) => b.gust_kn - a.gust_kn)[0];
  const start = new Date(records[0].time).getTime();
  const end = new Date(records.at(-1).time).getTime();
  const days = [...new Set(records.map(item => localDayKey(item.time)))].sort();
  const dayCards = days.map(day => {
    const items = records.filter(item => localDayKey(item.time) === day);
    const dir = circularDirection(items);
    const peak = items.filter(item => Number.isFinite(item.gust_kn)).sort((a, b) => b.gust_kn - a.gust_kn)[0];
    const label = new Date(`${day}T12:00:00`).toLocaleDateString('de-CH', { weekday: 'short', day: '2-digit', month: '2-digit' });
    return `<div class="measurement-hour"><b>${label}</b><strong>${value(average(items, 'wind_kn'), ' kn')}</strong><span>${Number.isFinite(dir) ? `${compass(dir)} · ${dir}°` : 'Richtung –'}</span><small>Maximum ${value(peak?.gust_kn, ' kn')} um ${peak ? timeLabel(peak.time, 'Europe/Zurich') : '–'} · ${items.length} Werte</small></div>`;
  }).join('');
  $('#measurement-content').innerHTML = `
    <div class="measurement-summary">
      <div><span>Ø Mittelwind · 7 Tage</span><strong>${value(average(records, 'wind_kn'), ' kn')}</strong><small>aus 10-Minuten-Werten</small></div>
      <div><span>Stärkste Böe</span><strong>${value(weeklyPeak?.gust_kn, ' kn')}</strong><small>${weeklyPeak ? `Wochenmaximum um ${timeLabel(weeklyPeak.time, 'Europe/Zurich')}` : 'nicht verfügbar'}</small></div>
      <div><span>Mittlere Richtung</span><strong>${Number.isFinite(direction) ? compass(direction) : '–'}</strong><small>${Number.isFinite(direction) ? `${direction}°` : 'nicht verfügbar'}</small></div>
      <div><span>Messabdeckung</span><strong>${records.length}</strong><small>unveränderte Messpunkte</small></div>
    </div>
    <div class="measurement-scroll" tabindex="0" aria-label="Messgrafik horizontal scrollbar">
      <div class="mobile-scroll-hint">↔ Grafik horizontal wischen</div>
      <div class="measurement-plot week">
        <div class="measurement-legend"><span><i></i>Mittelwind</span><span><i class="gust"></i>Maximale Böen</span><span>Zahlen: Messwerte in kn · Lücken bleiben sichtbar</span></div>
        <svg viewBox="0 0 1000 220" role="img" aria-label="Gemessener Windverlauf der letzten sieben Tage">
          <line class="grid" x1="0" y1="205" x2="1000" y2="205"/><line class="grid" x1="0" y1="107" x2="1000" y2="107"/>
          ${timelineLines(records, 'gust_kn', start, end, maxValue, 'gust-line', 21)}${timelineLines(records, 'wind_kn', start, end, maxValue, 'wind-line', 21)}
          ${timelineLabels(records, 'wind_kn', start, end, maxValue, window.innerWidth <= 520 ? 144 : 72, 'measured', 15, 'Europe/Zurich')}
          ${peakLabelsByDay(records, start, end, maxValue, 'Europe/Zurich')}
        </svg>
        <div class="timeline-axis"><span>${dateTime(records[0].time)}</span><b>7 Tage gemessen</b><span>${dateTime(records.at(-1).time)}</span></div>
      </div>
    </div>
    <div class="measurement-hours">${dayCards}</div>`;
  $('#measurement-content').hidden = false;
}

async function loadMeasurementHistory(spot) {
  state.measurementController?.abort();
  const controller = new AbortController();
  state.measurementController = controller;
  state.measurementData = null; state.measurementDay = null;
  $('#measured-history').hidden = true;
  $('#measurement-content').hidden = true;
  $('#measurement-error').hidden = true;
  $('#measurement-loading').hidden = false;
  const timeout = setTimeout(() => controller.abort(), 20000);
  try {
    const response = await fetch(`/api/v1/measurement-history/${encodeURIComponent(spot)}`, { signal: controller.signal });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    if (!data.available) return;
    state.measurementData = data;
    $('#measured-history').hidden = false;
    $('#measured-history-source').href = data.source_url;
    text('#measured-history-description', `${data.station_name} (${data.distance_km} km) · offizielle 10-Minuten-Messwerte · Zeiten lokal Schweiz`);
    renderMeasurementHistory();
    renderChart();
  } catch (error) {
    if (controller.signal.aborted || state.measurementController !== controller) return;
    $('#measured-history').hidden = false;
    $('#measurement-error').hidden = false;
  } finally {
    clearTimeout(timeout);
    if (state.measurementController === controller) $('#measurement-loading').hidden = true;
  }
}

function browserQuality(model, station) {
  let score = model.available ? 30 : 0;
  const reasons = [];
  let delta = null;
  if (station.available && Number.isFinite(station.wind_kn)) {
    score += 35;
    const distance = station.distance_km ?? 999;
    let ceiling;
    if (distance <= 1) { score += 15; ceiling = 100; reasons.push('Messstation liegt direkt am Spot'); }
    else if (distance <= 5) { score += 12; ceiling = 95; reasons.push('Messstation liegt sehr nahe am Spot'); }
    else if (distance <= 15) { score += 5; ceiling = 80; reasons.push('Messstation ist eine regionale Referenz'); }
    else if (distance <= 30) { score += 2; ceiling = 72; reasons.push('Messstation ist nur regional repräsentativ'); }
    else { ceiling = 65; reasons.push('Messstation ist weit entfernt'); }
    const age = station.observation_age_minutes;
    if (Number.isFinite(age) && age <= 20) { score += 10; reasons.push('Messung ist höchstens 20 Minuten alt'); }
    else if (Number.isFinite(age) && age <= 40) { score += 5; ceiling = Math.min(ceiling, 90); reasons.push('Messung ist leicht verzögert'); }
    else if (Number.isFinite(age)) { ceiling = Math.min(ceiling, 70); reasons.push('Messung ist älter als 40 Minuten'); }
    else reasons.push('Messalter ist nicht eindeutig bestimmbar');
    if (station.quality_flags?.length) { ceiling = Math.min(ceiling, 70); reasons.push('Stationswert hat einen Plausibilitätswarnhinweis'); }
    if (Number.isFinite(model.wind_kn)) {
      delta = Math.round(Math.abs(station.wind_kn - model.wind_kn) * 10) / 10;
      if (delta <= 3) { score += 10; reasons.push('Messung und Modell stimmen gut überein'); }
      else if (delta <= 6) { score += 5; reasons.push('Messung und Modell weichen moderat ab'); }
      else reasons.push('Messung und Modell weichen stark ab');
    }
    score = Math.min(score, ceiling);
    if (ceiling < 100) reasons.push(`Qualität wegen Messdistanz auf ${ceiling}/100 begrenzt`);
  } else reasons.push('Keine aktuelle Stationsmessung verfügbar');
  score = Math.min(score, 100);
  return { score, label: score >= 80 ? 'hoch' : score >= 55 ? 'mittel' : 'begrenzt', delta_kn: delta, reasons };
}

async function fetchBrowserModel(spot, signal) {
  const params = new URLSearchParams({
    latitude: spot.lat, longitude: spot.lon,
    current: 'temperature_2m,wind_speed_10m,wind_direction_10m,wind_gusts_10m,weather_code,cloud_cover',
    hourly: 'wind_speed_10m,wind_direction_10m,wind_gusts_10m,temperature_2m,precipitation_probability',
    forecast_days: '7', timezone: 'auto', wind_speed_unit: 'kn',
  });
  const url = `https://api.open-meteo.com/v1/forecast?${params}`;
  const response = await fetch(url, { signal });
  if (!response.ok) throw new Error(`Open-Meteo HTTP ${response.status}`);
  const raw = await response.json();
  const current = raw.current;
  const hourly = raw.hourly;
  const offset = raw.utc_offset_seconds || 0;
  const forecast = (hourly.time || []).map((time, index) => ({
    time: isoWithOffset(time, offset),
    wind_kn: hourly.wind_speed_10m?.[index] ?? null,
    gust_kn: hourly.wind_gusts_10m?.[index] ?? null,
    direction_deg: hourly.wind_direction_10m?.[index] ?? null,
    temperature_c: hourly.temperature_2m?.[index] ?? null,
    rain_probability: hourly.precipitation_probability?.[index] ?? null,
  }));
  return {
    available: true, type: 'model', provider: 'Open-Meteo Browser-Fallback', source_url: url,
    observed_at: isoWithOffset(current.time, offset), fetched_at: new Date().toISOString(), cache_status: 'browser',
    timezone: raw.timezone || 'UTC', utc_offset_seconds: offset,
    wind_kn: current.wind_speed_10m, gust_kn: current.wind_gusts_10m,
    direction_deg: current.wind_direction_10m, direction: compass(current.wind_direction_10m),
    temperature_c: current.temperature_2m, cloud_cover: current.cloud_cover,
    forecast, method: 'Direkter Browser-Fallback; Modellwert, keine Messung',
  };
}

function dailyOpenMeteo(raw) {
  const daily = raw.daily || {};
  return (daily.time || []).map((date, index) => {
    const direction = daily.wind_direction_10m_dominant?.[index] ?? null;
    return {
      date, wind_kn: daily.wind_speed_10m_max?.[index] ?? null,
      gust_kn: daily.wind_gusts_10m_max?.[index] ?? null,
      direction_deg: direction, direction: Number.isFinite(direction) ? compass(direction) : null,
    };
  });
}

async function fetchBrowserHistory(spot, signal) {
  const today = new Date();
  const currentYear = today.getFullYear();
  const archiveEnd = new Date(today); archiveEnd.setDate(today.getDate() - 3);
  const format = date => date.toISOString().slice(0, 10);
  const requests = [];
  for (let year = currentYear - 4; year <= currentYear; year += 1) {
    const start = new Date(Date.UTC(year, 0, 1));
    const end = new Date(Math.min(Date.UTC(year, 11, 31), archiveEnd.getTime()));
    if (start > end) continue;
    const params = new URLSearchParams({
      latitude: spot.lat, longitude: spot.lon,
      daily: 'wind_speed_10m_max,wind_gusts_10m_max,wind_direction_10m_dominant',
      timezone: 'auto', wind_speed_unit: 'kn', start_date: format(start), end_date: format(end),
    });
    requests.push(fetch(`https://archive-api.open-meteo.com/v1/archive?${params}`, { signal }).then(response => {
      if (!response.ok) throw new Error(`Archive HTTP ${response.status}`);
      return response.json();
    }));
  }
  const settled = await Promise.allSettled(requests);
  const records = {};
  settled.forEach(result => {
    if (result.status === 'fulfilled') dailyOpenMeteo(result.value).forEach(item => { records[item.date] = item; });
  });
  if (!Object.keys(records).length) throw new Error('Browser history unavailable');
  return {
    available: true, provider: 'Open-Meteo Browser-Fallback',
    source_url: 'https://open-meteo.com/en/docs/historical-weather-api',
    records: Object.values(records).sort((a, b) => a.date.localeCompare(b.date)),
    warning: settled.some(result => result.status === 'rejected') ? 'Einzelne Archivjahre sind derzeit nicht erreichbar.' : null,
  };
}

function timelineLines(records, key, start, end, maxValue, className, gapMinutes) {
  const width = 1000; const height = 205; const duration = end - start;
  const valid = records.filter(item => {
    const time = new Date(item.time).getTime();
    return Number.isFinite(item[key]) && time >= start && time <= end;
  }).sort((a, b) => new Date(a.time) - new Date(b.time));
  const groups = []; let group = [];
  valid.forEach((item, index) => {
    const time = new Date(item.time).getTime();
    const previous = index ? new Date(valid[index - 1].time).getTime() : null;
    if (previous && time - previous > gapMinutes * 60 * 1000) {
      if (group.length) groups.push(group);
      group = [];
    }
    const x = (time - start) / duration * width;
    const y = height - item[key] / maxValue * (height - 14);
    group.push(`${x.toFixed(1)},${y.toFixed(1)}`);
  });
  if (group.length) groups.push(group);
  return groups.map(points => `<polyline class="${className}" points="${points.join(' ')}"/>`).join('');
}

function timelineLabels(records, key, start, end, maxValue, every, dotType = '', offsetY = -10, timeZone = null) {
  const width = 1000; const height = 205; const duration = end - start;
  return records.filter((item, index) => index % every === 0 && Number.isFinite(item[key])).map(item => {
    const time = new Date(item.time).getTime();
    if (time < start || time > end) return '';
    const x = (time - start) / duration * width;
    const y = height - item[key] / maxValue * (height - 14);
    const labelY = Math.max(12, y + offsetY);
    const label = `${timeLabel(item.time, timeZone)} · ${item[key]}`;
    return `<circle class="timeline-dot ${dotType}" cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="3.5"><title>${dateTime(item.time, timeZone)} · ${item[key]} kn</title></circle><text class="timeline-value" x="${x.toFixed(1)}" y="${labelY.toFixed(1)}" text-anchor="middle">${label}</text>`;
  }).join('');
}

function peakLabelsByDay(records, start, end, maxValue, timeZone) {
  const keys = [...new Set(records.map(item => localDayKey(item.time, timeZone)))];
  const peaks = keys.map(key => records.filter(item => localDayKey(item.time, timeZone) === key && Number.isFinite(item.gust_kn)).sort((a, b) => b.gust_kn - a.gust_kn)[0]).filter(Boolean);
  const width = 1000; const height = 205; const duration = end - start;
  return peaks.map(item => {
    const time = new Date(item.time).getTime();
    if (time < start || time > end) return '';
    const x = (time - start) / duration * width;
    const y = height - item.gust_kn / maxValue * (height - 14);
    const label = `Max ${timeLabel(item.time, timeZone)} · ${item.gust_kn}`;
    return `<circle class="timeline-dot gust" cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="4"><title>${dateTime(item.time, timeZone)} · Böe ${item.gust_kn} kn</title></circle><text class="timeline-value max-gust" x="${x.toFixed(1)}" y="${Math.max(12, y - 11).toFixed(1)}" text-anchor="middle">${label}</text>`;
  }).join('');
}

function forecastDateRow(records, timeZone) {
  const keys = [...new Set(records.map(item => localDayKey(item.time, timeZone)))];
  const now = new Date();
  const today = localDayKey(now.toISOString(), timeZone);
  const tomorrowDate = new Date(now.getTime() + 24 * 60 * 60 * 1000);
  const tomorrow = localDayKey(tomorrowDate.toISOString(), timeZone);
  return `<div class="forecast-date-row" style="grid-template-columns:repeat(${Math.max(1, keys.length)}, minmax(0, 1fr))">${keys.map(key => {
    const first = records.find(item => localDayKey(item.time, timeZone) === key);
    const date = first ? new Date(first.time) : new Date(`${key}T12:00:00`);
    const full = new Intl.DateTimeFormat('de-CH', { timeZone, weekday: 'short', day: '2-digit', month: '2-digit' }).format(date);
    const title = key === today ? 'Heute' : key === tomorrow ? 'Morgen' : new Intl.DateTimeFormat('de-CH', { timeZone, weekday: 'long' }).format(date);
    return `<div><b>${title}</b><span>${full}</span></div>`;
  }).join('')}</div>`;
}

function renderChart() {
  const chart = $('#forecast-chart');
  const forecast = (state.liveData?.model?.forecast || []).filter(item => new Date(item.time).getTime() >= Date.now() - 60 * 60 * 1000);
  const timeZone = state.liveData?.model?.timezone || 'UTC';
  const now = Date.now();
  const days = state.forecastView === 'week' ? 7 : state.forecastView === 'three' ? 3 : 1;
  const start = now - 60 * 60 * 1000;
  let end;
  if (state.forecastView === 'day') end = now + 24 * 60 * 60 * 1000;
  else {
    const forecastDays = [...new Set(forecast.filter(item => new Date(item.time).getTime() >= now).map(item => localDayKey(item.time, timeZone)))];
    const finalKey = forecastDays[Math.min(days, forecastDays.length) - 1];
    const finalRecords = forecast.filter(item => localDayKey(item.time, timeZone) === finalKey);
    end = finalRecords.length ? Math.max(...finalRecords.map(item => new Date(item.time).getTime())) : now + days * 24 * 60 * 60 * 1000;
  }
  const visible = forecast.filter(item => { const time = new Date(item.time).getTime(); return time >= start && time <= end; });
  text('#forecast-title', state.forecastView === 'day' ? '24‑Stunden-Prognose' : state.forecastView === 'three' ? '3‑Tage-Prognose' : '7‑Tage-Prognose');
  if (!visible.length) {
    chart.innerHTML = '<p>Keine Prognose verfügbar.</p>';
    return;
  }
  const maxValue = Math.max(10, ...visible.flatMap(item => [item.wind_kn, item.gust_kn]).filter(Number.isFinite));
  const mobile = window.innerWidth <= 520;
  const labelEvery = mobile
    ? (state.forecastView === 'day' ? 2 : state.forecastView === 'three' ? 6 : 12)
    : (state.forecastView === 'day' ? 2 : state.forecastView === 'three' ? 6 : 12);
  const minWidth = mobile
    ? (state.forecastView === 'day' ? 1000 : state.forecastView === 'three' ? 1500 : 2100)
    : (state.forecastView === 'day' ? 900 : state.forecastView === 'three' ? 1350 : 1800);
  const dateRow = forecastDateRow(visible, timeZone);
  chart.innerHTML = `<div class="timeline-scroll" tabindex="0" aria-label="Prognosegrafik horizontal scrollbar"><div class="mobile-scroll-hint">↔ Grafik horizontal wischen</div><div class="timeline-plot" style="min-width:${minWidth}px">${dateRow}<svg viewBox="0 0 1000 220">
    <line class="grid" x1="0" y1="205" x2="1000" y2="205"/><line class="grid" x1="0" y1="107" x2="1000" y2="107"/>
    ${timelineLines(forecast, 'gust_kn', start, end, maxValue, 'forecast-gust', 91)}
    ${timelineLines(forecast, 'wind_kn', start, end, maxValue, 'forecast-wind', 91)}
    ${timelineLabels(forecast, 'gust_kn', start, end, maxValue, labelEvery, 'gust', -12, timeZone)}
    ${timelineLabels(forecast, 'wind_kn', start, end, maxValue, labelEvery, 'forecast', 17, timeZone)}
    </svg><div class="timeline-axis"><span>Jetzt · ${timeLabel(new Date(now).toISOString(), timeZone)}</span><b>${days === 1 ? '24 Stunden' : days === 3 ? '3 Tage Prognose' : '7 Tage Prognose'}</b><span>${dateTime(new Date(end).toISOString(), timeZone)}</span></div></div></div>`;
}

function historyDirection(records) {
  const counts = {};
  records.forEach(item => { if (item.direction) counts[item.direction] = (counts[item.direction] || 0) + 1; });
  return Object.entries(counts).sort((a, b) => b[1] - a[1])[0]?.[0] || '–';
}
function average(records, key) {
  const values = records.map(item => item[key]).filter(Number.isFinite);
  return values.length ? Math.round(values.reduce((sum, item) => sum + item, 0) / values.length * 10) / 10 : null;
}

function standardDeviation(values) {
  if (!values.length) return 0;
  const mean = values.reduce((sum, number) => sum + number, 0) / values.length;
  return Math.sqrt(values.reduce((sum, number) => sum + ((number - mean) ** 2), 0) / values.length);
}

function windStatistics(records, kite) {
  const valid = records.filter(item => Number.isFinite(item.wind_kn));
  if (!valid.length || !kite) return null;
  const min = kite.min_kn; const max = kite.max_kn;
  const kiteable = valid.filter(item => item.wind_kn >= min && item.wind_kn <= max);
  const good = kiteable.filter(item => !Number.isFinite(item.gust_kn) || item.gust_kn <= max + 6);
  const years = new Set(valid.map(item => item.date.slice(0, 4))).size || 1;
  const monthly = Array.from({ length: 12 }, (_, month) => {
    const observed = valid.filter(item => Number(item.date.slice(5, 7)) - 1 === month);
    const positive = good.filter(item => Number(item.date.slice(5, 7)) - 1 === month);
    return { month, days: Math.round(positive.length / years), probability: observed.length ? Math.round(positive.length / observed.length * 100) : 0 };
  });
  const top = [...monthly].sort((a, b) => b.probability - a.probability).slice(0, 3);
  const winds = good.map(item => item.wind_kn);
  const mean = winds.length ? winds.reduce((sum, number) => sum + number, 0) / winds.length : 0;
  const consistency = mean ? Math.max(0, Math.min(100, Math.round(100 - standardDeviation(winds) / mean * 100))) : 0;
  const security = top.length ? Math.round(top.reduce((sum, item) => sum + item.probability, 0) / top.length) : 0;
  const goodPerYear = Math.round(good.length / years);
  const kiteablePerYear = Math.round(kiteable.length / years);
  const score = Math.round(security * .45 + consistency * .25 + Math.min(100, goodPerYear / 120 * 100) * .3);
  return { monthly, top, consistency, security, score, goodPerYear, kiteablePerYear, good };
}

function monthName(month, long = false) {
  return new Intl.DateTimeFormat('de-CH', { month: long ? 'long' : 'short' }).format(new Date(2024, month, 1));
}

function renderStatistics(records) {
  const stats = windStatistics(records, state.liveData?.spot?.kite);
  if (!stats) return;
  state.spotStats[state.spot] = { ...stats, name: state.liveData.spot.name };
  $('#month-overview').innerHTML = stats.monthly.map(item => `<div class="month-card${stats.top.some(top => top.month === item.month) ? ' top' : ''}"><b>${monthName(item.month)}</b><strong>${item.days}</strong><small>gute Tage</small><div class="month-bar"><i style="width:${item.probability}%"></i></div></div>`).join('');
  const sectors = ['N','NE','E','SE','S','SW','W','NW'];
  const counts = Object.fromEntries(sectors.map(name => [name, 0]));
  stats.good.forEach(item => {
    if (!Number.isFinite(item.direction_deg)) return;
    counts[sectors[Math.round(item.direction_deg / 45) % 8]] += 1;
  });
  const total = Object.values(counts).reduce((sum, number) => sum + number, 0) || 1;
  $('#direction-overview').innerHTML = sectors.map(name => `<div class="direction-item"><b>${name}</b><span>${Math.round(counts[name] / total * 100)}%</span></div>`).join('');
  renderRanking();
}

function renderRanking() {
  const entries = Object.entries(state.spotStats).sort((a, b) => b[1].score - a[1].score);
  $('#ranking-list').innerHTML = entries.length ? entries.slice(0, 5).map(([id, item], index) => `<div class="ranking-row${id === state.spot ? ' active' : ''}"><span>${index + 1}</span><div><b>${item.name}</b><small>${item.goodPerYear} gute Tage/Jahr</small></div><strong>${item.score}</strong></div>`).join('') : '<div class="ranking-loading">Statistik wird geladen …</div>';
}
function maximum(records, key) {
  const values = records.map(item => item[key]).filter(Number.isFinite);
  return values.length ? Math.max(...values) : null;
}
function localDate(raw) { return new Date(`${raw}T12:00:00`); }
function sameMonth(item, anchor) {
  const day = localDate(item.date);
  return day.getFullYear() === anchor.getFullYear() && day.getMonth() === anchor.getMonth();
}
function statCard(label, records) {
  return `<div class="history-stat"><b>${label}</b><strong>${value(average(records, 'wind_kn'), ' kn')}</strong><span>Ø Tagesmaximum</span><small>Spitze ${value(maximum(records, 'wind_kn'), ' kn')} · meist ${historyDirection(records)}</small></div>`;
}
function renderHistoryMonth(records, anchor) {
  const monthRecords = records.filter(item => sameMonth(item, anchor));
  const byDate = Object.fromEntries(monthRecords.map(item => [item.date, item]));
  const year = anchor.getFullYear();
  const month = anchor.getMonth();
  const first = new Date(year, month, 1);
  const days = new Date(year, month + 1, 0).getDate();
  const offset = (first.getDay() + 6) % 7;
  const cells = Array.from({ length: offset }, () => '<div class="history-day empty"></div>');
  for (let day = 1; day <= days; day += 1) {
    const key = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
    const item = byDate[key];
    cells.push(`<div class="history-day${item ? '' : ' missing'}"><b>${day}</b><strong>${item ? value(item.wind_kn, ' kn') : '–'}</strong><span>${item?.direction ? `${item.direction} · ${Math.round(item.direction_deg)}°` : 'keine Daten'}</span><small>${item ? `Böe ${value(item.gust_kn, ' kn')}` : ''}</small></div>`);
  }
  return `${statCard('Monat', monthRecords)}<div class="calendar-weekdays"><span>Mo</span><span>Di</span><span>Mi</span><span>Do</span><span>Fr</span><span>Sa</span><span>So</span></div><div class="history-calendar">${cells.join('')}</div>`;
}
function renderHistoryWeek(records) {
  const today = new Date(); today.setHours(23, 59, 59, 999);
  const start = new Date(today); start.setDate(today.getDate() - 6); start.setHours(0, 0, 0, 0);
  const week = records.filter(item => { const day = localDate(item.date); return day >= start && day <= today; });
  return `${statCard('Letzte 7 Tage', week)}<div class="history-days">${week.map(item => `<div class="history-day"><b>${localDate(item.date).toLocaleDateString('de-CH', { weekday: 'short', day: '2-digit' })}</b><strong>${value(item.wind_kn, ' kn')}</strong><span>${item.direction || '–'} · ${Number.isFinite(item.direction_deg) ? `${Math.round(item.direction_deg)}°` : '–'}</span><small>Böe ${value(item.gust_kn, ' kn')}</small></div>`).join('')}</div>`;
}
function renderHistoryYear(records, anchor) {
  const year = anchor.getFullYear();
  const cards = Array.from({ length: 12 }, (_, month) => {
    const subset = records.filter(item => { const day = localDate(item.date); return day.getFullYear() === year && day.getMonth() === month; });
    return statCard(new Intl.DateTimeFormat('de-CH', { month: 'short' }).format(new Date(year, month, 1)), subset);
  });
  return `<div class="history-summary-grid">${cards.join('')}</div>`;
}
function renderHistoryFive(records) {
  const current = new Date().getFullYear();
  const cards = [];
  for (let year = current - 4; year <= current; year += 1) {
    cards.push(statCard(String(year), records.filter(item => localDate(item.date).getFullYear() === year)));
  }
  return `<div class="history-summary-grid five">${cards.join('')}</div>`;
}
function renderHistory() {
  if (!state.historyData?.records) return;
  const records = state.historyData.records;
  const content = $('#history-content');
  const view = state.historyView;
  const anchor = state.historyDate;
  $('#history-nav').hidden = view === 'five' || view === 'week';
  $('#history-period').textContent = view === 'month'
    ? new Intl.DateTimeFormat('de-CH', { month: 'long', year: 'numeric' }).format(anchor)
    : String(anchor.getFullYear());
  content.innerHTML = view === 'week' ? renderHistoryWeek(records)
    : view === 'month' ? renderHistoryMonth(records, anchor)
    : view === 'year' ? renderHistoryYear(records, anchor)
    : renderHistoryFive(records);
  content.hidden = false;
}
async function loadHistory(spot, spotMeta) {
  state.historyController?.abort();
  state.historyController = new AbortController();
  state.historyData = null;
  state.historyDate = new Date();
  $('#history-loading').hidden = false;
  $('#history-content').hidden = true;
  $('#history-error').hidden = true;
  const timeout = setTimeout(() => state.historyController.abort(), 30000);
  try {
    let data;
    try {
      const response = await fetch(`/api/v1/history/${encodeURIComponent(spot)}`, { signal: state.historyController.signal });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      data = await response.json();
      if (!data.available) throw new Error('history unavailable');
    } catch (_) {
      data = await fetchBrowserHistory(spotMeta, state.historyController.signal);
    }
    state.historyData = data;
    $('#history-source').href = data.source_url;
    renderHistory();
    renderStatistics(data.records);
  } catch (_) {
    $('#history-error').hidden = false;
  } finally {
    clearTimeout(timeout);
    $('#history-loading').hidden = true;
  }
}

function renderSource(data) {
  const station = data.station;
  const kwind = data.spot.kwind;
  $('#station-card').classList.toggle('unavailable', !station.available && !kwind);
  if (station.available) {
    text('#station-provider', 'MeteoSchweiz');
    text('#station-description', 'Offizielle 10‑Minuten-Stationsmessung');
    text('#station-label', 'Station');
    text('#station-name', `${station.station_name} (${station.distance_km} km)`);
    text('#station-time', dateTime(station.observed_at));
    text('#station-status', cacheLabel(station));
    $('#station-link').href = station.source_url;
    $('#station-link').textContent = 'Quelldatei öffnen ↗';
  } else if (kwind) {
    text('#station-provider', kwind.name);
    text('#station-description', kwind.kind || 'Zusätzliches globales Live-Stationsnetz. Werte werden aus Lizenzgründen direkt bei KWind geprüft.');
    text('#station-label', kwind.station_id ? 'Stations-ID' : 'Suche');
    text('#station-name', kwind.station_id || data.spot.name);
    text('#station-time', 'Live extern');
    text('#station-status', 'Verknüpft');
    $('#station-link').href = kwind.url;
    $('#station-link').textContent = kwind.station_id ? 'KWind Live öffnen ↗' : 'KWind-Station suchen ↗';
  } else {
    text('#station-provider', 'Lokale Messung');
    text('#station-description', 'Noch keine Stationsquelle hinterlegt.');
    text('#station-name', 'Nicht verfügbar');
    text('#station-time', '–');
    text('#station-status', 'Offen');
    $('#station-link').href = '#';
    $('#station-link').textContent = 'Quelle vorschlagen';
  }

  const stationHistoryLink = $('#station-history-link');
  stationHistoryLink.hidden = !kwind?.history_url;
  stationHistoryLink.href = kwind?.history_url || '#';
  stationHistoryLink.textContent = 'KWind-Messhistorie ↗';

  const kwindPanel = $('#kwind-live');
  const kwindWidget = $('#kwind-widget');
  kwindPanel.hidden = !kwind?.widget_url;
  if (kwind?.widget_url) {
    if (kwindWidget.src !== kwind.widget_url) kwindWidget.src = kwind.widget_url;
    $('#kwind-live-link').href = kwind.url;
    $('#kwind-history-link').href = kwind.history_url;
  } else {
    kwindWidget.removeAttribute('src');
  }

  const windguru = data.spot.windguru;
  const windguruPanel = $('#windguru-live');
  const windguruStations = $('#windguru-stations');
  windguruPanel.hidden = !windguru?.stations?.length;
  windguruStations.replaceChildren();
  if (windguru?.stations?.length) {
    $('#windguru-link').href = windguru.url;
    text('#windguru-note', windguru.note);
    windguru.stations.forEach(item => {
      const card = document.createElement('div');
      const name = document.createElement('strong');
      const distance = document.createElement('span');
      name.textContent = item.name;
      distance.textContent = item.distance_km === 0 ? 'direkt am Spot' : `${item.distance_km} km entfernt`;
      card.append(name, distance);
      windguruStations.append(card);
    });
  } else {
    text('#windguru-note', '');
  }

  const externalMeasurements = data.spot.external_measurements || [];
  const externalPanel = $('#external-live');
  const externalSources = $('#external-sources');
  externalPanel.hidden = externalMeasurements.length === 0;
  externalSources.replaceChildren();
  externalMeasurements.forEach(item => {
    const card = document.createElement('div');
    card.className = 'external-source';
    const link = document.createElement('a');
    const name = document.createElement('strong');
    const kind = document.createElement('span');
    const meta = document.createElement('small');
    link.href = item.url;
    link.target = '_blank';
    link.rel = 'noopener';
    name.textContent = item.name;
    kind.textContent = item.kind;
    const distance = Number.isFinite(item.distance_km) ? `${item.distance_km} km entfernt · ` : '';
    meta.textContent = `${distance}${item.note || 'Extern öffnen'}`;
    link.append(name, kind, meta);
    card.append(link);
    if (item.embed_url) {
      const frame = document.createElement('iframe');
      frame.src = item.embed_url;
      frame.title = `${item.name} Live-Messung`;
      frame.loading = 'lazy';
      frame.referrerPolicy = 'strict-origin-when-cross-origin';
      card.append(frame);
    }
    externalSources.append(card);
  });

  const model = data.model;
  $('#model-card').classList.toggle('unavailable', !model.available);
  text('#model-wind', value(model.wind_kn, ' kn'));
  text('#model-time', model.available ? dateTime(model.observed_at) : '–');
  text('#model-status', cacheLabel(model));
  $('#model-link').href = model.source_url || 'https://open-meteo.com/en/docs';

  const school = data.spot.school;
  $('#local-card').classList.toggle('unavailable', !school);
  text('#school-name', school?.name || 'Lokale Quelle fehlt');
  text('#school-kind', school?.kind || 'Hier ist noch keine öffentlich geprüfte Kite-Schule oder lokaler Club hinterlegt.');
  text('#school-verified', school ? new Date(`${school.verified}T12:00:00`).toLocaleDateString('de-CH') : 'Offen');
  const link = $('#school-link');
  link.href = school?.url || '#';
  link.hidden = !school;
}

function render(data) {
  const live = preferred(data);
  const sourceName = live.type === 'measurement' ? 'MeteoSchweiz Messung' : 'Open‑Meteo Modell';
  text('#live-panel-title', live.type === 'measurement' ? 'Live-Messung' : 'Aktueller Modellwert');
  text('#live-panel-kind', live.type === 'measurement' ? 'ECHTE MESSUNG' : 'KEINE DIREKTE MESSUNG');
  text('#spot-title', `${data.spot.name} · ${data.spot.region}`);
  text('#freshness', `Aktualisiert ${dateTime(data.generated_at)}`);
  text('#wind-value', value(live.wind_kn));
  text('#gust-value', value(live.gust_kn, ' kn'));
  text('#temp-value', value(live.temperature_c, ' °C'));
  text('#distance-value', data.station.available ? value(data.station.distance_km, ' km') : '–');
  text('#wind-direction', Number.isFinite(live.direction_deg) ? `${live.direction || compass(live.direction_deg)} · ${Math.round(live.direction_deg)}°` : '–');
  text('#wind-source', sourceName);
  $('#wind-arrow').style.transform = `rotate(${live.direction_deg ?? 0}deg)`;

  const signal = $('#signal');
  signal.className = `signal ${data.signal.level}`;
  signal.querySelector('b').textContent = data.signal.label;
  text('#signal-reason', data.signal.reason);

  text('#quality-score', data.quality.score);
  text('#quality-label', data.quality.label);
  $('#quality-bar').style.width = `${data.quality.score}%`;
  $('#quality-reasons').innerHTML = data.quality.reasons.map(reason => `<li>${reason}</li>`).join('');
  text('#model-delta', Number.isFinite(data.quality.delta_kn)
    ? `Abweichung Messung ↔ Modell: ${data.quality.delta_kn} kn`
    : data.station.available ? 'Vergleich erst mit Modellwert möglich' : 'Vergleich erst mit Messwert möglich');

  renderChart();
  renderSource(data);
  const guide = data.spot.spotguide;
  text('#local-note', [data.spot.local_note, guide?.wind_info].filter(Boolean).join(' '));
  const guideLink = $('#spotguide-link');
  guideLink.hidden = !guide;
  guideLink.href = guide?.url || '#';
  guideLink.textContent = guide ? `${guide.name} öffnen ↗` : '';
  text('#disclaimer', data.disclaimer);
}

async function load(spot = state.spot) {
  state.spot = spot;
  state.controller?.abort();
  state.controller = new AbortController();
  const timeout = setTimeout(() => state.controller.abort(), 15000);
  $('#dashboard').setAttribute('aria-busy', 'true');
  $('#loading').hidden = false;
  $('#content').hidden = true;
  $('#error').hidden = true;
  try {
    const response = await fetch(`/api/v1/wind/${encodeURIComponent(spot)}`, { signal: state.controller.signal });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    if (!data.model.available) {
      try {
        data.model = await fetchBrowserModel(data.spot, state.controller.signal);
        data.quality = browserQuality(data.model, data.station);
      } catch (_) {}
    }
    state.liveData = data;
    render(data);
    loadHistory(spot, data.spot);
    loadMeasurementHistory(spot);
    try { localStorage.setItem(`windatlas:${spot}`, JSON.stringify({ at: Date.now(), data })); } catch (_) {}
    $('#content').hidden = false;
  } catch (error) {
    let cached = null;
    try { cached = JSON.parse(localStorage.getItem(`windatlas:${spot}`)); } catch (_) {}
    if (cached?.data) {
      render(cached.data);
      text('#freshness', `Offline-Wert von ${dateTime(cached.data.generated_at)}`);
      $('#content').hidden = false;
    } else {
      $('#error').hidden = false;
    }
  } finally {
    clearTimeout(timeout);
    $('#loading').hidden = true;
    $('#dashboard').setAttribute('aria-busy', 'false');
  }
}

$$('.spot-chip').forEach(button => button.addEventListener('click', () => {
  $$('.spot-chip').forEach(item => { item.classList.remove('active'); item.setAttribute('aria-pressed', 'false'); });
  button.classList.add('active');
  button.setAttribute('aria-pressed', 'true');
  history.replaceState(null, '', `#${button.dataset.spot}`);
  load(button.dataset.spot);
}));
$('#retry').addEventListener('click', () => load());
$$('[data-history-view]').forEach(button => button.addEventListener('click', () => {
  state.historyView = button.dataset.historyView;
  $$('[data-history-view]').forEach(item => { item.classList.toggle('active', item === button); item.setAttribute('aria-selected', String(item === button)); });
  renderHistory();
}));
$$('[data-forecast-view]').forEach(button => button.addEventListener('click', () => {
  state.forecastView = button.dataset.forecastView;
  $$('[data-forecast-view]').forEach(item => { item.classList.toggle('active', item === button); item.setAttribute('aria-selected', String(item === button)); });
  renderChart();
}));
$('#advanced-toggle').addEventListener('click', () => {
  const button = $('#advanced-toggle');
  const open = button.getAttribute('aria-expanded') !== 'true';
  button.setAttribute('aria-expanded', String(open));
  $('#advanced-data').classList.toggle('open', open);
  button.querySelector('span').textContent = open ? 'Messdetails und Quellen schließen' : 'Weitere Messdetails und Quellen';
});
$('#history-prev').addEventListener('click', () => {
  const step = state.historyView === 'month' ? -1 : -12;
  state.historyDate = new Date(state.historyDate.getFullYear(), state.historyDate.getMonth() + step, 1);
  renderHistory();
});
$('#history-next').addEventListener('click', () => {
  const step = state.historyView === 'month' ? 1 : 12;
  const candidate = new Date(state.historyDate.getFullYear(), state.historyDate.getMonth() + step, 1);
  if (candidate <= new Date()) state.historyDate = candidate;
  renderHistory();
});

const requested = location.hash.slice(1);
const target = requested && document.querySelector(`[data-spot="${CSS.escape(requested)}"]`);
if (target) target.click(); else load();
