# Eleição 2026 Aberta

A eleição para presidente de 2026, 1º e 2º turno, estado por estado e urna por urna, com dados oficiais do TSE.
Mostra onde estão as diferenças de votos, quais urnas fecharam depois das 17h (e o resultado com e sem elas) e tem
um simulador por estado. Publicado em https://amarigo.github.io/segredos-abertos/eleicao2026/.

Nada aqui é segredo: os boletins de urna lidos, o código e cada conta estão neste diretório. Qualquer pessoa pode
refazer tudo e chegar aos mesmos números.

## Como funciona

```
dados/tse/        resultados oficiais do TSE (Brasil, cada estado e exterior), arquivos "-u.json" como vieram
dados/brutos/     boletim de cada seção, já lido: hora de abertura, hora de encerramento e votos (um .jsonl.gz por estado)
etl/el_etl/       coletor e análise em Python
site/             a página (HTML, CSS e JavaScript, sem build) e o desenho do mapa
```

1. `oficial.py` baixa os resultados oficiais do site de resultados do TSE.
2. `turno1.py` baixa, para cada estado, o arquivo "Boletim de Urna" do Portal de Dados Abertos do TSE e guarda
   uma linha por seção com a hora de abertura, a hora de encerramento e os votos para presidente.
3. `turno2.py` faz o mesmo para o 2º turno, lendo o boletim de urna digital (.bu) de cada seção no site de
   resultados, porque o arquivo do Portal ainda não tinha saído. `ber.py` lê o formato do boletim (ASN.1/BER).
4. `analisar.py` converte a hora de cada urna para Brasília (o fuso de cada cidade sai da hora em que as urnas
   abriram) e soma os votos das urnas que fecharam depois de cada horário de corte.
5. `validar.py` confere antes de publicar: a soma das urnas tem que ser igual ao total oficial, voto por voto
   (cada candidato, brancos, nulos e comparecimento), no Brasil, em cada estado e no exterior. Se não bater, o
   site da eleição não é publicado.
6. `montar.py` põe os números na página e gera as planilhas por estado para baixar.

O GitHub Action do Segredos Abertos roda os testes, monta e confere o site da eleição a partir de `dados/` e
publica em `/eleicao2026/`. Uma falha aqui não trava o site nacional.

### Fontes

| Dado | Fonte |
| --- | --- |
| Resultados oficiais por estado | [Site de resultados do TSE](https://resultados.tse.jus.br/oficial/app/index.html) |
| Urnas do 1º turno (horário e votos) | [Boletim de Urna, Portal de Dados Abertos do TSE](https://dadosabertos.tse.jus.br/dataset/resultados-2026-boletim-de-urna) |
| Urnas do 2º turno (horário e votos) | Boletim de urna digital de cada seção, no [site de resultados do TSE](https://resultados.tse.jus.br/oficial/app/index.html) |
| Mapa | MapSVG, pacote [@svg-maps/brazil](https://www.npmjs.com/package/@svg-maps/brazil) (CC BY 4.0) |

O único texto que não é do TSE é o quadro sobre a prorrogação até as 19h no 2º turno: são fatos relatados pela
imprensa, marcados como "Notícia", de veículos de perfis diferentes.

## Rodar localmente

```bash
cd eleicao2026/etl
pip install -r ../../etl/requirements.txt -r ../../etl/requirements-dev.txt
python -m pytest -q tests

# monta o site a partir de dados/ (confere com o oficial antes)
python -m el_etl.build montar --saida ../../site/dist/eleicao2026
python -m http.server 8000 --directory ../../site/dist   # abra http://localhost:8000/eleicao2026/

# baixa tudo de novo do TSE (demora: são mais de 500 mil seções no 2º turno)
python -m el_etl.build coletar --turno 1 2
```

Testes no navegador (de dentro de `site/`, depois de montar): `npm run test:e2e:eleicao`.

## Números conferidos

| | 1º turno | 2º turno |
| --- | --- | --- |
| Registros de seção lidos | 499.206 | 517.179 |
| Urnas com horário de fechamento | 499.176 | 499.178 |
| Seções agregadas (votaram na mesma urna de outra) | | 17.931 |
| Soma das urnas = total oficial do TSE | sim, voto por voto | sim, voto por voto |

No 1º turno, o TSE conta como nulo o voto no número 28 (candidatura que não valeu). A conferência faz o mesmo.

## Riscos e testes

| Risco | Testes | Trava em produção |
| --- | --- | --- |
| Soma das urnas diferente do oficial | `test_validar`, `test_ponta_a_ponta::test_nao_publica_se_nao_bater` | `validar.py` bloqueia a publicação |
| Seção contada duas vezes | `test_validar::test_secao_repetida_bloqueia` | `validar.py` bloqueia |
| Fuso errado (hora de Brasília errada) | `test_analisar::test_fuso_*`, `test_todas_fecham_as_17h_*` | fuso tirado da hora de abertura de cada cidade |
| Boletim lido errado | `test_boletim` (boletim de urna verdadeiro do TSE) | soma tem que bater com o oficial |
| Página quebrada ou número diferente do oficial na tela | `site/e2e/eleicao2026.spec.ts` (computador e celular, com caos) | testes no navegador antes de publicar |
