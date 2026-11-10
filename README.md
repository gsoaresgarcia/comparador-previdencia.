# Comparador de Previdência — CVM

Aplicação Flask para comparar **rentabilidade histórica** pela variação da cota de dois fundos registrados na CVM, com janelas móveis de 6, 12, 24, 36, 48 e 60 meses, data final selecionável e PDF.

## Publicação no Render

1. Envie todos os arquivos e a pasta `templates/` deste projeto à raiz do repositório GitHub.
2. No Render, escolha **New > Blueprint**, conecte o repositório e confirme o serviço definido em `render.yaml`.
3. Aguarde o deploy e abra a URL `https://...onrender.com` fornecida pelo Render.

Alternativamente, **New > Web Service**: Python, build `pip install -r requirements.txt`, start `gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 240`.

## Desenvolvimento local

```bash
pip install -r requirements.txt
python app.py
```

Acesse http://localhost:5000.

## Observações importantes

- Fonte: arquivos mensais de **Informe Diário de FI** da CVM, campo `VL_QUOTA`. Pesquisa no cadastro CVM `cad_fi.csv`.
- O retorno é `(cota final / cota inicial - 1) * 100`. Não contempla taxas de previdência, tributos, fluxos, nem regras de carregamento ou rentabilidade individual.
- A data efetiva de cada extremidade pode variar por fundo; só se aceita uma cota observada até 10 dias antes da data-alvo. Ausência de histórico é indicada como indisponível, nunca preenchida com estimativas.
- A primeira consulta a 60 meses pode ser **muito lenta** ou ultrapassar limites de rede/memória do plano gratuito do Render. O cache é em memória e reinicia com a instância. Para uso intenso, implemente ingestão incremental em banco de dados.
- Dados de classes de fundos reestruturados conforme CVM 175 podem exigir identificação adicional; confirme se o CNPJ escolhido corresponde ao produto previdenciário do cliente.
- Não implementa ainda carteira por emissor, composição de ativos nem comparação com benchmark.
- **Não use em comunicação com clientes sem conferir os resultados com o extrato e a base oficial.**
