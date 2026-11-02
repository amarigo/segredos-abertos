"""Anotações do GitHub Actions que levam o motivo de cada problema para o painel de status (/status/)."""
import importlib.util
import json
from pathlib import Path

from sa_etl.util import anotar

RAIZ = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("anotar_script", RAIZ / "anotar.py")
script = importlib.util.module_from_spec(spec)
spec.loader.exec_module(script)


def test_fora_do_actions_nao_imprime(monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    anotar("error", "Conferência", "algo")
    assert capsys.readouterr().err == ""


def test_escapa_quebras_e_titulo(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    anotar("warning", "Minas Nossa: conferência, MG", "linha 1\nlinha 2 com 50%")
    err = capsys.readouterr().err.strip()
    assert err == "::warning title=Minas Nossa%3A conferência%2C MG::linha 1%0Alinha 2 com 50%25"


def test_barreira_nomeia_as_secoes(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    f = tmp_path / "verificacao.json"
    f.write_text(json.dumps({"barradas": ["cota", "emendas"], "limite_sem_motivo": 0.02,
                             "secoes": {"cota": {"titulo": "Cota parlamentar"}, "emendas": {"titulo": "Emendas"}}}))
    assert script.main(["barreira", str(f)]) == 0
    err = capsys.readouterr().err
    # o GitHub desfaz %25 -> %; a vírgula só é escapada no título
    assert "::error title=Verificação com a segunda fonte::" in err
    assert "acima de 2%25 em Cota parlamentar, Emendas." in err


def test_avisos_um_por_linha_e_arquivo_faltando(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    f = tmp_path / "meta.json"
    f.write_text(json.dumps({"avisos": ["Emendas: o Portal não respondeu", "Senado: cópia de 01/11/2026"]}))
    script.main(["avisos", str(f), "Aviso da coleta"])
    script.main(["avisos", str(tmp_path / "nao-existe.json")])
    linhas = capsys.readouterr().err.strip().splitlines()
    assert linhas == ["::warning title=Aviso da coleta::Emendas: o Portal não respondeu",
                      "::warning title=Aviso da coleta::Senado: cópia de 01/11/2026"]
