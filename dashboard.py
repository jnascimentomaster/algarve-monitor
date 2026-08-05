# -*- coding: utf-8 -*-
"""Algarve Monitor: exportacao para o dashboard local.

Le os itens classificados e as series de indicadores do monitor.db e escreve
dados.js (window.DADOS), que o dashboard.html carrega directamente em file://
sem servidor.

Uso (na pasta com monitor.db):
    python dashboard.py
Depois abrir dashboard.html no browser.
"""
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
PASTA = Path(__file__).parent
DB = PASTA / "monitor.db"
SAIDA = PASTA / "dados.js"

N_PERIODOS = 60          # janela exportada por serie e ambito

# Rotulo legivel e sentido da variacao homologa: +1 quando subir e bom sinal,
# -1 quando subir e mau (desemprego). O dashboard usa isto para a cor da seta.
SERIES_META = {
    "dormidas": ("Dormidas em alojamento turístico", 1),
    "hospedes": ("Hóspedes em alojamento turístico", 1),
    "constituicoes": ("Constituição de pessoas colectivas", 1),
    "dormidas_anual": ("Dormidas em alojamento turístico (anual)", 1),
    "hospedes_anual": ("Hóspedes em alojamento turístico (anual)", 1),
    "desemprego": ("Desemprego registado", -1),
    "voos_aterrados": ("Aeronaves aterradas em Faro", 1),
    "voos_descolados": ("Aeronaves descoladas em Faro", 1),
    "passageiros_desembarcados": ("Passageiros desembarcados em Faro", 1),
    "voos_chegadas": ("Chegadas diárias a Faro", 1),
    "voos_partidas": ("Partidas diárias de Faro", 1),
    "preco_habitacao": ("Valor mediano de venda por m²", 0),
    "consumo_electrico": ("Consumo de electricidade", 1),
}
ORDEM = list(SERIES_META)

# Fase 1b: series com ambito 'Concelho|SECCAO'. Saem do painel de indicadores e
# vao para window.DADOS.empresas, ja agregadas por sector.
SECTORES = {
    "tech": ["J"],
    "turismo": ["I"],
    "construcao": ["F", "L"],
    "comercio": ["G"],
    "agro_mar": ["A"],
    "outros": ["B", "C", "D", "E", "H", "M", "N", "P", "Q", "R", "S"],
}
SECTOR_ROTULOS = {
    "todos": "Todos os sectores", "tech": "Tecnologia", "turismo": "Turismo",
    "construcao": "Construção e imobiliário", "comercio": "Comércio",
    "agro_mar": "Agro-alimentar e mar", "outros": "Outros sectores",
}
EMPRESAS_META = {
    "empresas_stock": ("Empresas activas", "n", "A"),
    "empresas_nascimentos": ("Nascimentos de empresas", "n", "A"),
    "empresas_mortes": ("Mortes de empresas", "n", "A"),
    "empresas_vn": ("Volume de negócios", "eur", "A"),
    "empresas_pessoal": ("Pessoal ao serviço", "n", "A"),
    "vab_sector": ("VAB por ramo (Algarve)", "eur", "A"),
    "constituicoes_mes": ("Constituições", "n", "M"),
    "dissolucoes_mes": ("Dissoluções", "n", "M"),
}
N_MESES_EMPRESAS = 24


def periodicidade(periodo):
    p = periodo or ""
    if "T" in p:
        return "T"
    return {4: "A", 7: "M", 10: "D"}.get(len(p), "?")


def ler_indicadores(con):
    """-> lista de series, cada uma com os ambitos e os ultimos N periodos.

    Para as series com desagregacao por concelho e acrescentado um ambito
    'regiao' calculado por soma dos concelhos disponiveis em cada periodo.
    Nota: quando o INE marca um concelho como confidencial o ponto nao existe,
    logo a soma regional desses meses fica ligeiramente subestimada.
    """
    try:
        linhas = con.execute(
            "SELECT serie, ambito, periodo, valor, unidade, fonte "
            "FROM indicadores ORDER BY serie, ambito, periodo").fetchall()
    except sqlite3.OperationalError:
        return []          # tabela ainda nao existe: o dashboard corre na mesma

    bruto = {}
    for serie, ambito, periodo, valor, unidade, fonte in linhas:
        if "|" in ambito:          # series por sector: vao para ler_empresas
            continue
        s = bruto.setdefault(serie, {"unidade": unidade, "fonte": fonte,
                                     "ambitos": {}})
        s["ambitos"].setdefault(ambito, []).append((periodo, valor))

    out = []
    for serie in sorted(bruto, key=lambda s: (ORDEM.index(s)
                                              if s in ORDEM else 99, s)):
        s = bruto[serie]
        concelhos = {a: p for a, p in s["ambitos"].items() if a != "regiao"}
        if concelhos and "regiao" not in s["ambitos"]:
            soma = {}
            for pontos in concelhos.values():
                for periodo, valor in pontos:
                    if valor is not None:
                        soma[periodo] = soma.get(periodo, 0.0) + valor
            s["ambitos"]["regiao"] = sorted(soma.items())
        ambitos = {}
        for ambito, pontos in s["ambitos"].items():
            pontos = [[p, v] for p, v in sorted(pontos) if v is not None]
            if pontos:
                ambitos[ambito] = pontos[-N_PERIODOS:]
        if not ambitos:
            continue
        qualquer = next(iter(ambitos.values()))
        rotulo, sentido = SERIES_META.get(serie, (serie, 1))
        out.append({
            "serie": serie,
            "rotulo": rotulo,
            "sentido": sentido,
            "unidade": s["unidade"],
            "fonte": s["fonte"],
            "periodicidade": periodicidade(qualquer[-1][0]),
            "por_concelho": bool(concelhos),
            "ambitos": ambitos,
        })
    return out


