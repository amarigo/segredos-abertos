# Como sites de transparência do exterior mostram o dinheiro de cada político (pesquisa de 09/11/2026)

> Aviso de método: nesta sessão, a busca na web funcionou, mas a leitura direta das páginas foi bloqueada para
> opensecrets.org (recusado), theyworkforyou.com, mysociety.org e research.mysociety.org (domínios fora da rede
> permitida). Os fatos abaixo vêm dos trechos e resumos que a busca devolveu, com o link da página original. Onde só
> havia fonte secundária, está dito. O que conheço de memória e não consegui conferir ficou em "Lacunas".

## 1. OpenSecrets (EUA): finanças pessoais, campanha, lobby e situação da organização

### Takeaway
O OpenSecrets resolve o problema de "valores em faixas" somando o mínimo e o máximo de cada item declarado e mostrando
uma faixa com um valor médio (ponto do meio) como melhor estimativa; o perfil do político junta, lado a lado, maiores
doadores e maiores setores. Desde 2021 é a fusão do Center for Responsive Politics com o FollowTheMoney (estados), e
desde abril de 2025 não tem mais API pública.

### Cited Findings
- Fusão: em junho de 2021 o Center for Responsive Politics (OpenSecrets.org, federal) e o National Institute on Money
  in Politics (FollowTheMoney.org, estados) se juntaram e formaram a OpenSecrets — [Common Dreams, comunicado de
  2021](https://commondreams.org/newswire/2021/06/02/leading-money-politics-data-nonprofits-merge-form-opensecrets-state-art);
  [Ballotpedia](https://ballotpedia.org/Follow_The_Money); [Maryland Matters](https://marylandmatters.org/2021/06/03/2-nonprofits-that-track-money-in-politics-are-merging/)
- O site followthemoney.org continuaria atualizado até o lançamento do site novo — [Election Law Blog](https://electionlawblog.org/2021/leading-money-in-politics-data-nonprofits-merge-to-form-opensecrets-a-state-of-the-art-democratic-accountability-organization/)
- Situação em 2026: a OpenSecrets segue ativa, publicando sobre as eleições de meio de mandato de 2026 (estimativa de
  US$ 11,9 bilhões de gasto total, citada por terceiros), PACs de liderança e gastos externos; em 6/8/2026 anunciou
  melhoria na base de lobby; em março de 2026 fez parceria de conteúdo com a Newsreel para público jovem. Não apareceu
  troca de direção nem crise em 2026 — [resumo do feed da OpenSecrets (rss-parrot)](https://rss-parrot.net/web/feeds/opensecrets.org);
  [Common Dreams](https://www.commondreams.org/news/billionaires-buying-2026-midterms); [Relatório anual 2025 (PDF)](https://dkftve4js3etk.cloudfront.net/2025-annual-report/OpenSecrets-2025-Annual-Report.pdf)
- API pública encerrada em 15/04/2025; hoje só há download em lote (conta gratuita com aprovação, defasado em relação
  ao site, atualizado poucas vezes por ano no ciclo corrente) ou acordo comercial — [Bellingcat Toolkit](https://bellingcat.gitbook.io/toolkit/more/all-tools/opensecrets);
  [SVCAF](https://svcaf.org/pages/comprehensive-api-resources-for-ai-driven-legislative-analysis/) (fontes secundárias)
- Finanças pessoais: a declaração do Congresso dá ativos e dívidas em faixas, não em valores exatos. A OpenSecrets soma
  todas as faixas de ativos e subtrai as de dívidas, forma uma faixa total de patrimônio e mostra a média como melhor
  palpite — [Ballotpedia](https://ballotpedia.org/Net_worth_of_United_States_Senators_and_Representatives);
  [Ballotpedia, patrimônio do domicílio](https://ballotpedia.org/Household_net_worth_(Member_of_Congress))
- O número de destaque é o ponto do meio entre o mínimo e o máximo (ex.: US$ 16 milhões da dep. Carol Miller) —
  [PolitiFact](https://api.politifact.com/factchecks/2022/oct/27/west-virginia-democratic-party/rep-carol-miller-west-virginia-worth-over-16-milli)
- Guia de dados da OpenSecrets: a faixa representa os extremos do que o declarante pode valer; o patrimônio real fica
  em algum ponto dentro dela — [OpenData User's Guide (2015, cópia)](https://www.maraamdwidar.com/uploads/8/1/2/9/81297114/userguide.pdf)
- Armadilha de interpretação: o patrimônio inclui cônjuge e filhos dependentes. No caso de Ilhan Omar, o domicílio
  ia de ~US$ 6 milhões a US$ 30 milhões, mas o patrimônio pessoal dela ia de −US$ 82 mil a +US$ 65 mil; a faixa larga
  virou boato de "ganhou US$ 30 milhões" — [Yahoo/checagem](https://www.yahoo.com/news/articles/inspecting-claim-ilhan-omars-net-220700049.html);
  [Yahoo, contexto](https://www.yahoo.com/news/articles/trumps-claim-ilhan-omar-worth-235600331.html)
- Perfil de campanha: a OpenSecrets há muito tempo mostra, para cada político, "maiores doadores" (organizações) e
  "maiores setores" lado a lado com totais em dólar; a API antiga tinha funções separadas para os dois rankings —
  [arquivo Harvard](https://cyber.harvard.edu/archive/dvd-discuss2/msg15144.html); [ropensecretsapi](https://packages.oit.ncsu.edu/cran/web/packages/ropensecretsapi/refman/ropensecretsapi.html)
- A OpenSecrets compila as prestações de contas da FEC para mostrar receitas de cada PAC e número de doadores —
  [Wikipedia, KochPAC](https://en.wikipedia.org/wiki/KochPAC)
- Concentração: 1% dos doadores respondeu por 98% das doações a grupos externos no ciclo 2025–2026 (dado OpenSecrets
  citado pela Newsweek) — [Newsweek](https://newsweek.com/the-billionaires-who-spent-won-and-lost-the-most-at-the-midterms-12661688)

### Inferences
- Para o Brasil: a declaração de bens do TSE dá valor exato por item (não faixas), então dá para mostrar o número sem a
  ginástica de faixas. Mas a lição do caso Omar vale: separar o que é do político do que é do domicílio, e mostrar
  variação entre eleições com o aviso de que bem declarado é valor de aquisição, não de mercado.
- O padrão "maiores doadores × maiores setores" lado a lado funciona para doações eleitorais (TSE) e também para
  "empresas que receberam da cota parlamentar", que o Segredos Abertos já tem: top fornecedores e top categorias.
- O fim da API da OpenSecrets mostra o risco de depender de terceiros: melhor coletar direto da fonte oficial (no
  Brasil, TSE/Câmara/Senado), como o projeto já faz.

### Gaps
- Não consegui ler a página de método das finanças pessoais (https://www.opensecrets.org/personal-finances/methodology)
  nem o layout atual do perfil do político; os blocos que lembro (resumo de campanha, origem do dinheiro por tamanho de
  doação, dentro/fora do estado, setores, maiores doadores, finanças pessoais, lobby, "porta giratória", operações com
  ações) não foram conferidos nesta sessão.
- Não confirmei o texto do aviso da OpenSecrets de que "a organização em si não doou; o dinheiro veio do PAC, de
  funcionários e familiares dela" (agregação de doadores pelo empregador declarado), nem a regra de codificação de
  setores (códigos de categoria por empregador/ocupação, feitos à mão). Ver https://www.opensecrets.org/about/methodology.
- Sem fonte nesta sessão sobre as páginas de operações com ações (STOCK Act) e "Revolving Door".

## 2. TheyWorkForYou (Reino Unido, mySociety): votos resumidos, interesses e despesas

### Takeaway
O TheyWorkForYou transforma votações em frases simples por tema ("política"), com regras públicas: só votos de
"ação" contam, votos são marcados como "pontuam" ou "informativos", ausências não contam, e há uma medida separada de
alinhamento ao partido. No dinheiro, o projeto WhoFundsThem junta e explica o registro de interesses financeiros.

### Cited Findings
- Revisão de 2024: os resumos passaram a usar só "votos de ação" (que usam poderes do Parlamento), deixando de fora os
  "votos de fala" — [mySociety, revisão 2024](https://research.mysociety.org/html/2024-voting-records/)
- Cada voto é marcado como "que pontua" ou "informativo"; os resumos agrupam votos numa "política", e cada voto concorda
  ou discorda dela; só os que pontuam formam a frase principal — [TheyWorkForYou, informação sobre votos](https://www.theyworkforyou.com/voting-information/)
- Ausências não contam, porque não há como saber o motivo (doença, licença-maternidade). Em 2015 a regra era outra:
  ausência valia metade de um voto a favor — [TheyWorkForYou](https://www.theyworkforyou.com/voting-information/);
  [mySociety 2015](https://www.mysociety.org/2015/08/21/everything-about-theyworkforyous-voting-information/)
- Como a orientação de bancada nem sempre é pública, o site calcula o alinhamento: a distância entre o voto do
  deputado (0% ou 100%) e a parcela do partido que votou igual — [TheyWorkForYou](https://www.theyworkforyou.com/voting-information/);
  [mySociety, "How far does your MP tread the party line?"](https://www.mysociety.org/2015/08/03/how-far-does-your-mp-tread-the-party-line/)
- Os resumos aparecem para "todo o período" e para cada governo desde 1997, para não misturar votos antigos e
  recentes — [TheyWorkForYou](https://www.theyworkforyou.com/voting-information/)
- Pontuação: cada votação dá pontos conforme o voto; a soma é comparada com a de um deputado que sempre votou com a
  política — [mySociety 2015](https://www.mysociety.org/2015/08/21/everything-about-theyworkforyous-voting-information/)
- Palavras: o site usava "voted strongly for" e "voted moderately against"; usuários perguntavam como alguém vota
  "fortemente", o que levou a mudança de texto. O site-irmão australiano They Vote For You trocou "voted strongly
  against" por "consistently against" depois de reclamação de políticos liberais — [mySociety 2015](https://www.mysociety.org/2015/08/21/everything-about-theyworkforyous-voting-information/);
  [Pedestrian.tv](https://www.pedestrian.tv/news/liberal-mps-vote-backfired)
- Disputa pública: a LabourList chamou de "mentiras" citações corretas do TheyWorkForYou — sinal de que o rótulo do
  resumo vira munição política — [Lib Dem Voice](https://www.libdemvoice.org/theyworkforyou-13471.html)
- Deputado como "teller" (contador de votos) é tratado como voto do seu lado, regra herdada do Public Whip e
  discutida — [GitHub mysociety/theyworkforyou #566](https://github.com/mysociety/theyworkforyou/issues/566)
- Em 2025 a mySociety lançou o TheyWorkForYou Votes (votes.theyworkforyou.com), plataforma própria para os dados e
  métodos de votação; atualizações dos resumos em março de 2025 e julho de 2026 — [mySociety, TWFY Votes](https://www.mysociety.org/2025/05/19/theyworkforyou-votes/);
  [sobre](https://votes.theyworkforyou.com/help/about); [atualização julho 2026](https://www.mysociety.org/2026/07/01/theyworkforyou-voting-summaries-update-july-2026/)
- WhoFundsThem: projeto de dinheiro na política sobre o Registro de Interesses Financeiros dos deputados; o registro
  "tem muito dado e pouco contexto", e o projeto pergunta, por exemplo, o que fazem as organizações doadoras — [mySociety WhoFundsThem](https://www.mysociety.org/democracy/who-funds-them/)
- No TheyWorkForYou: registros de interesses de todos os parlamentos do Reino Unido num lugar, planilhas para baixar,
  registros eleitorais, destaque para interesses ligados a setores de baixa confiança ou a governos "não livres", e
  lista de grupos parlamentares (APPGs) — [mySociety WhoFundsThem](https://www.mysociety.org/category/democracy/who-funds-them/);
  [planilha nova do registro](https://www.mysociety.org/2024/08/20/new-register-of-interests-spreadsheet-with-much-richer-data/)
- Voluntários revisaram o registro inteiro; relatório "Beyond Transparency" (março de 2025); registros dos parlamentos
  regionais adicionados em março de 2025; o registro da Câmara dos Comuns sai a cada duas semanas (post de junho de
  2026) — [mySociety democracia 2025](https://www.mysociety.org/2025/03/13/mysocietys-democracy-work-in-2025/);
  [O que sabemos dos interesses financeiros](https://www.mysociety.org/2024/09/25/what-do-we-know-about-mps-financial-interests/)
- Declarações de interesse ligadas às perguntas parlamentares — [mySociety 2024](https://www.mysociety.org/2024/10/31/better-declarations-of-interest-for-parliamentary-questions/)

### Inferences
- O Segredos Abertos já tem espectro esquerda-direita e votos por partido. O modelo TWFY sugere: (a) agrupar votações
  em temas com frase simples ("votou quase sempre a favor de X"), (b) publicar a lista de votações de cada tema e quais
  pontuam, (c) não contar ausência, (d) mostrar "votou com o partido em N% das vezes" calculado pela parcela do
  partido, útil porque a orientação de bancada da Câmara existe mas nem sempre é dada.
- Evitar adjetivos de intensidade ("fortemente"): preferir frequência ("quase sempre", "na maioria das vezes").
- O "destaque" do WhoFundsThem (interesse ligado a setor sensível) é análogo a um alerta "esta empresa paga pela cota
  também recebeu emenda/contrato" ou "doador de campanha é fornecedor da cota".

### Gaps
- Não consegui ler as faixas exatas de texto e os limites de pontuação atuais (ex.: "consistently voted for", "almost
  always", "generally", "mix of votes") nem a página do deputado; leitura direta bloqueada.
- Não achei fonte sobre como o TheyWorkForYou mostra as despesas do IPSA hoje (lembro de link para o site do IPSA, sem
  conferir).

## 3. Outros sites: GovTrack, ProPublica, FEC, HowTheyVote.eu, Integrity Watch EU, abgeordnetenwatch.de

### Takeaway
Os modelos ativos e mais úteis são: FEC (páginas oficiais com resumo de arrecadação, caixa e doações por estado e por
tamanho), Integrity Watch EU e abgeordnetenwatch (renda extra em faixas, reuniões com lobistas), HowTheyVote.eu (cada
votação nominal com placar por país e por deputado, dados abertos). ProPublica Represent acabou; o GovTrack retirou as
notas anuais por serem pouco confiáveis.

### Cited Findings
- ProPublica Represent e a Congress API não existem mais (página atualizada em 10/07/2024; documentação só como
  histórico) — [ProPublica](https://www.propublica.org/datastore/api/propublica-congress-api); [docs](https://projects.propublica.org/api-docs/congress-api/)
- A API do Congresso da Sunlight Foundation foi desligada em 01/10/2017 — [GitHub propublica/sunlight-congress](https://github.com/propublica/sunlight-congress)
- GovTrack encerrou dados em lote e API em 2016 — [GovTrack](https://www.govtrack.us/posts/124/2016-12-10_ending-govtracks-bulk-data-and-api)
- GovTrack calcula ideologia e liderança pela coautoria de projetos (quem assina projetos parecidos fica perto na
  escala; quem tem projetos coassinados por colegas influentes ganha liderança); não dá nota para quem apresentou menos
  de 10 projetos — [Ballotpedia](https://ballotpedia.org/GovTrack%27s_Political_Spectrum_%26_Legislative_Leadership_ranking);
  [Wisconsin Examiner](https://wisconsinexaminer.com/2020/02/24/measuring-effectiveness-and-ideology-of-wisconsins-members-of-congress/)
- Em julho de 2024 o GovTrack retirou a página de 2019 que chamava Kamala Harris de "senadora mais liberal", depois de
  avisar que as notas de um ano só eram pouco confiáveis — [WLOS](https://wlos.com/news/nation-world/government-transparency-site-pulls-page-naming-kamala-harris-most-liberal-senator-government-transparency-site-govtrack-removed-a-2019-page-naming-vice-president-kamala-harris-as-that-years-most-liberal-senator)
- A medida do GovTrack teve correlação ~0,90 com o NOMINATE (Poole-Rosenthal) — [Sunlight Foundation 2014](https://sunlightfoundation.com/2014/06/11/how-partisan-are-your-states-legislators/) (fonte secundária, antiga)
- FEC.gov, página do candidato: bloco de totais (receitas, contribuições, contribuições individuais detalhadas e não
  detalhadas, de partido, de outros comitês, do próprio candidato), resumo de caixa (saldo final, dívidas e empréstimos
  a receber e a pagar), total gasto com detalhe, e tabelas de contribuições individuais por estado e por tamanho; aviso
  de que dados novos podem levar até 48 horas — [FEC, exemplo](https://www.fec.gov/data/candidate/H0NY01095/?tab=summary);
  [FEC, outro exemplo](https://www.fec.gov/data/candidate/S6FL00806/)
- HowTheyVote.eu: cada votação nominal do Parlamento Europeu com placar (sim/não/abstenção com %, quem não votou),
  resultado por país e por deputado com grupo e país, link para o documento e lista de fontes (XML oficial, Observatório
  Legislativo, notas de imprensa); dados abertos em CSV no GitHub; só votos nominais (não pega voto secreto nem de mão
  levantada); correções de voto tratadas à parte — [HowTheyVote.eu, exemplo](https://howtheyvote.eu/votes/191581);
  [sobre](https://howtheyvote.eu/about); [GitHub HowTheyVote/data](https://awesome.ecosyste.ms/projects/github.com%2FHowTheyVote%2Fdata);
  [FOSDEM 2026](https://fosdem.org/2026/schedule/event/how-they-vote)
- Integrity Watch EU (Transparency International EU): renda extra dos eurodeputados declarada em faixas brutas largas,
  daí a grande distância entre mínimo e máximo; a seção mostra ainda dados da legislatura 2019–2024 enquanto processa as
  novas declarações — [Integrity Watch EU](https://www.integritywatch.eu/mepincomes.php); [sobre](https://www.integritywatch.eu/about.php)
- Exemplo de como comunicar faixas: "27% dos 705 eurodeputados declararam juntos entre 3,9 e 11,5 milhões de euros de
  renda extra" (análise de 2021) — [TI EU](https://transparency.eu/burning-candle-mep-income/)
- Reuniões com lobistas: depois do Qatargate, eurodeputados e assessores precisam publicar reuniões; 500 organizações
  respondem por quase metade (47%) das reuniões do mandato — [TI EU, reuniões](https://transparency.eu/new-mep-meetings/?output=pdf);
  [TI EU, ferramenta de lobistas](https://transparency.eu/who-really-has-the-eus-ear-introducing-the-new-integrity-watch-eu-lobbyists-tool/)
- abgeordnetenwatch.de: o perfil do deputado tem abas "Nebentätigkeiten" (atividades e renda extra) e "Abstimmungen"
  (votações nominais importantes da legislatura) — [abgeordnetenwatch em 3 minutos](https://www.abgeordnetenwatch.de/abgeordnetenwatchde-in-3-minuten);
  [exemplo de votação](https://www.abgeordnetenwatch.de/bundestag/17/abstimmungen/offenlegung-von-nebeneinkuenften-auf-euro-und-cent)
- Renda extra no Bundestag era declarada em níveis (de 3 para 10, de 1.000–3.500 € até mais de 250.000 €); o site
  usava o piso de cada nível nas somas (estimativa conservadora) e publicava rankings dos "maiores ganhos" — [abgeordnetenwatch, lista 2018](https://www.abgeordnetenwatch.de/recherchen/nebentaetigkeiten/das-sind-die-nebeneinkuenfte-der-bundestagsabgeordneten-0);
  [Spitzenverdiener](https://www.abgeordnetenwatch.de/recherchen/nebentaetigkeiten/spitzenverdiener-im-parlament);
  regras mais rígidas desde a reforma de 2021/2022 segundo [bundestagwahlumfrage.de](https://bundestagwahlumfrage.de/ratgeber/bundestag/nebeneinkuenfte-abgeordnete/) (fonte secundária, não conferida)

### Inferences
- Padrão de faixas: duas escolas — ponto do meio (OpenSecrets) e piso (abgeordnetenwatch). O piso é mais seguro contra
  acusação de exagero; mostrar sempre "entre X e Y".
- O FEC é o modelo de "página oficial seca": totais, caixa, dívidas e distribuição por tamanho e estado. O equivalente
  brasileiro é a prestação de contas do TSE (DivulgaCandContas).
- HowTheyVote mostra bem um ponto que o Segredos Abertos já segue: link para a fonte de cada votação e dados abertos.
- O recuo do GovTrack é um alerta para o espectro esquerda-direita do Segredos Abertos: evitar títulos de "o mais X"
  com base em um ano só e em poucos votos; mostrar incerteza ou janela longa.

### Gaps
- Não achei fonte atual sobre o Parltrack nem sobre o layout do perfil de eurodeputado no HowTheyVote (busca só trouxe
  páginas de votação).
- Não conferi se o FEC mostra mapa (as buscas só mostraram cabeçalhos das tabelas por estado).

## 4. Equivalentes brasileiros: Ranking dos Políticos, Transparência Brasil (Excelências, Às Claras), Políticos.org.br

### Takeaway
O Ranking dos Políticos dá nota com peso declarado (75% votos, 10% gastos, 10% presença, 5% privilégios), mas os votos
"certos" são escolhidos por um conselho com viés liberal-conservador declarado. A Transparência Brasil foi pioneira em
juntar financiamento de campanha e processos por parlamentar (Excelências, Às Claras), mas o Excelências parece
descontinuado.

### Cited Findings
- Nota do Ranking dos Políticos: votos 75%, gastos 10%, presença 10%, privilégios 5%; bônus por produção legislativa;
  cada condenação judicial tira 0,5 ponto; voto alinhado à orientação do Ranking ganha a pontuação integral do projeto;
  quais projetos entram é decidido pelo "Conselho de Leis"; dados das APIs da Câmara, do Senado e dos tribunais —
  [Ranking, cálculo da nota 2026](https://ranking.org.br/en/articles/metodologia-ranking-dos-politicos-calculo-nota);
  [critérios](https://ranking.org.br/en/criteria-and-methodology)
- O Ranking se diz apartidário mas "não neutro" (eficiência, ambiente de negócios, combate à corrupção); a Wikipédia o
  descreve como think tank de linha liberal e conservadora e registra críticas aos critérios — [Quem somos](https://ranking.org.br/en/about-us);
  [Wikipédia](https://pt.wikipedia.org/wiki/Ranking_dos_Pol%C3%ADticos)
- Excelências (Transparência Brasil): mostrou financiamento de campanha e envolvimento em escândalos de parlamentares de
  todo o país; orientou a Lei da Ficha Limpa; dados coletados à mão de pelo menos cinco fontes públicas e dos projetos
  Deu no Jornal e Às Claras "ao longo de onze anos" (texto no passado sugere fim) — [Transparência Brasil](https://www.transparencia.org.br/en/projects/excelencias/)
- Às Claras: análise do financiamento eleitoral desde 2002 — [Idec](https://idec.org.br/print/23445);
  [Transparência Brasil, "Custo do voto" (PDF)](https://www.transparencia.org.br/downloads/publicacoes/custo%20do%20voto.pdf)

### Inferences
- Espaço livre no Brasil: um perfil que junte, com fonte oficial e sem nota ideológica, gastos de mandato + doações de
  campanha + bens declarados + empresas e donos. O Segredos Abertos pode ocupar isso sem dar "nota", diferente do
  Ranking.
- Se o projeto der algum índice, publicar pesos e lista de votações, como o Ranking e o TWFY fazem, e separar fato
  (dados) de julgamento.

### Gaps
- Não pesquisei Políticos.org.br nem "Mapa da Política" (sem resultados nesta rodada); não sei se estão ativos.
- Não confirmei se o Excelências/Às Claras estão no ar em 2026.

## 5. Técnicas didáticas e lições de método

### Takeaway
Os sites que funcionam usam frase simples com regra pública, faixa + estimativa central quando o dado oficial é em
faixas, comparação com a média e com o partido, e link para a fonte em cada número; os que tropeçaram (GovTrack 2024,
caso Omar) mostraram rótulos fortes demais com dados frágeis.

### Cited Findings
- Frase simples por tema com método publicado e votações listadas — [TheyWorkForYou](https://www.theyworkforyou.com/voting-information/)
- Comparação com o próprio partido (alinhamento) — [mySociety 2015](https://www.mysociety.org/2015/08/03/how-far-does-your-mp-tread-the-party-line/)
- Faixa + ponto do meio, com aviso de que o valor real está "em algum ponto da faixa" — [Ballotpedia](https://ballotpedia.org/Net_worth_of_United_States_Senators_and_Representatives)
- Somar pelo piso das faixas (estimativa mínima garantida) — [abgeordnetenwatch](https://www.abgeordnetenwatch.de/recherchen/nebentaetigkeiten/das-sind-die-nebeneinkuenfte-der-bundestagsabgeordneten-0)
- Dar contexto ao dado bruto (o que faz o doador; destacar setores sensíveis) — [WhoFundsThem](https://www.mysociety.org/democracy/who-funds-them/)
- Não dar nota sem dado suficiente (GovTrack: mínimo de 10 projetos; retirada das notas de um ano) — [Ballotpedia](https://ballotpedia.org/GovTrack%27s_Political_Spectrum_%26_Legislative_Leadership_ranking);
  [WLOS](https://wlos.com/news/nation-world/government-transparency-site-pulls-page-naming-kamala-harris-most-liberal-senator-government-transparency-site-govtrack-removed-a-2019-page-naming-vice-president-kamala-harris-as-that-years-most-liberal-senator)
- Concentração como manchete ("1% dos doadores = 98%") — [Newsweek](https://newsweek.com/the-billionaires-who-spent-won-and-lost-the-most-at-the-midterms-12661688)

### Inferences
- Para o perfil do Segredos Abertos: (1) bloco de resumo com 3–4 números e "comparado com a média da Casa"; (2) "de
  onde vem / para onde vai" (doadores → político → fornecedores da cota → donos), um gráfico "siga o dinheiro";
  (3) temas de votação em frase simples com regra pública; (4) alertas só com regra objetiva e fonte (ex.: doador que é
  fornecedor, empresa aberta há pouco tempo); (5) mínimo de dados antes de rotular no espectro.
- Deduplicar doadores: no Brasil, CPF/CNPJ do doador vêm na prestação de contas do TSE, o que evita o trabalho de
  juntar nomes escritos de jeitos diferentes que a OpenSecrets faz pelo empregador declarado (esta comparação é minha,
  sem fonte sobre o processo interno da OpenSecrets).

### Gaps
- Sem fonte nesta sessão sobre como a OpenSecrets junta doadores repetidos e codifica setores (método interno de
  categorias). Vale ler https://www.opensecrets.org/about/methodology e a página de códigos de categoria numa sessão com
  acesso a esse domínio.
- Não achei avaliação de uso (testes com usuários) de nenhum desses sites.
