---
name: painel-analises
description: Use ao criar ou mudar análises, gráficos ou tabelas para baixar do painel /analises/ do Segredos Abertos (analises/tabelas.py e analises/painel.html).
---

# Painel de análises do Segredos Abertos

O painel em `/analises/` mostra todos os dados do projeto em gráficos e oferece as mesmas tabelas em CSV.
Ele tem duas partes, e as duas sempre mudam juntas:

1. `analises/tabelas.py`: a lista `TABELAS`. Cada `Tabela` tem nome, seção (`grupo`), descrição, link da
   fonte oficial, colunas com tipo (`texto`, `inteiro`, `decimal`, `data`, `logico`, `link`) e uma função
   que gera as linhas a partir dos arquivos do site.
2. `analises/painel.html`: uma página só, com uma função por aba (`abaPoliticos`, `abaEmendas`...). Cada aba
   lê as tabelas com `tabela("nome")` e desenha com os ajudantes `barras`, `linhas`, `rosca`, `desenhar`
   (ECharts), `kpis` e `grade` (tabela com links).

## Regras do projeto que valem aqui

- Dados reais e oficiais. A coleta é feita em `etl/` pela API oficial primeiro (veja CLAUDE.md). O painel só
  reorganiza os arquivos que o site já publica; não busque dados novos em `tabelas.py`.
- Todo dado com link para o original: quando o JSON tiver a URL da fonte (nota fiscal, votação, pagamento,
  página do Portal da Transparência), ponha numa coluna do tipo `link` e mostre na aba com `tipo: "link"`.
- Nunca mostre CPF inteiro: os documentos já vêm mascarados do coletor; não desfaça isso.
- Texto para o público em português simples, sem jargão.

## Como adicionar uma análise

1. Ache o arquivo de origem em `site/public/data` (ou `site/public-mg/data`) e o tipo dele em `site/src/data.ts`
   ou na página correspondente em `site/src/pages/`.
2. Em `tabelas.py`, escreva `g_minha_tabela(d)` que devolve dicionários (use `d.n("arquivo.json")`,
   `d.m(...)` para Minas e `d.varios(base, "pasta")`), e acrescente a `Tabela(...)` em `TABELAS`.
3. Em `painel.html`, use a tabela numa aba existente ou crie uma aba nova em `ABAS`. Sempre termine o cartão
   com `fontes("minha_tabela")` e trate tabela vazia com `vazio()`.
4. Rode `python -m pytest -q analises/tests` (um teste confere que toda tabela pedida pelo painel existe).
5. Veja a página: `python analises/publicar.py ... --saida /tmp/analises` e abra com `python -m http.server`.
   Confira em tela de celular (390 px) e no modo escuro.

## Gráficos

- Biblioteca: Apache ECharts, versão fixa no `<script>` do jsDelivr (`echarts@5.5.1`). Não troque por
  `@latest`.
- Cores vêm das variáveis CSS (`cor("s1")`, `cor("esq")`, `cor("dir")`, `cor("sim")`, `cor("nao")`) para
  funcionar no claro e no escuro. Esquerda em vermelho (`esq`), direita em azul (`dir`), como no site.
- Barras horizontais para rankings (nomes longos cabem), linha para séries no tempo, rosca só para poucas
  partes de um todo.

## Painel publicado no Claude

O mesmo `painel.html` pode ser publicado como Artifact no Claude junto com a pasta `tabelas/` (o painel lê
`tabelas/` pelo caminho relativo). Os links de download apontam sempre para o GitHub Pages, que é a cópia
atualizada todo dia.

## Origem

Esta skill foi escrita para este projeto. Ela substitui a ideia de usar a skill de Power BI de
github.com/lukasreese/powerbi-claude-skills, que não foi copiada porque o repositório não tem licença.
