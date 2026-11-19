"""Abre um aviso (issue) no GitHub para cada fonte oficial que falhou mais de 3 vezes seguidas, e fecha quando volta.

Lê o arquivo gravado por etl/falhas_seguidas.py. Um aviso por fonte, com o título fixo "Fonte com falhas seguidas:
{fonte}": se já está aberto, só atualiza o texto (quantas falhas, desde quando, o último motivo), sem comentário novo a
cada execução. Precisa do `gh` e de GH_TOKEN com permissão de escrever issues (job "fontes" do "Dados e site").

Uso: python etl/avisar_fontes.py falhas.json
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

PREFIXO = "Fonte com falhas seguidas: "


def gh(*args: str) -> str:
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout


def texto(fonte: str, x: dict, limite: int, execucao: str) -> str:
    return (
        f"A fonte **{fonte}** falhou **{x['seguidas']} vezes seguidas** (mais de {limite}), desde {x['desde']} (UTC).\n\n"
        f"- Último motivo: `{x['motivo']}`\n"
        f"- Aviso no site: {x['aviso']}\n"
        f"- Última execução: {execucao}\n\n"
        "Enquanto isso, o site mostra a última cópia boa desta fonte, com a data dela, e a coleta continua tentando de "
        "novo. Tentar de novo não está resolvendo: verifique o motivo e procure um caminho alternativo, sempre oficial "
        "(outra API oficial, o arquivo de dados abertos para download, outro endereço da mesma fonte), registrando no "
        "código por que a API não serviu (regra do CLAUDE.md).\n\n"
        "Este aviso fecha sozinho quando a fonte voltar a responder.\n"
    )


def abertos() -> dict[str, int]:
    lista = json.loads(gh("issue", "list", "--state", "open", "--limit", "200", "--search", f'in:title "{PREFIXO.strip()}"',
                          "--json", "number,title"))
    return {i["title"][len(PREFIXO):]: i["number"] for i in lista if i["title"].startswith(PREFIXO)}


def main(argv: list[str]) -> int:
    d = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    execucao = f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/{os.environ.get('GITHUB_REPOSITORY', '')}/actions/runs/{os.environ.get('GITHUB_RUN_ID', '')}"
    ja = abertos()
    for fonte, x in sorted((d.get("acima") or {}).items()):
        corpo = texto(fonte, x, d.get("limite", 3), execucao)
        if fonte in ja:
            gh("issue", "edit", str(ja[fonte]), "--body", corpo)
            print(f"Aviso #{ja[fonte]} atualizado: {fonte} ({x['seguidas']} falhas seguidas)")
        else:
            url = gh("issue", "create", "--title", PREFIXO + fonte, "--body", corpo).strip()
            print(f"Aviso aberto: {url} ({fonte})")
    for fonte in d.get("voltaram") or []:
        if fonte in ja:
            gh("issue", "close", str(ja[fonte]), "--comment", f"A fonte voltou a responder na execução {execucao}.")
            print(f"Aviso #{ja[fonte]} fechado: {fonte} voltou")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
