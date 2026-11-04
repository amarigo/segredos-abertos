"""Sonda temporária: como o TSE publica os eleitos de 2026 (governador, senador, deputados)."""
import json
import requests

s = requests.Session()
s.headers['User-Agent'] = 'segredos-abertos (dados abertos)'


def get(u, n=1500):
    try:
        r = s.get(u, timeout=60)
        print('\n###', r.status_code, u, r.headers.get('content-type'), len(r.content))
        print(r.text[:n])
        return r
    except Exception as e:  # noqa
        print('\n### ERRO', u, e)


r = get('https://resultados.tse.jus.br/oficial/comum/config/ele-c.json', 300)
ids = []
if r is not None and r.ok:
    for c in r.json().get('c', []):
        for e in c.get('e', []):
            if '2026' in json.dumps(e):
                print('ELEICAO', json.dumps(e, ensure_ascii=False)[:600])
                ids.append(e.get('cd'))
for e in ids:
    e6 = str(e).zfill(6)
    for cargo in ('0003', '0005', '0006', '0007'):
        get(f'https://resultados.tse.jus.br/oficial/ele2026/{e}/dados-simplificados/sp/sp-c{cargo}-e{e6}-r.json', 2500)
    get(f'https://resultados.tse.jus.br/oficial/ele2026/{e}/dados-simplificados/df/df-c0008-e{e6}-r.json', 800)
    get(f'https://resultados.tse.jus.br/oficial/ele2026/{e}/config/mun-e{e6}-cm.json', 300)
D = 'https://divulgacandcontas.tse.jus.br/divulga/rest/v1'
r = get(f'{D}/eleicao/ordinarias', 200)
eid = None
if r is not None and r.ok:
    for e in r.json():
        if str(e.get('ano')) == '2026':
            print('DIVULGA', json.dumps(e, ensure_ascii=False))
            eid = eid or e.get('id')
if eid:
    r = get(f'{D}/candidatura/listar/2026/SP/{eid}/6/candidatos', 3000)
    if r is not None and r.ok:
        cs = r.json().get('candidatos', [])
        print('N candidatos dep fed SP', len(cs))
        el = [c for c in cs if 'leito' in str(c.get('descricaoTotalizacao'))]
        print('eleitos', len(el))
        if el:
            get(f'{D}/candidatura/buscar/2026/SP/{eid}/candidato/{el[0]["id"]}', 6000)
    get(f'{D}/candidatura/listar/2026/SP/{eid}/3/candidatos', 2000)
C = 'https://dadosabertos.tse.jus.br/api/3/action'
r = get(f'{C}/package_show?id=candidatos-2026', 200)
if r is not None and r.ok:
    for res in r.json()['result']['resources']:
        print('RES', res.get('name'), res.get('url'), res.get('last_modified') or res.get('created'))
r = get(f'{C}/package_search?q=resultados%202026&rows=20', 200)
if r is not None and r.ok:
    for p in r.json()['result']['results']:
        print('PKG', p['name'], '|', p['title'])
