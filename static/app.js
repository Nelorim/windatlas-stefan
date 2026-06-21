const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const state = { spot: document.querySelector('.spot-chip')?.dataset.spot || 'silvaplana', controller: null };

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

function renderChart(forecast = []) {
  const chart = $('#forecast-chart');
  const now = Date.now() - 60 * 60 * 1000;
  const future = forecast.filter(item => new Date(item.time).getTime() >= now).slice(0, 16);
  const max = Math.max(20, ...future.map(item => item.gust_kn || item.wind_kn || 0));
  chart.innerHTML = future.map(item => {
    const wind = item.wind_kn || 0;
    const height = Math.max(4, Math.round((wind / max) * 112));
    const hour = new Date(item.time).toLocaleTimeString('de-CH', { hour: '2-digit', minute: '2-digit' });
    return `<div class="chart-hour"><div class="chart-bar-wrap"><span class="chart-bar" data-value="${wind}" style="height:${height}px"></span></div><b>${hour}</b><small>${item.gust_kn ?? '–'} Böe</small></div>`;
  }).join('') || '<p>Keine Prognose verfügbar.</p>';
}

function renderSource(data) {
  const station = data.station;
  $('#station-card').classList.toggle('unavailable', !station.available);
  text('#station-name', station.available ? `${station.station_name} (${station.distance_km} km)` : 'Nicht verfügbar');
  text('#station-time', station.available ? dateTime(station.observed_at) : '–');
  text('#station-status', cacheLabel(station));
  $('#station-link').href = station.source_url || 'https://opendatadocs.meteoswiss.ch/a-data-groundbased/a1-automatic-weather-stations';

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
  text('#wind-direction', live.direction || '–');
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
  text('#local-note', data.spot.local_note);
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

const requested = location.hash.slice(1);
const target = requested && document.querySelector(`[data-spot="${CSS.escape(requested)}"]`);
if (target) target.click(); else load();
