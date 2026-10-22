"""TEMPORÁRIO: mede quanto tempo as consultas de atuação do Senado e da Câmara levam."""
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from sa_etl import recursos as R  # noqa: E402

S = requests.Session()
S.headers["User-Agent"] = R._session.headers.get("User-Agent", "x")


def mede(nome, url):
    t = time.time()
    try:
        r = S.get(url, timeout=90, headers={"Accept": "text/html,application/json"})
        print(f"{time.time() - t:6.1f}s {r.status_code} {len(r.content):>8} B  {nome}  {url}", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"{time.time() - t:6.1f}s ERRO {type(e).__name__}  {nome}  {url}", flush=True)


for cod in ("5672", "5953", "4981", "5982"):
    for ano in (2026, 2024):
        mede("autoria", R.SENADO_AUTORIA.format(cod=cod, ano=ano))
        mede("relatoria", R.SENADO_RELATORIA.format(cod=cod, ano=ano))
        mede("discursos", R.SENADO_DISCURSOS.format(cod=cod, ano=ano))
        mede("recursos", R.SENADO_JSON.format(cod=cod, ano=ano))
        mede("pessoal", R.SENADO_PESSOAL.format(cod=cod, ano=ano))
for dep in ("204554", "74374", "220593"):
    for ano in (2026, 2023):
        mede("camara", f"https://www.camara.leg.br/deputados/{dep}?ano={ano}")
# A função inteira, como a coleta usa
for cod in ("5672", "5953"):
    t = time.time(); r = R.senado_ano(cod, 2025); print(f"senado_ano {cod}: {time.time() - t:.1f}s", (r or {}).get("atuacao"), flush=True)
t = time.time(); r = R.camara_ano("204554", 2025); print(f"camara_ano: {time.time() - t:.1f}s", (r or {}).get("atuacao"), flush=True)
