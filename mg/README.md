# Minas Nossa

O recorte de Minas Gerais do Segredos Abertos, publicado em https://amarigo.github.io/segredos-abertos/mg/.

- `etl/mg_etl/recorte.py`: deputados federais e senadores de MG, a partir dos dados nacionais gerados na mesma execução.
- `etl/mg_etl/tse.py` e `cidades.py`: histórico de cada cidade desde 1996 (prefeito, vice, vereadores por partido, como a cidade votou), com os arquivos de dados abertos do TSE.
- `etl/mg_etl/partidos_hist.py`: o nome de hoje dos partidos que mudaram de nome ou se juntaram a outros.
- `etl/mg_etl/almg.py`: deputados estaduais da ALMG, com a verba indenizatória nota por nota (API mensal da ALMG; só o ano atual e o anterior, `ANOS_RECENTES`; cada execução baixa até 700 meses, do mais novo para o mais antigo, e o site avisa enquanto um ano está incompleto), projetos e requerimentos.
- `etl/mg_etl/emendas_mg.py`: emendas estaduais (quem indicou, quem recebeu, quanto foi pago).
- `etl/mg_etl/governo.py` e `equipe.py`: eleições para governador e vice (TSE) e, pelo Dados MG, o salário e as viagens pagas ao governador, vice e secretários de estado.
- `etl/mg_etl/siconfi.py` e `emendas_federais.py`: o dinheiro de cada cidade (contas da prefeitura no SICONFI e emendas federais no Portal da Transparência).
- `etl/mg_etl/fontes.py`: funções comuns; `sem_cpf` apaga qualquer número com cara de CPF de textos livres (nome de fornecedor, motivo de viagem).
- `etl/mg_etl/validar.py`: a conferência antes de publicar.
- O site é o mesmo do nacional, montado com `npm run build:mg` (pasta `site/`).

Para incluir uma cidade, acrescente-a em `CIDADES` (`etl/mg_etl/cidades.py`).

Rodar localmente (de dentro de `mg/etl`):

```bash
PYTHONPATH=../../etl python -m mg_etl.build --nacional ../../site/public/data --saida ../../site/public-mg/data --cache .cache
PYTHONPATH=../../etl python -m mg_etl.validar ../../site/public-mg/data
```
