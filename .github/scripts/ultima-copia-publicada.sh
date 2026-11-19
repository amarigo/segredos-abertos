#!/usr/bin/env bash
# Última cópia do site inteiro que foi ao ar pelo "Dados e site", extraída em $1.
#
# Usada por terras-raras.yml (troca só a página de Terras Raras) e pelo próprio "Dados e site" (se a coleta do Brasil
# falhar, publica de novo os dados do Brasil que já estavam no ar). Vale o pacote "github-pages" (guardado 7 dias) mais
# novo de uma execução do "Dados e site" no main cujo job "publicar" terminou com sucesso. Não basta a execução ter dado
# certo: desde 19/11/2026 uma execução pode publicar com os dados anteriores do Brasil e mesmo assim avisar o erro; e
# uma execução pode ter dado certo e não ter publicado. Nunca uma cópia feita por terras-raras.yml.
# Precisa de GH_TOKEN (permissão actions: read) e REPO (dono/nome).
set -euo pipefail
DEST="$1"
gh api "repos/$REPO/actions/artifacts?name=github-pages&per_page=100" \
  --jq '.artifacts | map(select(.expired == false and .workflow_run.head_branch == "main")) | sort_by(.created_at) | reverse | .[] | "\(.id) \(.workflow_run.id) \(.created_at)"' \
  > "$RUNNER_TEMP/pacotes.txt"
ESCOLHIDO=""
while read -r ART RUN QUANDO; do
  [ "$(gh api "repos/$REPO/actions/runs/$RUN" --jq '.path')" = ".github/workflows/dados-e-site.yml" ] || continue
  PUB=$(gh api "repos/$REPO/actions/runs/$RUN/jobs?per_page=50" --jq '[.jobs[] | select(.name == "publicar") | .conclusion] | first // ""')
  if [ "$PUB" = "success" ]; then
    ESCOLHIDO="$ART"
    echo "Cópia do site: pacote $ART da execução $RUN, de $QUANDO" | tee -a "${GITHUB_STEP_SUMMARY:-/dev/null}"
    break
  fi
done < "$RUNNER_TEMP/pacotes.txt"
if [ -z "$ESCOLHIDO" ]; then
  echo "::error title=Cópia do site::Nenhuma cópia do site publicada nos últimos 7 dias. Rode Actions > Dados e site > Run workflow."
  exit 1
fi
gh api "repos/$REPO/actions/artifacts/$ESCOLHIDO/zip" > "$RUNNER_TEMP/site.zip"
rm -rf "$RUNNER_TEMP/pacote" && unzip -q "$RUNNER_TEMP/site.zip" -d "$RUNNER_TEMP/pacote"
mkdir -p "$DEST" && tar -xf "$RUNNER_TEMP/pacote/artifact.tar" -C "$DEST"
rm -rf "$RUNNER_TEMP/site.zip" "$RUNNER_TEMP/pacote"
# Confere que é mesmo o site inteiro
for f in index.html data/meta.json mg/index.html eleicao2026/index.html terras-raras/index.html; do
  test -f "$DEST/$f" || { echo "::error title=Cópia do site::A cópia do site não tem $f"; exit 1; }
done
