# Onde ficam as tarefas: GitHub Issues

As tarefas e especificações deste repositório ficam nas issues do GitHub. Use o `gh` para tudo.

Nas sessões do Claude na nuvem, o GitHub recusa os comandos do `gh` que usam GraphQL (`gh issue create`,
`gh issue view`, `gh issue list`, `gh issue edit`, `gh repo view`...), com erro HTTP 403. Nesse caso, use a API REST
pelo `gh api`, como mostrado em "Pela API REST" abaixo. No computador de alguém, os dois jeitos funcionam.

## Como fazer

- **Criar uma issue**: `gh issue create --title "..." --body "..."`. Para texto de várias linhas, use heredoc.
- **Ler uma issue**: `gh issue view <número> --json number,title,body,labels,comments`.
- **Listar issues**: `gh issue list --state open --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'`, com os filtros `--label` e `--state` que precisar.
- **Pôr uma issue dentro de outra (sub-issue)**: `gh issue create --parent <mãe> ...`, ou depois `gh issue edit <mãe> --add-sub-issue <filha>` (`gh` 2.94 ou mais novo). Com `gh` mais velho: `gh api --method POST repos/<dono>/<repo>/issues/<mãe>/sub_issues -F sub_issue_id=<id-da-filha>` (o id do banco, como em **Bloqueio** abaixo). Sem sub-issues, escreva `Parte de #<mãe>` no começo do texto da filha.
- **Bloqueio**: use as **dependências de issue** do próprio GitHub, que aparecem na tela. Para ligar: `gh issue create --blocked-by <n>,<n> ...` ou `gh issue edit <filha> --add-blocked-by <bloqueadora>` (`gh` 2.94 ou mais novo). Com `gh` mais velho: `gh api --method POST repos/<dono>/<repo>/issues/<filha>/dependencies/blocked_by -F issue_id=<id-da-bloqueadora>`, em que `<id-da-bloqueadora>` é o **id do banco** (`gh api repos/<dono>/<repo>/issues/<n> --jq .id`), _não_ o `#número` nem o `node_id`. Onde as dependências não existirem, escreva `Bloqueada por: #<n>, #<n>` no começo do texto da filha. Uma tarefa fica livre quando todas as bloqueadoras estão fechadas.
- **Contar bloqueios abertos**: `gh api repos/<dono>/<repo>/issues/<n> --jq .issue_dependencies_summary.blocked_by` (só os abertos; 0 quer dizer que pode começar). `gh issue view <n> --json blockedBy` também lista os fechados, então filtre: `--jq '[.blockedBy.nodes[] | select(.state == "OPEN")] | length'`.
- **Comentar**: `gh issue comment <número> --body "..."`
- **Pôr / tirar etiquetas**: `gh issue edit <número> --add-label "..."` / `--remove-label "..."`
- **Fechar**: escreva a explicação com `gh issue comment <número> --body "..."` e depois `gh issue close <número>`. Numa issue já fechada, `gh issue close --comment` descarta o comentário e mesmo assim termina sem erro.

O `gh` descobre o repositório sozinho pelo `git remote -v` quando roda dentro da cópia.

Abra issues só no repositório do próprio dono. Nunca em `mattpocock/skills` (de onde vêm estas skills). Num fork, o
`gh` pode usar o repositório de origem; antes da primeira issue da sessão, confira o destino com
`gh repo view --json nameWithOwner` (ou `gh api repos/<dono>/<repo> --jq .full_name`) e confirme com a pessoa se não
for o repositório dela.

## Pela API REST

Equivalentes que funcionam também nas sessões na nuvem (troque `<dono>/<repo>` pelo deste repositório):

