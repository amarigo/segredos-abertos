# Minas Nossa

O recorte de Minas Gerais do Segredos Abertos, publicado em https://amarigo.github.io/segredos-abertos/mg/.

- `etl/mg_etl/recorte.py`: deputados federais e senadores de MG, a partir dos dados nacionais gerados na mesma execução.
- `etl/mg_etl/tse.py` e `cidades.py`: histórico de cada cidade desde 1996 (prefeito, vice, vereadores por partido, como a cidade votou), com os arquivos de dados abertos do TSE.
- `etl/mg_etl/partidos_hist.py`: o nome de hoje dos partidos que mudaram de nome ou se juntaram a outros.
- `etl/mg_etl/validar.py`: a conferência antes de publicar.
- O site é o mesmo do nacional, montado com `npm run build:mg` (pasta `site/`).

Para incluir uma cidade, acrescente-a em `CIDADES` (`etl/mg_etl/cidades.py`).

Rodar localmente (de dentro de `mg/etl`):

```bash
PYTHONPATH=../../etl python -m mg_etl.build --nacional ../../site/public/data --saida ../../site/public-mg/data --cache .cache
PYTHONPATH=../../etl python -m mg_etl.validar ../../site/public-mg/data
```
