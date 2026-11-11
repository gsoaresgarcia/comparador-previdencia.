"""Historical comparison on common dates. No forecast or invented observations."""
import math,re,statistics
from datetime import date,timedelta
from dateutil.relativedelta import relativedelta
from data_store import CATALOG,read
FUNDS={re.sub(r'\D','',f['cnpj']):f for f in CATALOG}
WINDOWS=(6,12,24,36,48,60)
def clean(s):return re.sub(r'\D','',str(s or ''))
def metrics(a,b,dates,rates):
    total=b/a-1
    return total

def compute(obj):
    ids=[clean(obj.get('fund1')),clean(obj.get('fund2'))]
    if any(c not in FUNDS for c in ids) or ids[0]==ids[1]:raise ValueError('Selecione dois fundos diferentes da grade.')
    try:
        end=date.fromisoformat(obj.get('end','')); horizon=int(obj.get('horizon',24)); target=float(obj.get('target',1000000))
    except (ValueError,TypeError):raise ValueError('Confira a data, o período e o valor desejado.')
    if end>date.today():raise ValueError('Escolha uma data até hoje.')
    if horizon not in WINDOWS:raise ValueError('Período inválido.')
    if not math.isfinite(target) or not 0<target<=1e12:raise ValueError('Informe um patrimônio entre R$ 0,01 e R$ 1 trilhão.')
    data=read(); series=[data['funds'].get(c,{}) for c in ids]; cdi=data['cdi']
    common=sorted(set(series[0])&set(series[1])); desired=end-relativedelta(months=horizon)
    def boundary(day):
        ds=[d for d in common if (day-timedelta(days=10)).isoformat()<=d<=day.isoformat()]
        return ds[-1] if ds else None
    last=boundary(end); first=boundary(desired)
    summary=[]
    for m in WINDOWS:
        s=boundary(end-relativedelta(months=m))
        summary.append({'months':m,'start':s,'end':last,'returns':[(x[last]/x[s]-1)*100 for x in series] if s and last and s<last else [None,None]})
    report={'funds':[FUNDS[c] for c in ids],'end_requested':end.isoformat(),'start_requested':desired.isoformat(),'horizon':horizon,'target':target,'updated_at':data['updated_at'],'summary':summary,'latest_available':[max(x) if x else None for x in series]}
    if not first or not last or first>=last:
        raise ValueError('Não há cotas comuns suficientes para esse período. Tente uma janela menor ou uma data anterior. Últimas cotas: '+', '.join(str(x) for x in report['latest_available']))
    dates=[d for d in common if first<=d<=last]; expected=[d for d in sorted(cdi) if first<d<=last]
    # Require full CDI-aligned daily observations for risk; never annualize multi-day gaps as daily.
    complete=bool(expected) and all(d in dates for d in expected) and dates[1:]==expected
    returns=[[x[dates[i]]/x[dates[i-1]]-1 for i in range(1,len(dates))] for x in series]
    stats=[]
    for x,rs in zip(series,returns):
        factor=x[last]/x[first]; item={'return_pct':(factor-1)*100,'required_initial':target/factor,'gain':target-target/factor,'volatility':None,'sharpe':None,'annualized':None}
        if complete and len(rs)>=20:
            vol=statistics.stdev(rs); excess=[r-cdi[d] for r,d in zip(rs,dates[1:])]; sd=statistics.stdev(excess)
            item.update(volatility=vol*math.sqrt(252)*100,sharpe=statistics.mean(excess)/sd*math.sqrt(252) if sd>1e-12 else None,annualized=(factor**(252/len(rs))-1)*100)
        stats.append(item)
    curve=[]; benchmark=1.; cdi_complete=complete
    for i,d in enumerate(dates):
        if i and cdi_complete:benchmark*=1+cdi[d]
        curve.append({'date':d,'values':[(x[d]/x[first]-1)*100 for x in series],'cdi':(benchmark-1)*100 if cdi_complete else None})
    monthly=[]; cur=date.fromisoformat(first).replace(day=1); stop=date.fromisoformat(last)
    while cur<=stop:
        monthend=cur+relativedelta(months=1)-timedelta(days=1); prior=cur-timedelta(days=1)
        s=boundary(prior); e=boundary(min(monthend,stop)); partial=False
        if s is None or s<first:s=first;partial=True
        if monthend>date.fromisoformat(report['end_requested']):partial=True
        if s and e and first<=s<e<=last:
            ds=[d for d in sorted(cdi) if s<d<=e]; ok=bool(ds) and all(d in common for d in ds) and ds[-1]==e
            monthly.append({'month':cur.strftime('%Y-%m'),'partial':partial,'start':s,'end':e,'values':[(x[e]/x[s]-1)*100 for x in series], 'cdi':(math.prod(1+cdi[d] for d in ds)-1)*100 if ok else None})
        cur+=relativedelta(months=1)
    report.update(start=first,end=last,observations=len(dates),stats=stats,curve=curve,monthly=monthly,risk_complete=complete and len(dates)>20,cdi_return=curve[-1]['cdi'])
    return report
