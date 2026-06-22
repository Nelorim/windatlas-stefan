import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import create_app
from config import SPOTS
from services import _daily_history, direction_name, kite_signal, quality_report


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

    def test_unknown_spot_is_404(self):
        response = self.client.get("/api/v1/wind/atlantis")
        self.assertEqual(response.status_code, 404)

    def test_requested_international_spots_are_configured(self):
        expected = {
            "silvaplana", "viana", "malcesine", "colico", "loissin",
            "jambiani", "berlingen", "sulawesi", "softades", "kb-zone",
            "selena-bay", "mui-ne",
        }
        self.assertEqual(set(SPOTS), expected)

    def test_unhooked_guides_cover_swiss_spots(self):
        self.assertIn("unhooked.ch", SPOTS["silvaplana"]["spotguide"]["url"])
        self.assertIn("unhooked.ch", SPOTS["berlingen"]["spotguide"]["url"])

    def test_kwind_is_only_enabled_for_kb_zone(self):
        linked = {spot_id for spot_id, spot in SPOTS.items() if spot.get("kwind")}
        self.assertEqual(linked, {"kb-zone"})
        self.assertEqual(SPOTS["kb-zone"]["kwind"]["station_id"], "64f17bf1779ccbba6bfef479")

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
        self.assertEqual(set(linked), {"malcesine", "jambiani", "berlingen", "kb-zone", "selena-bay", "mui-ne"})
        for source in linked.values():
            self.assertTrue(source["url"].startswith("https://www.windguru.cz/"))
            self.assertTrue(source["stations"])
            self.assertTrue(all(item["distance_km"] >= 0 for item in source["stations"]))

    def test_mui_ne_windguru_station_is_direct(self):
        source = SPOTS["mui-ne"]["windguru"]
        self.assertTrue(source["url"].endswith("/station/14164"))
        self.assertEqual(source["stations"][0]["distance_km"], 0)

    def test_hurghada_spots_share_windguru_reference(self):
        self.assertIs(SPOTS["kb-zone"]["windguru"], SPOTS["selena-bay"]["windguru"])
        self.assertEqual(SPOTS["kb-zone"]["windguru"]["stations"][0]["distance_km"], 2.2)

    def test_jambiani_uses_direct_windguru_station(self):
        source = SPOTS["jambiani"]["windguru"]
        self.assertTrue(source["url"].endswith("/station/5839"))
        self.assertEqual(source["stations"][0]["distance_km"], 0)

    def test_requested_external_measurements_are_linked(self):
        expected_hosts = {
            "silvaplana": "meteoschweiz.admin.ch",
            "viana": "weatherlink.com",
            "malcesine": "kitecampione.net",
            "loissin": "windfinder.com",
        }
        for spot_id, host in expected_hosts.items():
            self.assertIn(host, SPOTS[spot_id]["external_measurements"][0]["url"])
        self.assertEqual(SPOTS["loissin"]["external_measurements"][0]["distance_km"], 8.2)

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


class QualityTests(unittest.TestCase):
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
