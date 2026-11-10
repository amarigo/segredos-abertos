# Segredos Abertos: guia do projeto

Portal de transparência sobre o dinheiro público no Brasil: gastos da cota parlamentar, votações, emendas
parlamentares, arrecadação e gastos da União, incentivos a empresas e projetos em andamento (tramitação).
Sites irmãos no mesmo repositório: Minas Nossa (`/mg/`), Eleição 2026 (`/eleicao2026/`), Terras Raras em Minas
(`/terras-raras/`), painel de análises (`/analises/`) e painel de status (`/status/`).
Publicado em https://amarigo.github.io/segredos-abertos/. Visão geral em [README.md](README.md).

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

## Tecnologia

- Coleta (ETL): Python 3.12 (`etl/sa_etl`, `mg/etl/mg_etl`, `eleicao2026/etl/el_etl`). Dependências fixas em
  `etl/requirements.txt` (`requests`, `numpy`, `pypdf` para ler o texto dos pareceres). Não há backend nem servidor: o resultado da coleta são arquivos JSON.
- Site e app: React 18 + TypeScript + Vite (`site/`), instalável no celular como PWA. O Minas Nossa é o mesmo site,
  montado com `--mode mg`. Eleição 2026 (`eleicao2026/site/`), Terras Raras (`terras-raras/gerar_pagina.py`) e o
  painel de status (`status/`) são páginas próprias, sem React.
- Dados: arquivos JSON gerados em `site/public/data/` e `site/public-mg/data/` (fora do git). Downloads e consultas
  de CNPJ ficam em `etl/.cache/`, guardado entre execuções pelo cache do GitHub Actions. Dados escritos à mão ficam
  em `terras-raras/dados/*.csv` e `site/src/corrupcao/dados.ts`, cada item com link da fonte.
- Hospedagem e publicação: GitHub Pages, publicado pelo workflow
  [`dados-e-site.yml`](.github/workflows/dados-e-site.yml) (job `publicar`).

## Atualização

- Todo dia às **3h17 de Brasília** (`cron: "17 6 * * *"`, UTC) o workflow "Dados e site" roda os testes, coleta,
  confere, verifica com a segunda fonte, monta todos os sites e publica. Também roda a cada push no `main`.
- Se uma fonte oficial falhar, a coleta usa a última cópia boa, mostra aviso com a data dela, e
  [`tentar-de-novo.yml`](.github/workflows/tentar-de-novo.yml) tenta de novo a cada 2 horas até tudo responder.
- Para atualizar na hora: Actions > Dados e site > Run workflow (branch `main`). Opções `ignorar_queda` e
  `ignorar_barreira` só quando a queda ou a diferença for real e entendida.

## Fontes de dados

Todas as áreas abaixo são coletadas todo dia, na execução das 3h17 (os dados de origem mudam no ritmo de cada fonte).

