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
| Projetos em andamento (pauta dos próximos 14 dias, recém-apresentados, medidas provisórias e prazos) | [API da Câmara](https://dadosabertos.camara.leg.br/swagger/api.html) (`/eventos`, `/eventos/{id}/pauta`, `/proposicoes`) e [API do Senado](https://legis.senado.leg.br/dadosabertos/docs/) (`/plenario/agenda`, `/comissao/agenda`, `/processo`); no Minas Nossa, o arquivo de proposições da [ALMG](https://dadosabertos.almg.gov.br/) |
| Empresas e sócios | Base CNPJ da Receita Federal, via [Minha Receita](https://minhareceita.org) |
| Emendas parlamentares (quem fez, área, quem recebeu) | [Portal da Transparência](https://portaldatransparencia.gov.br/download-de-dados/emendas-parlamentares), arquivo completo |
| Pagamentos do governo federal a empresas e entidades (página de incentivos) | [Portal da Transparência](https://portaldatransparencia.gov.br/download-de-dados/despesas), arquivos diários de despesas |
| Renúncia fiscal por empresa (página de incentivos) | [Portal da Transparência](https://portaldatransparencia.gov.br/download-de-dados/renuncias), com dados da Receita Federal. Primeiro pela [API de dados](https://portaldatransparencia.gov.br/api-de-dados) (consulta `renuncias-valor`, chave no secret `PORTAL_TRANSPARENCIA_CHAVE`); os arquivos de download ficam como reserva |
| Arrecadação e gastos: receitas, despesas por grupo e por função, gasto com pessoal de cada Poder e limites da LRF | [API do Siconfi, Tesouro Nacional](https://apidatalake.tesouro.gov.br/docs/siconfi/) (RREO anexos 1 e 2, RGF anexo 1) |
| Arrecadação por imposto, estado e setor da economia | [Receita Federal, dados de arrecadação](https://www.gov.br/receitafederal/pt-br/acesso-a-informacao/dados-abertos/receitadata/arrecadacao) (arquivos CSV; a Receita não tem API para isso) |
| Gasto do Executivo por órgão, programa, ação e tipo de despesa | [Portal da Transparência, orçamento da despesa](https://portaldatransparencia.gov.br/download-de-dados/orcamento-despesa) (arquivo anual; a API não cruza órgão com tipo de despesa) |
| Servidores do Executivo: concursados, cargos de confiança e comissionados | [Portal da Transparência, servidores SIAPE](https://portaldatransparencia.gov.br/download-de-dados/servidores) (arquivo mensal; a API só consulta servidor por servidor) |
| Funcionários da Câmara e do Senado por vínculo | [Arquivo de funcionários da Câmara](https://dadosabertos.camara.leg.br/arquivos/funcionarios/json/funcionarios.json) e [API de servidores do Senado](https://adm.senado.gov.br/adm-dadosabertos/api/v1/servidores/servidores) |
| Inflação (IPCA) para comparar anos | [API do SIDRA, IBGE](https://sidra.ibge.gov.br/tabela/1737) |

## Corrupção (/corrupcao)

Os maiores escândalos (Mensalão, Sanguessugas, Petrolão, Lava Jato, Banco Master, Careca do INSS e políticos cassados),
com linha do tempo, pessoas e a situação de cada uma na Justiça, delações e acordos, empresas, o que dizem a esquerda,
a direita e a Justiça, e um placar por partido. Não existe API oficial que junte processos, delações e cassações, então
o conteúdo é escrito à mão em `site/src/corrupcao/dados.ts`, cada item com o link da fonte original, e conferido na data
de `ATUALIZADO_EM`. Esquerda, centro ou direita vêm da pesquisa de Bolognesi, Ribeiro e Codato (revista Dados, 2023).
Os testes em `site/tests/corrupcao.test.ts` exigem fonte https em tudo e conferem as contas do placar.

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
