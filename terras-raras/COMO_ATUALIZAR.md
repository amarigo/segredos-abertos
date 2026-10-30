# Como atualizar o Tracker de Terras Raras de Minas Gerais

O tracker está em dois lugares, gerados das mesmas planilhas desta pasta (`terras-raras/` no repositório
amarigo/segredos-abertos, que é a cópia principal):

- **Site público:** https://amarigo.github.io/segredos-abertos/terras-raras/ (montado pelo GitHub Action "Dados e site"
  a cada push no `main` e todo dia; comando: `python terras-raras/gerar_pagina.py --site site/dist/terras-raras/index.html`).
- **Link privado do Claude:** https://claude.ai/artifact/4kJniSvA8P5jnAx12ShfVP (gerado com `python3 gerar_pagina.py`;
  republicar sempre neste mesmo link).

## Como a página está organizada (estilo trackdatacenters.com)
Mapa primeiro, depois navegação: **região → município → projeto → empresa**. Cada projeto e empresa tem página própria com ficha, licenças, donos da terra, impactos e fontes. Menu: Mapa, Painel econômico, Empresas, Licenças, Notícias e processos, Aprender, O que pedir, Sobre, Enviar informação.
- A ligação projeto ↔ empresa vem da coluna `empresas_ids` de `projetos.csv` (ids de `empresas.csv` separados por `;`).

## Informações enviadas pelo público
- **No site público**, "Enviar informação" abre uma issue no GitHub já preenchida (título começa com `[Terras raras]`, etiqueta `terras-raras`).
- **No link do Claude**, os envios ficam na base da própria página (coleção `envios`, um documento por pessoa). Só o dono lê; envia quem tem acesso de **Colaborador** ou mais.
- Na atualização semanal, o Claude lê os dois, confere cada dica com fonte e só então coloca nas planilhas. Dica sem fonte não entra.

## Jeito mais fácil
Escreva no projeto: **"atualize o tracker de terras raras"**. O Claude pesquisa notícias e documentos novos, edita as planilhas desta pasta, gera a página de novo e republica no mesmo link.

## Jeito manual
1. Abra a planilha da seção em `dados/` (Excel ou Google Sheets).
2. Adicione ou corrija uma linha. **Toda linha precisa de link da fonte e data.**
3. Salve como **CSV UTF-8** (mesmo nome de arquivo, sem mudar o cabeçalho).
4. Na pasta do tracker, rode `python3 gerar_pagina.py`. Isso cria `tracker.html` e avisa se algum município não foi encontrado no mapa.
5. Faça commit no `main` (o site público se atualiza sozinho) e peça ao Claude para republicar o link privado.

## O que cada planilha guarda
| Arquivo | Seção da página | Uma linha é |
|---|---|---|
| `projetos.csv` / `areas_potencial.csv` | Mapa | coluna `municipios_mapa`: nomes exatos do IBGE separados por `;` |
| `licencas.csv` | Licenças pendentes | uma licença ou aprovação aguardando decisão |
| `areas_potencial.csv` | Áreas com potencial | área apontada em estudo (Codemge, SGB) sem projeto licenciado |
| `empresas.csv` | Empresas e donos | uma empresa, investidor, comprador, vendedor ou financiador |
| `projetos.csv` | Projetos | um projeto (mina, refinaria, passivo) |
| `donos_terra.csv` | Donos da terra | quem tem o direito minerário e quem é dono da superfície em uma área |
| `numeros.csv` | Painel econômico | um indicador; preencha `valor_grafico` (R$ milhões, ou % para TIR) e `categoria` para entrar nos gráficos |
| `leis.csv` | Leis | uma lei, PL, norma, decisão municipal |
| `impactos.csv` | Impactos ambientais | um tipo de impacto com evidência |
| `processos_noticias.csv` | Processos e notícias | um acontecimento datado (ação, licença, negócio, notícia) |
| `propostas.csv` | O que pedir aos legisladores | uma proposta com exemplo de outro país |

## Regras simples
- Datas no formato `AAAA-MM-DD` (ou `AAAA-MM` se não souber o dia).
- Campo `confianca`: `confirmado` (fonte oficial ou várias fontes), `fonte única`, ou `a verificar`.
- Campo `verificado_em`: data em que você conferiu a linha. A página mostra a data mais recente como "atualizado em".
- Não apague linhas antigas de processos e notícias: mude o `status`.

## Checklist de cada atualização (semanal ou quinzenal)
- [ ] Ler os envios novos: issues `[Terras raras]` no GitHub e a coleção `envios` do link do Claude
- [ ] Feam/Semad e pauta do Copam (CMI): andamento das LIs do Caldeira (SEI 2090.01.0003107/2026-75) e Colossus (SEI 2090.01.0005881/2026-61)
- [ ] Justiça Federal (Subseção de Poços de Caldas): decisão da ação civil pública
- [ ] TCU: abertura da auditoria pedida pelo MPTCU
- [ ] CIMCE / governo federal: decisão sobre a compra da Meteoric pela Lynas (assembleia prevista jan/2027)
- [ ] Câmara dos Deputados: tramitação do PL 500/2026; regulamentação da Lei 15.506/2026
- [ ] ALMG e Câmaras de Poços, Caldas e Andradas: novos projetos de lei, moções, audiências
- [ ] ASX: anúncios de MEI, VMM, PNN, AXL, LYC (financiamento, compradores, decisão final de investimento)
- [ ] SEC/NYSE: Rare Earths Americas (REA)
- [ ] Feam: EIA/RIMA da St George (Araxá) e eventual pedido da Resouro (Tiros)
- [ ] ASX: SGQ (St George), OCN (Oceana), EQN (Equinox), ENV (Enova)
- [ ] ANM (Cadastro Mineiro/SIGMINE): novos requerimentos de terras raras em todo MG, com atenção a Alto Paranaíba, Jequitinhonha e Sul de Minas
- [ ] SGB: resultados do mapeamento do Alto Paranaíba
- [ ] Imprensa regional (Poços Já, Folha Regional, SulMinasTV, Jornal Mantiqueira) e nacional

## Como descobrir quem é dono de quê
- **Direito minerário:** ANM, Cadastro Mineiro e SIGMINE (busca por município ou CNPJ).
- **Sócios de empresa brasileira:** consulta de CNPJ (quadro de sócios, QSA) e JUCEMG.
- **Dono da terra:** matrícula do imóvel no Cartório de Registro de Imóveis (Poços de Caldas, Caldas, Andradas); CAR/SICAR mostra o imóvel rural.
- **Acionistas de empresa listada:** relatórios anuais e avisos de "substantial holder" na ASX; formulários na SEC.