| Área | Fonte (API primeiro) | Coletor |
|---|---|---|
| Gastos: cota dos deputados (CEAP) | API da Câmara (`/deputados`); notas pelo arquivo anual `camara.leg.br/cotas/Ano-{ano}.csv.zip` (volume); passagens e página oficial do deputado para completar | `etl/sa_etl/camara.py`, `passagens.py`, `recursos.py` |
| Gastos: cota dos senadores (CEAPS) | API administrativa do Senado (`adm.senado.gov.br/adm-dadosabertos/api/v1/senadores/despesas_ceaps/{ano}`) | `etl/sa_etl/senado.py` |
| Gastos: servidores do Executivo, da Câmara e do Senado | Portal da Transparência, arquivo mensal do SIAPE (a API só consulta servidor por servidor); arquivo de funcionários da Câmara; API de servidores do Senado | `etl/sa_etl/fin_pessoal.py` |
| Gasto com assessores: comparação justa entre estados | API SIDRA do IBGE (população, tabela 6579; rendimento do trabalho principal da PNAD Contínua, tabela 5436; a outra API do IBGE, `servicodados`, recusa o GitHub Actions); verba e teto de cada deputado pela página oficial (`recursos.py`); secretários de hoje pelo arquivo de funcionários da Câmara; teto mensal, faixa de salário e cota por estado pela página "Gastos parlamentares" da Câmara (sem API); equipe dos senadores pela API administrativa do Senado | `etl/sa_etl/gabinetes.py` |
| Empresas e donos | Base CNPJ da Receita Federal, via Minha Receita | `etl/sa_etl/cnpj.py` |
| Votações | Câmara: arquivos de votações em CSV, conferidos com a API (`/votacoes/{id}/votos`); Senado: API `/votacao` | `etl/sa_etl/camara.py`, `senado.py`, `temas.py`, `ideologia.py` |
| Emendas | Portal da Transparência, arquivo completo de emendas (ZIP); pagamentos pelos arquivos diários de despesas | `etl/sa_etl/emendas.py`, `pagamentos.py` |
| Emendas Pix: em que a prefeitura gastou e a quem pagou | API do Transferegov, Transferências Especiais (`api-publica.transferegov.gestao.gov.br/especiais`): plano de ação, executor, metas e pagamentos do relatório de gestão; leitura aos poucos (15 min por execução), cada tabela vale 7 dias | `etl/sa_etl/transferegov.py` |
| Arrecadação e gastos da União | API do Siconfi (Tesouro): RREO anexos 1 e 2 (dívida desde 2018, bimestre a bimestre, em `fin_divida.py`), RGF anexo 1; pessoas do Executivo pela API do Portal (`servidores/por-orgao`); Receita Federal, CSV de arrecadação (sem API); Portal da Transparência, orçamento da despesa (arquivo anual); IPCA pela API do SIDRA/IBGE | `etl/sa_etl/fin_tesouro.py`, `fin_receita.py`, `fin_orcamento.py`, `financas.py` |
| Incentivos | Renúncia fiscal pelos arquivos anuais do Portal (a API `renuncias-valor` tem as mesmas linhas, mas sem filtro de ano leva 8 horas; fica de reserva e avisa se tiver ano novo; chave no secret `PORTAL_TRANSPARENCIA_CHAVE`); pagamentos a empresas pela API do Portal (`despesas/recursos-recebidos`, todo favorecido, mês a mês, lida pelo workflow semanal [`pagamentos-empresas.yml`](.github/workflows/pagamentos-empresas.yml)), arquivos diários como reserva (recusados para robôs desde 29/10/2026) | `etl/sa_etl/incentivos.py`, `renuncias.py`, `recursos_recebidos.py` |
| Tramitação | API da Câmara (`/eventos`, `/eventos/{id}/pauta`, `/proposicoes`, `/proposicoes/{id}/relacionadas`) e API do Senado (`/plenario/agenda`, `/comissao/agenda`, `/processo`, `/processo/{id}`); argumentos a favor e contra copiados do PDF oficial da justificação, do parecer e do voto em separado (a API não traz o texto); na pauta, sem documento oficial contra, quem fala contra em notícias (API do GDELT, depois RSS de busca do Google e do Bing Notícias; frase copiada da página da notícia, com veículo, data e link, marcada como fonte não oficial) | `etl/sa_etl/tramitacao.py`, `debate.py`, `noticias.py` |
| Dia a dia (presença e gastos de cada data) | Câmara: arquivos anuais de eventos dos dados abertos (`eventos`, `eventosPresencaDeputados`, `eventosOrgaos`), a mesma publicação da API `/eventos/{id}/deputados`, que só traz um evento por vez (a consulta por deputado lista eventos sem presença); conferidos todo dia com a API. Senado: votações nominais da API `/votacao`. Cidade do fornecedor pelo CNPJ (Receita). Pontos para conferir: presença em Brasília e refeição de restaurante de outro estado na mesma data (só Câmara) | `etl/sa_etl/agenda.py` |
| Punições e condenações oficiais | API do Portal da Transparência (`/ceis`, `/cnep`, `/ceaf`, 15 linhas por página, leitura aos poucos: 8 min por execução, a lista vale 3 dias; chave no secret `PORTAL_TRANSPARENCIA_CHAVE`); listas do TCU pela API da Plataforma de Certidões (`certidoes.apps.tcu.gov.br/api/publico`: contas irregulares, fins eleitorais, inabilitados, inidôneos); CPF dos deputados pela API da Câmara (`/deputados/{id}`). Empresa pelo CNPJ, sócio pelo nome e meio do CPF, deputado pelo CPF; senadores ficam de fora (o Senado não publica CPF) | `etl/sa_etl/sancoes.py` |
| Julgamentos do STF (voto de cada ministro) | Sem API pública: serviços JSON do próprio portal do STF (`pauta/services/calendario-service.asp`, `lista-service.asp`, `sistemas.stf.jus.br/repgeral/votacao`), só Plenário Virtual; leitura aos poucos (10 min por execução), sessão encerrada há 20 dias fica guardada. TSE ainda fora: o site recusa acesso automático (Akamai, HTTP 403) e a busca de jurisprudência exige captcha | `etl/sa_etl/tribunais.py` |
| Fotos dos políticos | Deputados federais: API da Câmara (`urlFoto`); senadores: API do Senado (`UrlFotoParlamentar`); deputados estaduais: endereço da foto da página oficial da ALMG, conferido na coleta (a API da ALMG não traz foto); governador e vice: ZIP de fotos dos candidatos do TSE (só as dos eleitos vão para o site). Sem foto, o site mostra as iniciais; o perfil dá o crédito da fonte (`site/src/components/Foto.tsx`) | `camara.py`, `senado.py`, `mg/etl/mg_etl/almg.py`, `governo.py` |
| Shows e cultura em MG | Contratação de artistas: API de consultas do PNCP (inexigibilidade, art. 74, II da Lei 14.133, e o resultado de cada item), leitura aos poucos (8 min por execução, com a mesma pausa entre pedidos das licitações, por causa do HTTP 429); emendas Pix com show ou evento: arquivos do Transferegov que o coletor nacional já grava; Lei Rouanet: API do SALIC (`/incentivadores` e `/projetos`, UF=MG); população e regiões: APIs do IBGE (agregado 6579 e localidades) | `mg/etl/mg_etl/cultura.py` |
| Minas Gerais | ALMG (API e dados abertos), TSE, Dados MG (viagens do governo pelo SCDP), Siconfi, Portal da Transparência; mapa das cidades visitadas pela API de malhas do IBGE (`mapa_mg.py`) | `mg/etl/mg_etl/` (veja `mg/README.md`) |
| Licitações e contratações diretas (governo de MG e cada cidade) | API de consulta do PNCP (`pncp.gov.br/api/consulta/v1`: `/contratacoes/publicacao` por UF, município e modalidade; `/contratos` por órgão); a API limita os pedidos (HTTP 429): leitura aos poucos (18 min por execução); cidades ano a ano (o ano atual vale 1 dia), estado só no ano atual, mês a mês (mês atual vale 3 dias, os outros 30) | `mg/etl/mg_etl/pncp.py` |
| Eleição 2026 | Resultados e boletins de urna do TSE | `eleicao2026/etl/el_etl/` (veja `eleicao2026/README.md`) |
| Eleitos de 2026 (mandato 2027) | Resultado da eleição estadual no site de resultados do TSE (JSON oficial); conferido com os arquivos de candidatos e de vagas (dados abertos do TSE, via API CKAN); API da Câmara e do Senado para quem já tem mandato. Baixado à mão pelo workflow [`eleitos-2026.yml`](.github/workflows/eleitos-2026.yml), não todo dia | `eleicao2026/etl/el_etl/eleitos.py` |
| Terras Raras | Sem API que junte os dados: planilhas à mão em `terras-raras/dados/`, cada linha com fonte e data | `terras-raras/gerar_pagina.py` (veja `terras-raras/COMO_ATUALIZAR.md`) |

