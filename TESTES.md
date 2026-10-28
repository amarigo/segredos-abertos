# Como testamos o Segredos Abertos

O site publica números sobre pessoas públicas. Um total errado, um voto contado duas vezes ou um CPF à mostra
causam dano real. Por isso a estratégia junta três ideias:

1. **Testes baseados em riscos**: começamos pelo que pode dar mais errado e pelo estrago que faria, e cada risco
   tem testes e uma trava em produção.
2. **Pirâmide de testes**: muitos testes pequenos e rápidos na base, menos testes grandes no topo.
3. **Engenharia de caos**: derrubamos, atrasamos e corrompemos de propósito as fontes oficiais (simuladas) e
   conferimos que o site continua certo, ou avisa, ou não publica. Nunca publica dado errado calado.

## 1. Riscos, do mais grave ao menos grave

| # | Risco | Chance | Estrago | Testes | Trava em produção |
|---|---|---|---|---|---|
| R1 | Total de um parlamentar ou empresa diferente da soma das notas | média | alto | `test_ponta_a_ponta`, `test_propriedades::test_montar_somas_batem…`, `test_validar` | `validar.py` confere todas as somas e bloqueia a publicação |
| R2 | API do Senado instável: meses de votação ou ano da cota faltando | alta | alto | `test_caos::test_senado_*`, `test_ceaps_*` | cópia guardada de cada mês e ano; mês sem cópia vira aviso no site; queda > 20% bloqueia |
| R3 | Votação ou voto contado duas vezes (linhas repetidas, paginação) | média | alto | `test_caos::test_*repet*`, `test_propriedades::test_votacoes_camara_sem_voto_duplicado` | coletor remove repetidos; `validar.py` bloqueia votação ou voto repetido e placar que não bate |
| R4 | CPF de pessoa física aparecendo no site (LGPD) | média | alto | `test_ponta_a_ponta::test_cpf_*`, `test_propriedades::test_link_de_detalhe_nunca_leva_cpf` | `validar.py` procura CPF sem máscara em todos os arquivos e dentro dos links |
| R5 | Link perigoso (`javascript:`) vindo de uma fonte adulterada | baixa | alto | `test_propriedades::test_url_segura_*`, `site/e2e` (segurança) | coletor e site só aceitam http(s); CSP no HTML; `validar.py` bloqueia |
| R6 | Cadeia de holdings errada ou infinita (empresa sócia de si mesma) | média | médio | `test_ponta_a_ponta::test_holdings_*`, `test_propriedades::test_donos_finais_termina_em_qualquer_grafo` | limite de 5 níveis e marca de ciclo; `validar.py` confere a cadeia |
| R7 | Link da nota fiscal quebrado (PDF 404 na Câmara) | alta | médio | `test_ponta_a_ponta::test_notas_sem_pdf_*`, `test_caos::test_site_da_camara_fora_do_ar_*` | conferência diária dos PDFs; sem PDF, link para a página oficial da despesa |
| R8 | Arquivo oficial trocado por página de erro, cortado ou vazio | média | alto | `test_caos` (modos html, vazio, truncado, lixo) | o coletor confere se é .zip/.csv/JSON de verdade antes de usar e guarda a última cópia boa |
| R9 | Emendas: arquivo do Portal fora do ar ou com colunas novas | média | médio | `test_caos::test_portal_da_transparencia_*`, `test_emendas` | usa a cópia antiga; sem cópia, aviso; somas por tipo e área conferidas |
| R10 | Site em branco por causa de um arquivo com defeito | média | médio | `site/e2e` (caos no navegador) | aviso no lugar da página; o menu continua funcionando |
| R11 | Total diferente da página oficial da Câmara | média | médio | `test_etl::test_completa_com_valor_oficial`, `test_passagens_*` | `validar.py` alerta quando mais de 10% dos deputados não batem |
| R12 | Dependência com falha de segurança conhecida | média | médio | job `seguranca` (pip-audit, npm audit) | versões fixas e atualizadas |

## 2. A pirâmide

```
                 ▲  Navegador (Playwright): 15 cenários × computador e celular
                ▲▲▲   jornada, segurança, caos no navegador         site/e2e
              ▲▲▲▲▲▲▲  Integração: coleta inteira contra o governo simulado
             ▲▲▲▲▲▲▲▲▲   + conferência dos arquivos (validar.py)    etl/tests/test_ponta_a_ponta.py, test_validar.py
           ▲▲▲▲▲▲▲▲▲▲▲▲▲  Caos no coletor: 27 experimentos + macaco do caos
          ▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲   etl/tests/test_caos.py
        ▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲  Unitários e de propriedades (Hypothesis gera milhares de entradas)
       ▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲   etl/tests/test_etl.py, test_emendas.py, test_propriedades.py, site/tests
```

- **Unitários**: cada leitor de arquivo oficial, cada conta e cada regra (grupos de despesa, temas, votos).
- **Propriedades**: regras que valem para qualquer entrada, testadas com entradas geradas: `to_float` lê qualquer
  valor em reais; o CNPJ da matriz sempre tem dígitos certos; a máscara nunca mostra o CPF inteiro; qualquer grafo
  de sócios termina; para qualquer lista de despesas, todas as somas do site batem.
