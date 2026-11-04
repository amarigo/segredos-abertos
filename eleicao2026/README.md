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
   Quando o TSE publicou o bweb do 2º turno (27/10/2026), `bweb2.py` conferiu o SHA-512 de cada arquivo e comparou
   seção por seção: votos, comparecimento, aptos e horários iguais nas 499.205 urnas. A hora de recebimento de cada
   boletim passou a ser a do bweb (`DT_BU_RECEBIDO`); a antiga, do `-aux.json`, fica em `rec_aux`.
4. `analisar.py` converte a hora de cada urna para Brasília (o fuso de cada cidade sai da hora em que as urnas
   abriram) e soma os votos das urnas que fecharam depois de cada horário de corte.
5. `noite.py` refaz a apuração ao longo da noite: soma os boletins na ordem em que o TSE os recebeu (hora oficial de
   recebimento de cada boletim) e guarda a parcial a cada 5 minutos, no Brasil e em cada estado.
6. `logs.py` baixa o registro (log) de cada urna, nos dois turnos, e conta as linhas "O voto do eleitor foi
   computado" do dia da eleição, com a hora de cada uma. Guarda, por urna, quantos votos vieram depois das 17h
   de Brasília (em `dados/brutos/<turno>turno_log/`). O registro não diz em quem foi o voto (o voto é secreto).
   `depois17.py` junta isso aos boletins. Só entram as urnas em que o total de votos do registro é igual ao
   comparecimento do boletim; se faltar o registro de alguma urna, o site não é publicado.
7. `locais.py` baixa o arquivo oficial "Eleitorado por local de votação - 2026" (Portal de Dados Abertos do TSE),
   com o local de votação, a latitude e a longitude de cada seção, e guarda em `dados/tse/locais_votacao_2026.jsonl.gz`.
   `mudancas.py` soma as urnas por cidade e por local de votação nos dois turnos (a soma das cidades tem que dar o
   total oficial) e faz os testes estatísticos: valores impossíveis, a mesma urna nos dois turnos, último dígito e
   comparecimento × votos.
8. `validar.py` confere antes de publicar: a soma das urnas tem que ser igual ao total oficial, voto por voto
   (cada candidato, brancos, nulos e comparecimento), no Brasil, em cada estado e no exterior. Se não bater, o
   site da eleição não é publicado.
9. `montar.py` põe os números na página e gera as planilhas por estado para baixar.

O GitHub Action do Segredos Abertos roda os testes, monta e confere o site da eleição a partir de `dados/` e
publica em `/eleicao2026/`. Uma falha aqui não trava o site nacional.

### Fontes

