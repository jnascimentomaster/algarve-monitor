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
}
ORDEM = list(SERIES_META)


def periodicidade(periodo):
    return {4: "A", 7: "M", 10: "D"}.get(len(periodo or ""), "?")


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
    payload = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "total": len(itens),
        "itens": itens,
        "indicadores": indicadores,
    }
    SAIDA.write_text("window.DADOS = " +
                     json.dumps(payload, ensure_ascii=False) + ";",
                     encoding="utf-8")
    pontos = sum(len(p) for s in indicadores for p in s["ambitos"].values())
    print(f"{len(itens)} itens exportados para {SAIDA.name}")
    print(f"{len(indicadores)} séries de indicadores ({pontos} pontos)")
    print("Abre o dashboard.html no browser.")


if __name__ == "__main__":
    main()
