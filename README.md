# Segredos Abertos Brasil

Quanto cada deputado federal e senador gasta da cota parlamentar, com quais empresas, quem são os donos dessas empresas e como cada um vota. Tudo com dados oficiais, explicado de forma simples. Inspirado no [OpenSecrets](https://www.opensecrets.org/personal-finances) e no [Integrity Index](https://integrityindex.us/).

## Como funciona

```
etl/   coletor em Python: baixa os dados oficiais e gera arquivos JSON
site/  site e app (React + Vite, instalável no celular como PWA)
```

Um GitHub Action roda todo dia: baixa os dados, gera os JSON em `site/public/data/`, monta o site e publica no GitHub Pages.

### Fontes

| Dado | Fonte |
| --- | --- |
| Deputados, cota (CEAP), votações | [Dados Abertos da Câmara](https://dadosabertos.camara.leg.br) |
| Senadores, cota (CEAPS), votações | [Dados Abertos do Senado](https://www12.senado.leg.br/dados-abertos) |
| Empresas e sócios | Base CNPJ da Receita Federal, via [Minha Receita](https://minhareceita.org) |

## Rodar localmente

```bash
# dados (precisa de internet para os sites do governo)
cd etl
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q tests
python -m sa_etl.build --saida ../site/public/data --cache .cache --anos 2025 2026

# site
cd ../site
npm install
npm run dev
```

## Próximas etapas

1. Salários da equipe do gabinete (verba de gabinete).
2. Outras empresas do mesmo dono em toda a base da Receita (hoje: só entre fornecedores de parlamentares).
3. Doações de campanha (TSE) cruzadas com fornecedores.
4. Deputados estaduais (Assembleias) e governadores (portais estaduais).
5. App nas lojas Android e iOS.