O ponto de entrada da coleta nacional é `etl/sa_etl/build.py`. A tabela completa com links está no README.

## Regras de ouro

1. **Precisão dos dados primeiro.** Nunca publique um número que não foi conferido com a fonte oficial. Sempre dados
   reais, coerentes e com link para o original.
2. **Não causar dano a terceiros.** Não publique dado pessoal além do que a fonte oficial já torna público (CPF sempre
   mascarado; `validar.py` bloqueia CPF à mostra). Nunca exponha segredos: chaves ficam em variáveis de ambiente ou
   secrets do GitHub, nunca no repositório nem no chat.
3. Todo número mostrado numa página mostra a fonte e a data da última atualização.
4. Não escreva valores fixos no código; eles vêm dos arquivos de dados.

## Convenções

- Idioma: o site está em português (padrão), com inglês e espanhol traduzidos no navegador por
  `site/public/i18n/tradutor.js`, com dicionários em `site/public/i18n/en.json` e `es.json` (Eleição 2026:
  `eleicao2026/site/i18n/`). Dados oficiais (nomes, partidos, categorias) não são traduzidos. Código, comentários,
  commits e documentação do repositório são escritos em português, em linguagem simples.
- Menus (abas principais e barra dos projetos), em todos os sites: todas as abas sempre à vista. Se não couberem numa
  linha, quebram para a de baixo; nunca rolam de lado nem ficam cortadas. Conferido por `site/e2e/menu.ts`.
- Componentes comuns do site em `site/src/components/` (`ui.tsx`: `Barras`, `GastoMensal`, `Espectro`, `VotoBarra`,
  `LinkNota`, `Explain`...; `Selo.tsx`: selo da verificação). Reaproveite antes de criar um componente só para uma página.
