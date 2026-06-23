# WindAtlas CH — stabile Neuarchitektur

Eine schnelle, mobile Windübersicht für ausgewählte Kite- und Foilspots in Europa, Afrika und Asien. Die App trennt echte Messungen konsequent von Modellwerten und bleibt auch dann bedienbar, wenn eine Wetterquelle ausfällt.

Für Silvaplana enthält die App zusätzlich eine separate Wochenansicht mit den
offiziellen MeteoSchweiz-10-Minuten-Messungen (Mittelwind, Böen und Richtung).
Die lokale Kitesailing-Seite bleibt als Live-/Kurzzeitreferenz direkt am Spot
verlinkt. Datenlücken werden niemals mit Modellwerten aufgefüllt.

Die Messwoche wird ohne Tagesauswahl als durchgehende Kurve dargestellt; direkt
an der Kurve stehen ablesbare Windwerte und darunter sieben Tageskarten mit
Mittelwind, Richtung und Böenmaximum. Für die mögliche Zukunft gibt es getrennt
gekennzeichnete Open-Meteo-Grafiken für 24 Stunden, die nächsten Stunden plus
zwei Tage sowie sieben Tage.

Alle Kurvenbeschriftungen kombinieren nun lokale Spot-Uhrzeit und Windwert.
Tageskarten und die gemessene Wochenkurve weisen das Böenmaximum zusätzlich mit
Uhrzeit aus. Die Prognosegrafik wird bei sämtlichen konfigurierten Spots geladen;
eine gemessene Historie erscheint nur bei tatsächlich angebundener Messstation.

Auf Mobilgeräten bleiben Kennzahlen und Tageskarten in einer einspaltigen,
lesbaren Ansicht. Nur die eigentliche Kurve lässt sich horizontal wischen; ein
sichtbarer Hinweis kennzeichnet dies. Die Monatsansicht wechselt unter 520 px
in eine zweispaltige Tagesliste und erzeugt keinen horizontalen Seitenüberlauf.

## Was diese Version stabil macht

- Die Startseite lädt **ohne Wetterabfrage**. Externe APIs können den Serverstart nicht mehr blockieren.
- `/healthz` ist rein lokal und antwortet sofort.
- Open-Meteo und MeteoSchweiz werden parallel abgefragt. Der Server erlaubt Open-Meteo bei einem kalten Render-Start bis zu sieben Sekunden, ohne die andere Quelle zu blockieren.
- Servercache: 5 Minuten für Modelle, 10 Minuten für Messungen.
- Stale-if-error: letzte gültige Modellwerte bis 6 Stunden, Messwerte bis 12 Stunden – sichtbar als veraltet markiert.
- Browsercache als letzte Rückfallebene.
- Keine Datenbank und kein schweres Frontend-Buildsystem.

## Datenqualität

| Quelle | Einordnung | Aktualisierung |
|---|---|---|
| MeteoSchweiz SwissMetNet | echte automatische Stationsmessung | 10 Minuten |
| Open-Meteo | Wettermodell am Spot, keine Messung | typischerweise 1–6 Stunden je Modell |
| Windguru Live Wind | verlinkte nahe Messstationen mit geprüfter Distanz; keine kopierten Rohwerte | abhängig von der Station |
| WeatherLink, Windfinder, Kitecampione | zusätzliche externe Live-Seiten; kein serverseitiges Kopieren | abhängig vom Anbieter |
| Kiteschulen / Clubs | öffentlich geprüfter lokaler Kontext | redaktionelles Prüfdatum |

Der Qualitätswert berücksichtigt Quellenverfügbarkeit, Stationsdistanz und Abweichung zwischen Messung und Modell. Er ist transparent und bewusst konservativ. Die Kite-Ampel ist nur eine Entscheidungshilfe, niemals eine Sicherheitsfreigabe.

## Windhistorie

Für jeden konfigurierten Spot stehen vier Ansichten bereit: **Woche**, **Monat**, **Jahr** und **5 Jahre**. Die Monatsansicht zeigt jeden Kalendertag mit Tagesmaximum, Böenspitze und – sofern vorhanden – dominanter Windrichtung. Jahres- und Fünfjahresansicht verdichten dieselben Tageswerte zu übersichtlichen Vergleichen.

Die Historie stammt aus der Open-Meteo Historical Weather API. Es handelt sich um Reanalyse- beziehungsweise Modellwerte am Spot, nicht um eine lückenlose Historie lokaler Messstationen. Das wird in der Oberfläche ausdrücklich gekennzeichnet. Historische Antworten werden sechs Stunden gecacht; bei einer kurzfristigen Störung kann der letzte gültige Stand bis zu sieben Tage weiter angezeigt werden.

