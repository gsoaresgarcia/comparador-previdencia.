import io,math
from html import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak,Flowable,KeepTogether
NAVY=colors.HexColor('#142d4e');BLUE=colors.HexColor('#1463b8');TEAL=colors.HexColor('#d95f02');GRAY=colors.HexColor('#64748b')
def num(v,n=2):return 'N/D' if v is None else f'{v:,.{n}f}'.replace(',','X').replace('.',',').replace('X','.')
def pct(v):return num(v)+'%' if v is not None else 'N/D'
def money(v):return 'R$ '+num(v)
def dt(d):return '/'.join(reversed(d.split('-')))
class Chart(Flowable):
    def __init__(self,r,show_cdi=True):Flowable.__init__(self);self.r=r;self.show_cdi=show_cdi;self.width=17.2*cm;self.height=7.1*cm
    def draw(self):
        c=self.canv; rows=self.r['curve'];left=38;bottom=26;w=self.width-left-8;h=self.height-bottom-15
        vals=[v for p in rows for v in p['values']]+[p['cdi'] for p in rows if self.show_cdi and p['cdi'] is not None];lo=min(0,min(vals));hi=max(vals);pad=max((hi-lo)*.03,.1);lo-=pad;hi+=pad
        def y(v):return bottom+(v-lo)/(hi-lo)*h
        c.setFont('Helvetica',8)
        for i in range(5):
            v=lo+(hi-lo)*i/4;yy=y(v);c.setStrokeColor(colors.HexColor('#e2e8f0'));c.line(left,yy,left+w,yy);c.setFillColor(GRAY);c.drawRightString(left-5,yy-3,num(v,1)+'%')
        for idx,col in [(2,colors.black),(0,BLUE),(1,TEAL)]:
            if idx==2 and (not self.show_cdi or rows[-1]['cdi'] is None):continue
            path=c.beginPath()
            for i,p in enumerate(rows):
                v=p['values'][idx] if idx<2 else p['cdi'];xx=left+w*i/max(len(rows)-1,1)
                if i==0:path.moveTo(xx,y(v))
                else:path.lineTo(xx,y(v))
            c.setStrokeColor(col);c.setLineWidth(.95 if idx<2 else 1.05);c.setDash();c.drawPath(path)
        c.setDash();c.setFillColor(GRAY);c.drawString(left,8,dt(rows[0]['date']));c.drawRightString(left+w,8,dt(rows[-1]['date']))
def options_for(obj=None):
    if obj is None: obj={}
    if not isinstance(obj,dict): raise ValueError('Opções do relatório inválidas.')
    windows=obj.get('windows',[12,24,36,48])
    if not isinstance(windows,list) or not windows or any(type(v) is not int or v not in [12,24,36,48] for v in windows):
        raise ValueError('Selecione pelo menos um período: 12, 24, 36 ou 48 meses.')
    out={'windows':sorted(set(windows))}
    for key,default in [('chart',True),('chart_cdi',True),('capital',True),('risk',False),('monthly',False)]:
        value=obj.get(key,default)
        if type(value) is not bool: raise ValueError('Seleção de seções inválida.')
        out[key]=value
    return out

