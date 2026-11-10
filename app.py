"""Comparador de cotas de fundos - dados oficiais de informes diários CVM."""
import csv
import io
import os
import re
import threading
import zipfile
from collections import defaultdict
from datetime import date, datetime
from functools import lru_cache
from urllib.parse import quote

import requests
from dateutil.relativedelta import relativedelta
from flask import Flask, jsonify, render_template, request, send_file
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

app = Flask(__name__)
app.json.ensure_ascii = False
BASE = 'https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS'
REGISTRY = 'https://dados.cvm.gov.br/dados/FI/CAD/DADOS/cad_fi.csv'
WINDOWS = (6, 12, 24, 36, 48, 60)
lock = threading.Lock()


def clean_cnpj(s):
    return re.sub(r'\D', '', str(s or ''))


def month_keys(start, end):
    cur = date(start.year, start.month, 1)
    last = date(end.year, end.month, 1)
    while cur <= last:
        yield cur.strftime('%Y%m')
        cur += relativedelta(months=1)


def csv_rows(content):
    stream = io.TextIOWrapper(io.BytesIO(content), encoding='utf-8-sig', errors='replace', newline='')
    return csv.DictReader(stream, delimiter=';')


@lru_cache(maxsize=1)
def registry():
    r = requests.get(REGISTRY, timeout=90, headers={'User-Agent': 'ComparadorPrevidencia/1.0'})
    r.raise_for_status()
    result = []
    for row in csv_rows(r.content):
        cnpj = clean_cnpj(row.get('CNPJ_FUNDO') or row.get('CNPJ_FUNDO_CLASSE'))
        name = row.get('DENOM_SOCIAL') or row.get('DENOM_SOCIAL_CLASSE') or ''
        if len(cnpj) == 14 and name:
            result.append({'cnpj': cnpj, 'name': name})
    return result


@lru_cache(maxsize=72)
def monthly_zip(ym):
    url = f'{BASE}/inf_diario_fi_{ym}.zip'
    r = requests.get(url, timeout=100, headers={'User-Agent': 'ComparadorPrevidencia/1.0'})
    r.raise_for_status()
    if len(r.content) > 180 * 1024 * 1024:
        raise ValueError('Arquivo mensal excede o limite de processamento.')
    return r.content


def read_month(ym, cnpjs):
    """Read all CSV members, tolerating historical schema changes."""
    data = defaultdict(list)
    with zipfile.ZipFile(io.BytesIO(monthly_zip(ym))) as archive:
        for filename in archive.namelist():
            if not filename.lower().endswith('.csv'):
                continue
            with archive.open(filename) as f:
                wrapper = io.TextIOWrapper(f, encoding='utf-8-sig', errors='replace', newline='')
                for row in csv.DictReader(wrapper, delimiter=';'):
                    cnpj = clean_cnpj(row.get('CNPJ_FUNDO') or row.get('CNPJ_FUNDO_CLASSE'))
                    if cnpj not in cnpjs:
                        continue
                    dt = row.get('DT_COMPTC')
                    raw = row.get('VL_QUOTA')
                    try:
                        v = float(raw.replace(',', '.'))
                        d = date.fromisoformat(dt)
                        if v > 0:
                            data[cnpj].append((d, v))
                    except (ValueError, TypeError, AttributeError):
                        continue
    return data


def historical(cnpjs, start, end):
    series = {cnpj: {} for cnpj in cnpjs}
    for ym in month_keys(start, end):
        data = read_month(ym, set(cnpjs))
        for cnpj, points in data.items():
            for dt, value in points:
                if start <= dt <= end:
                    series[cnpj][dt] = value
    return {c: sorted(v.items()) for c, v in series.items()}


def get_parameters(obj):
    cnpjs = [clean_cnpj(obj.get('fund1')), clean_cnpj(obj.get('fund2'))]
    if any(len(c) != 14 for c in cnpjs) or cnpjs[0] == cnpjs[1]:
        raise ValueError('Informe dois CNPJs diferentes, com 14 dígitos cada.')
    try:
        end = date.fromisoformat(obj.get('end', ''))
    except ValueError:
        raise ValueError('Data final inválida (AAAA-MM-DD).')
    if end > date.today():
        raise ValueError('A data final não pode estar no futuro.')
    windows = obj.get('windows', list(WINDOWS))
    if not isinstance(windows, list):
        raise ValueError('Selecione as janelas em uma lista.')
    windows = sorted(set(int(x) for x in windows))
    if not windows or any(x not in WINDOWS for x in windows):
        raise ValueError('Selecione janelas de 6, 12, 24, 36, 48 ou 60 meses.')
    return cnpjs, end, windows


