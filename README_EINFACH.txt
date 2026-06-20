WindAtlas Stefan 4.0 Portal

LOKAL AUF MAC STARTEN
1. ZIP entpacken.
2. Windatlas_Stefan_Portal_START.command doppelklicken.
3. Falls macOS blockiert: Rechtsklick > Öffnen.
4. Das Portal öffnet im Browser unter http://127.0.0.1:5050

CSV-REALDATEN IMPORTIEREN
Format:
time,spot,wind_speed_kn,wind_gust_kn
2025-06-01 13:00,Silvaplana,14.2,18.5

ONLINE STELLEN / TEILEN
Empfohlen: Render.com
1. Kostenloses Konto erstellen.
2. Neues Web Service Projekt erstellen.
3. Dieses Projekt hochladen oder mit GitHub verbinden.
4. Start Command: gunicorn app:app
5. Das Portal ist danach über einen Link erreichbar.

WICHTIG
Silvaplana, Malcesine und Colico sollen nur mit echten Messdaten bewertet werden.
Open-Meteo ist in dieser Version nicht als Hauptquelle aktiv.
