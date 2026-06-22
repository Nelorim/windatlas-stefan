"""Fast, failure-tolerant adapters for forecast and measurement sources."""

from __future__ import annotations

import csv
import io
import json
import math
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
METEOSWISS_FILE = (
    "https://data.geo.admin.ch/ch.meteoschweiz.ogd-smn/"
    "{station}/ogd-smn_{station}_t_now.csv"
)
METEOSWISS_RECENT_FILE = (
    "https://data.geo.admin.ch/ch.meteoschweiz.ogd-smn/"
    "{station}/ogd-smn_{station}_t_recent.csv"
)


@dataclass
class CacheEntry:
    value: Any
    fetched_monotonic: float


class TTLCache:
    """Small thread-safe cache with stale-if-error support."""

    def __init__(self) -> None:
        self._entries: dict[str, CacheEntry] = {}
        self._lock = threading.Lock()

    def get(self, key: str, ttl: int) -> Any | None:
        with self._lock:
            entry = self._entries.get(key)
            if entry and time.monotonic() - entry.fetched_monotonic <= ttl:
                return entry.value
        return None

    def stale(self, key: str, max_age: int) -> Any | None:
        with self._lock:
            entry = self._entries.get(key)
            if entry and time.monotonic() - entry.fetched_monotonic <= max_age:
                value = dict(entry.value)
                value["cache_status"] = "stale"
                return value
        return None

    def put(self, key: str, value: Any) -> Any:
        with self._lock:
            self._entries[key] = CacheEntry(value, time.monotonic())
        return value


CACHE = TTLCache()


def _fetch_text(url: str, timeout: float = 4.0) -> str:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "WindAtlas-CH/6.0 (+data-quality-dashboard)"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8-sig", errors="replace")


def _fetch_json(url: str, timeout: float = 4.0) -> dict[str, Any]:
    return json.loads(_fetch_text(url, timeout))


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _number(value: Any) -> float | None:
    try:
        if value in (None, "", "-"):
            return None
        return round(float(str(value).replace(",", ".")), 1)
    except (TypeError, ValueError):
        return None


