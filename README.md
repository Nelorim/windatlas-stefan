# WindAtlas CH — stabile Neuarchitektur

Eine schnelle, mobile Windübersicht für ausgewählte Kite- und Foilspots in Europa, Afrika und Asien. Die App trennt echte Messungen konsequent von Modellwerten und bleibt auch dann bedienbar, wenn eine Wetterquelle ausfällt.

## Was diese Version stabil macht

- Die Startseite lädt **ohne Wetterabfrage**. Externe APIs können den Serverstart nicht mehr blockieren.
- `/healthz` ist rein lokal und antwortet sofort.
- Open-Meteo und MeteoSchweiz werden parallel mit einem harten 4-Sekunden-Timeout abgefragt.
- Servercache: 5 Minuten für Modelle, 10 Minuten für Messungen.
- Stale-if-error: letzte gültige Modellwerte bis 6 Stunden, Messwerte bis 12 Stunden – sichtbar als veraltet markiert.
- Browsercache als letzte Rückfallebene.
- Keine Datenbank und kein schweres Frontend-Buildsystem.

## Datenqualität

| Quelle | Einordnung | Aktualisierung |
|---|---|---|
| MeteoSchweiz SwissMetNet | echte automatische Stationsmessung | 10 Minuten |
| Open-Meteo | Wettermodell am Spot, keine Messung | typischerweise 1–6 Stunden je Modell |
| KWind | externes Live-Stationsnetz; Suche wird direkt geöffnet | abhängig von lokaler Station |
| Kiteschulen / Clubs | öffentlich geprüfter lokaler Kontext | redaktionelles Prüfdatum |

Der Qualitätswert berücksichtigt Quellenverfügbarkeit, Stationsdistanz und Abweichung zwischen Messung und Modell. Er ist transparent und bewusst konservativ. Die Kite-Ampel ist nur eine Entscheidungshilfe, niemals eine Sicherheitsfreigabe.

## Windhistorie

Für jeden konfigurierten Spot stehen vier Ansichten bereit: **Woche**, **Monat**, **Jahr** und **5 Jahre**. Die Monatsansicht zeigt jeden Kalendertag mit Tagesmaximum, Böenspitze und – sofern vorhanden – dominanter Windrichtung. Jahres- und Fünfjahresansicht verdichten dieselben Tageswerte zu übersichtlichen Vergleichen.

Die Historie stammt aus der Open-Meteo Historical Weather API. Es handelt sich um Reanalyse- beziehungsweise Modellwerte am Spot, nicht um eine lückenlose Historie lokaler Messstationen. Das wird in der Oberfläche ausdrücklich gekennzeichnet. Historische Antworten werden sechs Stunden gecacht; bei einer kurzfristigen Störung kann der letzte gültige Stand bis zu sieben Tage weiter angezeigt werden.

KWind-Daten werden nicht kopiert oder serverseitig weiterverteilt. Die App verlinkt auf die KWind-Stationssuche, weil KWind die Stationsdaten laut eigener Information exklusiv für KWind und Windguru lizenziert. Eine direkte Integration kann ergänzt werden, sobald eine offizielle API-Freigabe vorliegt.

Für Silvaplana ist zusätzlich die vom Nutzer bereitgestellte feste KWind-Station `670cd9f112daffeffb13a8a0` über das offizielle KWind-Widget eingebunden. Livewerte und Messhistorie bleiben dabei technisch bei KWind. MeteoSchweiz Samedan wird nur als regionale Referenz behandelt und kann wegen der Distanz keine Datenqualität von 100/100 mehr erzeugen.

Mui Ne (Vietnam) ist als weiterer Spot enthalten. Die lokale Quelle ist die C2Sky-Webcamseite mit eingebundener Windguru-Livestation `14164`; Open-Meteo bleibt als klar gekennzeichneter Modellvergleich bestehen.

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
