"""1º turno: boletins de urna do Portal de Dados Abertos do TSE.

Para cada estado, o TSE publica um arquivo .zip ("bweb") com uma linha por seção, cargo e candidato. Guardamos só
as linhas de presidente, uma por seção, com a hora de abertura, a hora de encerramento e os votos.
"""
import csv
import gzip
import io
import json
import os
import time
import zipfile

import requests

# O carimbo no nome do arquivo é a versão publicada pelo TSE.
URL = 'https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2026/buweb/bweb_1t_{uf}_051020261403.zip'


def ler_zip(arquivo):
    """Devolve a lista de seções (dicionários) de presidente de um arquivo bweb."""
    z = zipfile.ZipFile(arquivo)
    nome = [n for n in z.namelist() if n.endswith('.csv')][0]
    secs = {}
    with z.open(nome) as f:
        r = csv.reader(io.TextIOWrapper(f, encoding='latin-1', newline=''), delimiter=';')
        h = next(r)
        ix = {k: i for i, k in enumerate(h)}
        cargo = ix['CD_CARGO_PERGUNTA']
        for row in r:
            if row[cargo] != '1':  # 1 = presidente
                continue
            k = (row[ix['SG_UF']], row[ix['CD_MUNICIPIO']], row[ix['NR_ZONA']], row[ix['NR_SECAO']])
            s = secs.get(k)
            if s is None:
                s = secs[k] = {
                    'uf': k[0], 'mun': k[1], 'nm': row[ix['NM_MUNICIPIO']], 'z': k[2], 's': k[3],
                    'apt': int(row[ix['QT_APTOS']]), 'comp': int(row[ix['QT_COMPARECIMENTO']]),
                    'tu': row[ix['CD_TIPO_URNA']], 'ab': row[ix['DT_ABERTURA']],
                    'en': row[ix['DT_ENCERRAMENTO']], 'rec': row[ix['DT_BU_RECEBIDO']],
                    'agr': row[ix['DS_SECOES_AGREGADAS']], 'v': {}}
            nv = row[ix['NR_VOTAVEL']]
            s['v'][nv] = s['v'].get(nv, 0) + int(row[ix['QT_VOTOS']])
    return list(secs.values())


def coletar(uf, saida, cache):
    """Baixa o bweb de um estado e grava `saida/UF.jsonl.gz`."""
    os.makedirs(cache, exist_ok=True)
    zp = os.path.join(cache, f'bweb_1t_{uf}.zip')
    if not os.path.exists(zp):
        for i in range(5):
            try:
                r = requests.get(URL.format(uf=uf), timeout=120)
                r.raise_for_status()
                with open(zp + '.tmp', 'wb') as f:
                    f.write(r.content)
                os.replace(zp + '.tmp', zp)
                break
            except requests.RequestException:
                if i == 4:
                    raise
                time.sleep(2 ** i)
    secs = ler_zip(zp)
    os.makedirs(saida, exist_ok=True)
    with gzip.open(os.path.join(saida, f'{uf}.jsonl.gz'), 'wt', encoding='utf-8') as o:
        for s in secs:
            o.write(json.dumps(s, ensure_ascii=False) + '\n')
    return len(secs)
