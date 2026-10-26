# Regras do projeto

## Fontes de dados: API primeiro

Para toda fonte de dados, verifique sempre se existe uma API oficial antes de
qualquer outra forma de coleta. A API é sempre a primeira opção.

Ordem de preferência:
1. API oficial (ex.: API da Câmara `dadosabertos.camara.leg.br/api/v2`, API do
   Senado `legis.senado.leg.br/dadosabertos`, API do Portal da Transparência
   `api.portaldatransparencia.gov.br`, API do Transferegov).
2. Arquivos oficiais de dados abertos para download (CSV/ZIP), quando a API
   não existe, não traz o dado ou é lenta demais para o volume.
3. Ler páginas HTML, só quando não há nenhuma das opções acima.

Ao usar a opção 2 ou 3, deixe escrito no código por que a API não serviu.