- **Criar**: `gh api --method POST repos/<dono>/<repo>/issues -f title='...' -f body='...' -f 'labels[]=needs-triage'`
- **Ler**: `gh api repos/<dono>/<repo>/issues/<n> --jq '{number, title, body, labels: [.labels[].name], state}'` e os comentários com `gh api repos/<dono>/<repo>/issues/<n>/comments --jq '[.[].body]'`
- **Listar**: `gh api --paginate 'repos/<dono>/<repo>/issues?state=open&labels=<etiqueta>' --jq '.[] | select(.pull_request | not) | {number, title, labels: [.labels[].name]}'`
- **Comentar**: `gh api --method POST repos/<dono>/<repo>/issues/<n>/comments -f body='...'`
- **Pôr etiqueta**: `gh api --method POST repos/<dono>/<repo>/issues/<n>/labels -f 'labels[]=...'`; **tirar**: `gh api --method DELETE repos/<dono>/<repo>/issues/<n>/labels/<etiqueta>`
- **Fechar**: comente como acima e depois `gh api --method PATCH repos/<dono>/<repo>/issues/<n> -f state=closed`
- **Pessoa responsável**: `gh api --method POST repos/<dono>/<repo>/issues/<n>/assignees -f 'assignees[]=<login>'`

## Pull requests na triagem

**PRs como pedido: não.** _(Mude para `sim` se este repositório trata PRs de fora como pedidos de funcionalidade; o `/triage` lê esta linha.)_

Com `sim`, os PRs passam pelas mesmas etiquetas e estados das issues, com os comandos `gh pr` equivalentes:

- **Ler um PR**: `gh pr view <número>`, depois `gh pr view <número> --comments` (fora de um terminal, `--comments` mostra só os comentários, não o texto) e `gh pr diff <número>` para as mudanças.
- **Listar PRs de fora para triagem**: `gh api --paginate 'repos/{owner}/{repo}/pulls?state=open' --jq '.[] | select(.author_association | IN("OWNER","MEMBER","COLLABORATOR") | not) | {number, title, author: .user.login, author_association, labels: [.labels[].name]}'`.
- **Comentar / etiquetar / fechar**: `gh pr comment`, `gh pr edit --add-label`/`--remove-label`, `gh pr close`.

Issues e PRs dividem a mesma numeração no GitHub, então um `#42` pode ser qualquer um dos dois: tente `gh pr view 42` e, se não for PR, `gh issue view 42`.

## Quando uma skill diz "publicar no rastreador de tarefas"

Crie uma issue no GitHub.

## Quando uma skill diz "buscar a tarefa"

Leia como em **Ler uma issue** acima.

## Operações do wayfinder

Usadas pelo `/wayfinder`. O **mapa** é uma única issue, e as **tarefas** são issues filhas dela.

- **Mapa**: uma issue com a etiqueta `wayfinder:map`, com as seções Notas / Decisões até agora / Neblina. `gh issue create --label wayfinder:map`.
- **Tarefa filha**: uma issue ligada ao mapa como sub-issue do GitHub (veja **Pôr uma issue dentro de outra**). Onde sub-issues não estiverem ligadas, ponha a filha numa lista de tarefas no texto do mapa e escreva `Parte de #<mapa>` no começo do texto dela. Etiquetas: `wayfinder:<tipo>` (`research`/`prototype`/`grilling`/`task`). Quando alguém pega a tarefa, ela é atribuída a essa pessoa.
- **Bloqueio**: veja **Bloqueio** em "Como fazer".
- **Próxima tarefa**: liste as filhas abertas do mapa (`gh issue list --state open`, só as sub-issues ou a lista de tarefas do mapa), tire as que têm bloqueio aberto (veja **Contar bloqueios abertos**, ou uma issue aberta na linha `Bloqueada por`) ou já têm responsável; vale a primeira na ordem do mapa.
- **Pegar**: `gh issue edit <n> --add-assignee @me`, a primeira escrita da sessão.
- **Resolver**: `gh issue comment <n> --body "<resposta>"`, depois `gh issue close <n>`, e acrescente um resumo com link em "Decisões até agora" no mapa.
