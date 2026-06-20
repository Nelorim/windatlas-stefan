from __future__ import annotations
from flask import Flask, render_template, request, redirect, url_for, send_from_directory
from pathlib import Path
import pandas as pd
import calendar

BASE = Path(__file__).resolve().parent
DATA_DIR = BASE / 'data' / 'messdaten'
UPLOAD_DIR = DATA_DIR
SPOTS = pd.read_csv(BASE / 'spots_config.csv')

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

COLORS = {
    'Nicht kitebar': '#f3f4f6',
    'Foil': '#86efac',
    'Foil sehr gut': '#fde68a',
    'Twintip': '#93c5fd',
    'Twintip optimal': '#c4b5fd',
    'Starkwind': '#fca5a5',
    'Keine Daten': '#e5e7eb'
}

def load_data() -> pd.DataFrame:
    frames=[]
    for p in DATA_DIR.glob('*.csv'):
        try:
            df = pd.read_csv(p)
            if {'time','wind_speed_kn'}.issubset(df.columns):
                if 'spot' not in df.columns:
                    df['spot'] = p.stem
                if 'wind_gust_kn' not in df.columns:
                    df['wind_gust_kn'] = pd.NA
                df['source_file'] = p.name
                frames.append(df)
        except Exception:
            pass
    if not frames:
        return pd.DataFrame(columns=['time','spot','wind_speed_kn','wind_gust_kn','source_file'])
    df = pd.concat(frames, ignore_index=True)
    df['time'] = pd.to_datetime(df['time'], errors='coerce')
    df = df.dropna(subset=['time','spot','wind_speed_kn'])
    df['date'] = df['time'].dt.date
    df['year'] = df['time'].dt.year
    df['month'] = df['time'].dt.month
    return df

def day_class(speeds: pd.Series) -> str:
    # Tageslogik: mindestens 2 Stunden über Schwelle; höchste erfüllte Kategorie gewinnt.
    if speeds.empty: return 'Keine Daten'
    if (speeds >= 24).sum() >= 2: return 'Starkwind'
    if ((speeds >= 16) & (speeds < 24)).sum() >= 2: return 'Twintip optimal'
    if (speeds >= 12).sum() >= 2: return 'Twintip'
    if ((speeds >= 15) & (speeds < 21)).sum() >= 2: return 'Foil sehr gut'
    if (speeds >= 8).sum() >= 2: return 'Foil'
    return 'Nicht kitebar'

def daily_table(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=['spot','date','year','month','class','max_speed','avg_speed','max_gust','source_file'])
    rows=[]
    for (spot, date), g in df.groupby(['spot','date']):
        speeds = pd.to_numeric(g['wind_speed_kn'], errors='coerce').dropna()
        rows.append({
            'spot': spot,
            'date': pd.to_datetime(date),
            'year': pd.to_datetime(date).year,
            'month': pd.to_datetime(date).month,
            'class': day_class(speeds),
            'max_speed': float(speeds.max()) if len(speeds) else None,
            'avg_speed': float(speeds.mean()) if len(speeds) else None,
            'max_gust': pd.to_numeric(g.get('wind_gust_kn'), errors='coerce').max(),
            'source_file': ', '.join(sorted(set(g['source_file'].astype(str))))
        })
    return pd.DataFrame(rows)

def summary(daily: pd.DataFrame) -> pd.DataFrame:
    spots = sorted(SPOTS['spot'].tolist())
    rows=[]
    for spot in spots:
        d = daily[daily['spot']==spot]
        rows.append({
            'spot': spot,
            'days_data': len(d),
            'foil_days': int(d['class'].isin(['Foil','Foil sehr gut','Twintip','Twintip optimal','Starkwind']).sum()) if not d.empty else 0,
            'foil_verygood': int(d['class'].isin(['Foil sehr gut','Twintip','Twintip optimal','Starkwind']).sum()) if not d.empty else 0,
            'twintip_days': int(d['class'].isin(['Twintip','Twintip optimal','Starkwind']).sum()) if not d.empty else 0,
            'twintip_optimal': int(d['class'].isin(['Twintip optimal','Starkwind']).sum()) if not d.empty else 0,
            'strong_days': int((d['class']=='Starkwind').sum()) if not d.empty else 0,
        })
    return pd.DataFrame(rows)

def months_available(daily):
    if daily.empty: return []
    return sorted(daily['year'].dropna().astype(int).unique(), reverse=True)

def calendar_matrix(daily, spot, year):
    d = daily[(daily['spot']==spot) & (daily['year']==year)]
    by_date = {r['date'].date(): r for _, r in d.iterrows()}
    out=[]
    for m in range(1,13):
        days=[]
        for day in range(1, calendar.monthrange(year,m)[1]+1):
            dt = pd.Timestamp(year=year, month=m, day=day).date()
            r = by_date.get(dt)
            cls = r['class'] if r is not None else 'Keine Daten'
            days.append({'day': day, 'class': cls, 'color': COLORS[cls], 'max': None if r is None else r['max_speed']})
        out.append({'month': calendar.month_name[m], 'month_no': m, 'days': days})
    return out

@app.route('/')
def index():
    raw=load_data(); daily=daily_table(raw); summ=summary(daily)
    return render_template('index.html', summary=summ.to_dict('records'), colors=COLORS, files=sorted([p.name for p in DATA_DIR.glob('*.csv')]))

@app.route('/spot/<spot>')
def spot(spot):
    raw=load_data(); daily=daily_table(raw)
    years=months_available(daily[daily['spot']==spot])
    year=int(request.args.get('year', years[0] if years else 2025))
    cal=calendar_matrix(daily, spot, year)
    d=daily[(daily['spot']==spot)&(daily['year']==year)]
    return render_template('spot.html', spot=spot, year=year, years=years, cal=cal, colors=COLORS, rows=d.sort_values('date').to_dict('records'))

@app.route('/upload', methods=['GET','POST'])
def upload():
    if request.method=='POST':
        f=request.files.get('file')
        if f and f.filename.endswith('.csv'):
            f.save(UPLOAD_DIR / f.filename)
        return redirect(url_for('index'))
    return render_template('upload.html')

@app.route('/download/<name>')
def download(name):
    return send_from_directory(DATA_DIR, name, as_attachment=True)

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5050, debug=False)
