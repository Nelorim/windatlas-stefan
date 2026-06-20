from flask import Flask, render_template, request, redirect, url_for
import pandas as pd, requests, os, io
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlencode

app = Flask(__name__)
BASE = Path(__file__).parent
DATA_DIR = BASE/'data'/'messdaten'
DATA_DIR.mkdir(parents=True, exist_ok=True)
SPOTS = pd.read_csv(BASE/'spots_config.csv')

FOIL_MIN=8; FOIL_GOOD=11; FOIL_VERYGOOD=15; FOIL_STRONG=21
TT_MIN=12; TT_OPT=16; TT_STRONG=24


def color_class(v):
    if pd.isna(v): return 'nodata'
    if v >= TT_STRONG: return 'strong'
    if v >= TT_OPT: return 'ttopt'
    if v >= FOIL_VERYGOOD: return 'foilvery'
    if v >= TT_MIN: return 'tt'
    if v >= FOIL_MIN: return 'foil'
    return 'nowind'

def label(v):
    return {'nodata':'Keine Daten','strong':'Starkwind','ttopt':'Twintip optimal','foilvery':'Foil sehr gut','tt':'Twintip','foil':'Foil','nowind':'Nicht kitebar'}[color_class(v)]

def openmeteo_url(row, years=5):
    end=date.today()-timedelta(days=2)
    start=end.replace(year=end.year-years) if not (end.month==2 and end.day==29) else end-timedelta(days=365*years)
    params={
        'latitude':row.latitude,'longitude':row.longitude,'start_date':start.isoformat(),'end_date':end.isoformat(),
        'hourly':'wind_speed_10m,wind_gusts_10m,wind_direction_10m','wind_speed_unit':'kn','timezone':row.timezone
    }
    return 'https://archive-api.open-meteo.com/v1/archive?'+urlencode(params)

def fetch_openmeteo(row):
    url=openmeteo_url(row)
    r=requests.get(url,timeout=60); r.raise_for_status()
    hourly=r.json().get('hourly',{})
    df=pd.DataFrame(hourly)
    if df.empty: return df
    df['time']=pd.to_datetime(df['time'])
    df['wind_speed_kn']=pd.to_numeric(df['wind_speed_10m'], errors='coerce')
    df['wind_gust_kn']=pd.to_numeric(df.get('wind_gusts_10m'), errors='coerce') if 'wind_gusts_10m' in df else None
    df['source']='Open-Meteo Modell/Reanalyse'
    return df[['time','wind_speed_kn','wind_gust_kn','source']]

def load_csv_for_spot(spot):
    files=list(DATA_DIR.glob('*.csv'))
    frames=[]
    for f in files:
        try:
            df=pd.read_csv(f)
            if 'spot' in df.columns:
                df=df[df['spot'].astype(str)==spot]
            elif spot.lower().replace(' ','_') not in f.stem.lower():
                continue
            if {'time','wind_speed_kn'}.issubset(df.columns):
                df['time']=pd.to_datetime(df['time'])
                df['wind_speed_kn']=pd.to_numeric(df['wind_speed_kn'],errors='coerce')
                if 'wind_gust_kn' not in df: df['wind_gust_kn']=None
                df['source']='CSV Realdaten: '+f.name
                frames.append(df[['time','wind_speed_kn','wind_gust_kn','source']])
        except Exception:
            pass
    return pd.concat(frames,ignore_index=True) if frames else pd.DataFrame()

def daily_from_hourly(df):
    if df.empty: return pd.DataFrame(columns=['date','max_kn','foil','foil_very','tt','tt_opt','strong','class','label'])
    df=df.copy(); df['date']=df['time'].dt.date
    rows=[]
    for d,g in df.groupby('date'):
        sp=g['wind_speed_kn']
        mx=float(sp.max()) if sp.notna().any() else None
        rows.append({'date':pd.to_datetime(d),'max_kn':mx,'foil':int((sp>=FOIL_MIN).sum()>=2),'foil_very':int((sp>=FOIL_VERYGOOD).sum()>=2),'tt':int((sp>=TT_MIN).sum()>=2),'tt_opt':int((sp>=TT_OPT).sum()>=2),'strong':int((sp>=TT_STRONG).sum()>=2),'class':color_class(mx),'label':label(mx)})
    return pd.DataFrame(rows)

def data_for_spot(row):
    csv=load_csv_for_spot(row.spot)
    model=pd.DataFrame()
    if row.source_mode != 'csv_required':
        try: model=fetch_openmeteo(row)
        except Exception: model=pd.DataFrame()
    elif csv.empty:
        # deliberately avoid model as main data for thermal spots
        model=pd.DataFrame()
    df=csv if not csv.empty else model
    return daily_from_hourly(df), ('CSV Realdaten' if not csv.empty else ('Open-Meteo Modell' if not model.empty else 'Keine Daten'))

def month_summary(daily):
    if daily.empty: return []
    d=daily.copy(); d['year']=d.date.dt.year; d['month']=d.date.dt.month
    g=d.groupby('month').agg(days=('date','count'), foil=('foil','sum'), foil_very=('foil_very','sum'), tt=('tt','sum'), tt_opt=('tt_opt','sum'), strong=('strong','sum')).reset_index()
    return g.to_dict('records')

def heatmap(daily, year=None):
    if daily.empty: return []
    if year is None: year=int(daily.date.dt.year.max())
    d=daily[daily.date.dt.year==year].copy()
    months=[]
    for m in range(1,13):
        md=d[d.date.dt.month==m]
        days=[{'day':int(r.date.day),'class':r['class'],'label':r['label'],'max':None if pd.isna(r.max_kn) else round(float(r.max_kn),1)} for _,r in md.iterrows()]
        months.append({'month':m,'days':days})
    return months

@app.route('/')
def index():
    rows=[]
    for _,r in SPOTS.iterrows():
        daily,src=data_for_spot(r)
        rows.append({'spot':r.spot,'country':r.country,'mode':r.source_mode,'source':src,'days':len(daily),'foil':int(daily.foil.sum()) if len(daily) else 0,'foil_very':int(daily.foil_very.sum()) if len(daily) else 0,'tt':int(daily.tt.sum()) if len(daily) else 0,'tt_opt':int(daily.tt_opt.sum()) if len(daily) else 0,'strong':int(daily.strong.sum()) if len(daily) else 0})
    return render_template('index.html', rows=rows)

@app.route('/spot/<spot>')
def spot(spot):
    r=SPOTS[SPOTS.spot==spot].iloc[0]
    daily,src=data_for_spot(r)
    year=int(request.args.get('year', daily.date.dt.year.max() if len(daily) else date.today().year))
    return render_template('spot.html', spot=spot, src=src, note=r.quality_note, ref=r.reference_url, months=month_summary(daily), heatmap=heatmap(daily,year), year=year, years=sorted(daily.date.dt.year.unique(), reverse=True) if len(daily) else [])

@app.route('/upload', methods=['GET','POST'])
def upload():
    if request.method=='POST':
        f=request.files.get('file')
        if f and f.filename.endswith('.csv'):
            f.save(DATA_DIR/f.filename)
            return redirect(url_for('index'))
    return render_template('upload.html')

if __name__=='__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT',5050)))
