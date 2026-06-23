"""Curated spot configuration. Keep editorial facts separate from live data."""

# Windguru values stay on Windguru. These entries only link curated nearby
# live stations whose name and distance could be verified on the spot page.
WINDGURU_MALCESINE = {
    "url": "https://www.windguru.cz/49196",
    "stations": [
        {"name": "Decollo Malcesine", "distance_km": 4.3},
        {"name": "Waterproofworld Brenzone", "distance_km": 7.3},
    ],
    "note": "See- und Hangstationen getrennt beurteilen; WindAtlas übernimmt keine Windguru-Rohwerte.",
}

WINDGURU_JAMBIANI = {
    "url": "https://www.windguru.cz/station/5839",
    "stations": [
        {"name": "Jambiani Kibijija / Coconuts Kite", "distance_km": 0},
    ],
    "note": "Direkte Windguru-Livestation in Jambiani; Gezeiten und lokale Abschattung zusätzlich prüfen.",
}

WINDGURU_BERLINGEN = {
    "url": "https://www.windguru.cz/246339",
    "stations": [
        {"name": "Startplatz Rebberg / Windbird", "distance_km": 11.5},
        {"name": "WSCÜ", "distance_km": 14.4},
    ],
    "note": "Regionale Referenz, keine Messung direkt am Kite-Einstieg in Berlingen.",
}

WINDGURU_HURGHADA = {
    "url": "https://www.windguru.cz/1251074",
    "stations": [
        {"name": "Hurghada / Paradise Kitesurf", "distance_km": 2.2},
        {"name": "Ohana Kiteboarding", "distance_km": 2.6},
    ],
    "note": "Nahe Windguru-Referenzstationen für Selena Bay im Küstenabschnitt nördlich von Hurghada.",
}

WINDGURU_MUI_NE = {
    "url": "https://www.windguru.cz/station/14164",
    "stations": [
        {"name": "Mui Ne C2SKY LIVE WINDSTATION", "distance_km": 0},
    ],
    "note": "Direkte Station am C2Sky-Kitecenter; Messwerte und Archiv bleiben bei Windguru.",
}

