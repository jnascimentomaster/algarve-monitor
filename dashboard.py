# -*- coding: utf-8 -*-
"""Algarve Monitor: exportacao para o dashboard local.

Le os itens classificados do monitor.db e escreve dados.js (window.DADOS),
que o dashboard.html carrega directamente em file:// sem servidor.

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
    payload = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "total": len(itens),
        "itens": itens,
    }
    SAIDA.write_text("window.DADOS = " +
                     json.dumps(payload, ensure_ascii=False) + ";",
                     encoding="utf-8")
    print(f"{len(itens)} itens exportados para {SAIDA.name}")
    print("Abre o dashboard.html no browser.")


if __name__ == "__main__":
    main()
