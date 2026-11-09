# Fontes do TSE ainda não usadas (prestação de contas, bens, filiação, contas partidárias, FEFC)

> Limitação desta pesquisa (09/11/2026): a sessão não conseguiu acessar `dadosabertos.tse.jus.br` (bloqueado pela rede da sessão) nem `www.tse.jus.br` (HTTP 403, o mesmo bloqueio Akamai já anotado no projeto). Os nomes, endereços e prazos abaixo vêm de resultados de busca que mostram essas páginas, de páginas dos TREs e de projetos no GitHub. Nenhuma chamada à API CKAN foi testada desta sessão. O próprio repositório registra que a API do DivulgaCandContas recusa robôs (veja abaixo).

## 1. Nome, endereço, formato, frequência e anos de cada conjunto de dados

### Takeaway
Tudo o que foi pedido existe como arquivo aberto oficial do TSE (ZIP com CSV por UF no CDN `cdn.tse.jus.br/estatistica/sead/odsele/...`). O catálogo fica no Portal de Dados Abertos (CKAN), um conjunto por ano: "Prestação de Contas Eleitorais - {ano}", "Candidatos - {ano}" (com bens), e o grupo "Partidos" (filiação). As contas anuais dos partidos saem pelo DivulgaSPCA, e a distribuição do FEFC sai numa página e em documentos do TSE, não num conjunto de dados.