- **Integração**: `tests/fakegov.py` imita os sites da Câmara, do Senado, da Receita e do Portal da Transparência
  com dados fictícios. A coleta roda inteira, como no GitHub Actions, e o resultado passa pela conferência.
- **Navegador**: o site de verdade (build de produção) com os dados fictícios, no Chrome de computador e de celular.

## 3. Engenharia de caos

Cada experimento tem uma hipótese ("o estado normal se mantém"), uma falha injetada e um resultado esperado.

**Estado normal**: os arquivos passam na conferência (`validar.py`) sem erros.

| Falha injetada | Onde | Resultado esperado |
|---|---|---|
| Erro 500, 429, tempo esgotado, conexão recusada | todas as fontes | novas tentativas; depois, última cópia boa ou aviso |
| Página de erro em HTML no lugar do dado | todas as fontes | não usa; não apaga a cópia boa |
| Resposta cortada no meio, vazia, ou bytes aleatórios | todas as fontes | nova tentativa; depois, cópia boa ou aviso |
| Meses da API do Senado fora do ar | votações do Senado | mês usa a cópia; sem cópia, aviso com os meses faltando |
| Linhas e votações repetidas | votações da Câmara e do Senado | nada repetido no site |
| Lista de deputados fora do ar ou vazia | Câmara | a coleta para; o site no ar continua o anterior |
| Cota do Senado sem cópia | Senado | aviso; a queda bloqueia a publicação |
| Falhas aleatórias em tudo, duas coletas seguidas | todas (macaco do caos) | ou para, ou publica dado consistente |
| Arquivo de dados não carrega, cortado, formato errado, lento | site no navegador | aviso no lugar da página, nunca tela em branco |

O macaco do caos roda 12 sementes em cada push e 60 na coleta diária. Para mais: `CAOS_RODADAS=300 python -m pytest -q tests/test_caos.py -k macaco`.

## 4. Travas em produção

A coleta diária só publica se `python -m sa_etl.validar` não achar erro. Ela confere:

- todas as somas (anos, grupos, categorias, meses, partidos, empresas, notas, emendas);
- votações: sem repetição, um voto por parlamentar, placar igual aos votos;
- holdings: cadeia sem repetição (a não ser marcada como ciclo) e dentro do limite;
- privacidade e segurança: nenhum CPF sem máscara (nem dentro de links), só links http(s), nomes de arquivo seguros;
- tamanho: pelo menos 400 deputados, 70 senadores e 50 votações;
- queda: nenhum total de ano nem contagem caiu mais de 20% em relação à versão no ar. Se a queda for real, rode o
  workflow à mão com "Publicar mesmo com queda grande".

Se algo falhar, o site no ar continua com a versão anterior, e o resumo do GitHub Actions mostra o motivo.
Problemas que não bloqueiam (uma fonte fora do ar, cópia antiga em uso) aparecem para quem lê o site, no topo da página inicial.

### Verificação independente (segunda fonte oficial)

A conferência acima vê se os arquivos batem entre si. Depois dela, `python -m sa_etl.verificar` sorteia números do site e
pergunta de novo a uma fonte oficial diferente. O resultado aparece no site (selo no fim de cada página e a página
`/verificacao`) e no resumo do GitHub Actions. Cada diferença é classificada por `oficial.classificar`: com motivo
conhecido (`oficial.MOTIVOS`), o site já usa o número oficial e explica; sem motivo, fica "em revisão". Mais de 2% de
diferenças sem motivo numa seção (com 20 ou mais conferidos) devolve código 3 e barra a publicação (para publicar
assim mesmo: `--ignorar-barreira`, ou a opção `ignorar_barreira` ao rodar o workflow à mão). Empresas com diferença
saem do cache de CNPJ; o cache vence em 30 dias.

| Seção | Número do site (fonte da coleta) | Conferido com |
|---|---|---|
| Cota | total do mês de cada deputado (arquivo anual) | API da Câmara, `/deputados/{id}/despesas` |
| Cota | quanto cada empresa recebeu de cada deputado no mês | API da Câmara, `/deputados/{id}/despesas` |
| Cota | total do mês de cada deputado (todos) | página oficial do deputado (só meses que o site não completou com ela) |
| Cota | total do ano de cada senador (soma nota por nota da CEAPS) | API do Senado, `recursos-utilizados` |
| Votações | voto de cada deputado (CSV) e placar oficial | API da Câmara, `/votacoes/{id}/votos` |
| Votações | voto de cada senador e placar | API do Senado de novo, e a ata da sessão (Secretaria de Atas) |
| Empresas | razão social e sócios (Minha Receita) | outra cópia da base da Receita (BrasilAPI) |
| Emendas | empenhado e pago por autor (arquivo do Portal) | API de dados do Portal da Transparência |
| Arrecadação e gastos | juros da dívida (orçamento do Portal) | RREO do Tesouro (SICONFI) |