def ler_empresas(con):
    """Series com ambito 'Concelho|SECCAO', agregadas por sector.

    'todos' usa a categoria TOT do INE, que nunca vem suprimida por segredo
    estatistico. Os restantes sectores sao a soma das seccoes com dado
    publicado, pelo que ficam subestimados quando o INE suprime uma celula
    (acontece em 6 a 11% das combinacoes concelho x seccao, quase sempre em
    seccoes marginais no Algarve: extractivas, electricidade, agua).
    """
    try:
        linhas = con.execute(
            "SELECT serie, ambito, periodo, valor, unidade, fonte "
            "FROM indicadores WHERE ambito LIKE '%|%' "
            "ORDER BY serie, ambito, periodo").fetchall()
    except sqlite3.OperationalError:
        return {"series": [], "sectores": SECTOR_ROTULOS}
    if not linhas:
        return {"series": [], "sectores": SECTOR_ROTULOS}

    # serie -> base -> periodo -> {seccao: valor}
    bruto, fontes = {}, {}
    for serie, ambito, periodo, valor, unidade, fonte in linhas:
        base, _, sec = ambito.partition("|")
        if valor is None:
            continue
        fontes[serie] = (unidade, fonte)
        bruto.setdefault(serie, {}).setdefault(base, {}) \
             .setdefault(periodo, {})[sec] = valor

    def agregar(por_seccao):
        out = {"todos": por_seccao.get("TOT")}
        for nome, secs in SECTORES.items():
            vals = [por_seccao[s] for s in secs if s in por_seccao]
            out[nome] = sum(vals) if vals else None
        return out

    series = []
    for serie in EMPRESAS_META:
        if serie not in bruto:
            continue
        rotulo, unidade_pref, perio = EMPRESAS_META[serie]
        unidade, fonte = fontes.get(serie, (unidade_pref, "INE"))
        bases = bruto[serie]
        # agregado regional por soma dos concelhos (excepto series ja regionais)
        if "regiao" not in bases and len(bases) > 1:
            soma = {}
            for por_periodo in bases.values():
                for periodo, secs in por_periodo.items():
                    alvo = soma.setdefault(periodo, {})
                    for s, v in secs.items():
                        alvo[s] = alvo.get(s, 0.0) + v
            bases = dict(bases)
            bases["regiao"] = soma
        ambitos = {}
        for base, por_periodo in bases.items():
            periodos = sorted(por_periodo)
            if perio == "M":
                periodos = periodos[-N_MESES_EMPRESAS:]
            por_sector = {}
            for periodo in periodos:
                for nome, val in agregar(por_periodo[periodo]).items():
                    if val is not None:
                        por_sector.setdefault(nome, []).append([periodo, val])
            if por_sector:
                ambitos[base] = por_sector
        if ambitos:
            series.append({
                "serie": serie, "rotulo": rotulo, "unidade": unidade,
                "fonte": fonte, "periodicidade": perio, "ambitos": ambitos,
            })
    return {"series": series, "sectores": SECTOR_ROTULOS}


def main():
    con = sqlite3.connect(DB)
    linhas = con.execute(
        "SELECT id, fonte_nome, url, titulo, descricao, publicado_em, "
        "classificacao FROM itens WHERE estado='classificado' "
        "ORDER BY publicado_em DESC").fetchall()
    itens = []
    for iid, fonte, url, titulo, desc, pub, cls in linhas:
        d = json.loads(cls)
        itens.append({
            "id": iid, "fonte": fonte, "url": url, "titulo": titulo,
            "publicado_em": pub,
            "categoria": d.get("categoria"),
            "relevancia": d.get("relevancia"),
            "municipio": d.get("municipio"),
            "sinal": d.get("sinal"),
            "montante_eur": d.get("montante_eur"),
            "resumo": d.get("resumo"),
            "entidades": d.get("entidades", []),
            "geo_forcado": d.get("geo_forcado", False),
        })
    indicadores = ler_indicadores(con)
    empresas = ler_empresas(con)
    try:
        novas = con.execute(
            "SELECT nome, concelho, cae, cae_seccao, capital_social, "
            "relevancia_tech, data_acto FROM empresas_registo "
            "WHERE acto='constituicao' ORDER BY data_acto DESC "
            "LIMIT 60").fetchall()
    except sqlite3.OperationalError:
        novas = []
    empresas["novas"] = [
        {"nome": n, "concelho": c, "cae": cae, "seccao": sec,
         "capital": cap, "tech": tech, "data": d}
        for n, c, cae, sec, cap, tech, d in novas]
    payload = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "total": len(itens),
        "itens": itens,
        "indicadores": indicadores,
        "empresas": empresas,
    }
    SAIDA.write_text("window.DADOS = " +
                     json.dumps(payload, ensure_ascii=False) + ";",
                     encoding="utf-8")
    pontos = sum(len(p) for s in indicadores for p in s["ambitos"].values())
    print(f"{len(itens)} itens exportados para {SAIDA.name}")
    print(f"{len(indicadores)} séries de indicadores ({pontos} pontos)")
    p_emp = sum(len(v) for s in empresas["series"]
                for a in s["ambitos"].values() for v in a.values())
    print(f"{len(empresas['series'])} séries de empresas por sector "
          f"({p_emp} pontos) · {len(empresas['novas'])} empresas no registo")
    print("Abre o dashboard.html no browser.")


if __name__ == "__main__":
    main()
