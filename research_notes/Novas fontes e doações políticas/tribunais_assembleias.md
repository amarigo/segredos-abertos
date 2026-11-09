# Tribunais de contas (TCU, TCEs, TCMs) e assembleias legislativas fora de MG: inventário de fontes

> Limitação desta pesquisa (09/11/2026): a sessão não tinha acesso de rede aos sites oficiais (portal.tcu.gov.br,
> al.sp.gov.br, api.portaldatransparencia.gov.br, opensanctions.org, CRAN etc. falharam com ENOTFOUND; `curl` também
> devolveu falha para todos). Tudo abaixo vem de resultados de busca (títulos, URLs e trechos), sem abrir as páginas.
> Nenhum endpoint foi testado. Antes de programar qualquer coletor, cada URL precisa ser conferida. Para isso, liberar
> esses domínios nas configurações de rede da sessão.

## 1. TCU e CGU: contas irregulares, inabilitados, inidôneos, acórdãos, CEIS/CNEP/CEPIM

### Takeaway
O TCU mantém três listas de responsabilização (contas julgadas irregulares/Cadirreg, inabilitados para cargo em
comissão e licitantes inidôneos). Elas podem ser consultadas e exportadas no portal e no sistema contas.tcu.gov.br,
mas a busca não achou uma API oficial documentada para elas. A lista eleitoral de 2026 (mais de 6,1 mil nomes) foi
entregue ao TSE em agosto de 2026. CEIS, CNEP e CEPIM saem pela API do Portal da Transparência, que o projeto já usa.

