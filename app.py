import io,uuid,time,threading
from collections import OrderedDict
from datetime import date
from flask import Flask,jsonify,render_template,request,send_file
from analytics import compute,FUNDS
from data_store import read,maybe_refresh
from report_pdf import build,options_for
app=Flask(__name__,template_folder='.')
app.json.ensure_ascii=False
REPORTS=OrderedDict();LOCK=threading.Lock()
@app.get('/')
def home():
    data=read();maybe_refresh()
    dates=[max(s) for s in data['funds'].values() if s];default=min(date.today().isoformat(),max(dates))
    return render_template('index.html',today=date.today().isoformat(),default_end=default,funds=list(FUNDS.values()),institutions=sorted({f['institution'] for f in FUNDS.values()}))
@app.get('/health')
def health():return jsonify(status='ok',version='2.0',updated_at=read()['updated_at'])
@app.get('/api/search')
def search():
    import unicodedata
    norm=lambda s:''.join(c for c in unicodedata.normalize('NFD',s).lower() if c.isalnum())
    q=norm(request.args.get('q',''));return jsonify(results=[f for f in FUNDS.values() if q in norm(f['name']+f['cnpj'])])
@app.post('/api/compare')
def compare():
    try:
        report=compute(request.get_json(force=True) or {});identifier=uuid.uuid4().hex;report['report_id']=identifier
        with LOCK:
            REPORTS[identifier]=(time.time(),report)
            while len(REPORTS)>64:REPORTS.popitem(last=False)
        return jsonify(report)
    except (ValueError,TypeError,KeyError) as e:return jsonify(error=str(e)),400
@app.post('/api/pdf')
def pdf():
    obj=request.get_json(force=True) or {};identifier=obj.get('report_id')
    with LOCK:cached=REPORTS.get(identifier) if identifier else None
    if not cached or time.time()-cached[0]>3600:return jsonify(error='A consulta expirou. Compare novamente antes de baixar o PDF.'),410
    try: options=options_for(obj.get('options'))
    except ValueError as e:return jsonify(error=str(e)),400
    return send_file(io.BytesIO(build(cached[1],options)),mimetype='application/pdf',as_attachment=True,download_name='comparativo-previdencia.pdf')
if __name__=='__main__':app.run(port=5000)
