# Segredos Abertos Brasil

Quanto cada deputado federal e senador gasta da cota parlamentar, com quais empresas, quem são os donos dessas empresas, para onde vai o dinheiro das emendas parlamentares, quais empresas e entidades mais recebem dinheiro público ou deixam de pagar impostos, e como cada um vota. Tudo com dados oficiais, explicado de forma simples. Inspirado no [OpenSecrets](https://www.opensecrets.org/personal-finances) e no [Integrity Index](https://integrityindex.us/).

## Como funciona

```
etl/          coletor em Python: baixa os dados oficiais e gera arquivos JSON
site/         site e app (React + Vite, instalável no celular como PWA)
mg/           Minas Nossa, o recorte de Minas Gerais (/mg/)
eleicao2026/  Eleição 2026 Aberta: presidente, 1º e 2º turno, urna por urna, com dados do TSE (/eleicao2026/)
```

Um GitHub Action roda todo dia: baixa os dados, gera os JSON em `site/public/data/`, monta o site e publica no GitHub Pages.

Se algum site oficial não responder, a coleta usa a última cópia que tem, mostra um aviso no site com a data dessa
cópia e tenta de novo sozinha a cada 2 horas ([`tentar-de-novo.yml`](.github/workflows/tentar-de-novo.yml)) até
todos os sites responderem.

**Atualizar na hora:** abra [Actions > Dados e site](https://github.com/amarigo/segredos-abertos/actions/workflows/dados-e-site.yml),
clique em **Run workflow** e confirme com o branch `main`. Em cerca de 30 a 60 minutos o site é publicado de novo.

### Fontes

| Dado | Fonte |
| --- | --- |
| Deputados, cota (CEAP), votações | [Dados Abertos da Câmara](https://dadosabertos.camara.leg.br) |
| Senadores, cota (CEAPS), votações | [Dados Abertos do Senado](https://www12.senado.leg.br/dados-abertos) |
| Empresas e sócios | Base CNPJ da Receita Federal, via [Minha Receita](https://minhareceita.org) |
| Emendas parlamentares (quem fez, área, quem recebeu) | [Portal da Transparência](https://portaldatransparencia.gov.br/download-de-dados/emendas-parlamentares), arquivo completo |
| Pagamentos do governo federal a empresas e entidades (página de incentivos) | [Portal da Transparência](https://portaldatransparencia.gov.br/download-de-dados/despesas), arquivos diários de despesas |
| Renúncia fiscal por empresa (página de incentivos) | [Portal da Transparência](https://portaldatransparencia.gov.br/download-de-dados/renuncias), com dados da Receita Federal. Se o download dos arquivos falhar, a coleta usa a [API de dados](https://portaldatransparencia.gov.br/api-de-dados) (consulta `renuncias-valor`), com a chave no secret `PORTAL_TRANSPARENCIA_CHAVE` |

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

## Testes e qualidade

Testes unitários e de propriedades, integração com os sites do governo simulados, engenharia de caos e testes no
navegador. A cada coleta, os dados só são publicados se passarem na conferência (`etl/sa_etl/validar.py`): somas,
votos repetidos, CPFs, links e quedas bruscas. Veja [TESTES.md](TESTES.md).

## Próximas etapas

1. Salários da equipe do gabinete (verba de gabinete).
2. Outras empresas do mesmo dono em toda a base da Receita (hoje: só entre fornecedores de parlamentares).
3. Doações de campanha (TSE) cruzadas com fornecedores.
4. Deputados estaduais (Assembleias) e governadores (portais estaduais).
5. App nas lojas Android e iOS.
