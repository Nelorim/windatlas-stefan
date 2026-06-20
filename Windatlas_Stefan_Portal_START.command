#!/bin/bash
cd "$(dirname "$0")"
echo "========================================"
echo " WindAtlas Stefan 4.0 Portal"
echo "========================================"
echo "Installiere/prüfe Python-Pakete..."
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
echo "Starte lokales Portal..."
echo "Browser-Adresse: http://127.0.0.1:5050"
python - <<'PY'
import webbrowser, time
webbrowser.open('http://127.0.0.1:5050')
PY
python app.py