### Cited Findings
**Prestação de contas eleitorais (campanhas)**
- Para 2026 há o conjunto CKAN "Prestação de Contas Eleitorais - 2026" (`dadosabertos.tse.jus.br/dataset/prestacao-de-contas-eleitorais-2026`, grupo `prestacao-de-contas-eleitorais-2026`). Ele traz quatro recursos: prestação de contas de órgãos partidários, prestação de contas de candidatos, CNPJ de campanha e extratos bancários de candidatos — [Portal de Dados Abertos do TSE, grupo 2026](https://dadosabertos.tse.jus.br/dataset/groups/prestacao-de-contas-eleitorais-2026); [recurso Órgãos partidários](https://dadosabertos.tse.jus.br/dataset/prestacao-de-contas-eleitorais-2026/resource/4b60ada3-66d9-474d-ba3f-a42a7bbcf90d); [recurso Extratos bancários de candidatos](https://dadosabertos.tse.jus.br/dataset/prestacao-de-contas-eleitorais-2026/resource/5f87ece6-91ed-4f36-86ec-6fc7322714cd); [recurso CNPJ](https://dadosabertos.tse.jus.br/dataset/prestacao-de-contas-eleitorais-2026/resource/e0f2af45-5b0f-48db-b806-ac7ce9119997)
- Endereço confirmado do arquivo dos órgãos partidários: `https://cdn.tse.jus.br/estatistica/sead/odsele/prestacao_contas/prestacao_de_contas_eleitorais_orgaos_partidarios_2026.zip`. O recurso CNPJ é um TXT dentro de ZIP — [resultado de busca do recurso no portal TSE](https://dadosabertos.tse.jus.br/dataset/prestacao-de-contas-eleitorais-2026/resource/4b60ada3-66d9-474d-ba3f-a42a7bbcf90d)
- O arquivo de candidatos de 2024 chama-se `prestacao_de_contas_eleitorais_candidatos_2024`. Dentro dele há um CSV por UF (`receitas_candidatos_2024_<UF>.csv`), separado por `;`, em latin-1, com `SQ_CANDIDATO` como chave — [basedosdados/pipelines issue #2095](https://github.com/basedosdados/pipelines/issues/2095) (citado no resumo da busca; página não aberta)
- Em 2026 os arquivos nacionais têm o sufixo `*_BR.csv`. Um projeto gerou seus dados a partir de um arquivo do TSE "gerado em 17/10/2026 04:05", ainda com contas parciais — [diazaraujo/doadores-presidencial-2026](https://github.com/diazaraujo/doadores-presidencial-2026)
- O TSE informa que a consulta de receitas e despesas está no Portal de Estatísticas Eleitorais e no DivulgaCandContas. Os dados abertos trazem as contas de órgãos partidários e de candidatos, os CNPJs de campanha e os extratos bancários — [TSE, notícia set/2026 (texto citado no resultado da busca)](https://www.tse.jus.br/comunicacao/noticias/2026/Setembro/tse-disponibiliza-dados-da-prestacao-de-contas-parcial-das-campanhas-eleitorais)
- Os documentos que comprovam as contas de 2024 (notas, recibos) podem ser consultados por CPF ou CNPJ do doador ou fornecedor, nas pastas Receitas e Despesas — [TSE, Consulta pública aos documentos comprobatórios 2024](https://www.tse.jus.br/eleicoes/eleicoes-2024-content/prestacao-de-contas/consulta-publica-aos-documentos-comprobatorios-das-prestacoes-de-contas)
- O DivulgaCandContas mostra o extrato bancário em PDF por um endpoint REST: `divulgacandcontas.tse.jus.br/divulga/rest/v1/prestador/buscar/extrato/pdf/{idEleicao}/{id}`. Exemplo de 2024: eleição 2045202024 — [exemplo indexado](https://divulgacandcontas.tse.jus.br/divulga/rest/v1/prestador/buscar/extrato/pdf/2045202024/000221191677MT3715281)

**Bens declarados de candidatos**
- O conjunto "Candidatos - 2026" reúne: Candidatos, Bens de Candidatos, Coligações, Vagas, Motivo da cassação, Redes sociais, Fotos e Proposta de governo — [Portal de Dados Abertos do TSE (resultado de busca)](https://dadosabertos.tse.jus.br/pt_PT/dataset/?_tags_limit=0&res_format=CSV&tags=Ano+2026)
- A coluna de descrição dos bens às vezes traz números de CPF em texto livre: 49 linhas numa auditoria, 20 delas com CPF válido. Despesas tinham 2.621 linhas e receitas 526 com CPF completo no campo `descricao` — [codigo-publico-brasil/dado-publico-brasil issue #195](https://github.com/codigo-publico-brasil/dado-publico-brasil/issues/195)

**Filiação partidária**
- O grupo "Partidos" do portal reúne delegados, órgãos partidários e "Perfil Filiação Partidária" (CSV em ZIP no `cdn.tse.jus.br`). A fonte é o sistema SGIP, atualizada toda semana segundo a página do conjunto. Os metadados do recurso de perfil são de 11/11/2021 — [Partidos - Perfil Filiação Partidária](https://dadosabertos.tse.jus.br/dataset/00e1a2a5-67e1-441b-9fd9-b8e59fc1189d/resource/0ca1f730-ab27-471d-b608-6d94a38dd24a?activity_id=13abac79-db5e-4dd8-b656-ddb65a95311e); [Partidos - conjunto](https://dadosabertos.tse.jus.br/dataset/delegados-partidarios); [grupo Partidos](https://dadosabertos.tse.jus.br/en/group/partidos)
- Em 2021 o TSE tirou do site a lista completa de filiados com busca por partido, UF, município e zona. Ficou só a estatística (perfil), e a lista sai com menos detalhe — [Conjur, 23/09/2021](https://conjur.com.br/2021-set-23/tse-restringe-divulgacao-dados-filiados-partidos/)
- A Base dos Dados mantém uma cópia "Filiação Partidária" com dados do TSE até abril de 2026 — [Base dos Dados](https://basedosdados.org/dataset/e68b1cfd-ca29-4bdc-b687-424d9c59760e)

**Contas anuais dos partidos (SPCA / DivulgaSPCA)**
- O DivulgaSPCA mostra as contas anuais de todos os diretórios (nacional, estadual e municipal), de 2007 a 2024. Há também um "Repositório de Dados Eleitorais" com dados abertos das contas anuais dos diretórios nacionais — [TSE, DivulgaSPCA](https://www.tse.jus.br/partidos/contas-partidarias/prestacao-de-contas/divulga-spca); [TSE, Prestação de contas partidária](https://www.tse.jus.br/partidos/contas-partidarias/prestacao-de-contas); [TRE-SP](https://www.tre-sp.jus.br/partidos/contas-partidarias/prestacao-de-contas)
- Prazo de entrega das contas do exercício 2025: 30/06/2026, pelo SPCA (Res. TSE 23.604/2019) — [TSE, notícia jun/2026](https://www.tse.jus.br/comunicacao/noticias/2026/Junho/partidos-tem-ate-30-de-junho-para-entregar-prestacao-de-contas-anual-a-justica-eleitoral)

**FEFC e Fundo Partidário**
- O FEFC de 2026 é de R$ 4.961.519.777,00, dividido entre 30 partidos: 2% em partes iguais e o resto pela representação no Congresso (Lei 9.504/97). O TSE publica a distribuição numa página própria e em notícia de junho de 2026 — [TSE, página FEFC 2026](https://www.tse.jus.br/eleicoes/eleicoes-2026-content/prestacao-de-contas/fundo-especial-de-financiamento-de-campanha-fefc); [TSE, notícia distribuição FEFC 2026](https://www.tse.jus.br/comunicacao/noticias/2026/Junho/tse-divulga-distribuicao-do-fundo-especial-de-financiamento-de-campanha-para-as-eleicoes-2026)
- PL recebe R$ 881,6 milhões e PT cerca de R$ 615 milhões. Para o União Brasil, a imprensa diverge: R$ 522 milhões ou R$ 526,4 milhões — [Correio da Manhã](https://www.correiodamanha.com.br/politica/2026/06/295388-fundo-eleitoral-2026-pl-lidera-repasses-com-rs-8816-milhoes.html); [Money Times](https://www.moneytimes.com.br/tse-divulga-distribuicao-de-r-49-bi-do-fundo-eleitoral-pl-pt-e-uniao-ficam-com-40-do-total/)
- O PT desistiu de uma ação que pedia a revisão do cálculo, e o cálculo de junho foi mantido — [Itatiaia](https://www.itatiaia.com.br/politica/tse-aceita-desistencia-do-pt-em-revisao-do-calculo-do-fundo-eleitoral-de-2026/)
- Fundo Partidário: 95% são divididos pela votação na última eleição para a Câmara. Partidos abaixo da cláusula de barreira ficam fora — [TRE-SP, jun/2026](https://www.tre-sp.jus.br/comunicacao/noticias/2026/Junho/eleicoes-2026-saiba-como-os-fundos-eleitoral-e-partidario-sao-usados-nas-campanhas-e-na-estrutura-dos-partidos)

### Inferences
- Os endereços do CDN seguem o mesmo padrão dos arquivos que o projeto já usa (`odsele/consulta_cand/consulta_cand_{ano}.zip`). Provavelmente: `odsele/prestacao_contas/prestacao_de_contas_eleitorais_candidatos_{ano}.zip` e `odsele/bem_candidato/bem_candidato_{ano}.zip`. Só o arquivo de órgãos partidários de 2026 foi confirmado. O caminho certo é achar cada URL por `package_show?id=prestacao-de-contas-eleitorais-{ano}` e `candidatos-{ano}`, como `eleitos.py` já faz.
- A divisão do FEFC por partido não tem CSV aberto confirmado. Talvez seja preciso ler a tabela publicada pelo TSE (PDF ou página), ou somar a receita "FEFC" dos arquivos de prestação de contas.

### Gaps
- Não foi possível listar o catálogo CKAN completo nem confirmar o slug de cada ano (2018, 2020, 2022, 2024) nem a data `metadata_modified`: rede bloqueada nesta sessão.
- Formato (CSV ou API) e endereço exatos do "Repositório de Dados Eleitorais" das contas anuais partidárias: não encontrados.
- A frequência de atualização dos arquivos de prestação de contas durante a campanha não está documentada nas fontes encontradas.

## 2. Existe API? Robôs conseguem acessar?

### Takeaway
A API CKAN padrão (`/api/3/action/package_show`, `package_search`) serve para achar os arquivos, e o projeto já a usa. O DivulgaCandContas tem uma API REST JSON não documentada (`/divulga/rest/v1`), mas ela recusa robôs. Não há API oficial que devolva receitas e despesas linha a linha. O caminho é o arquivo ZIP (opção 2 da regra do projeto).

### Cited Findings
- O repositório anota que a API do DivulgaCandContas (`divulgacandcontas.tse.jus.br/divulga/rest`) "recusa acesso automático (HTTP 403 'Access Denied', conferido do GitHub Actions em 04/11/2026)". O mesmo arquivo usa a API CKAN `dadosabertos.tse.jus.br/api/3/action/package_show?id={id}` e tem reserva direta no CDN — `eleicao2026/etl/el_etl/eleitos.py` (linhas 7-13, 43-51) e `eleicao2026/etl/el_etl/locais.py` (linha 22)
- Base da API do DivulgaCandContas usada por terceiros: `https://divulgacandcontas.tse.jus.br/divulga/rest/v1`. Funções: listar candidatos por município, consultar candidato, anos eleitorais, eleições ordinárias e suplementares, cargos, e `consultar_prestador_contas`. O projeto aponta para um Swagger, que não foi aberto — [karnagge/mcpcand](https://github.com/karnagge/mcpcand)
- O TSE não publica documentação oficial dessa API. Nenhuma página do TSE com essa documentação apareceu nas buscas — busca sem resultado (veja Gaps)

### Inferences
- Para receitas e despesas: usar o CKAN para achar o ZIP e baixar do CDN `cdn.tse.jus.br`, que hoje responde aos robôs (o projeto já baixa `consulta_cand`, `bweb` e fotos de lá). Anotar no código que a API do DivulgaCandContas foi recusada (403), como pede o CLAUDE.md.

### Gaps
- Esta sessão não confirmou se `cdn.tse.jus.br/.../prestacao_contas/*.zip` responde ao GitHub Actions. Por analogia com os arquivos já usados, deve responder.
- Não se sabe se o DivulgaSPCA tem API JSON.

## 3. Campos dos doadores, CPF/CNPJ (LGPD) e ligação com empresas

### Takeaway
A lei obriga a identificar cada doador por CPF ou CNPJ, e o TSE publica CPF e nome dos doadores nas contas. Os CSVs de 2026 trazem CPF, segundo um projeto que os usa. O portal precisa mascarar o CPF, pela regra de ouro 2, e também procurar CPF escondido em campos de texto livre. Desde 2015 empresas não podem doar. A ligação com empresas, então, se faz pelo doador pessoa física que é sócio (base CNPJ/Minha Receita, já usada) e pelo CNPJ dos fornecedores nas despesas.

### Cited Findings
- Toda doação em dinheiro precisa de documento bancário que identifique o CPF ou CNPJ do doador. Sem isso, o dinheiro é "recurso de origem não identificada" — [TSE Temas Selecionados, Caracterização de doação](https://temasselecionados.tse.jus.br/temas-selecionados/contas-de-campanha-eleitoral/doacoes-ou-contribuicoes/caracterizacao-de-doacao); [TRE-SC, pontos críticos](https://www.tre-sc.jus.br/partidos/prestacao-de-contas-partidarias/arquivos-pc/2023-apresentacao-pontos-criticos-de-exame)
- O TSE divulga as contas parciais "com a indicação dos nomes, do CPF dos doadores e dos respectivos valores doados" — [Monitor Mercantil](https://monitormercantil.com.br/candidatos-ja-devem-enviar-prestacao-de-contas-parcial-2/)
- Os CSVs `*_BR.csv` do TSE de 2026 contêm CPF. Por isso o projeto não os republica e mostra os doadores sem CPF — [diazaraujo/doadores-presidencial-2026](https://github.com/diazaraujo/doadores-presidencial-2026)
- Há CPF completo em texto livre (`descricao`) nas tabelas de receitas, despesas e bens do TSE. Um projeto passou a mascarar CPF e conta bancária e criou um teste que falha se aparecer CPF — [dado-publico-brasil issue #195](https://github.com/codigo-publico-brasil/dado-publico-brasil/issues/195)
- No julgamento sobre LGPD e registro de candidatura (PA 0600231-37), o ministro Fachin votou por manter públicos os dados de candidatos — [TSE, voto Fachin](https://www.tse.jus.br/comunicacao/arquivos/voto-ministro-edson-fachin-pa-0600231-37-aplicacao-da-lgpd-no-registro-de-candidatura); [Poder360 PDF](https://static.poder360.com.br/2022/08/Fachin-vota-por-manter-públicos-dados-de-candidatos.pdf)
- Em 2016 o arquivo de receitas tinha colunas de CPF/CNPJ e nome do doador, em `;` e latin1. O cabeçalho muda entre eleições — [generonumero/tse_candidatos_2016](https://github.com/generonumero/tse_candidatos_2016)

### Inferences
- Ligação com empresas: (a) despesas pagas a fornecedores com CNPJ ↔ base CNPJ, para achar fornecedores que também recebem do governo (PNCP, Portal) ou cujos sócios são doadores; (b) doador pessoa física ↔ sócios da base CNPJ. A Minha Receita mostra o CPF dos sócios mascarado (`***123456**`), então a ligação tem de usar nome mais os 6 dígitos centrais, com risco de homônimo. Isso deve ser descrito como "possível ligação", nunca como certeza.
- Nos arquivos de 2026, os nomes exatos das colunas (ex.: `NR_CPF_CNPJ_DOADOR`, `NM_DOADOR`, `CD_CNAE_DOADOR`, `DS_ORIGEM_RECEITA`, `NR_CPF_CNPJ_DOADOR_ORIGINARIO`) precisam ser conferidos no leiame do ZIP. Nenhuma fonte encontrada confirmou esses nomes.

### Gaps
- Não foi confirmado se o TSE passou a mascarar o CPF do doador no CSV depois da LGPD. A fonte de 2026 indica que não mascara, mas não diz se o CPF vem completo ou parcial.
- Não foi encontrado o leiame oficial com as colunas de 2026.

## 4. Prazos da prestação final de 2026 e o que existe em novembro de 2026

### Takeaway
As contas parciais foram publicadas em 15/09/2026. A prestação final vence em 03/11/2026 para quem só disputou o 1º turno e em 14/11/2026 para quem foi ao 2º turno (com os dois turnos). Em 09/11/2026 já devem existir as finais do 1º turno, que o TSE publica aos poucos, e as do 2º turno ainda faltam.

### Cited Findings
- O prazo final do 1º turno foi 03/11/2026, também para transferir sobras e devolver FEFC não usado. Quem disputou o 2º turno tem até 14/11/2026. A entrega é pelo sistema CONTA+JE — [TSE, notícia out/2026](https://www.tse.jus.br/comunicacao/noticias/2026/Outubro/candidaturas-e-partidos-tem-ate-3-de-novembro-para-prestar-contas-do-1o-turno); [TSE, CONTA+JE](https://www.tse.jus.br/eleicoes/eleicoes-2026-content/prestacao-de-contas/contaje-sistema-de-prestacao-de-contas); [TRE-AC](https://www.tre-ac.jus.br/comunicacao/noticias/2026/Outubro/prazo-para-prestacao-de-contas-finais-do-primeiro-turno-das-eleicoes-2026-termina-em-3-de-novembro); [TRE-PI](https://www.tre-pi.jus.br/comunicacao/noticias/2026/Novembro/eleicoes-2026-prazo-final-para-prestacao-de-contas)
- As contas parciais foram disponibilizadas a partir de 15/09/2026 — [TSE, notícia set/2026](https://www.tse.jus.br/comunicacao/noticias/2026/Setembro/tse-disponibiliza-dados-da-prestacao-de-contas-parcial-das-campanhas-eleitorais); [TSE, prazos](https://www.tse.jus.br/comunicacao/noticias/2026/Setembro/faltam-27-dias-confira-os-principais-prazos-da-prestacao-de-contas-eleitoral)
- Regras de 2026: Res. TSE 23.607/2019, alterada pela 23.731/2024. Para 2026 também vale a Res. 23.752/2026 — [TSE Res. 23.752/2026](https://www.tse.jus.br/legislacao/compilada/res/2026/resolucao-no-23-752-de-26-de-fevereiro-de-2026); [TRE-MG apresentação 2024](https://www.tre-mg.jus.br/eleicoes/eleicoes-2024-1/prestacao-de-contas/pasta-de-arquivos-das-prestacoes-de-contas-eleicoes-2024/apresentacao-cafe-com-contabilista-no-crc-mg-arrecadacao-e-gastos-de-campanha-nas-eleicoes-de-2024)

### Inferences
- O arquivo de 2026 vai mudar por semanas, com entregas atrasadas e retificações. A coleta deve baixar de novo enquanto ele mudar (como `tse.py` faz com a eleição do ano, a cada 20 h) e mostrar na página que as contas ainda não foram julgadas. O julgamento das contas dos eleitos precisa sair antes da diplomação, em dezembro.

### Gaps
- Não foi confirmada a data de publicação do arquivo aberto com as contas finais de 2026 (`metadata_modified`).

## 5. Limites legais: doação de empresas proibida (ADI 4650)

### Takeaway
O STF proibiu doações de pessoas jurídicas na ADI 4650 (17/09/2015), e a Lei 13.165/2015 incorporou a proibição. Pessoas físicas podem doar até 10% dos rendimentos brutos do ano anterior. Para o portal, "doação de empresa" nos dados de 2016 em diante é sinal de irregularidade ou de lançamento errado. A influência de empresas aparece por sócios e dirigentes que doam como pessoa física, e por fornecedores de campanha.

### Cited Findings
- ADI 4650, relator Min. Luiz Fux, julgada em 16 e 17/09/2015: doações de pessoas jurídicas a campanhas são inconstitucionais — [Dizer o Direito](https://www.dizerodireito.com.br/2015/10/stf-proibe-doacoes-de-pessoas-juridicas.html?m=1); [Damásio, Info 799](https://juris.damasio.com.br/jurisprudencia/julgado/799/adi-e-financiamento-de-campanha-eleitoral)
- Art. 23, §1º da Lei 9.504/97 (redação da Lei 13.165/2015): pessoa física pode doar até 10% dos rendimentos brutos do ano anterior — [Jornal Contábil](https://jornalcontabil.com.br/noticia/eleicoes-2020-conheca-aqui-as-regras-e-os-limites-para-doacoes-eleitorais/)
- Há doação vedada também de fontes como beneficiário do Bolsa Família (caso de vereador do RN cassado) — [AASP](https://www.aasp.org.br/?p=38367)

### Inferences
- Comparar anos é delicado. Até 2014 havia doação de empresas, então totais de 2014 e de 2018 em diante não se comparam diretamente. Desde 2018 o dinheiro público (FEFC e Fundo Partidário) é a maior fonte, e por isso vale cruzar a receita de cada candidato com a origem "FEFC".
- O TSE já cruza o limite de 10% com a Receita Federal. O portal não tem os rendimentos e não deve dizer que alguém passou do limite.

### Gaps
- Há um voto de Toffoli em 2023 na ADI 4650 (embargos ou revisão), mas o desfecho não foi encontrado — [Conjur PDF](https://www.conjur.com.br/wp-content/uploads/2023/09/voto-toffoli-doacoes-eleitorais.pdf)