def _cached_fetch(
    key: str,
    ttl: int,
    stale_for: int,
    loader: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    fresh = CACHE.get(key, ttl)
    if fresh is not None:
        result = dict(fresh)
        result["cache_status"] = "hit"
        return result
    try:
        value = loader()
        value["cache_status"] = "fresh"
        return CACHE.put(key, value)
    except (OSError, ValueError, KeyError, json.JSONDecodeError, urllib.error.URLError) as exc:
        stale = CACHE.stale(key, stale_for)
        if stale is not None:
            stale["warning"] = "Quelle vorübergehend nicht erreichbar; letzter gültiger Wert."
            return stale
        return {
            "available": False,
            "cache_status": "miss",
            "error": type(exc).__name__,
            "fetched_at": _iso_now(),
        }


def get_open_meteo(spot: dict[str, Any]) -> dict[str, Any]:
    params = {
        "latitude": spot["lat"],
        "longitude": spot["lon"],
        "current": ",".join(
            [
                "temperature_2m",
                "wind_speed_10m",
                "wind_direction_10m",
                "wind_gusts_10m",
                "weather_code",
                "cloud_cover",
            ]
        ),
        "hourly": ",".join(
            [
                "wind_speed_10m",
                "wind_direction_10m",
                "wind_gusts_10m",
                "temperature_2m",
                "precipitation_probability",
            ]
        ),
        "forecast_days": 2,
        "timezone": "auto",
        "wind_speed_unit": "kn",
    }
    url = f"{OPEN_METEO_URL}?{urllib.parse.urlencode(params)}"
    key = f"openmeteo:{spot['lat']}:{spot['lon']}"

    def load() -> dict[str, Any]:
        # Render cold starts and Open-Meteo TLS setup can occasionally exceed
        # the former four-second default although the API itself is healthy.
        raw = _fetch_json(url, timeout=7.0)
        current = raw["current"]
        hourly = raw["hourly"]
        forecast = []
        for index, stamp in enumerate(hourly["time"][:30]):
            forecast.append(
                {
                    "time": stamp,
                    "wind_kn": _number(hourly["wind_speed_10m"][index]),
                    "gust_kn": _number(hourly["wind_gusts_10m"][index]),
                    "direction_deg": _number(hourly["wind_direction_10m"][index]),
                    "temperature_c": _number(hourly["temperature_2m"][index]),
                    "rain_probability": _number(hourly["precipitation_probability"][index]),
                }
            )
        return {
            "available": True,
            "type": "model",
            "provider": "Open-Meteo",
            "source_url": url,
            "observed_at": current["time"],
            "fetched_at": _iso_now(),
            "wind_kn": _number(current["wind_speed_10m"]),
            "gust_kn": _number(current["wind_gusts_10m"]),
            "direction_deg": _number(current["wind_direction_10m"]),
            "temperature_c": _number(current["temperature_2m"]),
            "cloud_cover": _number(current["cloud_cover"]),
            "forecast": forecast,
            "method": "15-Minuten-Modellwert, keine Stationsmessung",
        }

    return _cached_fetch(key, ttl=300, stale_for=21_600, loader=load)


def _daily_history(raw: dict[str, Any]) -> list[dict[str, Any]]:
    daily = raw.get("daily") or {}
    times = daily.get("time") or []
    winds = daily.get("wind_speed_10m_max") or []
    gusts = daily.get("wind_gusts_10m_max") or []
    directions = daily.get("wind_direction_10m_dominant") or []
    records = []
    for index, stamp in enumerate(times):
        direction = _number(directions[index]) if index < len(directions) else None
        records.append(
            {
                "date": stamp,
                "wind_kn": _number(winds[index]) if index < len(winds) else None,
                "gust_kn": _number(gusts[index]) if index < len(gusts) else None,
                "direction_deg": direction,
                "direction": direction_name(direction),
            }
        )
    return records


def get_history(spot: dict[str, Any]) -> dict[str, Any]:
    """Five calendar years of daily model/reanalysis data, loaded independently."""
    today = date.today()
    start = date(today.year - 4, 1, 1)
    archive_end = today - timedelta(days=3)
    daily_variables = ",".join(
        ["wind_speed_10m_max", "wind_gusts_10m_max", "wind_direction_10m_dominant"]
    )
    common = {
        "latitude": spot["lat"],
        "longitude": spot["lon"],
        "daily": daily_variables,
        "timezone": "auto",
        "wind_speed_unit": "kn",
    }
    archive_urls = []
    for year in range(start.year, archive_end.year + 1):
        range_start = max(start, date(year, 1, 1))
        range_end = min(archive_end, date(year, 12, 31))
        archive_urls.append(
            f"{OPEN_METEO_ARCHIVE_URL}?{urllib.parse.urlencode({**common, 'start_date': range_start.isoformat(), 'end_date': range_end.isoformat()})}"
        )
    recent_url = f"{OPEN_METEO_URL}?{urllib.parse.urlencode({**common, 'past_days': 7, 'forecast_days': 1})}"
    key = f"history:{spot['lat']}:{spot['lon']}:{today.isoformat()}"

    def load() -> dict[str, Any]:
        pool = ThreadPoolExecutor(max_workers=len(archive_urls) + 1, thread_name_prefix="history-source")
        archive_futures = [pool.submit(_fetch_json, item, 10.0) for item in archive_urls]
        recent_future = pool.submit(_fetch_json, recent_url, 8.0)
        done, _ = wait([*archive_futures, recent_future], timeout=11.0)
        records = {}
        successful_archives = 0
        for future in archive_futures:
            if future not in done:
                continue
            try:
                for item in _daily_history(future.result()):
                    records[item["date"]] = item
                successful_archives += 1
            except (OSError, ValueError, KeyError, json.JSONDecodeError, urllib.error.URLError):
                continue
        if recent_future in done:
            try:
                for item in _daily_history(recent_future.result()):
                    records[item["date"]] = item
            except (OSError, ValueError, KeyError, json.JSONDecodeError, urllib.error.URLError):
                pass
        pool.shutdown(wait=False, cancel_futures=True)
        if not records:
            raise ValueError("historical archive unavailable")
        ordered = [records[key] for key in sorted(records) if start.isoformat() <= key <= today.isoformat()]
        result = {
            "available": True,
            "type": "reanalysis",
            "provider": "Open-Meteo Historical Weather",
            "source_url": "https://open-meteo.com/en/docs/historical-weather-api",
            "method": "Tägliche Reanalyse/Modellrekonstruktion, keine lückenlose Stationsmessung",
            "start_date": start.isoformat(),
            "end_date": today.isoformat(),
            "fetched_at": _iso_now(),
            "records": ordered,
        }
        if successful_archives < len(archive_urls):
            result["warning"] = f"Teildaten: {successful_archives} von {len(archive_urls)} Archivjahren geladen."
        return result

    return _cached_fetch(key, ttl=21_600, stale_for=604_800, loader=load)


def _csv_rows(text: str) -> list[dict[str, str]]:
    first_line = text.splitlines()[0] if text.splitlines() else ""
    delimiter = ";" if first_line.count(";") > first_line.count(",") else ","
    return list(csv.DictReader(io.StringIO(text), delimiter=delimiter))


def _first(row: dict[str, str], *names: str) -> str | None:
    lowered = {key.lower().strip(): value for key, value in row.items()}
    for name in names:
        if name.lower() in lowered:
            return lowered[name.lower()]
    return None


def _observation_age_minutes(raw: str | None) -> float | None:
    if not raw:
        return None
    parsed = None
    for parser in (
        lambda value: datetime.fromisoformat(value.replace("Z", "+00:00")),
        lambda value: datetime.strptime(value, "%d.%m.%Y %H:%M"),
    ):
        try:
            parsed = parser(raw)
            break
        except (TypeError, ValueError):
            continue
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return round(max(0.0, (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds() / 60), 1)


def get_meteoswiss(spot: dict[str, Any]) -> dict[str, Any]:
    station = spot.get("station")
    if not station:
        return {
            "available": False,
            "provider": "Keine eingebundene Stationsmessung",
            "cache_status": "not_configured",
            "fetched_at": _iso_now(),
        }
    station_id = station["id"].lower()
    url = METEOSWISS_FILE.format(station=station_id)
    key = f"meteoswiss:{station_id}"

    def load() -> dict[str, Any]:
        rows = _csv_rows(_fetch_text(url))
        if not rows:
            raise ValueError("empty MeteoSwiss CSV")
        row = rows[-1]
        observed_at = _first(row, "reference_timestamp", "timestamp", "time", "date")
        wind = _kmh_to_kn(_number(_first(row, "fu3010z0")))
        gust = _kmh_to_kn(_number(_first(row, "fu3010z1")))
        direction = _number(_first(row, "dkl010z0"))
        if wind is None:
            raise ValueError("station wind value missing")
        quality_flags = []
        if gust is not None and gust < wind:
            gust = None
            quality_flags.append("gust_below_mean")
        if direction is not None and not 0 <= direction <= 360:
            direction = None
            quality_flags.append("invalid_direction")
        age_minutes = _observation_age_minutes(observed_at)
        if age_minutes is not None and age_minutes > 30:
            quality_flags.append("stale_observation")
        return {
            "available": True,
            "type": "measurement",
            "provider": "MeteoSchweiz",
            "source_url": url,
            "station_id": station["id"],
            "station_name": station["name"],
            "distance_km": station["distance_km"],
            "observed_at": observed_at,
            "observation_age_minutes": age_minutes,
            "fetched_at": _iso_now(),
            "wind_kn": wind,
            "gust_kn": gust,
            "direction_deg": direction,
            "temperature_c": _number(_first(row, "tre200s0")),
            "quality_flags": quality_flags,
            "method": "Offizielle 10-Minuten-Stationsmessung",
        }

    return _cached_fetch(key, ttl=600, stale_for=43_200, loader=load)


def get_measurement_history(spot: dict[str, Any]) -> dict[str, Any]:
    """Return seven days of genuine 10-minute station observations.

    No forecast or reanalysis values are used to fill gaps. At present this
    adapter is enabled only for configured MeteoSwiss stations.
    """
    station = spot.get("station")
    if not station:
        return {
            "available": False,
            "reason": "Für diesen Spot ist keine frei abrufbare Messhistorie eingebunden.",
            "fetched_at": _iso_now(),
        }
    station_id = station["id"].lower()
    url = METEOSWISS_RECENT_FILE.format(station=station_id)
    key = f"measurement-history:{station_id}"

    def load() -> dict[str, Any]:
        rows = _csv_rows(_fetch_text(url, timeout=15.0))
        parsed: list[tuple[datetime, dict[str, Any]]] = []
        for row in rows:
            raw_stamp = _first(row, "reference_timestamp", "timestamp", "time", "date")
            try:
                stamp = datetime.strptime(raw_stamp or "", "%d.%m.%Y %H:%M").replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            wind = _kmh_to_kn(_number(_first(row, "fu3010z0")))
            if wind is None:
                continue
            gust = _kmh_to_kn(_number(_first(row, "fu3010z1")))
            direction = _number(_first(row, "dkl010z0"))
            if gust is not None and gust < wind:
                gust = None
            if direction is not None and not 0 <= direction <= 360:
                direction = None
            parsed.append(
                (
                    stamp,
                    {
                        "time": stamp.isoformat(timespec="minutes").replace("+00:00", "Z"),
                        "wind_kn": wind,
                        "gust_kn": gust,
                        "direction_deg": direction,
                        "direction": direction_name(direction),
                    },
                )
            )
        if not parsed:
            raise ValueError("MeteoSwiss recent file contains no wind observations")
        latest = max(item[0] for item in parsed)
        start = latest - timedelta(days=7)
        records = [record for stamp, record in parsed if start < stamp <= latest]
        return {
            "available": True,
            "type": "measurement",
            "provider": "MeteoSchweiz",
            "station_id": station["id"],
            "station_name": station["name"],
            "distance_km": station["distance_km"],
            "source_url": url,
            "method": "Unveränderte 10-Minuten-Stationsmessungen; Datenlücken werden nicht modelliert.",
            "timezone": "UTC",
            "start_time": records[0]["time"],
            "end_time": records[-1]["time"],
            "fetched_at": _iso_now(),
            "records": records,
        }

    return _cached_fetch(key, ttl=600, stale_for=86_400, loader=load)


def _kmh_to_kn(value: float | None) -> float | None:
    return round(value / 1.852, 1) if value is not None else None


def direction_name(degrees: float | None) -> str | None:
    if degrees is None:
        return None
    names = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    return names[round(degrees / 22.5) % 16]


def quality_report(model: dict[str, Any], station: dict[str, Any]) -> dict[str, Any]:
    # Agreement with a model is useful, but cannot turn a regional station into
    # an on-spot measurement. Distance therefore imposes a hard, honest ceiling.
    score = 30 if model.get("available") else 0
    reasons: list[str] = []
    delta = None
    if station.get("available") and station.get("wind_kn") is not None:
        score += 35
        distance = station.get("distance_km", 999)
        if distance <= 1:
            score += 15
            ceiling = 100
            reasons.append("Messstation liegt direkt am Spot")
        elif distance <= 5:
            score += 12
            ceiling = 95
            reasons.append("Messstation liegt sehr nahe am Spot")
        elif distance <= 15:
            score += 5
            ceiling = 80
            reasons.append("Messstation ist eine regionale Referenz")
        elif distance <= 30:
            score += 2
            ceiling = 72
            reasons.append("Messstation ist nur regional repräsentativ")
        else:
            ceiling = 65
            reasons.append("Messstation ist weit entfernt")
        age = station.get("observation_age_minutes")
        if age is not None and age <= 20:
            score += 10
            reasons.append("Messung ist höchstens 20 Minuten alt")
        elif age is not None and age <= 40:
            score += 5
            ceiling = min(ceiling, 90)
            reasons.append("Messung ist leicht verzögert")
        elif age is not None:
            ceiling = min(ceiling, 70)
            reasons.append("Messung ist älter als 40 Minuten")
        else:
            reasons.append("Messalter ist nicht eindeutig bestimmbar")
        if station.get("quality_flags"):
            ceiling = min(ceiling, 70)
            reasons.append("Stationswert hat einen Plausibilitätswarnhinweis")
        if model.get("wind_kn") is not None:
            delta = round(abs(station["wind_kn"] - model["wind_kn"]), 1)
            if delta <= 3:
                score += 10
                reasons.append("Messung und Modell stimmen gut überein")
            elif delta <= 6:
                score += 5
                reasons.append("Messung und Modell weichen moderat ab")
            else:
                reasons.append("Messung und Modell weichen stark ab")
        score = min(score, ceiling)
        if ceiling < 100:
            reasons.append(f"Qualität wegen Messdistanz auf {ceiling}/100 begrenzt")
    else:
        reasons.append("Keine aktuelle Stationsmessung verfügbar")
    score = min(score, 100)
    label = "hoch" if score >= 80 else "mittel" if score >= 55 else "begrenzt"
    return {"score": score, "label": label, "delta_kn": delta, "reasons": reasons}


def kite_signal(spot: dict[str, Any], model: dict[str, Any], station: dict[str, Any]) -> dict[str, str]:
    wind = station.get("wind_kn") if station.get("available") else model.get("wind_kn")
    gust = station.get("gust_kn") if station.get("available") else model.get("gust_kn")
    limits = spot["kite"]
    if wind is None:
        return {"level": "unknown", "label": "Keine Aussage", "reason": "Aktuelle Daten fehlen."}
    if gust is not None and gust > limits["max_kn"]:
        return {"level": "red", "label": "Kritisch", "reason": "Böen liegen über dem konfigurierten Bereich."}
    if wind < limits["min_kn"]:
        return {"level": "amber", "label": "Eher zu wenig", "reason": "Wind liegt unter dem Spot-Schwellenwert."}
    return {"level": "green", "label": "Windfenster", "reason": "Windstärke liegt im konfigurierten Bereich; keine Sicherheitsfreigabe."}


def build_payload(spot_id: str, spot: dict[str, Any]) -> dict[str, Any]:
    # Independent providers run concurrently: worst-case latency is one timeout, not two.
    pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="wind-source")
    model_future = pool.submit(get_open_meteo, spot)
    station_future = pool.submit(get_meteoswiss, spot)
    done, _ = wait([model_future, station_future], timeout=8.0)

    def completed(future, provider: str) -> dict[str, Any]:
        if future not in done:
            return {
                "available": False,
                "provider": provider,
                "cache_status": "miss",
                "error": "HardTimeout",
                "fetched_at": _iso_now(),
            }
        try:
            return future.result()
        except Exception as exc:  # Provider failure must never take down the endpoint.
            return {
                "available": False,
                "provider": provider,
                "cache_status": "miss",
                "error": type(exc).__name__,
                "fetched_at": _iso_now(),
            }

    model = completed(model_future, "Open-Meteo")
    station = completed(station_future, "MeteoSchweiz")
    pool.shutdown(wait=False, cancel_futures=True)
    for source in (model, station):
        source["direction"] = direction_name(source.get("direction_deg"))
    return {
        "spot": {"id": spot_id, **spot},
        "model": model,
        "station": station,
        "quality": quality_report(model, station),
        "signal": kite_signal(spot, model, station),
        "generated_at": _iso_now(),
        "disclaimer": "Entscheidungshilfe, keine Sicherheits- oder Startfreigabe. Vor Ort Regeln, Warnungen und Bedingungen prüfen.",
    }