def build(r,options=None):
    o=options_for(options);buf=io.BytesIO();styles=getSampleStyleSheet()
    RED=colors.HexColor('#cc0000')
    for name,size,leading,color in [('Body',9,13,NAVY),('Small',7.5,10,GRAY),('Title',24,28,NAVY),('Head',13,17,NAVY),('Header',8,10,colors.white),('Month',7,9,NAVY),('Year',11,13,NAVY)]:
        styles.add(ParagraphStyle(name='BR'+name,fontName='Helvetica',fontSize=size,leading=leading,textColor=color,spaceAfter=6 if name!='Month' else 0))
    def p(text,style='Body'):return Paragraph(text,styles['BR'+style])
    def table(rows,widths,monthly=False):
        t=Table(rows,colWidths=widths,repeatRows=1,hAlign='LEFT')
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),NAVY),('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),6.2 if monthly else 9),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('TOPPADDING',(0,0),(-1,-1),2 if monthly else 8),('BOTTOMPADDING',(0,0),(-1,-1),2 if monthly else 8),('LEFTPADDING',(0,0),(-1,-1),2 if monthly else 8),('RIGHTPADDING',(0,0),(-1,-1),2 if monthly else 8),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor('#f4f6f8'),colors.white])]))
        if monthly:t.setStyle(TableStyle([('ALIGN',(1,0),(-1,-1),'CENTER')]))
        return t
    names=[f['name'] for f in r['funds']];headers=[p(escape(n),'Header') for n in names]
    windows=[x for x in r['summary'] if x['months'] in o['windows']]
    scope=', '.join(str(v) for v in o['windows'])+' meses'
    story=[p('<font color="#cc0000"><b>PREVIDÊNCIA | ATENDIMENTO SANTANDER</b></font>','Small'),p('Seu futuro merece<br/>uma boa comparação.','Title'),p('Gabriel Garcia | Assessor de Investimentos'),p('Uma visão do histórico para apoiar nossa conversa sobre sua previdência.','Small')]
    for i,f in enumerate(r['funds']):
        story.append(p(f'<font color="{["#1463b8","#d95f02"][i]}"><b>{escape(f["name"])}</b></font> <font size="7">| CNPJ {f["cnpj"]}</font>'))
    story += [Spacer(1,6),p('Como os fundos se comparam','Head'),p('Rentabilidade acumulada nos períodos selecionados: '+scope+'.','Small')]
    rows=[['Período',*headers]]
    for x in windows:rows.append([str(x['months'])+' meses',pct(x['returns'][0]),pct(x['returns'][1])])
    story.append(table(rows,[3.2*cm,7*cm,7*cm]))
    dates='; '.join(f'{x["months"]}m: {dt(x["start"])} a {dt(x["end"])}' for x in windows if all(v is not None for v in x['returns']))
    story += [Spacer(1,5),p('Datas de comparação: '+(dates or 'histórico comum indisponível')+'.','Small')]
    valid=[x for x in windows if all(v is not None for v in x['returns'])]
    if valid:
        x=valid[0];diff=x['returns'][0]-x['returns'][1]
        insight=(f'Nos {x["months"]} meses selecionados, <b>{escape(names[0 if diff>0 else 1])}</b> apresentou retorno {num(abs(diff))} pontos percentuais superior ao outro fundo.' if abs(diff)>=.005 else f'Nos {x["months"]} meses selecionados, os fundos tiveram retornos semelhantes.')
        story.append(p(insight+' O histórico é um dos elementos da decisão; risco, prazo e condições do plano também importam.'))
    if o['chart']:
        story += [p('A trajetória do patrimônio','Head'),p(f'Histórico de {r["horizon"]} meses | {dt(r["start"])} a {dt(r["end"])}.','Small'),p(f'<font color="#1463b8">{escape(names[0])}</font> | <font color="#d95f02">{escape(names[1])}</font>' + (' | <font color="#000000">CDI</font>' if o['chart_cdi'] else ''),'Small'),Chart(r,show_cdi=o['chart_cdi'])]
    story.append(p('Rentabilidade passada não garante resultados futuros. Os períodos foram selecionados para esta apresentação e não representam todo o histórico dos fundos.','Small'))
    if o['capital'] or o['risk']:
        story += [PageBreak(),p('Da comparação à sua decisão','Title')]
    a,b=r['stats']
    if o['capital']:
        story += [p('Quanto seria necessário investir?','Head'),p(f'Aplicação inicial necessária para alcançar <b>{money(r["target"])}</b>, usando o retorno de cada período selecionado abaixo.')]
        rows=[['Período',*headers]]
        for x in windows:
            dates=dt(x['start'])+' a '+dt(x['end']) if x['start'] and x['end'] else 'Histórico insuficiente'
            cells=[p(str(x['months'])+' meses<br/><font size="7">'+dates+'</font>')]
            for v in x['returns']:
                cells.append(p('<b>'+money(r['target']/(1+v/100))+'</b><br/><font size="8">Retorno: '+pct(v)+'</font>') if v is not None else 'N/D')
            rows.append(cells)
        story += [table(rows,[5.2*cm,6*cm,6*cm]),p('Retorno e aplicação inicial usam exatamente as mesmas datas em cada linha. Uma aplicação única, sem aportes ou resgates. Valores nominais, antes do IR e das condições individuais do plano; sem ajuste pela inflação. É uma reconstrução do passado, não uma promessa de ganho.','Small')]
    if o['risk']:
        story += [Spacer(1,8),p('Retorno e risco, lado a lado','Head'),p(f'Indicadores de {dt(r["start"])} a {dt(r["end"])}.','Small'),table([['Indicador',*headers],['Retorno anualizado',pct(a['annualized']),pct(b['annualized'])],['Volatilidade anualizada',pct(a['volatility']),pct(b['volatility'])],['Sharpe anualizado (CDI)',num(a['sharpe']),num(b['sharpe'])]],[5.2*cm,6*cm,6*cm]),p('Volatilidade indica quanto o retorno oscilou. Sharpe relaciona o retorno acima do CDI ao risco assumido; valores negativos indicam excesso médio negativo no período.','Small')]
    story += [Spacer(1,10),p('Vamos conversar sobre sua previdência?','Head'),p('No atendimento Santander, podemos avaliar como sua previdência se encaixa nos seus objetivos, no prazo de investimento e no seu perfil. Antes de qualquer decisão, vamos conferir taxas, tributação, carências e condições do plano.')]
    methodology=[p('Fontes e notas da comparação','Small'),p('Cotas: CVM, Informe Diário (VL_QUOTA). CDI: Banco Central, SGS 12. Retornos pela variação das cotas, com despesas do fundo já refletidas. Mesmas datas para ambos os fundos em cada período, com tolerância de até 10 dias anteriores ao limite solicitado. N/D: histórico ou dados insuficientes; não usamos estimativas para preencher lacunas.','Small')]
    if o['capital']:methodology.append(p('Aplicação inicial = patrimônio final desejado ÷ (1 + retorno acumulado).','Small'))
    if o['risk']:methodology.append(p('Volatilidade: desvio-padrão amostral dos retornos diários × √252. Sharpe: média do excesso diário sobre CDI ÷ desvio-padrão amostral do excesso × √252. Anualização: fator acumulado elevado a 252/n, menos 1. Risco exige ao menos 20 retornos e dados alinhados ao CDI; lacunas ou denominador nulo geram N/D.','Small'))
    methodology.append(p(f'Base atualizada: {r["updated_at"][:10]} (UTC). Material comparativo elaborado pelo assessor, sem caráter de recomendação personalizada ou documento oficial do Santander. Estratégias e riscos podem diferir.','Small'))
    story += [Spacer(1,12),*methodology]
    if o['monthly']:
        story += [PageBreak(),p('Rentabilidade mês a mês','Title'),p(f'Período: {dt(r["start"])} a {dt(r["end"])}. Retornos mensais, com meses parciais marcados por asterisco.','Small')]
        months=['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez']
        for year in sorted({x['month'][:4] for x in r['monthly']},reverse=True):
            by_month={int(x['month'][5:]):x for x in r['monthly'] if x['month'].startswith(year)};rows=[['Fundo',*months]]
            for idx,name in enumerate([*names,'CDI']):
                row=[p(escape(name),'Month')]
                for month in range(1,13):
                    x=by_month.get(month);v=(x['values'][idx] if idx<2 else x['cdi']) if x else None
                    row.append(pct(v)+('*' if x['partial'] else '') if x else '-')
                rows.append(row)
            story.append(KeepTogether([Spacer(1,5),p(year,'Year'),table(rows,[3.7*cm]+[1.125*cm]*12,True)]))
        story += [Spacer(1,8),p('* Mês parcial. -: fora da janela. N/D: dado indisponível.','Small')]
    def footer(c,doc):
        c.setStrokeColor(RED);c.line(1.9*cm,1.35*cm,19.1*cm,1.35*cm);c.setFont('Helvetica',8);c.setFillColor(GRAY);c.drawString(1.9*cm,1*cm,'Gabriel Garcia | Atendimento Santander');c.drawRightString(19.1*cm,1*cm,str(doc.page))
    doc=SimpleDocTemplate(buf,pagesize=A4,rightMargin=1.9*cm,leftMargin=1.9*cm,topMargin=1.5*cm,bottomMargin=1.7*cm,title='Sua previdência em perspectiva',author='Gabriel Garcia')
    doc.build(story,onFirstPage=footer,onLaterPages=footer);return buf.getvalue()
