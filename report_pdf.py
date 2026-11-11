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
    def __init__(self,r):Flowable.__init__(self);self.r=r;self.width=17.2*cm;self.height=7.1*cm
    def draw(self):
        c=self.canv; rows=self.r['curve'];left=38;bottom=26;w=self.width-left-8;h=self.height-bottom-15
        vals=[v for p in rows for v in p['values']]+[p['cdi'] for p in rows if p['cdi'] is not None];lo=min(0,min(vals));hi=max(vals);pad=max((hi-lo)*.03,.1);lo-=pad;hi+=pad
        def y(v):return bottom+(v-lo)/(hi-lo)*h
        c.setFont('Helvetica',8)
        for i in range(5):
            v=lo+(hi-lo)*i/4;yy=y(v);c.setStrokeColor(colors.HexColor('#e2e8f0'));c.line(left,yy,left+w,yy);c.setFillColor(GRAY);c.drawRightString(left-5,yy-3,num(v,1)+'%')
        for idx,col in [(2,GRAY),(0,BLUE),(1,TEAL)]:
            if idx==2 and rows[-1]['cdi'] is None:continue
            path=c.beginPath()
            for i,p in enumerate(rows):
                v=p['values'][idx] if idx<2 else p['cdi'];xx=left+w*i/max(len(rows)-1,1)
                if i==0:path.moveTo(xx,y(v))
                else:path.lineTo(xx,y(v))
            c.setStrokeColor(col);c.setLineWidth(.95 if idx<2 else .7);c.setDash();c.drawPath(path)
        c.setDash();c.setFillColor(GRAY);c.drawString(left,8,dt(rows[0]['date']));c.drawRightString(left+w,8,dt(rows[-1]['date']))
