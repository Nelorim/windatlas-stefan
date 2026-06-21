import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import create_app
from config import SPOTS
from services import direction_name, kite_signal, quality_report


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

    @patch("app.build_payload")
    def test_wind_endpoint(self, build_payload):
        build_payload.return_value = {"spot": {"id": "silvaplana"}}
        response = self.client.get("/api/v1/wind/silvaplana")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["spot"]["id"], "silvaplana")


class QualityTests(unittest.TestCase):
    def test_direction_compass(self):
        self.assertEqual(direction_name(0), "N")
        self.assertEqual(direction_name(225), "SW")

    def test_good_agreement_scores_high(self):
        model = {"available": True, "wind_kn": 15}
        station = {"available": True, "wind_kn": 16, "distance_km": 4}
        result = quality_report(model, station)
        self.assertEqual(result["label"], "hoch")
        self.assertEqual(result["delta_kn"], 1)

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

