import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import create_app
from config import SPOTS
from services import _daily_history, _observation_age_minutes, _timestamp_with_offset, direction_name, get_history, get_measurement_history, get_meteoswiss, get_open_meteo, kite_signal, quality_report


class AppTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config.update(TESTING=True)
        self.client = self.app.test_client()

    def test_health_check_never_needs_upstream(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["status"], "ok")

    def test_home_is_rendered(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"WindAtlas", response.data)
        self.assertIn(b"MeteoSchweiz", response.data)

    def test_forecast_periods_are_graph_only_and_quality_comes_first(self):
        response = self.client.get("/")
        self.assertNotIn(b'id="forecast-summaries"', response.data)
        self.assertIn(b">24 Stunden<", response.data)
        self.assertIn(b">3 Tage<", response.data)
        self.assertIn(b">7 Tage<", response.data)
        live_position = response.data.index(b'class="metric-grid primary-live"')
        quality_position = response.data.index(b'class="quality-card panel"')
        measurement_position = response.data.index(b'class="wind-card panel"')
        forecast_position = response.data.index(b'class="forecast panel primary-forecast"')
        decision_position = response.data.index(b'class="decision-grid"')
        advanced_position = response.data.index(b'id="advanced-data"')
        self.assertLess(quality_position, measurement_position)
        self.assertLess(live_position, forecast_position)
        self.assertLess(forecast_position, decision_position)
        self.assertLess(forecast_position, advanced_position)

    def test_javascript_is_revalidated_after_deploy(self):
        response = self.client.get("/static/app.js")
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-cache", response.headers["Cache-Control"])
        response.close()

    def test_unknown_spot_is_404(self):
        response = self.client.get("/api/v1/wind/atlantis")
        self.assertEqual(response.status_code, 404)

    def test_requested_international_spots_are_configured(self):
        expected = [
            "silvaplana", "colico", "berlingen", "loissin", "mui-ne",
            "jambiani", "selena-bay", "viana", "malcesine", "sulawesi",
            "softades",
        ]
        self.assertEqual(list(SPOTS), expected)
        self.assertNotIn("kb-zone", SPOTS)

    def test_unhooked_guides_cover_swiss_spots(self):
        self.assertIn("unhooked.ch", SPOTS["silvaplana"]["spotguide"]["url"])
        self.assertIn("unhooked.ch", SPOTS["berlingen"]["spotguide"]["url"])

    def test_kwind_is_not_enabled_after_kb_zone_removal(self):
        linked = {spot_id for spot_id, spot in SPOTS.items() if spot.get("kwind")}
        self.assertEqual(linked, set())

    def test_silvaplana_uses_current_kitesailing_weather_page(self):
        source = SPOTS["silvaplana"]["school"]
        self.assertTrue(source["url"].endswith("/spot/wetter-wassersport"))
        self.assertIn("Windrichtung", source["kind"])

    def test_mui_ne_uses_c2sky_live_page(self):
        self.assertIn("c2skykitecenter.com", SPOTS["mui-ne"]["school"]["url"])
        self.assertIn("14164", SPOTS["mui-ne"]["school"]["kind"])

    def test_selena_bay_does_not_use_kwind(self):
        self.assertIsNone(SPOTS["selena-bay"]["kwind"])

    def test_windguru_links_only_have_verified_station_distances(self):
        linked = {spot_id: spot["windguru"] for spot_id, spot in SPOTS.items() if spot.get("windguru")}
        self.assertEqual(set(linked), {"malcesine", "jambiani", "berlingen", "selena-bay", "mui-ne"})
        for source in linked.values():
            self.assertTrue(source["url"].startswith("https://www.windguru.cz/"))
            self.assertTrue(source["stations"])
            self.assertTrue(all(item["distance_km"] >= 0 for item in source["stations"]))

    def test_mui_ne_windguru_station_is_direct(self):
        source = SPOTS["mui-ne"]["windguru"]
        self.assertTrue(source["url"].endswith("/station/14164"))
        self.assertEqual(source["stations"][0]["distance_km"], 0)

    def test_selena_bay_keeps_hurghada_windguru_reference(self):
        self.assertEqual(SPOTS["selena-bay"]["windguru"]["stations"][0]["distance_km"], 2.2)

    def test_jambiani_uses_direct_windguru_station(self):
        source = SPOTS["jambiani"]["windguru"]
        self.assertTrue(source["url"].endswith("/station/5839"))
        self.assertEqual(source["stations"][0]["distance_km"], 0)

    def test_requested_external_measurements_are_linked(self):
        expected_hosts = {
            "viana": "weatherlink.com",
            "malcesine": "kitecampione.net",
            "loissin": "windfinder.com",
        }
        for spot_id, host in expected_hosts.items():
            self.assertIn(host, SPOTS[spot_id]["external_measurements"][0]["url"])
        self.assertEqual(SPOTS["loissin"]["external_measurements"][0]["distance_km"], 8.2)

    def test_silvaplana_uses_free_sia_live_data(self):
        station = SPOTS["silvaplana"]["station"]
        self.assertEqual(station["id"], "SIA")
        self.assertEqual(station["name"], "Segl-Maria")
        self.assertLess(station["distance_km"], 5)

    @patch("services._fetch_text")
    def test_free_sia_csv_is_normalized(self, fetch_text):
        fetch_text.return_value = (
            "station_abbr;reference_timestamp;tre200s0;dkl010z0;fu3010z0;fu3010z1\n"
            "SIA;22.06.2026 12:30;23;239;16.6;27.4\n"
        )
        source = get_meteoswiss(SPOTS["silvaplana"])
        self.assertTrue(source["available"])
        self.assertEqual(source["wind_kn"], 9.0)
        self.assertEqual(source["gust_kn"], 14.8)
        self.assertEqual(source["direction_deg"], 239)

    @patch("services._fetch_text")
    def test_sia_measurement_history_contains_only_recent_real_values(self, fetch_text):
        fetch_text.return_value = (
            "station_abbr;reference_timestamp;dkl010z0;fu3010z0;fu3010z1\n"
            "SIA;14.06.2026 12:00;180;9.26;18.52\n"
            "SIA;21.06.2026 11:50;225;14.816;22.224\n"
            "SIA;21.06.2026 12:00;230;16.668;24.076\n"
        )
        source = get_measurement_history(SPOTS["silvaplana"])
        self.assertTrue(source["available"])
        self.assertEqual(source["type"], "measurement")
        self.assertEqual(len(source["records"]), 2)
        self.assertEqual(source["records"][0]["wind_kn"], 8.0)
        self.assertEqual(source["records"][0]["direction"], "SW")
        self.assertIn("nicht modelliert", source["method"])

    @patch("services._fetch_json")
    def test_forecast_contains_full_seven_days(self, fetch_json):
        times = [f"2026-06-{22 + index // 24:02d}T{index % 24:02d}:00" for index in range(168)]
        fetch_json.return_value = {
            "current": {
                "time": times[0], "temperature_2m": 15, "wind_speed_10m": 8,
                "wind_direction_10m": 220, "wind_gusts_10m": 14, "cloud_cover": 10,
            },
            "hourly": {
                "time": times, "wind_speed_10m": [8] * 168,
                "wind_direction_10m": [220] * 168, "wind_gusts_10m": [14] * 168,
                "temperature_2m": [15] * 168, "precipitation_probability": [0] * 168,
            },
        }
        spot = {"lat": 88.1, "lon": 77.2}
        source = get_open_meteo(spot)
        self.assertEqual(len(source["forecast"]), 168)
        self.assertIn("forecast_days=7", fetch_json.call_args.args[0])

    @patch("services._fetch_json")
    def test_history_is_loaded_in_parallel_year_chunks(self, fetch_json):
        fetch_json.return_value = {
            "daily": {
                "time": ["2026-06-20"],
                "wind_speed_10m_max": [12],
                "wind_gusts_10m_max": [18],
                "wind_direction_10m_dominant": [225],
            }
        }
        result = get_history(SPOTS["silvaplana"])
        self.assertTrue(result["available"])
        self.assertGreaterEqual(fetch_json.call_count, 5)
        self.assertEqual(result["records"][0]["direction"], "SW")

    @patch("app.build_payload")
    def test_wind_endpoint(self, build_payload):
        build_payload.return_value = {"spot": {"id": "silvaplana"}}
        response = self.client.get("/api/v1/wind/silvaplana")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["spot"]["id"], "silvaplana")

    @patch("app.get_history")
    def test_history_endpoint(self, get_history):
        get_history.return_value = {"available": True, "records": [{"date": "2026-06-20", "wind_kn": 12}]}
        response = self.client.get("/api/v1/history/viana")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["available"])
        self.assertEqual(response.json["records"][0]["wind_kn"], 12)

    @patch("app.get_measurement_history")
    def test_measurement_history_endpoint(self, get_measurement_history):
        get_measurement_history.return_value = {"available": True, "type": "measurement", "records": []}
        response = self.client.get("/api/v1/measurement-history/silvaplana")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["type"], "measurement")


