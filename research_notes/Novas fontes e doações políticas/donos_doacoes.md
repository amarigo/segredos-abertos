# Ligar donos de empresas (sócios na base CNPJ) a doações de campanha e a dinheiro público

> Notas de pesquisa, 09/11/2026. Limitação importante: nesta sessão, a rede só abriu buscas e o github.com. Os sites
> transparencia.org.br, dadosabertos.tse.jus.br, atlaspublico.com.br, investigadora.substack.com e portaltela.com
> **não abriram** (DNS bloqueado pela sessão). Por isso, várias afirmações abaixo vêm dos trechos de busca, não da
> página inteira. Antes de usar no código, confira cada uma na fonte original.

## 1. Chaves de cruzamento: como o CPF aparece na base CNPJ e nos dados do TSE

### Takeaway
Na base CNPJ da Receita, o CPF do sócio pessoa física vem **mascarado, com só os 6 dígitos do meio visíveis**
(`***123456**`). Nos arquivos de receitas de campanha do TSE de 2026, o CPF do doador **aparece** (o arquivo "traz
CPF e CNPJ"), mas não consegui confirmar se vem completo ou mascarado. A chave segura é **nome completo normalizado +
os 6 dígitos do meio do CPF**; se um dos dois não bate, trata-se como pessoas diferentes.

### Cited Findings
- Base CNPJ: a Receita mascara o CPF dos sócios nos dados abertos; só os seis dígitos do meio ficam visíveis. Guia
  recomenda comparar nome completo + esses seis dígitos e, se um não bater, tratar como pessoas diferentes; quando o
  sócio é empresa, o CNPJ resolve — [Atlas Público, guia "sócios de uma empresa"](https://atlaspublico.com.br/guias/socios-de-uma-empresa-e-outras-empresas) (via trecho de busca; página não abriu)
- Fornecedor comercial confirma o mesmo formato, já mascarado na origem — [Apify, Brazil CNPJ Bulk Enrichment](https://apify.com/pegai/brazil-cnpj-enrichment)
- O próprio coletor do projeto já usa essa chave: `chave_socio` em `etl/sa_etl/cnpj.py` ("A Receita mascara o CPF
  (***123456**), então usamos nome + dígitos visíveis"), e sócio-empresa é identificado pela raiz do CNPJ — código local `etl/sa_etl/cnpj.py` linhas 128-133 e 272-273
- O projeto socios-brasil (Brasil.IO, Álvaro Justen) ainda apaga dados sensíveis: remove o CPF que aparece na razão
  social de empresas individuais (MEI/EI) e limpa o endereço dos sócios nesses casos; dados sob CC BY-SA 4.0 com pedido
  de citar a fonte original e quem tratou — [github.com/turicas/socios-brasil](https://github.com/turicas/socios-brasil)
- **Atenção MEI/EI**: na base CNPJ, a razão social de empresário individual costuma conter o CPF completo; por isso o
  socios-brasil o apaga — [github.com/turicas/socios-brasil](https://github.com/turicas/socios-brasil)
- TSE 2026: projeto independente com os doadores da campanha presidencial diz que os arquivos
  `receitas_candidatos_2026_BR.csv` e `receitas_candidatos_doador_originario_2026_BR.csv` "trazem CPF e CNPJ" e por
  isso não os põe no repositório; o site deles não mostra o CPF — [github.com/diazaraujo/doadores-presidencial-2026](https://github.com/diazaraujo/doadores-presidencial-2026) e [data/LEEME.md](https://github.com/diazaraujo/doadores-presidencial-2026/blob/main/data/LEEME.md)
- Projeto estudantil de 2024 com os mesmos arquivos marca "Dados pessoais | Remover antes de gravar", indício de que os
  arquivos brutos trazem dado pessoal do doador — [github.com/VKzinhon/Big-Data-TSE](https://github.com/VKzinhon/Big-Data-TSE)
- TSE divulgou a prestação de contas parcial de 2026 em setembro; dados completos no Repositório de Dados Eleitorais e
  no Portal de Dados Abertos (grupo "Prestação de Contas Eleitorais") — [TSE, notícia set/2026](https://www.tse.jus.br/comunicacao/noticias/2026/Setembro/tse-disponibiliza-dados-da-prestacao-de-contas-parcial-das-campanhas-eleitorais); [Portal de Dados Abertos do TSE](https://dadosabertos.tse.jus.br/group/prestacao-de-contas-eleitorais)
- Busca pública por CPF/CNPJ de doador existe no DivulgaCandContas (até 10 resultados por busca) — [Infosimples, descrição da consulta TSE doadores e fornecedores](https://infosimples.com/consultas/tse-doadores-fornecedores/)
- CPF do **candidato**: a Res. TSE 23.729/2024 ocultou o CPF no DivulgaCandContas e nos dados abertos, inclusive de
  eleições anteriores, alegando a LGPD — [Transparência Brasil](https://www.transparencia.org.br/noticias/apos-acao-da-sociedade-civil-tse-voltara-a-divulgar-cpf-de-candidatos-nas-eleicoes-de-2026); [Revista Cenarium](https://revistacenarium.com.br/justica-eleitoral-preve-fim-de-sigilo-do-cpf-de-candidatos-em-2026/)
- Em jan/2026 Transparência Brasil e mais 8 entidades pediram a volta; a minuta posta em consulta pública em 19/01/2026
  tirou o CPF da lista de dados sigilosos; Transparência Brasil diz que os dados de 2026 já trazem o CPF do candidato —
  [Transparência Brasil (pedido)](https://www.transparencia.org.br/noticias/organizations-ask-the-electoral-court-to-re-disclose-the-cpf-of-candidates-for-the-2026-elections); [Transparência Brasil (volta)](https://www.transparencia.org.br/noticias/tse-volta-a-divulgar-cpf-de-candidatos-apos-mobilizacao-da-sociedade-civil/); [Abraji](https://www.abraji.org.br/noticias/tse-acolhe-pedido-da-abraji-e-organizacoes-e-preve-volta-da-divulgacao-de-cpf-de-candidatos-em-2026); [Papo M3](https://papom3realidades.com.br/eleicoes-2026-justica-eleitoral-deve-tornar-publico-cpf-de-candidatos/)
- Site independente informa que os arquivos de candidatos de 2020 e 2024 publicam o CPF mascarado, o que impede ligar
  com segurança uma candidatura daqueles anos a uma pessoa — [Ficha (duranteos)](https://ficha.duranteos.com/) (fonte secundária)
- Abraji: sem CPF fica difícil separar homônimos e cruzar com outras bases — [Abraji](https://www.abraji.org.br/noticias/tse-acolhe-pedido-da-abraji-e-organizacoes-e-preve-volta-da-divulgacao-de-cpf-de-candidatos-em-2026)
- Estudo acadêmico em MG cruzou doadores (TSE) com sócios de empresas comparando nome **e** CPF do doador com nome e CPF
  dos sócios (base privada de sócios) — [SBBD/SBC, artigo](https://sol.sbc.org.br/index.php/sbbd/article/download/25554/25374) (via trecho de busca)
- Erro de digitação existe nos dados declarados (ex.: doadora digitou o CPF no campo de valor) — [Metrópoles](https://www.metropoles.com/brasil/doadora-eleitoral-erra-e-digita-o-cpf-no-lugar-do-valor)

### Inferences
- Algoritmo recomendado (todas as etapas determinísticas, sem "fuzzy" publicado):
  1. Do doador TSE (CPF de 11 dígitos, se vier completo): extrair `cpf[3:9]` (os 6 do meio) e normalizar o nome
     (maiúsculas, sem acento, espaços simples, sem pontuação).
  2. Do sócio CNPJ: `doc` = `***XXXXXX**` → `XXXXXX`; mesmo nome normalizado.
  3. Casar só quando **nome completo idêntico E 6 dígitos iguais**. Os 6 dígitos sozinhos têm 10⁶ combinações para
     ~200 milhões de CPFs (~200 pessoas por combinação), então nunca usar os dígitos sem o nome; o nome sozinho também
     não serve (homônimos). Juntos, a chance de colisão é muito baixa, mas não zero (dois "JOSE DA SILVA" com os mesmos
     6 dígitos do meio são possíveis; o cálculo exato de taxa de erro não foi encontrado — ver Gaps).
  4. Se o CPF do doador vier mascarado no mesmo padrão, a chave é a mesma. Se vier ausente, **não casar** (só nome
     não é aceitável sob a regra de ouro 1).
  5. Guardar a "força" do casamento e publicar só o nível exato.
- Para o candidato beneficiário, usar o `SQ_CANDIDATO` do TSE e, para 2026, o CPF do candidato (de novo público), e
  ligar ao deputado/senador do site pela lista de eleitos já coletada (`eleicao2026/etl/el_etl/eleitos.py`).
- Nunca publicar o CPF que vier do TSE, mesmo completo: mostrar só no formato da Receita (`***.123.456-**`), o que
  bate com a regra "CPF sempre mascarado" e com `validar.py`.

### Gaps
- Não consegui abrir o dicionário de dados do TSE para confirmar se `NR_CPF_CNPJ_DOADOR` em 2026 (e 2024/2022) vem com
  11 dígitos ou mascarado. Conferir baixando o ZIP `prestacao_de_contas_eleitorais_candidatos_2026` (cdn.tse.jus.br).
- Não achei medição publicada da taxa de falsos positivos de "nome + 6 dígitos". Dá para medir no próprio projeto:
  contar, na base de sócios, quantos pares (nome normalizado, 6 dígitos) aparecem com mais de uma data de entrada/
  faixa etária divergente.
- Não confirmei o texto final da Res. TSE 23.751/2026 (citada pelo TSE como base da divulgação de 2026) sobre CPF —
  [TSE, informações técnicas](https://www.tse.jus.br/eleicoes/informacoes-tecnicas-sobre-a-divulgacao-de-resultados).

## 2. Projetos e estudos que já fazem esse cruzamento

### Takeaway
A literatura acadêmica mostra que, antes de 2015, empresas que doavam a candidatos vencedores recebiam mais contratos
(efeito causal, desenho de descontinuidade). Entre ferramentas, o CruzaGrafos (Abraji + Brasil.IO) é a mais próxima do
que o projeto quer; a Rosie/Serenata trata só de reembolsos da cota, não de doações.

### Cited Findings
- Boas, Hidalgo & Richardson, "The Spoils of Victory: Campaign Donations and Government Contracts in Brazil",
  *Journal of Politics* 76(2), 2014, pp. 415-429: regressão descontínua (quase vencedores × quase perdedores, deputado
  federal 2006); empresas de obras públicas que doaram a candidatos do PT que venceram ganharam R$ 138.601 a
  R$ 346.267 a mais em contratos por doador, 14 a 39 vezes a doação média; efeito só no partido do governo —
  [MIT DSpace](https://dspace.mit.edu/handle/1721.1/99693); [versão de trabalho, Kellogg/Notre Dame](https://kellogg.nd.edu/sites/default/files/old_files/documents/379_0.pdf); [IHU Unisinos, "até 39 vezes"](https://ihu.unisinos.br/541351-empresas-recuperam-em-contratos-ate-39-vezes-o-valor-doado-a-politicos)
- Conflito de números: a versão de 2011 falava em R$ 147 mil, 8,5 vezes a doação; outra síntese cita "ao menos 8,5
  vezes" para o artigo publicado. Usar o número da versão publicada e citar a página — [Kellogg working paper](https://kellogg.nd.edu/sites/default/files/old_files/documents/379_0.pdf); [MIT DSpace](https://dspace.mit.edu/handle/1721.1/99693)
- Arvate, Barbosa & Fuzitani, "Campaign donation and government contracts in Brazilian states", FGV EESP Texto para
  Discussão 336 (2013): regressão descontínua com deputados estaduais de 2006 em 8 estados; retorno líquido alto, maior
  em partidos tradicionais e para doadores de deputados da coalizão do governador — [RePEc/IDEAS](https://ideas.repec.org/p/fgv/eesptd/336.html); [Repositório FGV](https://repositorio.fgv.br/items/2236719f-0f5a-4244-b81d-ce55bf2a4e9c)
- Estudo relacionado da FGV: "Procuring donors: how government contracts affect campaign contributions" (causalidade
  no sentido inverso: contratos atraem doações) — [Repositório FGV](https://repositorio.fgv.br/items/868a0de0-d202-4687-908c-74511f811e07)
- Contraponto: artigo na Revista de Sociologia e Política testou se doadores são recompensados com contratos federais
  e concluiu que a hipótese "ainda não foi confirmada pelos testes" — [Redalyc](https://www.redalyc.org/pdf/238/23850131003.pdf) (via trecho de busca)
- Perfil das empresas doadoras 2002-2014 — [Revista Ambiente/UFRN](https://periodicos.ufrn.br/ambiente/article/view/10912)
- Transparência Brasil (Claudio Weber Abramo): os maiores doadores dependem de contratos públicos; os 30 maiores
  doadores de 2010 deram R$ 521,6 milhões; doação via partido/comitê esconde o destino final — [Congresso em Foco](https://www.congressoemfoco.com.br/noticia/58071/site-analisa-dados-sobre-empresas-doadoras-de-campanhas); relatório "As rotas das doações eleitorais" (2025) — [Transparência Brasil, PDF](https://backend.transparencia.org.br/wp-content/uploads/2025/09/As-rotas-das-doacoes-eleitorais-1.pdf) (não abriu nesta sessão)
- Rosie (Operação Serenata de Amor): robô que confere reembolsos da cota parlamentar (achou empresas fechadas emitindo
  notas); não encontrei fonte de que cruze sócios com doações — [Wikipedia](https://en.wikipedia.org/wiki/Operation_Serenata_de_Amor); [Olhar Digital](https://olhardigital.com.br/2017/01/23/noticias/conheca-o-robo-dedicado-a-investigar-a-corrupcao-na-camara-dos-deputados/)
- CruzaGrafos (Abraji + Brasil.IO): mostra sócios e administradores de empresas, candidaturas e bens declarados;
  acesso restrito a associados da Abraji; repórter usou para achar empresário ligado a todas as empresas de uma
  licitação — [IJNet](https://ijnet.org/pt-br/story/cruzagrafos-ferramenta-para-mapear-neg%C3%B3cios-e-conex%C3%B5es-de-candidatos-%C3%A0s-elei%C3%A7%C3%B5es)
- Guia de pautas com dados do TSE (bens, doações) — [IJNet](https://ijnet.org/pt-br/story/como-encontrar-pautas-em-dados-de-pol%C3%ADticos-e-do-tse)

### Inferences
- Os estudos causais são de antes de 2015 (doação de empresa). Servem para contextualizar, não para afirmar que um caso
  específico do site é "retribuição". Um caso individual nunca prova causalidade.
- Nenhuma ferramenta pública aberta encontrada faz exatamente "fornecedor da cota/emenda → sócio → doação ao mesmo
  parlamentar". O Segredos Abertos seria pioneiro em fazê-lo de forma aberta e diária.

### Gaps
- Às Claras (Transparência Brasil, histórico): não achei página atual nem metodologia.
- Não achei metodologia publicada do cruzamento sócio-doador do CruzaGrafos.

## 3. Doação de empresa proibida desde 2015: migração para doação de pessoa física dos donos

### Takeaway
Doação de empresa está proibida desde 2015 (STF, ADI 4650, e Lei 13.165/2015); pessoa física pode doar até 10% do
rendimento bruto do ano anterior. Reportagens de 2018 e 2022 mostram empresários financiando campanhas pelo CPF,
inclusive a candidatos rivais; não achei levantamento nacional que meça a migração.

### Cited Findings
- Proibição desde 2015 e limite de 10% do rendimento bruto do ano anterior para pessoa física — [Politize](https://www.politize.com.br/financiamento-privado-de-campanhas/); [Migalhas](https://www.migalhas.com.br/quentes/227067/proibida-doacao-de-empresas-a-campanhas-eleitorais)
- 2018: empresários seguiram financiando candidatos pelo CPF; em MG, nove campanhas de deputado federal entre as que
  mais receberam de pessoas físicas, sobretudo empresários (dados do TRE-MG durante a campanha) — [Brasil de Fato](https://brasildefato.com.br/2018/09/20/proibicao-de-doacoes-empresariais-nao-blindam-politica-dos-interesses-privados/)
- 2022: "Com doação proibida por empresas, sócios repassam milhões para candidatos rivais" — [Jornal Opção](https://www.jornalopcao.com.br/campanha/com-doacao-proibida-por-empresas-socios-repassam-milhoes-para-candidatos-rivais-422570/) (texto completo não lido)
- 2022, maiores doadores pessoa física: Rubens Ometto (R$ 8,9 milhões até então); Marcos Ermírio de Moraes e Salim
  Mattar acima de R$ 3 milhões cada (levantamento Nexo até 12/09/2022) — [Gazeta do Povo](https://www.gazetadopovo.com.br/eleicoes/2022/maiores-doadores-campanha-eleicoes-2022/); [Suno](https://www.suno.com.br/noticias/doadores-campanha-eleicoes-2022/)
- TSE identificou R$ 300 milhões em doações suspeitas (ex.: doadores sem renda compatível) — [Exame](https://exame.com/brasil/tse-identifica-r-300-mi-de-doacoes-suspeitas-para-candidatos); doações de beneficiários do Bolsa Família acima de R$ 15 milhões — [Congresso em Foco](https://congressoemfoco.com.br/noticia/46117/doacoes-de-beneficiarios-do-bolsa-familia-para-eleicoes-superam-r-15-milhoes)

### Inferences
- Depois de 2015 o elo "empresa doou" virou "sócio doou". É exatamente o cruzamento sócio (QSA) × doador (TSE) que
  recupera o vínculo. Usar também o arquivo `receitas_candidatos_doador_originario`, porque dinheiro passa por partido
  e comitê antes de chegar ao candidato.
- Doações "laranja" (pessoa sem renda) não aparecem no cruzamento por sócio; ficam fora do escopo.

### Gaps
- Sem levantamento nacional que compare 2014 × 2018 × 2022 a fatia de doações vinda de sócios de empresas.

## 4. Base legal e ética: LGPD, regras do TSE, risco de difamação, como redigir

### Takeaway
Os dados de doador são publicados pela própria Justiça Eleitoral por obrigação legal, e a LGPD permite tratar dado de
acesso público respeitando finalidade, boa-fé e interesse público (art. 7º §§3º, 4º e 7º). O risco jurídico está em
**afirmar** ligação (homônimo) ou **insinuar** troca de favores. Redigir como coincidência documentada, com link para
cada fonte, nunca como acusação.

### Cited Findings
- LGPD art. 7º §3º: tratar dado de acesso público considerando finalidade, boa-fé e interesse público; §4º dispensa
  consentimento para dado tornado manifestamente público pelo titular; §7º permite uso posterior para nova finalidade
  legítima, preservados os direitos do titular — [Modelo Inicial, texto do art. 7º](https://modeloinicial.com.br/lei/LGPD/array-0x55e12f1eea90/art-7); [Migalhas](https://www.migalhas.com.br/depeso/293745/a-excecao-dos-dados-pessoais-tornados-manifestamente-publicos-pelo-titular-na-lgpd)
- ANPD: a LGPD vale também para dado público e manifestamente público, com princípios e direitos dos titulares — [ANPD, perguntas frequentes](https://www.gov.br/anpd/pt-br/perguntas-frequentes.pdf); [Serpro, dados públicos na LGPD](https://www.serpro.gov.br/lgpd/menu/protecao-de-dados/dados-publicos-lgpd)
- A lei eleitoral exige nome e CPF de doadores; o TSE já discutiu tirar bases do ar citando dados sensíveis (filiação
  partidária); o próprio TSE disse que a transparência de dado de interesse público é regida pela LAI — [A Gazeta](https://www.agazeta.com.br/brasil/tse-decide-sobre-sigilo-de-doacao-eleitoral-entidades-temem-retrocesso-0222); [Mais Goiás, 2026](https://www.maisgoias.com.br/politica/tse-vai-decidir-sobre-sigilo-de-doacao-eleitoral-e-entidades-temem-retrocesso/)
- Recibos eleitorais trazem nome, dados bancários e CPF do doador (estudo InternetLab sobre o DivulgaCandContas) —
  [InternetLab, PDF](https://internetlab.org.br/wp-content/uploads/2022/08/divulgacandcontas-vf.pdf)
- Voto do ministro Fachin (2022) pela manutenção de dados de candidatos públicos frente à LGPD — [TSE](https://www.tse.jus.br/comunicacao/arquivos/voto-ministro-edson-fachin-pa-0600231-37-aplicacao-da-lgpd-no-registro-de-candidatura); [Poder360, PDF](https://static.poder360.com.br/2022/08/Fachin-vota-por-manter-públicos-dados-de-candidatos.pdf)
- Ética de fornecedor: sócios em comum não provam relação comercial — [Apify, CNPJ sócios e relacionamentos](https://apify.com/codsec/cnpj-socios-e-relacionamentos)

### Inferences
- Nota importante (sem fonte oficial encontrada sobre o tema específico): em 2026 o TSE voltou a discutir sigilo de
  doações (notícias de julho/2026). **Antes de lançar, conferir se a regra mudou** e se os arquivos de 2026 continuam
  com identificação do doador.
- Regras práticas para o site:
  - Publicar só o que a fonte oficial já publica (nome do doador, valor, data, candidato; CPF só mascarado `***.XXX.XXX-**`).
  - Doador que **não** é sócio de empresa ligada ao parlamentar não ganha página nem destaque.
  - Texto neutro e factual, em 3 fatos com link cada um: "A empresa X recebeu R$ Y da cota do deputado Z
    ([Câmara]). Um sócio da empresa segundo a Receita ([CNPJ]) aparece como doador de R$ W à campanha de Z em 2022
    ([TSE]). Os dados mostram coincidência de nomes e de parte do CPF; não indicam irregularidade."
  - Evitar verbos como "retribuiu", "pagou de volta", "esquema", "favoreceu".
  - Mostrar a ordem no tempo (doação antes ou depois do pagamento), sem tirar conclusão.
  - Canal de correção e retirada para homônimo, com prazo.
  - Base legal sugerida: interesse público + dado de acesso público (art. 7º §3º) e finalidade jornalística/de
    controle social; registrar isso em um documento interno (o projeto não é poder público).

### Gaps
- Não achei guia da ANPD específico sobre doadores de campanha nem sobre a exceção jornalística (art. 4º, II, "a").
- Não achei jurisprudência específica de difamação por cruzamento doador × fornecedor; consultar advogado (Abraji tem
  apoio jurídico a associados).

## 5. Bens declarados pelos candidatos e empresas do próprio político ou de parentes

### Takeaway
A declaração de bens do TSE traz cotas de empresas, mas em 2022 o TSE chegou a esconder o nome das empresas
("quotas ou quinhão de capital") e voltou atrás. O caminho mais confiável é o inverso: procurar o nome + 6 dígitos do
CPF do político (público de novo em 2026) entre os sócios da base CNPJ. Parentes não são identificáveis de forma
confiável só com dados oficiais.

### Cited Findings
- TSE publica planilhas de bens por eleição; candidatos podem ter bens não declarados por estarem em nome de pessoa
  jurídica — [IJNet](https://ijnet.org/pt-br/story/como-encontrar-pautas-em-dados-de-pol%C3%ADticos-e-do-tse)
- 2022: o TSE trocou nome de empresa por rótulos genéricos e depois decidiu voltar a divulgar o detalhe; sem prazo
  para manter públicos os dados do candidato — [InfoMoney](https://www.infomoney.com.br/?p=1918390); [O Imparcial](https://oimparcial.com.br/politica/2022/08/tse-decide-divulgar-informacoes-detalhadas-sobre-bens-de-candidatos/); [Gazeta SP](https://www.gazetasp.com.br/brasil/tse-restringe-transparencia-sobre-bens-de-candidatos/); [JC Concursos](https://jcconcursos.com.br/noticia/brasil/detalhamento-na-descricao-de-bens-dos-candidatos-volta-ser-exigido-pelo-tse-99633)
- 2026: 6.933 de 20.608 candidatos registrados declararam patrimônio zero; valor declarado não é valor de mercado —
  [Correio da Manhã](https://www.correiodamanha.com.br/politica/2026/08/312591-um-terco-dos-candidatos-as-eleicoes-de-2026-declara-nao-ter-bens.html)
- 2024: UOL achou candidato a prefeito de SP que omitiu empresa e declarou outras abaixo do valor da Receita (via
  trecho de busca, matéria original não aberta) — [InfoMoney / resultados de busca](https://www.infomoney.com.br/?p=1918390)
- Portal TSE de consulta ao patrimônio — [TSE, 2022](https://www.tse.jus.br/comunicacao/noticias/2022/Agosto/eleicoes-2022-consulte-o-patrimonio-dos-candidatos-no-portal-do-tse)

### Inferences
- Com o CPF do candidato de novo público em 2026, cruzar `cpf[3:9]` + nome com o QSA dá "empresas em que o político é
  sócio", e daí "a empresa do próprio parlamentar recebeu emenda/pagamento" — sinal mais forte que doação.
- Comparar com a declaração de bens: empresa no QSA que não aparece nos bens = divergência a mostrar como fato, sem
  adjetivo.
- Parentes: a base CNPJ não traz parentesco; sobrenome igual não serve. Não publicar parentesco sem fonte oficial
  (ex.: nomeação, decisão judicial, reportagem com documento).

### Gaps
- Não confirmei os nomes das colunas do arquivo de bens (`bem_candidato_{ano}`); conferir no dicionário do TSE.
- Para 2020/2024, o CPF do candidato está mascarado nos arquivos (segundo fonte secundária), o que limita o cruzamento
  histórico.