| Dado | Fonte |
| --- | --- |
| Resultados oficiais por estado | [Site de resultados do TSE](https://resultados.tse.jus.br/oficial/app/index.html) |
| Urnas do 1º turno (horário e votos) | [Boletim de Urna, Portal de Dados Abertos do TSE](https://dadosabertos.tse.jus.br/dataset/resultados-2026-boletim-de-urna) |
| Urnas do 2º turno (horário e votos) | Boletim de urna digital de cada seção, no [site de resultados do TSE](https://resultados.tse.jus.br/oficial/app/index.html), conferido seção por seção com o [Boletim de Urna do 2º turno, Portal de Dados Abertos do TSE](https://dadosabertos.tse.jus.br/dataset/resultados-2026-boletim-de-urna) |
| Hora em que o TSE recebeu cada boletim | 1º turno: campo `DT_BU_RECEBIDO` do Boletim de Urna; 2º turno: campo `DT_BU_RECEBIDO` do Boletim de Urna do 2º turno |
| Hora de cada voto (sem o voto) | Registro (log) de cada urna (`-log.jez`), no [site de resultados do TSE](https://resultados.tse.jus.br/oficial/app/index.html) |
| Local de votação de cada seção, com latitude e longitude | [Eleitorado por local de votação - 2026, Portal de Dados Abertos do TSE](https://dadosabertos.tse.jus.br/dataset/eleitorado-2026) |
| Fotos dos candidatos | Fotos oficiais do [site de resultados do TSE](https://resultados.tse.jus.br/oficial/app/index.html) |
| Mapa | MapSVG, pacote [@svg-maps/brazil](https://www.npmjs.com/package/@svg-maps/brazil) (CC BY 4.0) |

O único texto que não é do TSE é o quadro sobre a prorrogação até as 19h no 2º turno: são fatos relatados pela
imprensa, marcados como "Notícia", de veículos de perfis diferentes.

## Quem assume em 2027 (eleitos/)

Página com os governadores, senadores, deputados federais, estaduais e distritais eleitos em 2026, para o mandato que
começa em 2027: partido, federação, coligação, votos, foto oficial, vice ou suplentes, quem foi reeleito e quem é novo
no cargo. Publicada em https://amarigo.github.io/segredos-abertos/eleicao2026/eleitos/.

```
dados/eleitos/resultados/   resultado de cada cargo e estado, como veio do TSE (.json.gz)
dados/eleitos/candidatos.csv.gz   do arquivo de candidatos do TSE, só os cargos estaduais e federais e só as colunas usadas
dados/eleitos/vagas.csv     vagas de cada cargo em cada estado (arquivo de vagas do TSE)
dados/eleitos/camara.json, senado.json   deputados federais e senadores de hoje (APIs da Câmara e do Senado)
dados/eleitos/coleta.json   quando foi baixado e de onde
```

1. `eleitos.py` baixa o resultado da eleição estadual (6259, 1º turno, e 6260, 2º turno de governador) do site de
   resultados do TSE, os mesmos arquivos JSON que o aplicativo oficial lê. A API do DivulgaCandContas recusa acesso
   automático (HTTP 403), por isso não é usada.
2. Confere com a segunda fonte do TSE, os arquivos abertos achados pela API do Portal de Dados Abertos: o número de
   eleitos de cada cargo em cada estado tem que ser igual ao de vagas, cada eleito tem que constar como eleito no
   arquivo de candidatos (e vice-versa) e a apuração tem que estar em 100%. Se algo não bater, a página não mostra
   nenhum número, só diz que os eleitos estão em conferência; o resto do site da eleição continua.
3. "Reeleito": primeiro o campo `ST_REELEICAO` do registro da candidatura no TSE. Em 2026 o TSE publicou esse campo
   vazio (`#NE`, no arquivo complementar; conferido em 04/11/2026). Por isso, para deputado federal e senador, vale quem
   está no exercício do mesmo cargo hoje, segundo as APIs da Câmara e do Senado. Para governador e deputado estadual
   não há fonte oficial única de quem está no cargo hoje: a página não marca reeleito nem novo. Se o TSE preencher o
   campo, ele passa a valer sozinho na próxima coleta.
4. Quem já é deputado federal ou senador é achado nas APIs da Câmara e do Senado pelo dia de nascimento e pelo nome
   civil. O eleito ganha o link para o perfil oficial e para os gastos e votos que o Segredos Abertos já mostra.
5. A página também lê, no navegador, o `politicos.json` e o `partidos.json` do site do Brasil: a cota usada neste
   mandato e o lado de cada partido medido pelos votos na Câmara.

Para baixar de novo: Actions > Eleitos 2026 > Run workflow. O workflow guarda o que baixou neste diretório, no próprio
branch. Vale rodar depois de uma decisão da Justiça Eleitoral que mude um resultado e em fevereiro de 2027, quando a
Câmara publicar a 58ª legislatura: aí os deputados novos também ganham o link para os seus gastos e votos.

Localmente (precisa de acesso ao TSE): `python -m el_etl.build eleitos --baixar`. Sem `--baixar`, só confere o que já
está em `dados/eleitos/` e mostra o resumo.

O que já se ajusta sozinho em 2027, sem mudar código: a coleta da Câmara e do Senado (`etl/sa_etl/camara.py`,
`senado.py`) pega as legislaturas de todos os anos acompanhados, então a 58ª entra junto com a 57ª a partir de
fevereiro; a da ALMG (`mg/etl/mg_etl/almg.py`) passa da 20ª para a 21ª legislatura do mesmo jeito.

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
| Gráfico da noite diferente do oficial | `test_noite`, `test_ponta_a_ponta::test_site_completo`, e2e confere que a última parcial é igual ao total oficial | a página mostra a conferência e as seções sem hora |
| Boletim lido errado | `test_boletim` (boletim de urna verdadeiro do TSE) | soma tem que bater com o oficial |
| Página quebrada ou número diferente do oficial na tela | `site/e2e/eleicao2026.spec.ts` (computador e celular, com caos) | testes no navegador antes de publicar |
| Eleito faltando, sobrando ou trocado | `test_eleitos::test_falta_um_eleito_bloqueia`, `test_falta_um_estado_bloqueia`, `test_apuracao_incompleta_bloqueia` | número de eleitos = vagas do TSE e cada eleito consta como eleito no arquivo de candidatos; se não, a página dos eleitos não mostra números |
| Ligar o eleito à pessoa errada (homônimo, irmão gêmeo) | `test_eleitos::test_mesma_pessoa` | mesmo dia de nascimento e mesmo primeiro nome; com dúvida (mais de uma pessoa), não liga |
| Marcar reeleito sem fonte | `test_eleitos::test_reeleicao_sem_o_campo_do_tse_usa_camara_e_senado` | sem o campo do TSE, só deputado federal e senador são marcados, pelo exercício do cargo hoje |
| Página dos eleitos quebrada ou com número diferente do arquivo | `site/e2e/eleicao2026.spec.ts` (eleitos, computador e celular, sem os dados do site do Brasil) | testes no navegador antes de publicar |
