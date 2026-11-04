"""Sonda temporária: como o TSE publica os eleitos de 2026 (governador, senador, deputados)."""
import json
import requests

s = requests.Session()
s.headers['User-Agent'] = 'segredos-abertos (dados abertos)'


def get(u, n=1500):
    try:
        r = s.get(u, timeout=60)
        print('\n###', r.status_code, u, r.headers.get('content-type'), len(r.content), r.headers.get('last-modified'))
        print(r.text[:n])
        return r
    except Exception as e:  # noqa
        print('\n### ERRO', u, e)


r = get('https://resultados.tse.jus.br/oficial/comum/config/ele-c.json', 0)
d = r.json()
print(json.dumps({k: v for k, v in d.items() if k != 'arq'}, ensure_ascii=False)[:8000])
print(json.dumps(d.get('arq'), ensure_ascii=False)[:3000])
for e in (6257, 6259, 6260, 6261, 6262, 6263, 6264):
    e6 = str(e).zfill(6)
    get(f'https://resultados.tse.jus.br/oficial/ele2026/{e}/config/mun-e{e6}-cm.json', 300)
    for cargo in ('0003', '0005', '0006', '0007'):
        get(f'https://resultados.tse.jus.br/oficial/ele2026/{e}/dados-simplificados/sp/sp-c{cargo}-e{e6}-r.json', 1200)
C = 'https://dadosabertos.tse.jus.br/api/3/action'
r = get(f'{C}/package_show?id=resultados-2026', 0)
for res in r.json()['result']['resources']:
    print('RES', res.get('name'), res.get('url'), res.get('last_modified') or res.get('created'))
for u in ('https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/consulta_cand_2026.zip',):
    h = s.head(u, timeout=60)
    print('HEAD', h.status_code, u, h.headers.get('content-length'), h.headers.get('last-modified'))