Die fünf Kalenderjahre werden als getrennte Jahresabfragen parallel geladen. Dadurch bleibt die Antwort klein und schnell; fällt ein einzelnes Archivjahr aus, werden die übrigen Jahre angezeigt und als Teildaten gekennzeichnet, statt die gesamte Historie zu verwerfen.

Falls Open-Meteo Anfragen von der gemeinsam genutzten Render-Ausgangsadresse mit einem HTTP-Fehler ablehnt, fragt der Browser des Besuchers dieselben kostenlosen öffentlichen Endpunkte direkt ab. Dieser CORS-Fallback stellt Live-Prognose und Jahresarchive wieder her, ohne API-Schlüssel, kostenpflichtige Dienste oder Weitergabe persönlicher Zugangsdaten.

Für Silvaplana wird die frei verfügbare MeteoSchweiz-Station Segl-Maria (`SIA`) direkt aus der offiziellen 10-Minuten-CSV gelesen. Sie liegt rund 4,1 km vom Spot entfernt und ersetzt Samedan als Hauptreferenz. Windmittel, Böe, Richtung, Messzeit und Plausibilitätsstatus werden normalisiert; ein veralteter oder inkonsistenter Wert wird im Qualitätswert deutlich begrenzt.

Mui Ne (Vietnam) ist als weiterer Spot enthalten. Die lokale Quelle ist die C2Sky-Webcamseite mit eingebundener Windguru-Livestation `14164`; Open-Meteo bleibt als klar gekennzeichneter Modellvergleich bestehen.

Weitere konkret zugeordnete Messseiten sind WeatherLink Praia do Cabedelo für Viana do Castelo, Kitecampione als regionale Gardasee-Referenz für Malcesine und Windfinder Greifswald als 8,2 km entfernte Referenz für Loissin. Ein vorhandenes Windfinder-Premium-Abo wird nur in der persönlichen Browsersitzung genutzt; WindAtlas speichert weder Zugangsdaten noch Premium-Inhalte.

Diese Ausgabe verwendet ausschließlich kostenlose Zugänge. WeatherLink und Kitecampione werden als öffentliche Messseiten eingebettet, sofern der Anbieter das Einbetten im Browser zulässt. Kostenpflichtige WeatherLink- und Windfinder-APIs werden nicht verwendet; Windfinder bleibt eine externe Referenzseite. Es findet kein HTML-Scraping und keine Weiterverteilung geschützter Rohdaten statt.

Windguru Live Wind ist zusätzlich für Malcesine, Jambiani, Berlingen, Selena Bay und Mui Ne verknüpft. Angezeigt werden nur redaktionell bestätigte Stationsnamen und Distanzen. Bei Colico und Silvaplana wurden nahe Bergstationen bewusst nicht als Spotmessung übernommen; für Viana, Loissin, Sulawesi und Softades fehlt derzeit eine ausreichend eindeutig bestätigte nahe Windguru-Messstation. Externe Windguru-Werte erhöhen den WindAtlas-Qualitätswert nicht automatisch.

Offizielle Dokumentation:

- [MeteoSchweiz automatische Wetterstationen](https://opendatadocs.meteoswiss.ch/a-data-groundbased/a1-automatic-weather-stations)
- [Open-Meteo API-Dokumentation](https://open-meteo.com/en/docs)
- [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api)

## Lokal starten

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Danach: <http://localhost:5000>

Tests:

```bash
python -m unittest discover -s tests -v
```

## Render deployen

1. Den gesamten Inhalt dieses Ordners in das GitHub-Repository hochladen.
2. In Render **New → Blueprint** wählen und das Repository verbinden.
3. Render liest `render.yaml`; Build-, Start- und Health-Check-Befehle sind bereits definiert.
4. Erst deployen, danach `/healthz` und dann die Startseite prüfen.

Für einen bestehenden Web Service können dieselben Werte manuell gesetzt werden:

- Build: `pip install -r requirements.txt`
- Start: `gunicorn --workers 2 --threads 4 --timeout 20 --graceful-timeout 10 --keep-alive 5 --bind 0.0.0.0:$PORT app:app`
- Health Check: `/healthz`

## Neue Spots hinzufügen

In `config.py` einen Eintrag ergänzen. Für MeteoSchweiz muss die dreistellige Stations-ID stimmen. Eine entfernte Station wird nicht als lokal ausgegeben; ihre Distanz senkt den Qualitätswert sichtbar.

## Bewusste Grenzen

- Wind auf Alpenseen ist kleinräumig. Eine Station ausserhalb des Seebeckens kann die Lage am Wasser nicht vollständig abbilden.
- Öffentlich erreichbare Schul-Websites wurden geprüft; es wurde keine Schule kontaktiert und keine Partnerschaft behauptet.
- Lokale Verbote, Sturmwarnungen, Einstiegsvorschriften und Sichtprüfung vor Ort haben immer Vorrang.