Regras: fonte fora do ar ou API respondendo vazio vira "não conferido", nunca "conferido"; a cota só é conferida em
meses fechados há mais de 60 dias; a página de incentivos aparece como "sem segunda fonte" até haver uma.
Testes: `etl/tests/test_verificar.py` (fontes simuladas: tudo batendo, divergência, API vazia, fonte fora do ar, sem
chave, histórico), `etl/tests/test_oficial.py` (motivos, barreira, cache de CNPJ, total oficial do Senado, placar da
ata) e `site/e2e/site.spec.ts` (selos e avisos no fim da página; número em revisão com o oficial; sem arquivo, nenhum
selo).

## 5. Segurança

- Links: coletor (`url_segura`) e site (`linkSeguro`) só aceitam http(s).
- Nomes de arquivo: ids só com letras, números, `-` e `_` (`id_seguro`).
- CSP no HTML publicado: só scripts do próprio site, dados só do próprio site, sem plugins.
- O texto dos dados nunca vira HTML (o React escapa tudo; testado no navegador).
- GitHub Actions: permissões só de leitura, e a de publicar só no job de publicação.
- Dependências fixas e conferidas a cada push (`pip-audit`, `npm audit`).

Riscos aceitos: o `react-router-dom` 6 tem dois alertas moderados que só valem para redirecionamento com
endereços externos e para renderização no servidor; o site não usa nenhum dos dois. Corrigir exige migrar para a
versão 7. A CSP permite estilos embutidos (`'unsafe-inline'` em `style-src`), que os gráficos usam.

## 6. Como rodar

```bash
# coletor: unitários, propriedades, integração e caos
cd etl
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q tests

# site: unitários
cd ../site
npm ci
npm test

# site no navegador
python ../etl/tests/gerar_dados_teste.py public/data
npm run build
npx playwright install chromium
npm run test:e2e

# conferir uma coleta real antes de publicar
cd ../etl
python -m sa_etl.validar ../site/public/data --anterior https://amarigo.github.io/segredos-abertos/data/meta.json
```

## 7. Minas Nossa (pasta `mg/`)

O Minas Nossa é o recorte de Minas Gerais, publicado em `/mg/`. Usa os mesmos testes do nacional e mais estes:

| Risco | Como testamos |
|---|---|
| Recorte deixa político de outro estado, ou somas de empresas e votações erradas | `mg/etl/tests/test_recorte.py`: o recorte passa na conferência nacional (`sa_etl.validar`) e na de MG |
| Placar errado na votação (bancada de MG no lugar da Casa) | O placar da Casa vai em `placar_casa`; a conferência barra se for menor que o de MG |
| CPF dos candidatos (os arquivos do TSE trazem) | Só lemos colunas de uma lista fechada; a conferência procura números com cara de CPF na página da cidade; teste no navegador |
| TSE fora do ar, .zip cortado, página de erro, arquivo sem cabeçalho ou sem a cidade | FakeTSE (`faketse.py`) com esses defeitos; a coleta usa a última cópia ou deixa o ano de fora com aviso. Rodadas de caos com falhas ao acaso |
| Cadeiras da Câmara que não somam as vagas, dois prefeitos na mesma eleição, percentuais acima de 100 | Conferência das cidades (`mg_etl.validar`) e testes de mutação: estragamos um arquivo bom de 26 jeitos e cada defeito tem de ser pego |
| Partido antigo sem o nome de hoje (PMDB, PFL, PR...) | Tabela de sucessores (`partidos_hist.py`) com teste de cada linhagem |
| Somas erradas no estado: verba por tipo e por mês que não fecha o total, emenda paga sem indicação, dois governadores eleitos | `mg/etl/tests/test_estado.py` com FakeEstado (`fakeestado.py`), que simula ALMG, Dados MG, SICONFI e Portal da Transparência; a conferência do estado (`conferir_estado`) e 17 defeitos de mutação a mais |
| CPF de fornecedor pessoa física ou de servidor no nome ou no motivo da viagem | Nunca lemos as colunas de CPF; `sem_cpf` limpa o texto; a conferência procura CPF em todos os arquivos e o teste no navegador nas páginas do estado |
| ALMG, Dados MG ou SICONFI fora do ar, lentos (429), com página de erro, vazios ou cortados | Caos em cada fonte: a parte afetada some com aviso e o resto é publicado; a verba para depois de 5 falhas seguidas e continua na próxima execução |
| Ano de verba incompleto parecer que o deputado gastou pouco | `verba_completa` por ano e `meses_faltando` por deputado; o site mostra o aviso (teste no navegador) |
| Falha no Minas Nossa derrubar o site nacional | No GitHub Actions, a coleta de MG roda à parte (`continue-on-error`); se falhar, publica de novo o `dados-mg.zip` anterior |

```bash
# coletor de MG
python -m pytest -q mg/etl/tests

# site de MG no navegador
python etl/tests/gerar_dados_teste.py site/public/data
python mg/etl/tests/gerar_dados_teste_mg.py site/public/data site/public-mg/data
cd site && npm run build:mg && npm run test:e2e:mg
```