### Cited Findings
- O TCU publica a **lista de licitantes inidôneos**: pessoas que, por decisão do TCU, ficam impedidas de participar
  de licitações. Ficam fora dela responsáveis ainda não notificados, decisões ainda não transitadas em julgado e
  decisões anuladas ou suspensas. — [TCU, Licitantes inidôneos](https://portal.tcu.gov.br/responsabilizacao-publica/licitantes-inidoneos/)
- **Lista de responsáveis com contas julgadas irregulares** (Cadirreg): consulta pública por nome, CPF, estado ou
  município, com opção de exportar os dados. — [TCU, Contas julgadas irregulares](https://portal.tcu.gov.br/responsabilizacao-publica/contas-julgadas-irregulares); [Carta de serviços](https://portal.tcu.gov.br/carta-de-servicos/certidoes/lista-de-responsaveis-com-contas-julgadas-irregulares)
- Há também certidões: contas julgadas irregulares, contas irregulares **para fins eleitorais** e a certidão negativa
  de inabilitado/inidôneo. As certidões do TCU fazem parte da plataforma gov.br. — [TCU, Certidões](https://portal.tcu.gov.br/carta-de-servicos/certidoes); [Certidão para fins eleitorais](https://portal.tcu.gov.br/carta-de-servicos/certidoes/certidao-de-contas-julgadas-irregulares-para-fins-eleitorais); [Notícia gov.br](https://portal.tcu.gov.br/imprensa/noticias/certidoes-de-contas-julgadas-irregulares-pelo-tcu-integram-plataforma-govbr)
- **Eleições 2026:** o TSE recebeu do TCU a lista de gestores com contas julgadas irregulares nos últimos 8 anos, com
  mais de 6,1 mil responsáveis (cerca de 3% menos que em 2024). A lista sai do Cadirreg e reúne julgamentos sem
  recurso no TCU desde 2018. A lista eleitoral é um recorte da lista geral, só com casos que podem barrar a candidatura. — [TSE, notícia ago/2026](https://www.tse.jus.br/comunicacao/noticias/2026/Agosto/eleicoes-2026-tse-recebe-lista-de-gestores-publicos-com-contas-julgadas-irregulares-1); [Brasil 61](https://brasil61.com/n/tcu-lista-mais-de-6-mil-responsaveis-com-contas-irregulares-nordeste-e-sudeste-concentram-maioria-dos-nomes-bras2616859); [TCU, notícia](https://portal.tcu.gov.br/imprensa/noticias/tcu-entrega-ao-tse-lista-de-responsaveis-com-contas-julgadas-irregulares)
- Em 2024 o TSE publicou a própria versão da lista, com dados tirados todo dia do site do TCU (segundo trecho de busca;
  página não aberta). — [Conjur: "TSE divulga lista com 9,7 mil nomes"](https://www.conjur.com.br/?p=810103)
- O OpenSanctions mantém o conjunto `br_tcu_disqualified` (inabilitados do TCU). Ele indica **contas.tcu.gov.br**
  como fonte, em JSON, atualizado todo dia. Isso mostra que o dado existe em JSON nesse domínio, mas o endpoint não
  tem documentação oficial. — [OpenSanctions, br_tcu_disqualified](https://www.opensanctions.org/datasets/br_tcu_disqualified/)
- Há APIs comerciais de terceiros que raspam essas consultas do TCU (inidôneos, inabilitados, certidão negativa).
  Isso confirma que não existe API oficial simples. — [Infosimples TCU inidôneos](https://infosimples.com/consultas/tcu-inidoneos/); [Infosimples TCU inabilitados](https://infosimples.com/consultas/tcu-inabilitados/); [Infosimples CNI](https://infosimples.com/consultas/tcu-cni/)
- Página "Dados Abertos do TCU" na carta de serviços (conteúdo não aberto). — [TCU, Dados abertos do TCU](https://portal.tcu.gov.br/carta-de-servicos/transparencia/dados-abertos-do-tcu)
- O Boletim do TCU trata de APIs de dados abertos, mas exigidas **dos conselhos profissionais** (DN TCU 216/2025),
  e não das listas do próprio TCU. — resultado de busca sobre [btcu.apps.tcu.gov.br](https://btcu.apps.tcu.gov.br/api/obterDocumentoPdf/78425771)
- CEIS, CNEP e CEPIM ficam na seção Sanções do Portal da Transparência. A API (api.portaldatransparencia.gov.br) pede
  chave de cadastro, e o projeto já tem uma no secret `PORTAL_TRANSPARENCIA_CHAVE`. As rotas exatas não apareceram na
  busca. — [Portal da Transparência, dataportals](https://dataportals.org/portal/portal-da-transparencia-dados-abertos); [gov.br Conecta, catálogo](https://www.gov.br/conecta/catalogo/sistemas/controle-e-transparencia)

### Inferences
- Conhecimento prévio, **não verificado nesta sessão**:
  - A API do Portal tem as rotas `/api-de-dados/ceis`, `/cnep`, `/cepim`, `/ceaf` (filtro por CNPJ/CPF e paginação).
    O Portal também publica o arquivo completo de cada cadastro para download diário
    (`portaldatransparencia.gov.br/download-de-dados/ceis/AAAAMMDD`).
  - O TCU tem serviços ORDS em `contas.tcu.gov.br/ords/condenacao/consulta/inabilitados` e `.../inidoneas`.
  - O TCU tem uma API de acórdãos em `dados-abertos.apps.tcu.gov.br/api/acordao/recupera-acordaos`.
  - Os três precisam ser testados quando a rede estiver liberada.
- Pela ordem de preferência do projeto:
  - CEIS, CNEP e CEPIM: opção 1 (API do Portal), ou opção 2 (arquivo do Portal), já que o volume é pequeno.
  - Listas do TCU: o JSON do contas.tcu.gov.br, que é o próprio sistema oficial, está entre a opção 1 e a 3. É preciso
    deixar escrito no código que não há API documentada.
- Ponto para a regra de ouro 2 (não causar dano a terceiros): o Cadirreg traz CPF. Ele deve ser mascarado no site, e o
  cruzamento com políticos deve ser feito por CPF completo dentro da coleta, nunca por nome.

### Gaps
- Endpoints, formatos e campos exatos do Cadirreg, dos inabilitados, dos inidôneos e da API de acórdãos do TCU: não
  confirmados.
- Formato do arquivo da lista eleitoral 2026, e se o TSE publicou essa lista em dadosabertos.tse.jus.br: não
  encontrado.

## 2. Tribunais de contas estaduais e municipais: quais têm API ou dados abertos

### Takeaway
Vários TCEs têm portal de dados abertos ou API.
- APIs documentadas: TCE-PE, TCE-RJ, TCE-SC, TCE-CE e TCE-RN.
- CKAN com API: TCE-RS, com os dados do LicitaCon.
- API citada, mas não confirmada: TCE-SP (despesas de todos os municípios paulistas, menos a capital).
- TCE-PR: arquivos de download semanais, e na consulta por município "não em formato aberto".

A maioria cobre a execução orçamentária, as licitações e os contratos **municipais**, não o julgamento de contas de
políticos.

### Cited Findings
- **TCE-SP:**
  - O portal transparencia.tce.sp.gov.br traz a execução orçamentária de todos os municípios paulistas, menos a
    capital (que é do TCM-SP), com download em CSV.
  - As ferramentas mais usadas são a consulta de despesas por fornecedor, os conjuntos de dados e as APIs.
  - Fontes: [TCE-SP notícia](https://tce.sp.gov.br/6524-novo-portal-do-tce-facilita-acompanhamento-do-uso-do-dinheiro-publico); [TCE-SP, Portal recebe 613 mil visualizações](https://tce.sp.gov.br/6524-portal-transparencia-municipal-recebe-mais-613-mil-visualizacoes-desde-janeiro); [Painel da Transparência](https://tce.sp.gov.br/6524-painel-transparencia-disponibiliza-dados-sobre-orcamento-saude-e-ensino-municipios-paulistas)
  - O endereço `transparencia.tce.sp.gov.br/api/` só aparece em documentação de terceiros, sem confirmação oficial. — [cidadao.ai docs](https://anderson-ufrj.github.io/cidadao.ai-technical-docs/en-US/docs/api/apis-governamentais)
- **TCE-RS:**
  - Portal CKAN dados.tce.rs.gov.br, com API CKAN em `/api/3` segundo o dataportals.
  - O grupo Licitações tem cerca de 1.440 conjuntos (LicitaCon), muitos em ZIP, com marcas Municipal, Autarquia,
    Consórcio e Consolidado. Há também o grupo Contratos.
  - O site lista ainda uma "API LicitaCon Obras - Somente Consulta - Dados Abertos".
  - Fontes: [Dados Abertos TCE-RS](https://dados.tce.rs.gov.br/dataset); [grupo Licitações](http://dados.tce.rs.gov.br/group/licitacoes); [grupo Contratos](https://dados.tce.rs.gov.br/group/contratos); [dataportals TCE-RS](https://dataportals.org/portal/dados-abertos-tce-rs/); [Sistemas de controle externo](https://tcers.tc.br/sistemas-de-controle-externo/); [LicitaCon Obras](https://paineis.tcers.tc.br/extensions/licitacon/sobre.html)
- **TCE-PE:**
  - Tem API de dados abertos, com página de definições, em sistemas.tcepe.tc.br/DadosAbertos.
  - Existe o pacote R `tceper`, que é uma interface para ela.
  - Fontes: [API Dados Abertos TCE-PE](https://sistemas.tcepe.tc.br/DadosAbertos/); [Definições da API](https://www.tcepe.tc.br/internet/index.php/dados-abertos/definicoes-da-api); [tceper (R)](https://strategicprojects.r-universe.dev/tceper)
- **TCE-PR:**
  - Tem página de dados abertos.
  - O "Portal Informação para Todos" (PIT) dá download por município e ano (licitações, contratos etc.), com arquivos
    gerados 1 vez por semana. A própria consulta avisa que esses dados "não estão em formato aberto".
  - O tribunal lançou dados abertos de licitações de 399 municípios desde 2010 (cerca de 720 mil licitações).
  - Fontes: [Dados Abertos TCE-PR](https://www.tce.pr.gov.br/transparencia-do-tce-pr/dados-abertos-tce-pr.htm); [PIT Consulta](https://pit.tce.pr.gov.br/Dados/DadosConsulta/Consulta); [Bem Paraná](https://www.bemparana.com.br/noticia/tce-lanca-programa-de-dados-abertos-com-720-mil-licitacoes-de-prefeituras)
- **TCE-RJ:**
  - Portal dados.tcerj.tc.br com página "API" e conjuntos como Compras Diretas.
  - Os dados municipais vêm do SIGFIS e do e-TCERJ e não passaram por fiscalização.
  - Fontes: [TCE-RJ API](https://dados.tcerj.tc.br/api); [Portal de dados do TCERJ](https://www.tcerj.tc.br/portalnovo/pagina/portal-de-dados-do-tcerj)
- **Outros com API:**
  - TCE-SC — [APIs de dados abertos](https://www.tcesc.tc.br/apis-dados-abertos)
  - TCE-CE — [api.tce.ce.gov.br](https://api.tce.ce.gov.br/)
  - TCE-RN — [apidadosabertos.tce.rn.gov.br](https://apidadosabertos.tce.rn.gov.br/)
  - TCE-TO, só download — [Dados abertos](https://transparencia.tceto.tc.br/lgpd/dadosAbertos)
  - TCM-CE (portal de dados abertos) — [dataportals](https://dataportals.org/portal/dados-abertos-tcm-ce)
- O projeto acadêmico MiDES (execução orçamentária municipal) junta dados de vários TCEs, alguns convertidos para o
  BigQuery (Base dos Dados). — [MiDES, fontes originais](https://municipal-budget-execution.github.io/mides/original_source)

### Inferences
- Os dados dos TCEs se sobrepõem em boa parte ao PNCP e ao Siconfi, que o projeto já usa. O ganho maior está:
  - nos dados anteriores a 2023 (antes do PNCP);
  - no LicitaCon RS e no TCE-SP, que trazem a despesa empenhada e paga por fornecedor em cada prefeitura.
- Para "achados de auditoria" (pareceres prévios de contas de governador e prefeito, julgamentos), as buscas não
  acharam conjunto aberto. Isso deve ficar nos PDFs e sistemas de processos de cada TCE (opção 3).
- TCE-MG ("Fiscalizando com o TCE") não apareceu nos resultados. O repositório já cita tce.mg em
  `mg/etl/mg_etl/governo.py`.

### Gaps
- Endpoints, campos e limites de pedidos de cada API de TCE: não verificados.
- TCE-BA, TCE-GO, TCE-ES, TCE-SC (detalhes), TCM-SP, TCM-RJ, TCM-BA, TCM-GO: sem resultado específico.
- Lista de "contas irregulares para fins eleitorais" dos TCEs (cada TCE manda a sua ao TRE): não encontrada.

## 3. Assembleias legislativas (fora MG): verba indenizatória, gabinete e votações nominais

### Takeaway
Quase nenhuma assembleia publica **votações nominais** em formato aberto. As que têm algo de dados abertos para
deputados são:
- ALESP: XML de despesas de gabinete desde 2002, atualizado todo mês;
- ALEP-PR: API pública;
- ALEPE: API de parlamentares, pessoal, remuneração e contratos;
- CLDF: CKAN e API;
- ALEAC: API documentada.

A ALERJ não tem dados abertos nem registro do painel de votação. Dos outros estados pedidos (RS, BA, CE, GO, SC, ES),
a busca não achou API.

### Cited Findings
- **ALESP (SP), melhor caso para gastos:**
  - Arquivo XML de despesas dos gabinetes: completo em `al.sp.gov.br/repositorioDados/deputados/despesas_gabinetes.xml`
    e por ano em `despesas_gabinetes_AAAA.xml`, desde 2002.
  - Atualizado todo mês, com tipo de despesa, ano, mês, nome e CNPJ do fornecedor.
  - Fonte: [ALESP, documentação despesas_gabinetes](https://www.al.sp.gov.br/repositorioDados/docs/deputados/despesas_gabinetes.pdf)
- **ALESP, portal:**
  - Tem 26 conjuntos e 29 recursos, entre eles deputados.xml e proposituras.
  - Avisa que vai mudar para o CKAN `ckan.al.sp.gov.br/alesp-dados-abertos`, "em breve".
  - Fonte: [Portal Dados Abertos ALESP](https://www.al.sp.gov.br/dados-abertos/)
- **ALESP, votos:** não estão no portal de dados abertos. O projeto independente "assembleias" tira os votos dos
  relatórios em PDF de cada votação do painel. — [GitHub Tomoyo/assembleias](https://github.com/Tomoyo-Computer-Science-Research-Unit/assembleias)
- **ALERJ:** "não há dados abertos nem registro do painel" de votação, segundo o mesmo projeto. — [GitHub Tomoyo/assembleias](https://github.com/Tomoyo-Computer-Science-Research-Unit/assembleias)
- **ALEP (PR):**
  - API pública de dados abertos, com base em `webservices.assembleia.pr.leg.br/api/public`.
  - Cobre pesquisa legislativa por proposição. Não está confirmado se traz votos ou verba.
  - Fonte: [ALEP, API de Dados Abertos](https://transparencia.assembleia.pr.leg.br/servicos/dados-abertos)
- **ALEPE (PE):**
  - API de dados abertos com parlamentares, pessoal, remuneração, contratos, licitações e proposições.
  - Existe o pacote R `alepe`, que é uma interface para ela.
  - A verba indenizatória não aparece de forma explícita na descrição do pacote.
  - Fonte: [CRAN alepe](https://stat.ethz.ch/CRAN/web/packages/alepe/index.html)
- **CLDF (DF):**
  - Portal CKAN dados.cl.df.gov.br e API própria.
  - O projeto independente cldf-painel consolida 102 tabelas da CLDF.
  - Fontes: [Portal Dados Abertos CLDF](https://dados.cl.df.gov.br/); [GitHub maximusminus/cldf-painel](https://github.com/maximusminus/cldf-painel)
  - Um trabalho da UnB (2019) dizia que os demonstrativos e comprovantes da verba indenizatória da CLDF estavam em
    formato fechado. Pode estar desatualizado. — [UnB, BDM](https://www.bdm.unb.br/bitstream/10483/26513/1/2019_DanielVieira_PedroHenriqueGomes_produto.pdf)
- **ALEAC (AC):** tem página "Dados Abertos – Documentação da API". — [ALEAC](https://app.al.ac.leg.br/dados-abertos)
- **ALEGO (GO):**
  - Um preprint acadêmico indica que o portal de dados abertos estava inacessível. A leitura da tabela é incerta.
  - Ao mesmo tempo, a ALEGO teve nota 99,67% no ITGP de 2024. Esse índice mede transparência geral, não API.
  - Fontes: [Preprint SciELO](https://preprints.scielo.org/index.php/scielo/preprint/download/12275/22549/23235); [Jornal Opção](https://www.jornalopcao.com.br/ultimas-noticias/assembleia-legislativa-de-goias-mantem-selo-diamante-em-transparencia-de-2024-656541/)
- **ALRS, ALBA, ALECE, ALESC, ALES:** não achei API nem conjunto aberto de verba ou votos nas buscas. Não quer dizer
  que não existam.

### Inferences
- Ordem provisória, pelo que se viu, para expandir o Segredos Abertos:
  1. **ALESP:** XML de despesas por fornecedor com CNPJ, desde 2002. Encaixa direto no modelo da CEAP e no
     cruzamento com CNPJ.
  2. **CLDF:** CKAN e API.
  3. **ALEPE:** API com pessoal e remuneração.
  4. **ALEP-PR:** API, mais voltada a proposições.
  5. **ALEAC:** API.
  - Depois vêm os outros, e a ALERJ por último (nada aberto).
- Para votações nominais, nenhuma assembleia fora de MG apareceu com API. O caminho provável é ler PDFs do painel
  (opção 3), como faz o projeto "assembleias".
- Para governadores e vices, as fontes de gasto ficam no Executivo estadual (portais de transparência dos estados e
  Siconfi), não nas assembleias.

### Gaps
- Tabela comparativa do preprint "Democracia em Formato JSON: As Assembleias Legislativas Estaduais do Portal ao
  Endpoint" (quais casas têm API documentada com votos nominais): o texto completo não pôde ser aberto.
- Campos e cobertura da verba indenizatória da ALEPE, da CLDF, da ALEP e da ALEAC: não confirmados.
- Situação do CKAN da ALESP em nov/2026: não confirmada.

## 4. Projetos e avaliações que já mediram isso

### Takeaway
A avaliação de referência é o **ITGP Legislativo Estadual e Distrital**, da Transparência Internacional Brasil. Na
edição de 2023, só 4 das 27 casas foram satisfatórias, a ALMG ficou em 3º e a ALEAC teve a pior nota (14,4). Há
também projetos independentes no GitHub, e a Operação Serenata de Amor, que cobriu só a CEAP federal.

### Cited Findings
- **ITGP 2023:**
  - Avalia oito dimensões: legislação, plataformas, transparência legislativa, transparência administrativa,
    participação, transformação digital, governança e comunicação.
  - Só 4 de 27 assembleias tiveram resultado satisfatório, e 11 foram ruins ou péssimas.
  - Nenhuma tinha proteção a denunciantes, e falta transparência sobre os salários dos servidores.
  - Fontes: [TI Brasil, relatório (Poder360)](https://static.poder360.com.br/2023/05/Transparencia-Internacional-Casas-Legislativas.pdf); [Nota metodológica ITGP](https://docs.transparenciainternacional.org.br/biblioteca/itgp-legislativo-estadual-distrital-nota-metodologica.pdf); [BNews](https://www.bnews.com.br/noticias/politica/assembleias-de-11-estados-tem-indice-de-transparencia-ruim-ou-pessimo.html); [Conjur](https://www.conjur.com.br/2023-jul-23/transparencia-assembleias-legislativas-brasil//?print=1)
- ALMG em 3º no ITGP 2023. — [Estado de Minas](https://www.em.com.br/app/noticia/politica/2023/05/25/interna_politica,1498609/almg-fica-em-3-no-ranking-de-assembleias-da-transparencia-internacional.shtml)
- ALEAC com 14,4 pontos, "péssima", a pior do país (estudo citado em jan/2024). — [A Gazeta do Acre](https://agazetadoacre.com/2024/01/noticias/politica/aleac-tem-o-pior-indice-de-transparencia-do-brasil-aponta-estudo)
- A ALEP (PR) foi avaliada como "regular" e criou uma comissão especial para melhorar a transparência. — [Bem Paraná](https://www.bemparana.com.br/publicacao/blogs/politicaemdebate/apos-avaliacao-regular-assembleia-paranaense-cria-comissao-especial-para-aprimorar-transparencia/)
- Preprint acadêmico que compara as assembleias por critérios de API documentada, votos nominais, formatos
  JSON/XML/CSV e documentação técnica. — [SciELO Preprints](https://preprints.scielo.org/index.php/scielo/preprint/download/12275/22549/23235)
- Projetos independentes:
  - "assembleias" (votos, presença e proposições da ALERJ e da ALESP) — [GitHub](https://github.com/Tomoyo-Computer-Science-Research-Unit/assembleias)
  - cldf-painel — [GitHub](https://github.com/maximusminus/cldf-painel)
  - mcp-brasil (70 APIs públicas) — [GitHub](https://github.com/mcp-brasil/mcp-brasil)

### Inferences
- O ITGP mede transparência geral (o que está publicado no site), não a existência de API. Uma nota alta, como a da
  ALEGO, não garante dados legíveis por máquina.
- A Operação Serenata de Amor (OKBR) cobriu só a CEAP federal (conhecimento prévio, não verificado nesta sessão).
  Não achei evidência de que tenha coberto assembleias.

### Gaps
- Edições do ITGP Legislativo de 2024, 2025 e 2026 com a nota de cada casa: não encontradas, além da nota da ALEGO em
  2024.
- Relatórios da Transparência Brasil (a ONG, diferente da TI Brasil) e da Open Knowledge Brasil sobre assembleias: não
  achados nesta busca.