- Visual: padrão de site público brasileiro (gov.br): faixa azul-escura no topo com fio verde e amarelo, azul gov.br
  nos links e números, letra Raleway. As cores são variáveis CSS em `site/src/styles.css` (`:root`), incluindo a paleta
  validada das séries (`--s1`...`--c8`) e as cores de voto (`--sim`, `--nao`). Os gráficos do site são componentes
  próprios em SVG (`ui.tsx`); o painel de análises usa Apache ECharts (`analises/painel.html`, ajudantes `barras`,
  `linhas`, `rosca`, `desenhar`). Para mudar o painel, siga a skill `.claude/skills/painel-analises/`.
- Skills do agente (`.claude/skills/`): toda skill passa pelo SkillSpector da NVIDIA antes de entrar e a cada push
  (workflow [`skills-seguranca.yml`](.github/workflows/skills-seguranca.yml)). Como instalar uma skill nova e os achados
  aceitos em [`.claude/skillspector/README.md`](.claude/skillspector/README.md). Fichas de visual de marcas, só para
  consulta, em `.claude/referencias/design-md/`.

## Comandos

- Coletar dados localmente (precisa de internet):
  `cd etl && pip install -r requirements.txt -r requirements-dev.txt && python -m sa_etl.build --saida ../site/public/data --cache .cache --anos 2025 2026`
- Rodar o site: `cd site && npm install && npm run dev` (Minas Nossa: `npm run build:mg && npm run preview:mg`)
- Testes do coletor: `python -m pytest -q etl/tests` (também `mg/etl/tests`, `eleicao2026/etl/tests`, `analises/tests`)
- Testes do site: `cd site && npm test`; no navegador: `npm run test:e2e` (e `test:e2e:mg`, `test:e2e:eleicao`),
  depois de gerar dados fictícios com `python etl/tests/gerar_dados_teste.py site/public/data`
- Conferência dos dados (bloqueia a publicação se algo não bater):
  `cd etl && python -m sa_etl.validar ../site/public/data`
- Verificação com a segunda fonte oficial: `cd etl && python -m sa_etl.verificar ../site/public/data --cache .cache`
- Painel de status: não precisa de comando. `status/index.html` e `status/painel.js` leem tudo na hora pela API do
  GitHub Actions e pelos arquivos publicados. Testes das contas: `node --test status/painel.test.mjs`. O motivo de cada
  problema chega como anotação do Actions, escrita por `etl/anotar.py`.
- Painel de análises: `python analises/publicar.py --nacional site/public/data --mg site/public-mg/data --eleicao eleicao2026/dados/tse --terras terras-raras/dados --saida /tmp/analises`

## Conferência

- Estratégia de testes, riscos e engenharia de caos em [TESTES.md](TESTES.md). Cada risco tem testes e uma trava em
  produção; cada fonte tem testes contra o governo simulado (`etl/tests/fakegov*.py`).
- `etl/sa_etl/validar.py` confere somas, votos repetidos, CPFs, links e quedas maiores que 20%; se falhar, o site no
  ar continua com a versão anterior.
- `etl/sa_etl/verificar.py` sorteia números do site e confere cada um numa segunda fonte oficial. Mais de 2% de
  diferenças sem motivo numa seção (com 20 ou mais conferidos) barra a publicação.
- Média da Casa ao lado de cada número do perfil: `etl/sa_etl/medias.py` (`meta.json`, `medias_casa`). Dinheiro e
  equipe: média de quem ficou o período inteiro (nota da cota em todos os meses, com folga de um mês); quem ficou menos é
  comparado com a média proporcional aos meses. Taxas: média de todos que têm a taxa. `validar.py` refaz a conta.
- Avisos de erro e direito de resposta chegam como issues no GitHub (formulários em `.github/ISSUE_TEMPLATE/`, link
  no fim de cada página, `site/src/components/Confianca.tsx`). Cada aviso é conferido com a fonte oficial; se o site
  estiver errado, corrija com teste e registre o motivo como abaixo, e responda no próprio aviso com o que mudou.
- Diferenças com motivo entendido ficam registradas em `etl/sa_etl/oficial.py` (`MOTIVOS`), e não são investigadas de
  novo do zero. Diferenças sem motivo vão para o relatório de conferência manual `revisao-manual.md` e
  `revisao-manual.csv`, publicados junto dos dados (`data/`), onde a conclusão é anotada.

## Trabalho em threads

- Uma thread por funcionalidade; a cada etapa concluída, comece uma nova com uma passagem curta (o que foi feito, o
  que está aberto, arquivos tocados).
- Trabalho mecânico (tradução, atualizações de versão, testes, pequenos ajustes de tela) → Sonnet. Lógica de dados e
  arquitetura → Opus.
- O coordenador delega; não implementa.