def build(r):
    buf=io.BytesIO(); styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name='HeaderBR',fontSize=8,leading=10,textColor=colors.white))
    styles.add(ParagraphStyle(name='YearBR',fontSize=11,leading=13,textColor=NAVY,spaceBefore=5,spaceAfter=4))
    styles.add(ParagraphStyle(name='MonthBR',fontSize=7,leading=9,textColor=NAVY))
    styles.add(ParagraphStyle(name='BodyBR',fontName='Helvetica',fontSize=9,leading=13,textColor=NAVY,spaceAfter=8))
    styles.add(ParagraphStyle(name='SmallBR',fontSize=8,leading=11,textColor=GRAY,spaceAfter=6))
    styles.add(ParagraphStyle(name='TitleBR',fontSize=25,leading=29,textColor=NAVY,spaceAfter=10))
    styles.add(ParagraphStyle(name='HeadBR',fontSize=14,leading=18,textColor=NAVY,spaceBefore=12,spaceAfter=10))
    def p(t,style='BodyBR'):return Paragraph(t,styles[style])
    def table(rows,widths,compact=False):
        t=Table(rows,colWidths=widths,repeatRows=1,hAlign='LEFT');t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),NAVY),('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTNAME',(0,1),(-1,-1),'Helvetica'),('FONTSIZE',(0,0),(-1,-1),8),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('TOPPADDING',(0,0),(-1,-1),5 if compact else 8),('BOTTOMPADDING',(0,0),(-1,-1),5 if compact else 8),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor('#f0f5fa'),colors.white]),('LINEBELOW',(0,0),(-1,0),.5,NAVY)]));return t
    doc=SimpleDocTemplate(buf,pagesize=A4,rightMargin=1.9*cm,leftMargin=1.9*cm,topMargin=1.7*cm,bottomMargin=1.7*cm,title='Comparativo de Previdência',author='Gabriel Garcia')
    names=[f['name'] for f in r['funds']]
    headers=[p(escape(n),'HeaderBR') for n in names]
    a,b=r['stats'];story=[p('PREVIDÊNCIA | ANÁLISE HISTÓRICA','SmallBR'),p('Seu patrimônio,\n em perspectiva'.replace('\n','<br/>'),'TitleBR'),p(f"Janela de {r['horizon']} meses | {dt(r['start'])} a {dt(r['end'])}")]
    for i,f in enumerate(r['funds']):story.append(p(f'<font color="{["#1463b8","#d95f02"][i]}"><b>{escape(f["name"])}</b></font><br/><font size="8">CNPJ {f["cnpj"]}</font>'))
    story += [p('Crescimento acumulado','HeadBR'),p(f'<font color="#1463b8">{escape(names[0])}</font> | <font color="#d95f02">{escape(names[1])}</font> | CDI: cinza','SmallBR'),Chart(r),table([['Indicador',*headers],['Retorno acumulado',pct(a['return_pct']),pct(b['return_pct'])],['Retorno anualizado',pct(a['annualized']),pct(b['annualized'])],['Volatilidade anualizada',pct(a['volatility']),pct(b['volatility'])],['Sharpe anualizado (CDI)',num(a['sharpe']),num(b['sharpe'])]],[7.2*cm,5*cm,5*cm]),Spacer(1,10),p('Rentabilidade passada não garante rentabilidade futura. Comparação informativa, sem recomendação individual de investimento.','SmallBR'),PageBreak()]
    story += [p('Quanto precisaria ter investido?','TitleBR'),p(f'Para alcançar <b>{money(r["target"])}</b> em {dt(r["end"])}, com uma única aplicação em {dt(r["start"])}, o valor inicial seria:'),table([['Simulação histórica',*headers],['Aplicação inicial necessária',money(a['required_initial']),money(b['required_initial'])],['Ganho nominal no período',money(a['gain']),money(b['gain'])],['Patrimônio final desejado',money(r['target']),money(r['target'])]],[7.2*cm,5*cm,5*cm]),Spacer(1,12),p('Cálculo: patrimônio final desejado ÷ (1 + retorno acumulado). Sem aportes ou resgates intermediários. Valores nominais: sem ajuste pela inflação, IR, carregamento ou outras condições individuais do plano. As despesas debitadas do fundo já estão refletidas na cota. Esta é uma reconstrução histórica, não uma projeção.'),p('Outras janelas de comparação','HeadBR'),table([['Janela',*headers,'Período comum']]+[[f'{x["months"]} meses',pct(x['returns'][0]),pct(x['returns'][1]),dt(x['start'])+' a '+dt(x['end']) if all(v is not None for v in x['returns']) else 'Histórico insuficiente'] for x in r['summary']],[2*cm,3.3*cm,3.3*cm,8.6*cm]),p('N/D indica ausência de histórico comum suficiente. A análise não completa cotas ausentes com estimativas.','SmallBR'),PageBreak(),p('Rentabilidade mês a mês','TitleBR'),p('Retornos compostos pela variação das cotas entre as datas observadas. Meses parciais identificados com asterisco.','SmallBR')]
    months=['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez']
    years=sorted({x['month'][:4] for x in r['monthly']},reverse=True)
    for year in years:
        by_month={int(x['month'][5:]):x for x in r['monthly'] if x['month'].startswith(year)}
        rows=[['Fundo',*months]]
        for idx,name in enumerate([*names,'CDI']):
            row=[p(escape(name),'MonthBR')]
            for month in range(1,13):
                x=by_month.get(month)
                v=(x['values'][idx] if idx<2 else x['cdi']) if x else None
                row.append((num(v)+'%' if v is not None else 'N/D')+('*' if x and x['partial'] else '') if x else '—')
            rows.append(row)
        t=table(rows,[3.7*cm]+[1.125*cm]*12,compact=True)
        t.setStyle(TableStyle([('FONTSIZE',(0,0),(-1,-1),6.2),('LEFTPADDING',(0,0),(-1,-1),2),('RIGHTPADDING',(0,0),(-1,-1),2),('TOPPADDING',(0,0),(-1,-1),2),('BOTTOMPADDING',(0,0),(-1,-1),2),('ALIGN',(1,0),(-1,-1),'CENTER'),('TEXTCOLOR',(0,1),(0,1),BLUE),('TEXTCOLOR',(0,2),(0,2),TEAL)]))
        story.append(KeepTogether([p(year,'YearBR'),t]))
    story += [Spacer(1,12),p('* Período parcial. —: mês fora da janela analisada. N/D: dado indisponível.','SmallBR'),p('Fontes e metodologia','HeadBR'),p('Cotas: CVM, Informe Diário de Fundos de Investimento (VL_QUOTA). Benchmark: Banco Central, SGS 12, CDI diário (% ao dia). Dados públicos; nomes resumidos identificados pelo CNPJ.','SmallBR'),p(f"Janela solicitada: {dt(r['start_requested'])} a {dt(r['end_requested'])}. Datas comuns utilizadas: {dt(r['start'])} a {dt(r['end'])}; {r['observations']} cotas comuns. Cada limite aceita a última cota comum até 10 dias antes da data solicitada. Base atualizada em {r['updated_at'][:10]} (UTC).",'SmallBR'),p('Volatilidade: desvio-padrão amostral dos retornos diários × √252. Sharpe: média do excesso diário sobre o CDI ÷ desvio-padrão amostral desse excesso × √252. Retorno anualizado: fator acumulado elevado a 252/n, menos 1; n = número de retornos diários. Indicadores de risco exigem ao menos 20 retornos e série diária completa alinhada ao CDI. Sem CDI, com lacunas ou com denominador nulo, o indicador correspondente aparece como N/D.','SmallBR'),p('Fundos com diferentes estratégias e riscos não são equivalentes. Confira regulamento, taxas do plano, tributação e perfil do investidor antes de uma decisão.','SmallBR')]
    method_index=next(i for i,x in enumerate(story) if isinstance(x,Paragraph) and x.text=="Fontes e metodologia")
    methodology=story[method_index:];story=story[:method_index]
    breaks=[i for i,x in enumerate(story) if isinstance(x,PageBreak)]
    story[breaks[1]:breaks[1]]=methodology
    def footer(c,doc):
        c.setStrokeColor(colors.HexColor('#dbe5ef'));c.line(1.9*cm,1.35*cm,19.1*cm,1.35*cm);c.setFont('Helvetica',8);c.setFillColor(GRAY);c.drawString(1.9*cm,1*cm,'Comparador de Previdência | Gabriel Garcia');c.drawRightString(19.1*cm,1*cm,str(doc.page))
    doc.build(story,onFirstPage=footer,onLaterPages=footer);return buf.getvalue()
