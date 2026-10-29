"""Linha de comando.

    python -m el_etl.build montar --saida ../../site/dist/eleicao2026
        lê os boletins guardados em dados/, confere com o oficial e monta o site. Se a conferência falhar, não grava nada.

    python -m el_etl.build coletar [--turno 1 2] [--ufs SP RJ] [--cache .cache]
        baixa de novo do TSE os resultados oficiais e os boletins de urna e grava em dados/.
"""
import argparse
import json
import os
import shutil
import sys
import tempfile

from . import analisar, depois17, locais, montar, mudancas, noite, oficial, turno1, turno2, validar

AQUI = os.path.dirname(os.path.abspath(__file__))
DADOS = os.path.normpath(os.path.join(AQUI, '..', '..', 'dados'))


def cmd_coletar(a):
    oficial.baixar(os.path.join(DADOS, 'tse'))
    print('resultados oficiais: ok')
    ufs = a.ufs or oficial.UFS
    for t in a.turno:
        for uf in ufs:
            pasta = os.path.join(DADOS, 'brutos', f'{t}turno')
            n = turno1.coletar(uf, pasta, a.cache) if t == '1' else turno2.coletar(uf, pasta)
            print(f'{t}º turno, {uf}: {n} seções', flush=True)


def cmd_montar(a, dados=DADOS):
    of = oficial.juntar(os.path.join(dados, 'tse'))
    resumos, listas, noites, tardes, erros, todas = {}, {}, {}, {}, [], {}
    for t, e in oficial.ELEICOES.items():
        secs = analisar.ler_brutos(os.path.join(dados, 'brutos', f'{t}turno'))
        validos = set(of[e]['BR']['cand'])
        todas[t] = (secs, validos)
        resumo, urnas = analisar.analisar(secs, validos)
        erros += validar.conferir(t, secs, of[e], resumo)
        resumos[t] = resumo
        listas[t] = (urnas, validos)
        noites[t] = noite.apuracao(secs, validos, noite.DIAS[t])
        tardes[t] = depois17.resumo(secs, depois17.ler(os.path.join(dados, 'brutos', f'{t}turno_log')), validos)
        erros += depois17.conferir(t, tardes[t])
        print(f'{t}º turno: {len(secs)} registros de seção, {len(urnas)} urnas com horário, '
              f'{resumo["cut"][analisar.FECHA + 15].get("BR", {}).get("n", 0)} fecharam depois das 17h15')
        if tardes[t]:
            br = tardes[t]['uf'].get('BR', [0] * 7)
            print(f'   registros das urnas: {tardes[t]["conf"]}; {br[2]} votos depois das 17h em {br[1]} urnas')
    mud, cidades, locs = None, None, None
    caminho = os.path.join(dados, 'tse', 'locais_votacao_2026.jsonl.gz')
    if os.path.exists(caminho) and len(todas) == 2:
        ls, secao_local = locais.ler(caminho)
        mud, cidades, locs = mudancas.calcular(todas['1'][0], todas['2'][0], todas['1'][1], todas['2'][1], ls, secao_local)
        erros += mudancas.conferir(cidades, of)
        print(f'cidades: {len(cidades)}; urnas comparadas nos dois turnos: {mud["cons"]["n"]}; '
              f'fora do padrão: {mud["cons"]["k"]}; números impossíveis: {mud["imp"]}')
    if erros:
        print('A CONFERÊNCIA FALHOU. Nada foi gravado.')
        for x in erros[:50]:
            print(' -', x)
        return 1
    tmp = tempfile.mkdtemp(prefix='eleicao2026-')
    D = montar.dados_site(of, resumos, noites, tardes, mud)
    montar.gravar(tmp, D, of)
    if cidades:
        mudancas.gravar(tmp, cidades, locs)
    for t, (urnas, validos) in listas.items():
        analisar.gravar_planilhas(t, urnas, os.path.join(tmp, 'dados', 'urnas'))
        analisar.gravar_lista_site(t, urnas, validos, os.path.join(tmp, 'urnas'))
    if os.path.exists(a.saida):
        shutil.rmtree(a.saida)
    os.makedirs(os.path.dirname(os.path.abspath(a.saida)), exist_ok=True)
    shutil.move(tmp, a.saida)
    print('Conferência: tudo bate com o oficial do TSE. Site em', a.saida)
    if a.resumo:
        with open(a.resumo, 'w', encoding='utf-8') as f:
            json.dump(resumos, f, ensure_ascii=False)
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog='el_etl.build')
    sub = p.add_subparsers(dest='cmd', required=True)
    c = sub.add_parser('coletar')
    c.add_argument('--turno', nargs='+', default=['1', '2'], choices=['1', '2'])
    c.add_argument('--ufs', nargs='+')
    c.add_argument('--cache', default='.cache')
    m = sub.add_parser('montar')
    m.add_argument('--saida', required=True)
    m.add_argument('--resumo', help='grava também o resumo da análise (JSON)')
    a = p.parse_args(argv)
    if a.cmd == 'coletar':
        cmd_coletar(a)
        return 0
    return cmd_montar(a)


if __name__ == '__main__':
    sys.exit(main())
