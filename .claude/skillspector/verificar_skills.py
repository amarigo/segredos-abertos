"""Confere a segurança de todas as skills do projeto com o SkillSpector (NVIDIA).

Roda no CI (.github/workflows/skills-seguranca.yml) a cada push, a cada PR e
uma vez por semana, e pode rodar à mão:

    pip install "skillspector @ git+https://github.com/NVIDIA/SkillSpector@<commit>"
    python .claude/skillspector/verificar_skills.py

O que é conferido:
- cada pasta de .claude/skills/ que tem SKILL.md;
- cada DESIGN.md de .claude/referencias/ (material de consulta, lido pelo agente).

Uma skill passa quando o SkillSpector sai com código 0 (recomendação SAFE ou
CAUTION). Achados já revisados por uma pessoa e julgados alarme falso ficam em
.claude/skillspector/aceitos/<skill>.yaml; só achados novos contam. Ver o
README desta pasta para saber como revisar e aceitar.

A análise é só a estática (--no-llm): não precisa de chave de API nem gasta
dinheiro.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SKILLS = RAIZ / ".claude" / "skills"
REFERENCIAS = RAIZ / ".claude" / "referencias"
ACEITOS = Path(__file__).resolve().parent / "aceitos"


def alvos() -> list[tuple[str, Path, Path | None]]:
    """Lista (nome, caminho, arquivo de aceitos ou None) de tudo que será conferido."""
    lista: list[tuple[str, Path, Path | None]] = []
    for pasta in sorted(p for p in SKILLS.iterdir() if (p / "SKILL.md").is_file()):
        aceito = ACEITOS / f"{pasta.name}.yaml"
        lista.append((pasta.name, pasta, aceito if aceito.is_file() else None))
    for arquivo in sorted(REFERENCIAS.rglob("DESIGN.md")):
        nome = str(arquivo.parent.relative_to(RAIZ / ".claude"))
        lista.append((nome, arquivo, None))
    return lista


def conferir(caminho: Path, aceito: Path | None, saida: Path) -> tuple[int, dict]:
    cmd = ["skillspector", "scan", str(caminho), "--no-llm", "--format", "json", "--output", str(saida)]
    if aceito:
        cmd += ["--baseline", str(aceito)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    try:
        relatorio = json.loads(saida.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        relatorio = {"erro": (proc.stderr or proc.stdout)[-2000:]}
    return proc.returncode, relatorio


def main() -> int:
    linhas = ["| Item | Resultado | Nota de risco | Achados ativos | Aceitos (revisados) |", "|---|---|---|---|---|"]
    falhas: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        for nome, caminho, aceito in alvos():
            codigo, rel = conferir(caminho, aceito, Path(tmp) / "rel.json")
            risco = rel.get("risk_assessment", {})
            ativos = len(rel.get("issues", []))
            suprimidos = len(rel.get("suppressed", []))
            if codigo == 0:
                resultado = f"passou ({risco.get('recommendation', '?')})"
            else:
                resultado = "REPROVADA" if codigo == 1 else "ERRO ao conferir"
                falhas.append(nome)
                graves = sorted({f"{i.get('id')} {i.get('location', {}).get('file')}:{i.get('location', {}).get('start_line')}"
                                 for i in rel.get("issues", []) if i.get("severity") in ("HIGH", "CRITICAL")})
                detalhe = "; ".join(graves[:5]) or rel.get("erro", "")[:300]
                print(f"::error title=SkillSpector: {nome}::{resultado}, nota {risco.get('score')}. {detalhe}")
            linhas.append(f"| `{nome}` | {resultado} | {risco.get('score', '-')} | {ativos} | {suprimidos} |")

    texto = "## Segurança das skills (SkillSpector)\n\n" + "\n".join(linhas) + "\n"
    if falhas:
        texto += (f"\n**{len(falhas)} reprovada(s):** {', '.join(falhas)}. Veja .claude/skillspector/README.md "
                  "para revisar os achados.\n")
    print(texto)
    resumo = os.environ.get("GITHUB_STEP_SUMMARY")
    if resumo:
        with open(resumo, "a", encoding="utf-8") as f:
            f.write(texto)
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
