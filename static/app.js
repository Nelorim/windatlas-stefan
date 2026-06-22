const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const state = {
  spot: document.querySelector('.spot-chip')?.dataset.spot || 'silvaplana',
  controller: null,
  historyController: null,
  historyData: null,
  historyView: 'month',
  historyDate: new Date(),
};

function text(selector, value) { $(selector).textContent = value ?? '–'; }
function value(value, suffix = '') { return Number.isFinite(value) ? `${value}${suffix}` : '–'; }
function dateTime(raw) {
  if (!raw) return 'Unbekannt';
  const parsed = new Date(raw);
  return Number.isNaN(parsed.getTime()) ? raw : new Intl.DateTimeFormat('de-CH', { dateStyle: 'short', timeStyle: 'short' }).format(parsed);
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

function renderChart(forecast = []) {
  const chart = $('#forecast-chart');
  const now = Date.now() - 60 * 60 * 1000;
  const future = forecast.filter(item => new Date(item.time).getTime() >= now).slice(0, 16);
  const max = Math.max(20, ...future.map(item => item.gust_kn || item.wind_kn || 0));
  chart.innerHTML = future.map(item => {
    const wind = item.wind_kn || 0;
    const height = Math.max(4, Math.round((wind / max) * 112));
    const hour = new Date(item.time).toLocaleTimeString('de-CH', { hour: '2-digit', minute: '2-digit' });
    const direction = Number.isFinite(item.direction_deg) ? `${compass(item.direction_deg)} ${Math.round(item.direction_deg)}°` : 'Richtung –';
    return `<div class="chart-hour"><div class="chart-bar-wrap"><span class="chart-bar" data-value="${wind}" style="height:${height}px"></span></div><b>${hour}</b><small>${direction}<br>${item.gust_kn ?? '–'} Böe</small></div>`;
  }).join('') || '<p>Keine Prognose verfügbar.</p>';
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
async function loadHistory(spot) {
  state.historyController?.abort();
  state.historyController = new AbortController();
  state.historyData = null;
  state.historyDate = new Date();
  $('#history-loading').hidden = false;
  $('#history-content').hidden = true;
  $('#history-error').hidden = true;
  const timeout = setTimeout(() => state.historyController.abort(), 16000);
  try {
    const response = await fetch(`/api/v1/history/${encodeURIComponent(spot)}`, { signal: state.historyController.signal });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    if (!data.available) throw new Error('history unavailable');
    state.historyData = data;
    $('#history-source').href = data.source_url;
    renderHistory();
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
    externalSources.append(link);
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
  text('#model-delta', Number.isFinite(data.quality.delta_kn) ? `Abweichung Messung ↔ Modell: ${data.quality.delta_kn} kn` : 'Vergleich erst mit Messwert möglich');

  renderChart(data.model.forecast);
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
  const timeout = setTimeout(() => state.controller.abort(), 9000);
  $('#dashboard').setAttribute('aria-busy', 'true');
  $('#loading').hidden = false;
  $('#content').hidden = true;
  $('#error').hidden = true;
  try {
    const response = await fetch(`/api/v1/wind/${encodeURIComponent(spot)}`, { signal: state.controller.signal });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    render(data);
    loadHistory(spot);
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
