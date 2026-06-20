WINDATLAS STEFAN 4.1 CLOUD AUTOSTART

Ziel:
Diese Version ist fuer Online-Betrieb vorbereitet. Sie laeuft nach dem Deployment ohne Mac, ohne Terminal und ohne lokalen Rechner.

Empfohlene Plattform:
Render.com

Vorgehen Kurzfassung:
1. ZIP entpacken.
2. Ordner in ein neues GitHub Repository hochladen.
3. Bei Render.com anmelden.
4. New + > Web Service waehlen.
5. GitHub Repository verbinden.
6. Render erkennt render.yaml automatisch.
7. Deploy starten.
8. Danach ist die App unter einer Render-URL online erreichbar.

Wichtig:
- Der lokale Mac muss danach nicht laufen.
- Android, iPhone, iPad, Mac und Windows koennen die URL im Browser oeffnen.
- Fuer dauerhaften Upload echter CSV-Daten sollte spaeter ein permanenter Speicher angebunden werden.
- Aktuell liegen CSV-Dateien im Projektordner data/messdaten.

Start lokal bleibt weiterhin moeglich:
Windatlas_Stefan_Portal_START.command doppelklicken.

Cloud Startbefehl:
gunicorn app:app --bind 0.0.0.0:$PORT
