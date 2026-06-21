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
        raw = _fetch_json(url)
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
    archive_url = f"{OPEN_METEO_ARCHIVE_URL}?{urllib.parse.urlencode({**common, 'start_date': start.isoformat(), 'end_date': archive_end.isoformat()})}"
    recent_url = f"{OPEN_METEO_URL}?{urllib.parse.urlencode({**common, 'past_days': 7, 'forecast_days': 1})}"
    key = f"history:{spot['lat']}:{spot['lon']}:{today.isoformat()}"

    def load() -> dict[str, Any]:
        pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="history-source")
        archive_future = pool.submit(_fetch_json, archive_url, 12.0)
        recent_future = pool.submit(_fetch_json, recent_url, 8.0)
        done, _ = wait([archive_future, recent_future], timeout=13.0)
        if archive_future not in done:
            pool.shutdown(wait=False, cancel_futures=True)
            raise TimeoutError("historical archive timeout")
        records = {item["date"]: item for item in _daily_history(archive_future.result())}
        if recent_future in done:
            for item in _daily_history(recent_future.result()):
                records[item["date"]] = item
        pool.shutdown(wait=False, cancel_futures=True)
        ordered = [records[key] for key in sorted(records) if start.isoformat() <= key <= today.isoformat()]
        return {
            "available": True,
            "type": "reanalysis",
            "provider": "Open-Meteo Historical Weather",
            "source_url": archive_url,
            "method": "Tägliche Reanalyse/Modellrekonstruktion, keine lückenlose Stationsmessung",
            "start_date": start.isoformat(),
            "end_date": today.isoformat(),
            "fetched_at": _iso_now(),
            "records": ordered,
        }

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
        return {
            "available": True,
            "type": "measurement",
            "provider": "MeteoSchweiz",
            "source_url": url,
            "station_id": station["id"],
            "station_name": station["name"],
            "distance_km": station["distance_km"],
            "observed_at": _first(
                row, "reference_timestamp", "timestamp", "time", "date"
            ),
            "fetched_at": _iso_now(),
            "wind_kn": _kmh_to_kn(_number(_first(row, "fu3010z0"))),
            "gust_kn": _kmh_to_kn(_number(_first(row, "fu3010z1"))),
            "direction_deg": _number(_first(row, "dkl010z0")),
            "temperature_c": _number(_first(row, "tre200s0")),
            "method": "Offizielle 10-Minuten-Stationsmessung",
        }

    return _cached_fetch(key, ttl=600, stale_for=43_200, loader=load)


def _kmh_to_kn(value: float | None) -> float | None:
    return round(value / 1.852, 1) if value is not None else None


def direction_name(degrees: float | None) -> str | None:
    if degrees is None:
        return None
    names = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    return names[round(degrees / 22.5) % 16]


def quality_report(model: dict[str, Any], station: dict[str, Any]) -> dict[str, Any]:
    score = 45 if model.get("available") else 0
    reasons: list[str] = []
    delta = None
    if station.get("available") and station.get("wind_kn") is not None:
        score += 30
        distance = station.get("distance_km", 999)
        if distance <= 15:
            score += 10
            reasons.append("Messstation liegt nahe am Spot")
        elif distance <= 30:
            score += 4
            reasons.append("Messstation ist nur regional repräsentativ")
        else:
            reasons.append("Messstation ist weit entfernt")
        if model.get("wind_kn") is not None:
            delta = round(abs(station["wind_kn"] - model["wind_kn"]), 1)
            if delta <= 3:
                score += 15
                reasons.append("Messung und Modell stimmen gut überein")
            elif delta <= 6:
                score += 7
                reasons.append("Messung und Modell weichen moderat ab")
            else:
                reasons.append("Messung und Modell weichen stark ab")
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
    done, _ = wait([model_future, station_future], timeout=5.0)

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
