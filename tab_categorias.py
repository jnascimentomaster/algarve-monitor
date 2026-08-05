# -*- coding: utf-8 -*-
"""Crosstab categoria x ambito geografico (diagnostico do caso 'tech').

Uso (na pasta com monitor.db):
    python tab_categorias.py
"""
import json
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
con = sqlite3.connect(Path(__file__).parent / "monitor.db")

tab = {}
for (c,) in con.execute("SELECT classificacao FROM itens WHERE estado='classificado'"):
    d = json.loads(c)
    cat = d.get("categoria", "?")
    m = d.get("municipio", "?")
    amb = ("concelho" if m not in ("regiao", "fora_do_algarve", "indeterminado", None)
           else m)
    tab.setdefault(cat, {}).setdefault(amb, 0)
    tab[cat][amb] += 1

cols = ["concelho", "regiao", "indeterminado", "fora_do_algarve"]
print(f"{'categoria':<12}" + "".join(f"{c:>17}" for c in cols) + f"{'total':>8}")
for cat in sorted(tab, key=lambda k: -sum(tab[k].values())):
    linha = tab[cat]
    tot = sum(linha.values())
    print(f"{cat:<12}" + "".join(f"{linha.get(c,0):>17}" for c in cols) + f"{tot:>8}")
