"""Compact public CVM quota history. Downloads happen outside client requests."""
import csv, gzip, io, json, re, threading, time, urllib.request, zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parent
CATALOG = json.loads((ROOT/'funds.json').read_text())
IDS = {re.sub(r'\D','',f['cnpj']) for f in CATALOG}
BASE = 'https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS/'
STATE = None
LOCK = threading.Lock()
UPDATING = False
LAST_ATTEMPT = 0

def get(url):
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'ComparadorPrevidencia/2.0'}),timeout=90) as r:
        return r.read()

def month(ym):
    cache=ROOT/'data_months'/f'{ym}.json'
    if cache.exists(): return json.loads(cache.read_text())
    points={c:{} for c in IDS}
    content=get(BASE+f'inf_diario_fi_{ym}.zip')
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        for name in z.namelist():
            if not name.endswith('.csv'):continue
            with z.open(name) as src:
                for row in csv.DictReader(io.TextIOWrapper(src,encoding='utf-8-sig',errors='replace'),delimiter=';'):
                    c=re.sub(r'\D','',row.get('CNPJ_FUNDO_CLASSE') or row.get('CNPJ_FUNDO') or '')
                    if c not in IDS:continue
                    try:
                        d=row['DT_COMPTC']; v=float(row['VL_QUOTA'].replace(',','.'))
                        if v>0 and d<=date.today().isoformat(): points[c][d]=v
                    except (ValueError,KeyError):pass
    cache.parent.mkdir(exist_ok=True);cache.write_text(json.dumps(points,separators=(',',':')))
    return points

def cdi(start,end):
    url='https://api.bcb.gov.br/dados/serie/bcdata.sgs.12/dados?formato=json&dataInicial='+start.strftime('%d/%m/%Y')+'&dataFinal='+end.strftime('%d/%m/%Y')
    return {datetime.strptime(x['data'],'%d/%m/%Y').date().isoformat():float(x['valor'])/100 for x in json.loads(get(url))}

def save(data):
    target=ROOT/'snapshot.json.gz';tmp=ROOT/'snapshot.tmp'
    with gzip.open(tmp,'wt',encoding='utf8') as f:json.dump(data,f,separators=(',',':'))
    tmp.replace(target)

def read():
    global STATE
    with LOCK:
        if STATE is None:
            with gzip.open(ROOT/'snapshot.json.gz','rt',encoding='utf8') as f: STATE=json.load(f)
        return STATE

def refresh():
    global STATE,UPDATING
    try:
        old=read(); now=date.today(); prior=(now.replace(day=1)-timedelta(days=1))
        data={'funds':{c:dict(v) for c,v in old['funds'].items()},'cdi':dict(old['cdi']),'updated_at':old['updated_at']}
        for ym in [prior.strftime('%Y%m'),now.strftime('%Y%m')]:
            (ROOT/'data_months'/f'{ym}.json').unlink(missing_ok=True)
            for c,values in month(ym).items():data['funds'][c].update(values)
        data['cdi'].update(cdi(prior.replace(day=1),now));data['updated_at']=datetime.now(timezone.utc).isoformat()
        save(data)
        with LOCK: STATE=data
    except Exception as e:
        print('Atualização de dados adiada:',type(e).__name__,flush=True)
    finally: UPDATING=False

def maybe_refresh():
    global UPDATING,LAST_ATTEMPT
    age=time.time()-datetime.fromisoformat(read()['updated_at']).timestamp()
    with LOCK:
        if UPDATING or age<43200 or time.time()-LAST_ATTEMPT<3600:return
        UPDATING=True;LAST_ATTEMPT=time.time()
    threading.Thread(target=refresh,daemon=True).start()

if __name__=='__main__':
    months=[f'{y}{m:02}' for y in range(2021,date.today().year+1) for m in range(1,13) if f'{y}{m:02}'>='202109' and f'{y}{m:02}'<=date.today().strftime('%Y%m')]
    out={'funds':{c:{} for c in IDS},'cdi':{},'updated_at':datetime.now(timezone.utc).isoformat()}
    def collect(ym):
        for attempt in range(3):
            try:return ym,month(ym)
            except Exception:
                if attempt==2:raise
                time.sleep(2)
    with ThreadPoolExecutor(max_workers=3) as pool:
        for ym,points in pool.map(collect,months):
            for c,v in points.items():out['funds'][c].update(v)
            print(ym,sum(len(v) for v in points.values()),flush=True)
    out['cdi']=cdi(date(2021,9,1),date.today()); save(out)
    print('Snapshot pronto',len(out['cdi']),sum(len(v) for v in out['funds'].values()),flush=True)
