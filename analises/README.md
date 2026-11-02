# Painel de análises (/analises/)

Todos os dados do Segredos Abertos, do Minas Nossa, da Eleição 2026 e de Terras Raras em um painel só,
com gráficos e tabelas para baixar.

- Painel: https://amarigo.github.io/segredos-abertos/analises/
- Tabelas (CSV): https://amarigo.github.io/segredos-abertos/analises/tabelas/ e todas juntas em
  https://amarigo.github.io/segredos-abertos/analises/tabelas.zip
- Dicionário de dados (tabelas, colunas, tipos e fonte oficial): `tabelas/catalogo.json`

## Como funciona

```
analises/tabelas.py   lê os JSON que o site já usa e grava uma tabela CSV por assunto (71 tabelas)
analises/painel.html  a página do painel: gráficos com Apache ECharts, lendo as tabelas de ./tabelas/
analises/publicar.py  junta as duas coisas em site/dist/analises/ (página, tabelas e .zip)
analises/tests/       testes: totais iguais aos do site, CSV bem escrito, eleição igual ao TSE
```

O GitHub Action "Dados e site" roda `publicar.py` todo dia, depois da coleta, então o painel e as tabelas
se atualizam junto com o site. Não há coleta nova aqui: os dados vêm das APIs oficiais (Câmara, Senado,
Portal da Transparência, Tesouro, ALMG, TSE) pelo coletor em `etl/`, e cada tabela guarda o link do dado
original sempre que ele existe.

## Rodar no computador

```bash
python analises/publicar.py --nacional site/public/data --mg site/public-mg/data \
  --eleicao eleicao2026/dados/tse --terras terras-raras/dados --saida /tmp/analises
cd /tmp/analises && python -m http.server 8000   # abra http://localhost:8000
```

Sem os dados do site, rode antes `python etl/tests/gerar_dados_teste.py site/public/data` (dados fictícios).

## Por que não Power BI

O Power BI precisa de licença da Microsoft para publicar e compartilhar. O painel usa o
[Apache ECharts](https://github.com/apache/echarts) (licença Apache 2.0), que é gratuito e roda em qualquer
navegador. As tabelas CSV abrem no Excel, no LibreOffice, no Google Planilhas e também no Power BI, para
quem quiser.
