# -*- coding: utf-8 -*-
"""Adiciona observatorios regionais a base de entidades (verificados 2026-08-05).

Uso (na pasta com entidades.db):
    python patch_fontes_2.py
"""
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
DB = Path(__file__).parent / "entidades.db"
HOJE = "2026-08-05"

NOVAS = [
    ("OTSA - Observatório para o Turismo Sustentável do Algarve", "fonte_dados",
     "regional", None, "https://www.turismodoalgarve.pt/pt/menu/814/observatorio.aspx",
     "manual", None, "turismo,economia", 2,
     f"VERIFICADO {HOJE}: RTA+CCDR+UAlg+TdP, rede INSTO/OMT desde 2020; relatorios "
     "periodicos em PDF; tambem em travelbi.turismodeportugal.pt/observatorios"),
    ("OBSERVE - Observatório da Sustentabilidade do Algarve (UAlg)", "fonte_dados",
     "regional", "Faro", "https://observe.ualg.pt", "scrape", None,
     "turismo,economia,investigacao", 2,
     f"VERIFICADO {HOJE}: projecto CRESC Algarve 2020 encerrado; site com "
     "indicadores e documentos continua activo; baseline historica"),
    ("MONITUR - Monitorização do destino Algarve (UAlg)", "fonte_dados",
     "regional", "Faro", "https://monitur.ualg.pt", "manual", None,
     "turismo,economia", 3,
     f"VERIFICADO {HOJE}: projecto concluido em 2023, conteudos disponiveis; "
     "so para backfill de series historicas, sem actualizacao"),
]


def main():
    if not DB.exists():
        print(f"Nao encontro {DB}.")
        sys.exit(1)
    con = sqlite3.connect(DB)
    for e in NOVAS:
        try:
            con.execute(
                "INSERT INTO entidades (nome,tipo,ambito,municipio,website,"
                "metodo_acesso,url_recolha,camadas,prioridade,notas,"
                "verificado,ultima_verificacao) VALUES (?,?,?,?,?,?,?,?,?,?,1,?)",
                e + (HOJE,))
            print(f"+ {e[0]}")
        except sqlite3.IntegrityError:
            print(f"ja existe: {e[0]}")
    con.commit()
    n = con.execute("SELECT COUNT(*) FROM entidades").fetchone()[0]
    print(f"\nTotal de entidades: {n}")


if __name__ == "__main__":
    main()
