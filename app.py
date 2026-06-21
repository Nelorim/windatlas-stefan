"""WindAtlas CH — responsive, observable and resilient Flask application."""

from __future__ import annotations

import os
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template

from config import SPOTS
from services import build_payload


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.update(JSON_SORT_KEYS=False)

    @app.after_request
    def response_headers(response):
        if response.content_type.startswith("text/html"):
            response.headers["Cache-Control"] = "public, max-age=60"
        elif response.content_type.startswith(("text/css", "application/javascript")):
            response.headers["Cache-Control"] = "public, max-age=86400"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    @app.get("/")
    def index():
        public_spots = [
            {
                "id": spot_id,
                "name": spot["name"],
                "region": spot["region"],
                "lat": spot["lat"],
                "lon": spot["lon"],
            }
            for spot_id, spot in SPOTS.items()
        ]
        return render_template("index.html", spots=public_spots)

    @app.get("/api/v1/spots")
    def spots():
        return jsonify(
            [
                {
                    "id": spot_id,
                    "name": spot["name"],
                    "region": spot["region"],
                    "lat": spot["lat"],
                    "lon": spot["lon"],
                }
                for spot_id, spot in SPOTS.items()
            ]
        )

    @app.get("/api/v1/wind/<spot_id>")
    def wind(spot_id: str):
        spot = SPOTS.get(spot_id)
        if spot is None:
            return jsonify({"error": "Unbekannter Spot"}), 404
        return jsonify(build_payload(spot_id, spot))

    @app.get("/healthz")
    def health():
        # Never call upstream providers here: Render health checks must be instant.
        return jsonify(
            {
                "status": "ok",
                "service": "windatlas-ch",
                "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
        )

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
