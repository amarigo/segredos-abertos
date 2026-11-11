#!/usr/bin/env bash
# Instala o Chromium do Playwright (testes no navegador e imagens de prévia) sem depender do apt.
#
# Antes era "npx playwright install --with-deps chromium". O --with-deps roda apt-get, e em 11/11/2026 o espelho do
# Ubuntu da máquina do GitHub (azure.archive.ubuntu.com) parou de responder: cada pacote esperava 20 s, o passo levava
# minutos e falhava, e os testes do site nem começavam. Os pacotes que o apt tentava baixar eram só fontes extras
# (japonês, chinês, tailandês); as bibliotecas que o Chromium precisa já vêm na imagem ubuntu-latest.
#
# Agora: baixa o Chromium do servidor do Playwright (não usa apt) e confere se ele abre. Só se não abrir, chama o apt,
# com tempo limite e uma nova tentativa. Sai com erro se o Chromium continuar sem abrir.
set -uo pipefail

abre() {
  node -e 'import("@playwright/test").then(async ({ chromium }) => { const b = await chromium.launch(); await b.close(); })' 2>/dev/null
}

baixou=0
for t in 1 2 3; do
  npx playwright install chromium && { baixou=1; break; }
  echo "Download do Chromium falhou (tentativa $t)"
  [ "$t" -lt 3 ] && sleep $((t * 10))
done
if [ "$baixou" -ne 1 ]; then
  echo "::error title=Navegador::o download do Chromium falhou 3 vezes"
  exit 1
fi

if abre; then
  echo "Chromium abre com as bibliotecas da máquina; apt não foi preciso"
  exit 0
fi

for t in 1 2; do
  echo "Chromium não abriu; instalando as bibliotecas pelo apt (tentativa $t)"
  timeout -k 10 300 npx playwright install-deps chromium && abre && exit 0
done
echo "::error title=Navegador::o Chromium não abre e o apt não instalou as bibliotecas que faltam"
exit 1
