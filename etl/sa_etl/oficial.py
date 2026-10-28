"""Número oficial: os motivos conhecidos de diferença entre fontes e o que o site faz em cada caso.

Regra do projeto: quando duas publicações oficiais mostram números diferentes, entendemos o motivo e o site mostra o
número oficial. Cada motivo entendido vira uma entrada aqui, com:
- titulo e explica: o que acontece, em português simples (aparece no site, na página "Como conferimos os números");
- decisao: o que o site faz (qual número mostra e onde fica o resto);
- corrigido: True quando a coleta já aplica a decisão, e o número do site é o oficial.

O processo, a cada coleta (todo dia):
1. A coleta aplica as decisões abaixo (por exemplo, o total da cota do Senado não soma as notas sem tipo).
2. A verificação (verificar.py) confere uma amostra com outra fonte oficial e classifica cada diferença com
   `classificar`. Diferença com motivo conhecido aparece explicada; diferença sem motivo fica "em revisão" no site,
   com o número oficial ao lado.
3. Se uma seção tiver diferenças sem motivo demais (LIMITE_SEM_MOTIVO), a publicação é barrada e o site continua com
   a versão anterior, até alguém entender o motivo e registrá-lo aqui.
"""
from __future__ import annotations

import re

# Uma seção com mais que isso de diferenças sem motivo conhecido (e pelo menos MIN_AMOSTRA números conferidos)
# barra a publicação.
LIMITE_SEM_MOTIVO = 0.02
MIN_AMOSTRA = 20

MOTIVOS: dict[str, dict] = {
    "senado_sem_tipo": {
        "titulo": "Notas do Senado sem tipo de despesa",
        "explica": "A lista oficial de reembolsos da cota do Senado (CEAPS) traz algumas notas sem o tipo de despesa. "
                   "O total oficial que o Senado publica para cada senador não soma essas notas.",
        "decisao": "O site usa o total oficial do Senado. As notas sem tipo aparecem à parte, na página do senador, com o "
                   "valor e o link, sem entrar no total.",
        "corrigido": True,
    },
    "senado_painel_ata": {
        "titulo": "Placar do painel diferente do placar da ata",
        "explica": "O Senado publica os votos registrados no painel eletrônico e, à parte, a ata da sessão, escrita pela "
                   "Secretaria de Atas. Às vezes um voto é corrigido depois da votação e o placar da ata fica diferente "
                   "da soma do painel.",
        "decisao": "O site mostra o placar da ata, que é o resultado oficial anunciado. A lista de votos continua sendo a "
                   "do painel, e a página da votação avisa a diferença.",
        "corrigido": True,
    },
    "receita_copia_antiga": {
        "titulo": "Dados de empresa guardados de uma consulta antiga",
        "explica": "A Receita Federal atualiza a base de CNPJ todo mês. Uma consulta antiga, guardada pela coleta, pode "
                   "ter sócios ou nome que já mudaram.",
        "decisao": "A coleta consulta de novo as empresas a cada 30 dias e, quando a verificação acha uma diferença, apaga "
                   "a cópia guardada daquela empresa: na próxima atualização, ela vem com os dados do mês.",
        "corrigido": False,
    },
    "receita_meses_diferentes": {
        "titulo": "As duas cópias da base da Receita estão em meses diferentes",
        "explica": "A Receita Federal não tem uma consulta de CNPJ aberta: a base sai uma vez por mês, e serviços como o "
                   "Minha Receita e a BrasilAPI publicam cópias. Logo depois de uma atualização, uma cópia pode estar "
                   "um mês à frente da outra.",
        "decisao": "O site mostra a consulta do mês feita no Minha Receita e marca a empresa como em revisão até as duas "
                   "cópias concordarem.",
        "corrigido": False,
    },
    "camara_sigepa": {
        "titulo": "Passagens compradas e devolvidas pelo sistema da Câmara",
        "explica": "Desde agosto de 2025, os dados abertos da Câmara não trazem as passagens aéreas compradas pelo "
                   "sistema da própria Câmara (SIGEPA), nem as devoluções e remarcações delas. A página oficial do "
                   "deputado soma as duas. Num mês com mais devoluções que compras, a página mostra menos que as notas.",
        "decisao": "O site busca cada bilhete, comprado ou devolvido, na lista oficial de despesas da Câmara e soma ao "
                   "mês, com o link. Assim o total do mês fica igual ao da página oficial.",
        "corrigido": True,
    },
    "camara_fora_do_mandato": {
        "titulo": "Notas de meses fora do mandato",
        "explica": "A página oficial de cada deputado só soma os meses em que ele estava no cargo neste mandato. Notas de "
                   "outros meses (como devoluções de passagens) ficam de fora da página, mas estão nos dados abertos.",
        "decisao": "O site compara com a página oficial só nos meses em que ela mostra gasto.",
        "corrigido": True,
    },
}

SEM_MOTIVO = {
    "titulo": "Diferença ainda sem motivo conhecido",
    "explica": "A fonte oficial mostra um número diferente e ainda não entendemos por quê.",
    "decisao": "O número fica marcado como em revisão, com o número oficial ao lado. Se houver muitas diferenças assim "
               "numa seção, a atualização do site é barrada até entendermos o motivo.",
    "corrigido": False,
}


def _nome(s: str) -> str:
    from .util import norm_name
    return re.sub(r"[^A-Z0-9]+", " ", norm_name(s or "").upper()).strip()


def classificar(checagem: str, item: dict) -> str | None:
    """O motivo conhecido de uma diferença (id em MOTIVOS), ou None se ainda não sabemos.

    `item` é a divergência como a verificação registra, com campos extras que cada checagem preenche para isto
    (por exemplo, `sem_tipo` na cota do Senado e `minha_receita_agora` nas empresas)."""
    if checagem == "cota_senado_ano":
        st = item.get("sem_tipo") or 0
        if st and abs(item["site"] - st - item["oficial"]) <= 1.0:
            return "senado_sem_tipo"
    if checagem == "placar_senado_ata" and item.get("painel_difere_da_ata"):
        return "senado_painel_ata"
    if checagem == "empresas_receita":
        agora = item.get("minha_receita_agora")
        if agora is not None:
            return "receita_copia_antiga" if agora == item.get("oficial_normalizado") else "receita_meses_diferentes"
    return None