def compute(obj):
    cnpjs, end, windows = get_parameters(obj)
    start = end - relativedelta(months=max(windows)) - relativedelta(days=10)
    data = historical(cnpjs, start, end)
    result = []
    for months in windows:
        target = end - relativedelta(months=months)
        row = {'months': months, 'start_target': target.isoformat(), 'end_target': end.isoformat(), 'funds': []}
        for cnpj in cnpjs:
            points = data[cnpj]
            # Use the most recent observed quota at/before the boundary, with max 10-day tolerance.
            before_start = [p for p in points if p[0] <= target and (target-p[0]).days <= 10]
            before_end = [p for p in points if p[0] <= end and (end-p[0]).days <= 10]
            if before_start and before_end:
                s, e = before_start[-1], before_end[-1]
                row['funds'].append({'cnpj': cnpj, 'start': s[0].isoformat(), 'end': e[0].isoformat(), 'start_quota': s[1], 'end_quota': e[1], 'return_pct': (e[1]/s[1]-1)*100})
            else:
                row['funds'].append({'cnpj': cnpj, 'error': 'Cotas insuficientes nesta janela (fundo pode ter histórico menor ou ausência de informe).'})
        result.append(row)
    return {'as_of': end.isoformat(), 'source': 'CVM - Informe Diário de Fundos de Investimento (VL_QUOTA)', 'rows': result, 'cnpjs': cnpjs}


@app.get('/')
def home():
    return render_template('index.html', today=date.today().isoformat())


@app.get('/health')
def health():
    return jsonify(status='ok')


@app.get('/api/search')
def search():
    q = (request.args.get('q') or '').strip()
    if len(q) < 3:
        return jsonify(results=[])
    try:
        records = registry()
        normalized = clean_cnpj(q)
        if normalized and len(normalized) >= 3 and q.replace('.', '').replace('/', '').replace('-', '').isdigit():
            matches = [x for x in records if normalized in x['cnpj']]
        else:
            matches = [x for x in records if q.casefold() in x['name'].casefold()]
        return jsonify(results=matches[:30])
    except (requests.RequestException, ValueError) as e:
        return jsonify(error=f'Não foi possível consultar o cadastro CVM: {e}'), 503


@app.post('/api/compare')
def compare():
    try:
        return jsonify(compute(request.get_json(force=True)))
    except (ValueError, TypeError) as e:
        return jsonify(error=str(e)), 400
    except (requests.RequestException, zipfile.BadZipFile) as e:
        return jsonify(error=f'Falha ao obter dados da CVM: {e}'), 503


@app.post('/api/pdf')
def pdf():
    try:
        payload = request.get_json(force=True)
        report = compute(payload)
    except (ValueError, TypeError) as e:
        return jsonify(error=str(e)), 400
    except (requests.RequestException, zipfile.BadZipFile) as e:
        return jsonify(error=f'Falha ao obter dados da CVM: {e}'), 503
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=1.8*cm, leftMargin=1.8*cm, topMargin=1.8*cm, bottomMargin=1.8*cm)
    styles = getSampleStyleSheet()
    story = [Paragraph('Comparativo historico de fundos', styles['Title']), Spacer(1, 0.35*cm), Paragraph(f'Data de referencia: {report["as_of"]}', styles['Normal']), Spacer(1, 0.3*cm)]
    names = [str(payload.get('name1') or report['cnpjs'][0]), str(payload.get('name2') or report['cnpjs'][1])]
    for name, cnpj in zip(names, report['cnpjs']):
        story.append(Paragraph(f'{name} | CNPJ {cnpj}', styles['Normal']))
    story.append(Spacer(1, 0.45*cm))
    rows = [['Janela', 'Fundo 1', 'Fundo 2', 'Periodo observado']]
    for row in report['rows']:
        vals = [f'{f["return_pct"]:+.2f}%' if 'return_pct' in f else 'N/D' for f in row['funds']]
        dates = [f'{f["start"]} a {f["end"]}' for f in row['funds'] if 'start' in f]
        rows.append([f'{row["months"]} meses', vals[0], vals[1], dates[0] if dates else 'N/D'])
    table = Table(rows, colWidths=[2.6*cm, 2.8*cm, 2.8*cm, 8.0*cm], repeatRows=1)
    table.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor('#17365D')), ('TEXTCOLOR',(0,0),(-1,0),colors.white), ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#EDF2F7')]), ('GRID',(0,0),(-1,-1),0.3,colors.HexColor('#CBD5E1')), ('FONTSIZE',(0,0),(-1,-1),8), ('VALIGN',(0,0),(-1,-1),'MIDDLE'), ('BOTTOMPADDING',(0,0),(-1,-1),9), ('TOPPADDING',(0,0),(-1,-1),9)]))
    story.append(table)
    story.extend([Spacer(1, 0.5*cm), Paragraph('Fonte: CVM, Informe Diario de Fundos de Investimento. Rentabilidade acumulada calculada pela variacao da cota entre as datas observadas. Datas podem variar entre fundos conforme disponibilidade de informes. Valores nominais, sem ajuste por tributacao, taxas individuais ou aportes/resgates. Rentabilidade passada nao garante resultados futuros.', styles['Normal']), Spacer(1, 0.3*cm), Paragraph('Relatorio informativo; conferir dados oficiais antes de compartilhar com clientes.', styles['Italic'])])
    doc.build(story)
    buf.seek(0)
    return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name='comparativo-previdencia.pdf')


if __name__ == '__main__':
    app.run(debug=True, port=int(os.getenv('PORT', '5000')))
