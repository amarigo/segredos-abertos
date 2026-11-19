"""Falhas seguidas de cada fonte: motivo, nova tentativa e, depois de 3 falhas, aviso pedindo caminho alternativo."""
import importlib.util
import json
from pathlib import Path

from sa_etl import util

RAIZ = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("falhas_seguidas", RAIZ / "falhas_seguidas.py")
fs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fs)

AVISO = "Senadores da 57ª legislatura: a fonte oficial não respondeu; usando a cópia de 18/11/2026"


def _rodar(tmp_path, meta, *extra):
    (tmp_path / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    fs.main(["--meta", str(tmp_path / "meta.json"), "--estado", str(tmp_path / "estado.json"),
             "--saida", str(tmp_path / "saida.json"), *extra])
    return json.loads((tmp_path / "saida.json").read_text(encoding="utf-8"))


def test_mais_de_3_falhas_seguidas_pede_caminho_alternativo(tmp_path):
    meta = {"avisos": [AVISO], "avisos_tentar": [AVISO],
            "motivos_falha": {"Senadores da 57ª legislatura": "HTTPError: 503 Server Error"}}
    for n in range(1, 4):
        d = _rodar(tmp_path, meta)
        assert d["todas"]["Senadores da 57ª legislatura"]["seguidas"] == n
        assert d["acima"] == {}  # até 3 falhas: só tenta de novo
    d = _rodar(tmp_path, meta)
    x = d["acima"]["Senadores da 57ª legislatura"]
    assert x["seguidas"] == 4 and x["motivo"] == "HTTPError: 503 Server Error"
    # A fonte voltou: a contagem zera e o aviso é fechado
    d = _rodar(tmp_path, {"avisos": [], "avisos_tentar": []})
    assert d["todas"] == {} and d["voltaram"] == ["Senadores da 57ª legislatura"]


def test_aviso_que_nova_coleta_nao_resolve_nao_conta(tmp_path):
    d = _rodar(tmp_path, {"avisos": ["Pagamentos a empresas: o Portal recusa robôs"], "avisos_tentar": []})
    assert d["todas"] == {}


def test_etapa_do_brasil_falhou_conta_e_guarda_as_outras_fontes(tmp_path):
    _rodar(tmp_path, {"avisos_tentar": [AVISO]})
    d = _rodar(tmp_path, {"avisos_tentar": []}, "--etapa", "Conferência dos dados", "--motivo", "82 senadores")
    assert d["todas"]["Coleta do Brasil: Conferência dos dados"]["seguidas"] == 1
    # As fontes de dentro da coleta não foram lidas de novo: a contagem delas fica como estava
    assert d["todas"]["Senadores da 57ª legislatura"]["seguidas"] == 1
    assert d["voltaram"] == []


def test_com_copia_guarda_o_motivo_da_falha(tmp_path):
    dest = tmp_path / "x.json"
    dest.write_text('{"a": 1}', encoding="utf-8")
    import os
    os.utime(dest, (0, 0))  # cópia velha: pergunta à fonte

    def falha():
        raise ConnectionError("fonte fora do ar")
    util.MOTIVOS_FALHA.clear()
    assert util.com_copia(dest, falha, "Fonte teste") == {"a": 1}
    assert util.MOTIVOS_FALHA["Fonte teste"] == "ConnectionError: fonte fora do ar"
    util.MOTIVOS_FALHA.clear()
    util.AVISOS.clear()
