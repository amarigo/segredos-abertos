# Segredos Abertos Brasil

Quanto cada deputado federal e senador gasta da cota parlamentar, com quais empresas, quem são os donos dessas empresas, para onde vai o dinheiro das emendas parlamentares, quais empresas e entidades mais recebem dinheiro público ou deixam de pagar impostos, e como cada um vota. Tudo com dados oficiais, explicado de forma simples. Inspirado no [OpenSecrets](https://www.opensecrets.org/personal-finances) e no [Integrity Index](https://integrityindex.us/).

## Como funciona

```
etl/          coletor em Python: baixa os dados oficiais e gera arquivos JSON
site/         site e app (React + Vite, instalável no celular como PWA)
mg/           Minas Nossa, o recorte de Minas Gerais (/mg/)
eleicao2026/  Eleição 2026 Aberta: presidente, 1º e 2º turno, urna por urna, com dados do TSE (/eleicao2026/)
terras-raras/ Terras Raras em Minas: quem explora terras raras em MG, licenças, dinheiro, leis e propostas (/terras-raras/)
analises/     Painel de análises: todos os dados em gráficos e em tabelas CSV para baixar (/analises/)
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
| Projetos em andamento (pauta dos próximos 14 dias, recém-apresentados, medidas provisórias e prazos) | [API da Câmara](https://dadosabertos.camara.leg.br/swagger/api.html) (`/eventos`, `/eventos/{id}/pauta`, `/proposicoes`) e [API do Senado](https://legis.senado.leg.br/dadosabertos/docs/) (`/plenario/agenda`, `/comissao/agenda`, `/processo`); no Minas Nossa, o arquivo de proposições da [ALMG](https://dadosabertos.almg.gov.br/) |
| O que dizem a favor e contra cada projeto em pauta | Documentos oficiais primeiro (justificação, parecer e voto em separado, pelas APIs da Câmara e do Senado). Sem nenhum documento oficial contra: notícias que falam contra, achadas pela [API do GDELT](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/) e pelos feeds RSS de busca do Google Notícias e do Bing Notícias; a frase é copiada da página da notícia, com veículo, data e link, e marcada como fonte não oficial |
| Julgamentos do STF: como cada ministro votou (Plenário Virtual: ADI, ADC, ADO, ADPF, controle concentrado e RE no mérito, últimos 6 meses) | Portal do STF: [Plenário Virtual](https://portal.stf.jus.br/hotsites/plenariovirtual/), serviços `pauta/services/calendario-service.asp`, `lista-service.asp` e `sistemas.stf.jus.br/repgeral/votacao` (o STF não tem API pública documentada) |
| Dinheiro da campanha: doadores, doador originário e fornecedores de cada campanha (2018, 2022, 2026), ligados à cota, às emendas e aos sócios das empresas | TSE: [Prestação de contas eleitorais](https://dadosabertos.tse.jus.br/dataset/prestacao-de-contas-eleitorais-2026) (endereço do arquivo pela API CKAN do portal; não há API com receitas e despesas linha a linha, e a API do DivulgaCandContas recusa robôs); CPF e nome civil pela API da Câmara (`/deputados/{id}`) e do Senado (`/senador/{codigo}`) |
| Gasto com assessores: comparação justa entre estados (por cadeira, parte do teto usada, em salários do estado, por habitante, habitantes por assessor e por deputado) | [API SIDRA do IBGE](https://apisidra.ibge.gov.br/): [população estimada](https://sidra.ibge.gov.br/tabela/6579) e [rendimento médio do trabalho](https://sidra.ibge.gov.br/tabela/5436); verba e teto na página oficial de cada deputado; secretários de hoje no [arquivo de funcionários da Câmara](https://dadosabertos.camara.leg.br/arquivos/funcionarios/json/funcionarios.json); teto e cota por estado em [Gastos parlamentares](https://www.camara.leg.br/transparencia/gastos-parlamentares) (sem API) |
| Empresas e sócios | Base CNPJ da Receita Federal, via [Minha Receita](https://minhareceita.org) |
| Emendas parlamentares (quem fez, área, quem recebeu) | [Portal da Transparência](https://portaldatransparencia.gov.br/download-de-dados/emendas-parlamentares), arquivo completo |
| Emendas Pix: em que cada prefeitura e estado gastou e a quem pagou | [API do Transferegov, Transferências Especiais](https://api-publica.transferegov.gestao.gov.br/especiais/docs): plano de ação, metas e pagamentos do relatório de gestão |
| Pagamentos do governo federal a empresas e entidades (página de incentivos) | [Portal da Transparência](https://portaldatransparencia.gov.br/download-de-dados/despesas), arquivos diários de despesas |
| Renúncia fiscal por empresa (página de incentivos) | [Portal da Transparência](https://portaldatransparencia.gov.br/download-de-dados/renuncias), com dados da Receita Federal. Pelos arquivos anuais de download: a [API de dados](https://portaldatransparencia.gov.br/api-de-dados) (consulta `renuncias-valor`, chave no secret `PORTAL_TRANSPARENCIA_CHAVE`) traz as mesmas linhas (conferido em 04/11/2026), mas não filtra por ano e leva umas 8 horas para os 4 anos do site. A API fica de reserva e é consultada toda semana para ver se já tem um ano que os arquivos não têm. O site mostra a data da última publicação oficial |
| Arrecadação e gastos: receitas, despesas por grupo e por função, gasto com pessoal de cada Poder e limites da LRF | [API do Siconfi, Tesouro Nacional](https://apidatalake.tesouro.gov.br/docs/siconfi/) (RREO anexos 1 e 2, RGF anexo 1) |
| Arrecadação por imposto, estado e setor da economia | [Receita Federal, dados de arrecadação](https://www.gov.br/receitafederal/pt-br/acesso-a-informacao/dados-abertos/receitadata/arrecadacao) (arquivos CSV; a Receita não tem API para isso) |
| Gasto do Executivo por órgão, programa, ação e tipo de despesa | [Portal da Transparência, orçamento da despesa](https://portaldatransparencia.gov.br/download-de-dados/orcamento-despesa) (arquivo anual; a API não cruza órgão com tipo de despesa) |
| Servidores do Executivo: concursados, cargos de confiança e comissionados | [Portal da Transparência, servidores SIAPE](https://portaldatransparencia.gov.br/download-de-dados/servidores) (arquivo mensal; a API só consulta servidor por servidor) |
| Funcionários da Câmara e do Senado por vínculo | [Arquivo de funcionários da Câmara](https://dadosabertos.camara.leg.br/arquivos/funcionarios/json/funcionarios.json) e [API de servidores do Senado](https://adm.senado.gov.br/adm-dadosabertos/api/v1/servidores/servidores) |
| Inflação (IPCA) para comparar anos | [API do SIDRA, IBGE](https://sidra.ibge.gov.br/tabela/1737) |

## Minha rede (/rede)

Ferramenta pessoal para acompanhar políticos como uma rede. Ao seguir um político, a rede dele se monta com os dados
oficiais do próprio site: empresas pagas com a cota e seus sócios, votações recentes, projetos votados, partido e
destino das emendas Pix. Cada ligação guarda a fonte oficial (com link) e, quando há, o trecho de origem.

- **Visões:** mapa do político (foto no centro e blocos: quem recebeu da cota e seus donos, emendas Pix, últimos
  votos), lado a lado (uma coluna por político, com destaque dourado no que se repete), ranking em barras com fotos,
  em comum (os políticos como estações e, nas linhas, as empresas, donos e lugares que dividem), círculo e grafo livre.
  Clicar em qualquer item abre a ficha com a fonte de cada ligação.
- **Fontes próprias:** a pessoa cola um texto (notícia, documento, transcrição) ou abre um arquivo .txt, .md ou .html.
  O app encontra os políticos e empresas citados e transforma as frases marcadas em afirmações ligadas a quem elas citam.
- **Conexões que você ainda não fez:** objetos sem ligação direta, mas com ligações em comum.
- **Perguntar:** busca nas fontes e nas ligações, com resposta em trechos e o link de cada um.
- **Comparar:** indicadores de vários políticos lado a lado; a comparação guardada mostra depois o que mudou.
- **Novidades:** ao abrir a página, mostra o que mudou em cada político seguido desde a última visita (gastos, votos,
  empresas novas, partido, emendas).

A base fica só no navegador (IndexedDB), com exportar e importar em JSON; nada é enviado. Código em `site/src/rede/` e
`site/src/pages/Rede.tsx`; testes em `site/tests/rede.test.ts` e `site/e2e/rede.spec.ts`.

## Painel de status (/status/)

[amarigo.github.io/segredos-abertos/status/](https://amarigo.github.io/segredos-abertos/status/) mostra se a coleta diária
rodou, quando cada site foi atualizado, se as atualizações estão funcionando e, quando não estão, por quê: um resumo
(verde, amarelo ou vermelho), um calendário dos últimos 30 dias, cada parte da coleta com a última vez que funcionou,
o tempo de cada parte, a duração das coletas, os avisos da versão no ar, a verificação com a segunda fonte e o
histórico com o motivo de cada falha. É uma página estática (`status/index.html` e `status/painel.js`, sem bibliotecas)
que lê tudo na hora, no navegador, pela [API oficial do GitHub Actions](https://docs.github.com/pt/rest/actions) e
pelos arquivos publicados (`data/meta.json`, `data/verificacao.json`, `mg/data/meta.json`). Por isso mostra a situação
real mesmo quando uma coleta falha e o site não é publicado de novo. O motivo de cada problema chega como anotação do
GitHub Actions (`::error`/`::warning`), escrita pelos validadores e por `etl/anotar.py`. As contas do painel são
testadas em `status/painel.test.mjs` (`node --test status/painel.test.mjs`).

## Corrupção (/corrupcao)

Os maiores escândalos (Mensalão, Sanguessugas, Petrolão, Lava Jato, Banco Master, Careca do INSS e políticos cassados),
com linha do tempo, pessoas e a situação de cada uma na Justiça, delações e acordos, empresas, o que dizem a esquerda,
a direita e a Justiça, e um placar por partido. Não existe API oficial que junte processos, delações e cassações, então
o conteúdo é escrito à mão em `site/src/corrupcao/dados.ts`, cada item com o link da fonte original, e conferido na data
de `ATUALIZADO_EM`. Esquerda, centro ou direita vêm da pesquisa de Bolognesi, Ribeiro e Codato (revista Dados, 2023).
Os testes em `site/tests/corrupcao.test.ts` exigem fonte https em tudo e conferem as contas do placar.

## Painel de análises (/analises/)

Todos os dados dos sites (gastos, votações, partidos, empresas e donos, emendas, incentivos, contas do Brasil,
projetos, Minas Gerais, Eleição 2026 e terras raras) em um painel com gráficos e 71 tabelas CSV para baixar, cada
uma com o link da fonte oficial. Os gráficos usam o [Apache ECharts](https://github.com/apache/echarts) (licença
Apache 2.0). O painel é montado todo dia junto com o site e não faz coleta nova. Detalhes em
[analises/README.md](analises/README.md).

## Terras Raras em Minas (/terras-raras/)

Rastreador da mineração de terras raras em Minas Gerais: projetos e áreas com potencial num mapa interativo, empresas,
donos e países, donos da terra, licenças pendentes, painel com os números econômicos, processos e notícias, leis,
impactos ambientais e propostas para legisladores. Não existe API oficial que junte esses dados, então eles ficam em
planilhas CSV escritas à mão em `terras-raras/dados/`, cada linha com o link da fonte e a data em que foi conferida.
`python terras-raras/gerar_pagina.py --site site/dist/terras-raras/index.html` monta a página (um único HTML, mapa com
Leaflet e a malha municipal do IBGE). Dicas do público chegam como issues com a etiqueta `terras-raras`. Como atualizar:
[terras-raras/COMO_ATUALIZAR.md](terras-raras/COMO_ATUALIZAR.md).

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

## Idiomas (português, inglês e espanhol)

Os três sites (Brasil, Minas Nossa e Eleição 2026) têm os botões PT, EN e ES na barra dos projetos. Português é o
padrão. A tradução é feita no navegador por `site/public/i18n/tradutor.js`, com dicionários escritos à mão
(`site/public/i18n/en.json` e `es.json`; a Eleição 2026 tem os seus em `eleicao2026/site/i18n/`). Os dados oficiais
não são traduzidos: nomes de pessoas, empresas, partidos, programas, leis e categorias de gasto ficam como na fonte.
O link de cada idioma é o endereço com `?lang=en` ou `?lang=es`, e a escolha fica guardada no navegador.

Para achar textos novos sem tradução, com o site servido localmente:
`node scripts/textos.mjs http://localhost:4173/ public/i18n` (gera `faltando.json`).

## Buscadores e IAs

- `npm run paginas` e `npm run paginas:mg`, depois do build, geram uma página HTML simples (sem JavaScript) por
  político, empresa e votação, em português, inglês e espanhol, com link para a fonte oficial. Também geram
  `sitemap.xml` e `llms.txt` (um resumo do site e dos dados para assistentes de IA).
- Cada página tem título, descrição, `hreflang`, Open Graph e dados estruturados (schema.org).
- `robots.txt` libera buscadores e robôs de IA. Atenção: no GitHub Pages sem domínio próprio, os buscadores só leem
  o `robots.txt` da raiz do domínio (`amarigo.github.io/robots.txt`), então o arquivo daqui só vale se o site
  ganhar um domínio próprio. Para o Google achar todas as páginas logo, cadastre
  `https://amarigo.github.io/segredos-abertos/sitemap.xml` no Google Search Console.

## Testes e qualidade

Testes unitários e de propriedades, integração com os sites do governo simulados, engenharia de caos e testes no
navegador. A cada coleta, os dados só são publicados se passarem na conferência (`etl/sa_etl/validar.py`): somas,
votos repetidos, CPFs, links e quedas bruscas. Veja [TESTES.md](TESTES.md).

**Verificação independente** (`etl/sa_etl/verificar.py`): todo dia sorteamos números já prontos para o site e conferimos
cada um numa **segunda fonte oficial**, diferente da usada na coleta (por exemplo, a cota dos deputados vem do arquivo
anual da Câmara e é conferida na API da Câmara; o placar do Senado vem do painel e é conferido com a ata da sessão). Cada
seção do site mostra um selo com o resultado, e a página "Como conferimos os números" lista as diferenças com o link
para a fonte. As conferências se somam por 90 dias: com n números conferidos e nenhuma diferença, temos 95% de confiança
de que pelo menos 1 − 0,05^(1/n) estão certos. Para afirmar 99,99% são precisos cerca de 30 mil números conferidos sem
erro. Uma seção só aparece como conferida se todas as suas checagens rodaram e nenhuma achou diferença.

**Número oficial** (`etl/sa_etl/oficial.py`): quando duas publicações oficiais mostram números diferentes, entendemos o
motivo e o site usa o número oficial. Cada motivo entendido fica registrado em `oficial.py` (o que acontece e o que o
site faz), e a coleta aplica a decisão: por exemplo, o total da cota do Senado não soma as notas sem tipo de despesa
(como o total oficial do Senado), e o placar do Senado é o da ata quando ela difere do painel. A cada atualização, a
verificação classifica cada diferença: com motivo conhecido, aparece explicada; sem motivo, o número fica "em revisão"
na página, com o número oficial ao lado. Se uma seção tiver mais de 2% de diferenças sem motivo (com pelo menos 20
números conferidos), a publicação é barrada e o site continua com a versão anterior, até o motivo ser entendido e
registrado. Os avisos sobre os dados ficam sempre no fim de cada página, depois dos números.

## Próximas etapas

1. Salários da equipe do gabinete (verba de gabinete).
2. Outras empresas do mesmo dono em toda a base da Receita (hoje: só entre fornecedores de parlamentares).
3. Doações de campanha (TSE) cruzadas com fornecedores.
4. Deputados estaduais (Assembleias) e governadores (portais estaduais).
5. App nas lojas Android e iOS.
