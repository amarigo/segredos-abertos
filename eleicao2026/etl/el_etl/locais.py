"""Onde fica cada local de votação (escola, por exemplo) e quais seções votam nele, nos dois turnos.

Fonte: arquivo "Eleitorado por local de votação - 2026" do Portal de Dados Abertos do TSE (dadosabertos.tse.jus.br,
conjunto eleitorado-2026). A API do portal (CKAN) só diz onde está o arquivo; o TSE não tem API que devolva o local e
a latitude/longitude de cada seção, por isso baixamos o .zip oficial (uma linha por seção e turno).

Guardamos em dados/tse/locais_votacao_2026.jsonl.gz uma linha por local: estado, cidade, zona, número do local,
nome, bairro, latitude, longitude (como o TSE publica, sem corrigir) e as seções de cada turno.
"""
import collections
import csv
import gzip
import io
import json
import os
import sys
import time
import zipfile

import requests

CKAN = 'https://dadosabertos.tse.jus.br/api/3/action/package_show?id=eleitorado-2026'
NOME = 'Eleitorado por local de votação - 2026'


def url_do_arquivo():
    """Pergunta à API do portal onde está o arquivo (o endereço muda quando o TSE publica uma versão nova)."""
    r = requests.get(CKAN, timeout=60)
    r.raise_for_status()
    for x in r.json()['result']['resources']:
        if x['name'].strip() == NOME:
            return x['url']
    raise RuntimeError(f'arquivo "{NOME}" não encontrado no portal do TSE')


def _num(x):
    try:
        v = float(x.replace(',', '.'))
    except ValueError:
        return None
    return None if v in (0, -1) else round(v, 5)


def ler_zip(arquivo):
    """Uma entrada por local de votação, com as seções de cada turno."""
    locs = {}
    with zipfile.ZipFile(arquivo) as z:
        for nome in sorted(z.namelist()):
            if not nome.endswith('.csv') or 'BRASIL' in nome:  # o arquivo BRASIL repete os dos estados
                continue
            with z.open(nome) as f:
                for r in csv.DictReader(io.TextIOWrapper(f, encoding='latin-1', newline=''), delimiter=';'):
                    k = (r['SG_UF'], r['CD_MUNICIPIO'].zfill(5), r['NR_ZONA'].zfill(4), r['NR_LOCAL_VOTACAO'])
                    loc = locs.get(k)
                    if loc is None:
                        loc = locs[k] = {'uf': k[0], 'mun': k[1], 'z': k[2], 'l': k[3],
                                         'nm': r['NM_LOCAL_VOTACAO'].strip(), 'br': r['NM_BAIRRO'].strip(),
                                         'lat': _num(r['NR_LATITUDE']), 'lon': _num(r['NR_LONGITUDE']),
                                         's1': [], 's2': []}
                    loc['s' + r['NR_TURNO']].append(r['NR_SECAO'].zfill(4))
    for loc in locs.values():
        loc['s1'].sort()
        loc['s2'].sort()
    return [locs[k] for k in sorted(locs)]


def gravar(locs, saida):
    tmp = saida + '.tmp'
    with gzip.GzipFile(tmp, 'wb', mtime=0) as fo:
        for loc in locs:
            fo.write((json.dumps(loc, ensure_ascii=False, sort_keys=True) + '\n').encode())
    os.replace(tmp, saida)


def ler(caminho):
    """Devolve {(uf, mun, zona, seção): local} para cada turno ('1' e '2') e a lista de locais."""
    locs, secao = [], {'1': {}, '2': {}}
    if not os.path.exists(caminho):
        return locs, secao
    with gzip.open(caminho, 'rt', encoding='utf-8') as fh:
        for linha in fh:
            loc = json.loads(linha)
            loc['i'] = len(locs)
            locs.append(loc)
            for t in '12':
                for s in loc['s' + t]:
                    secao[t][(loc['uf'], loc['mun'], loc['z'], s)] = loc
    return locs, secao


def coletar(saida, cache='.cache'):
    os.makedirs(cache, exist_ok=True)
    zp = os.path.join(cache, 'eleitorado_local_votacao_2026.zip')
    if not os.path.exists(zp):
        u = url_do_arquivo()
        for i in range(5):
            try:
                with requests.get(u, timeout=600, stream=True) as r:
                    r.raise_for_status()
                    with open(zp + '.tmp', 'wb') as f:
                        for b in r.iter_content(1 << 20):
                            f.write(b)
                os.replace(zp + '.tmp', zp)
                break
            except requests.RequestException:
                if i == 4:
                    raise
                time.sleep(2 ** i)
    locs = ler_zip(zp)
    gravar(locs, saida)
    n = collections.Counter(len(x['s2']) > 0 for x in locs)
    print(f'{len(locs)} locais de votação ({n[True]} com seções no 2º turno)', file=sys.stderr)


if __name__ == '__main__':
    coletar(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'dados', 'tse',
                         'locais_votacao_2026.jsonl.gz'), *sys.argv[1:2])
