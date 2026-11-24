# Documentos do domínio

Como as skills de engenharia usam o glossário e o registro de decisões deste repositório ao explorar o código.

Este repositório tem um contexto só: um `GLOSSARY.md` na raiz e as decisões em `docs/adr/`.

## Antes de explorar, leia

- **`GLOSSARY.md`** na raiz.
- **`docs/adr/`**: as decisões (ADRs) que tocam a parte em que você vai mexer.

Se algum desses arquivos não existir, **siga em frente sem comentar**. Não aponte a falta nem sugira criá-los antes da
hora. A skill `/domain-modeling` (chamada pelo `/grill-with-docs` e pelo `/improve-codebase-architecture`) cria esses
arquivos quando um termo ou uma decisão é de fato resolvido.

## Estrutura

```
/
├── GLOSSARY.md
├── docs/adr/
│   ├── 0001-nome-da-decisao.md
│   └── 0002-outra-decisao.md
└── ...
```

## Use as palavras do glossário

Quando o que você escrever citar um conceito do projeto (título de issue, proposta de mudança, hipótese, nome de teste),
use o termo como está no `GLOSSARY.md`. Não troque por sinônimos que o glossário evita.

Se o conceito ainda não estiver no glossário, isso é um sinal: ou você está inventando um termo que o projeto não usa
(repense), ou falta mesmo esse termo (anote para o `/domain-modeling`).

## Avise quando contrariar uma decisão

Se o que você propõe contraria um ADR existente, diga isso com clareza em vez de passar por cima:

> _Contraria o ADR-0007 (nome da decisão), mas vale reabrir porque…_