class QualityTests(unittest.TestCase):
    def test_spot_local_utc_offset_is_attached(self):
        self.assertEqual(_timestamp_with_offset("2026-06-22T21:00", 10_800), "2026-06-22T21:00+03:00")
        self.assertEqual(_timestamp_with_offset("2026-06-22T18:00", -18_000), "2026-06-22T18:00-05:00")

    def test_meteoswiss_timestamp_age_is_parsed(self):
        self.assertIsNotNone(_observation_age_minutes("22.06.2026 12:30"))

    def test_daily_history_includes_direction(self):
        records = _daily_history({"daily": {
            "time": ["2026-06-20"],
            "wind_speed_10m_max": [14.2],
            "wind_gusts_10m_max": [20.1],
            "wind_direction_10m_dominant": [225],
        }})
        self.assertEqual(records[0]["direction"], "SW")
        self.assertEqual(records[0]["wind_kn"], 14.2)

    def test_direction_compass(self):
        self.assertEqual(direction_name(0), "N")
        self.assertEqual(direction_name(225), "SW")

    def test_good_agreement_scores_high(self):
        model = {"available": True, "wind_kn": 15}
        station = {"available": True, "wind_kn": 16, "distance_km": 4}
        result = quality_report(model, station)
        self.assertEqual(result["label"], "hoch")
        self.assertEqual(result["delta_kn"], 1)

    def test_regional_station_cannot_claim_full_quality(self):
        model = {"available": True, "wind_kn": 15}
        station = {"available": True, "wind_kn": 15, "distance_km": 10}
        result = quality_report(model, station)
        self.assertEqual(result["score"], 80)

    def test_old_station_measurement_is_capped(self):
        model = {"available": True, "wind_kn": 15}
        station = {"available": True, "wind_kn": 15, "distance_km": 0, "observation_age_minutes": 90}
        result = quality_report(model, station)
        self.assertEqual(result["score"], 70)

    def test_model_only_is_limited(self):
        result = quality_report({"available": True, "wind_kn": 12}, {"available": False})
        self.assertEqual(result["label"], "begrenzt")

    def test_gust_limit_is_critical(self):
        result = kite_signal(
            SPOTS["silvaplana"],
            {"available": True, "wind_kn": 15, "gust_kn": 35},
            {"available": False},
        )
        self.assertEqual(result["level"], "red")


if __name__ == "__main__":
    unittest.main()