SPOTS = {
    "silvaplana": {
        "name": "Silvaplana",
        "region": "Engadin · Schweiz",
        "lat": 46.459,
        "lon": 9.795,
        "station": {"id": "SIA", "name": "Segl-Maria", "distance_km": 4.1},
        "kwind": None,
        "external_measurements": [],
        "kite": {"min_kn": 9, "max_kn": 28, "directions": ["S", "SW", "WSW"]},
        "local_note": "Der thermische Malojawind ist lokal geprägt und wird vom Talmodell oft unterschätzt.",
        "spotguide": {
            "name": "Unhooked Spotguide",
            "url": "https://www.unhooked.ch/2008/spotguide/silvaplana/",
            "wind_info": "Lokaler Richtungscheck: Der Maloja benötigt eine südwestliche Grundströmung; Nordströmung/Julierwind kann die Thermik verhindern und sehr böig werden.",
        },
        "school": {
            "name": "Swiss Kitesurf / Kitesailing",
            "url": "https://www.kitesailing.ch/spot/wetter-wassersport",
            "kind": "Kiteschule direkt am Spot · Live-Mittelwind, Windspitzen und Windrichtung",
            "verified": "2026-06-22",
        },
    },
    "viana": {
        "name": "Viana do Castelo",
        "region": "Cabedelo · Portugal",
        "lat": 41.681,
        "lon": -8.833,
        "station": None,
        "kwind": None,
        "external_measurements": [
            {
                "name": "WeatherLink Praia do Cabedelo",
                "url": "https://www.weatherlink.com/embeddablePage/show/0722f5db3b314dd9a179ba37f6c4b772/fullscreen",
                "embed_url": "https://www.weatherlink.com/embeddablePage/show/0722f5db3b314dd9a179ba37f6c4b772/fullscreen",
                "kind": "Live-Wetterstation am Spot Viana do Castelo / Cabedelo",
                "note": "Externe Davis-WeatherLink-Anzeige; Werte werden nicht serverseitig kopiert.",
            },
        ],
        "kite": {"min_kn": 11, "max_kn": 34, "directions": ["N", "NNW", "NW"]},
        "local_note": "Atlantikspot mit thermischer Verstärkung und Welle; Gezeiten und Shorebreak vor Ort prüfen.",
        "school": {
            "name": "Kite Voodoo",
            "url": "https://kitevoodoo.com/",
            "kind": "Kiteschule an der Praia do Cabedelo",
            "verified": "2026-06-21",
        },
    },
    "malcesine": {
        "name": "Malcesine",
        "region": "Gardasee · Italien",
        "lat": 45.764,
        "lon": 10.813,
        "station": None,
        "kwind": None,
        "windguru": WINDGURU_MALCESINE,
        "external_measurements": [
            {
                "name": "Kitecampione Anemometer",
                "url": "https://www.kitecampione.net/",
                "embed_url": "https://www.kitecampione.net/",
                "kind": "Live-Anemometer in Campione del Garda",
                "note": "Regionale Gardasee-Referenz, keine direkte Messung in Malcesine.",
            },
        ],
        "kite": {"min_kn": 9, "max_kn": 30, "directions": ["N", "S"]},
        "local_note": "Peler am Morgen und Ora am Nachmittag sind thermisch geprägt; Startregeln und Lift-Betrieb beachten.",
        "school": {
            "name": "Easykite Malcesine",
            "url": "https://www.easykite.it/",
            "kind": "IKO-Kiteschule · veröffentlicht lokalen Wind-/Liftstatus",
            "verified": "2026-06-21",
        },
    },
    "colico": {
        "name": "Colico",
        "region": "Comer See · Italien",
        "lat": 46.138,
        "lon": 9.377,
        "station": None,
        "kwind": None,
        "kite": {"min_kn": 9, "max_kn": 29, "directions": ["S", "SSW", "N"]},
        "local_note": "Die Breva baut sich lokal am nördlichen Comer See auf und kann vom Flächenmodell unterschätzt werden.",
        "school": {
            "name": "Adrenakite",
            "url": "https://www.adrenakite.it/",
            "kind": "Kiteschule und Lift-Service am Comer See",
            "verified": "2026-06-21",
        },
    },
    "loissin": {
        "name": "Loissin",
        "region": "Ostsee · Deutschland",
        "lat": 54.130,
        "lon": 13.510,
        "station": None,
        "kwind": None,
        "external_measurements": [
            {
                "name": "Windfinder Greifswald",
                "url": "https://de.windfinder.com/forecast/greifswald",
                "kind": "Lokale Stationsmessung als regionale Referenz für Loissin",
                "distance_km": 8.2,
                "note": "Windfinder-Login und Premium-Abo bleiben ausschließlich im Browser des Nutzers.",
            },
        ],
        "kite": {"min_kn": 10, "max_kn": 30, "directions": ["W", "NW", "N", "NE"]},
        "local_note": "Flaches Boddenrevier; Startzone, Schulungsbereiche und lokale Naturschutzregeln beachten.",
        "school": {
            "name": "Kitesafe Loissin",
            "url": "https://kitesafe.de/",
            "kind": "Wassersportcenter und IKO-Kiteschule direkt am Greifswalder Bodden",
            "verified": "2026-06-21",
        },
    },
    "jambiani": {
        "name": "Jambiani",
        "region": "Sansibar · Tansania",
        "lat": -6.318,
        "lon": 39.548,
        "station": None,
        "kwind": None,
        "windguru": WINDGURU_JAMBIANI,
        "kite": {"min_kn": 10, "max_kn": 31, "directions": ["NE", "E", "SE"]},
        "local_note": "Starker Gezeiteneinfluss in der Lagune; fahrbare Wassertiefe und Riffzugang vor Ort prüfen.",
        "school": {
            "name": "Coconuts Kite",
            "url": "https://coconutskite.com/",
            "kind": "PRO-IKO-Kiteschule direkt in Jambiani",
            "verified": "2026-06-21",
        },
    },
    "berlingen": {
        "name": "Berlingen",
        "region": "Bodensee · Schweiz",
        "lat": 47.671,
        "lon": 9.020,
        "station": {"id": "GUT", "name": "Güttingen", "distance_km": 31},
        "kwind": None,
        "windguru": WINDGURU_BERLINGEN,
        "kite": {"min_kn": 10, "max_kn": 28, "directions": ["W", "NW", "NE", "E"]},
        "local_note": "Die MeteoSchweiz-Station liegt nicht direkt am Spot; regionale Livequellen und die Sichtprüfung am See ergänzend nutzen.",
        "spotguide": {
            "name": "Unhooked Spotguide",
            "url": "https://www.unhooked.ch/2008/spotguide/berlingen/",
            "wind_info": "Lokaler Richtungscheck: SW–W wird durch den Düseneffekt verstärkt; SW ist häufig böig, West meist besser und Nordost/Bise konstanter.",
        },
        "school": None,
    },
    "sulawesi": {
        "name": "Sulawesi · Jeneponto",
        "region": "Mallasoro · Indonesien",
        "lat": -5.6474,
        "lon": 119.5714,
        "station": None,
        "kwind": None,
        "kite": {"min_kn": 11, "max_kn": 35, "directions": ["E", "ESE", "SE"]},
        "local_note": "Der konkrete Spot ist Jeneponto/Mallasoro in Süd-Sulawesi; Hauptwindsaison ist typischerweise Mai bis Oktober.",
        "school": {
            "name": "Jeneponto Kitesurfing",
            "url": "https://indonesiakitesurfing.com/jeneponto-hotel-beach/",
            "kind": "Kiteresort und Schule direkt an der Mallasoro-Lagune",
            "verified": "2026-06-21",
        },
    },
    "softades": {
        "name": "Kiti / Softades Beach",
        "region": "Larnaca · Zypern",
        "lat": 34.8171,
        "lon": 33.5480,
        "station": None,
        "kwind": None,
        "kite": {"min_kn": 10, "max_kn": 31, "directions": ["SW", "WSW", "W"]},
        "local_note": "Thermik verstärkt sich meist nach Mittag; nur ausgewiesene Kitebereiche und lokale Regeln nutzen.",
        "school": {
            "name": "Kahuna Surfhouse",
            "url": "https://kahunasurfhouse.eu/",
            "kind": "Lizenzierte Kiteschule an Softades Beach · Live-Windanzeige",
            "verified": "2026-06-21",
        },
    },
    "selena-bay": {
        "name": "Selena Bay",
        "region": "Hurghada · Ägypten",
        "lat": 27.3177,
        "lon": 33.7108,
        "station": None,
        "kwind": None,
        "windguru": WINDGURU_HURGHADA,
        "kite": {"min_kn": 11, "max_kn": 34, "directions": ["N", "NNW", "NW"]},
        "local_note": "Rotes-Meer-Spot mit typischem Nordwind; Windabdeckung, Riff und Centerregeln vor Ort prüfen.",
        "school": {
            "name": "Selena Bay Resort",
            "url": "https://selenabay.com/home/",
            "kind": "Lokaler Resort- und Wassersportzugang",
            "verified": "2026-06-21",
        },
    },
    "mui-ne": {
        "name": "Mui Ne",
        "region": "Phan Thiet · Vietnam",
        "lat": 10.9412,
        "lon": 108.1938,
        "station": None,
        "kwind": None,
        "windguru": WINDGURU_MUI_NE,
        "kite": {"min_kn": 11, "max_kn": 35, "directions": ["NE", "ENE", "E", "SW", "WSW"]},
        "local_note": "C2Sky liegt direkt am Strand von Mui Ne. Die veröffentlichte Live-Messung stammt aus einer eingebundenen Windguru-Station; Monsunrichtung und Shorebreak vor Ort prüfen.",
        "school": {
            "name": "C2Sky Kitecenter",
            "url": "https://c2skykitecenter.com/de/mui-ne-webcam-2/",
            "kind": "IKO-Kiteschule direkt am Spot · Windguru-Livemessung (Spot 14164) und Webcam",
            "verified": "2026-06-22",
        },
    },
}

# Product order: nearest/high-priority spots first. Dict insertion order is
# preserved by Flask/Jinja and therefore controls both navigation and API lists.
SPOT_ORDER = (
    "silvaplana",
    "colico",
    "berlingen",
    "loissin",
    "mui-ne",
    "jambiani",
    "selena-bay",
    "viana",
    "malcesine",
    "sulawesi",
    "softades",
)
SPOTS = {spot_id: SPOTS[spot_id] for spot_id in SPOT_ORDER}
