# -*- coding: utf-8 -*-
"""Correccoes a base de entidades apos o check de 2026-08-04.

Aplica: dominios corrigidos (Barlavento, ABC, CRIA), INE marcado como valido
(o 500 era falta de parametros), e reclassificacao para scrape das fontes sem
RSS (camaras -> v2; UAlg e CCDR -> v1 via scrape; Expresso -> prioridade 3).

Uso (na pasta com entidades.db):
    python patch_fontes.py
"""
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
DB = Path(__file__).parent / "entidades.db"
HOJE = "2026-08-04"

PATCHES = [
    # (filtro nome LIKE, dict de campos)
    ("Barlavento%", {
        "website": "https://www.barlavento.pt",
        "url_recolha": "https://www.barlavento.pt/feed",
        "metodo_acesso": "rss", "verificado": 0,
        "nota": "dominio corrigido: migrou de barlavento.sapo.pt para barlavento.pt; re-testar"}),
    ("ABC - Algarve Biomedical Center%", {
        "website": "https://algarvebiomedicalcenter.pt",
        "url_recolha": "https://algarvebiomedicalcenter.pt/feed",
        "metodo_acesso": "rss", "verificado": 0,
        "nota": "dominio corrigido; alternativa com noticias proprias: https://abcri.pt/feed; re-testar"}),
    ("CRIA - Divisão de Empreendedorismo%", {
        "website": "https://cria.ualg.pt",
        "url_recolha": None, "metodo_acesso": "scrape", "verificado": 0,
        "nota": "ualg.pt/cria deu 404; candidato cria.ualg.pt por confirmar"}),
    ("INE - Instituto Nacional%", {
        "verificado": 1, "ultima_verificacao": HOJE,
        "nota": "HTTP 500 sem parametros e comportamento esperado; API valida com indicador concreto"}),
    ("Universidade do Algarve", {
        "metodo_acesso": "scrape", "url_recolha": None, "prioridade": 1,
        "nota": "sem RSS; scrape da pagina de noticias no v1"}),
    ("CCDR Algarve", {
        "metodo_acesso": "scrape", "url_recolha": None, "prioridade": 1,
        "nota": "sem RSS; scrape da pagina de noticias no v1"}),
    ("ANJE - Núcleo do Algarve", {
        "metodo_acesso": "scrape", "url_recolha": None,
        "nota": "sem RSS no site nacional"}),
    ("Algarve Daily News", {
        "metodo_acesso": "scrape", "url_recolha": None,
        "nota": "sem RSS"}),
    ("Expresso", {
        "metodo_acesso": "scrape", "url_recolha": None, "prioridade": 3,
        "nota": "sem RSS publico; cobertura via Google News chega"}),
    ("Câmara Municipal%", {
        "metodo_acesso": "scrape", "url_recolha": None,
        "nota": "sem RSS; scrape adiado para v2"}),
]


def main():
    if not DB.exists():
        print(f"Nao encontro {DB}.")
        sys.exit(1)
    con = sqlite3.connect(DB)
    total = 0
    for filtro, campos in PATCHES:
        nota = campos.pop("nota", None)
        sets = ", ".join(f"{k}=?" for k in campos)
        vals = list(campos.values())
        if nota:
            sets += ", notas=COALESCE(notas,'') || ?"
            vals.append(f" | patch {HOJE}: {nota}")
        cur = con.execute(
            f"UPDATE entidades SET {sets} WHERE nome LIKE ?", vals + [filtro])
        print(f"{cur.rowcount:2d} actualizadas: {filtro}")
        total += cur.rowcount
    con.commit()
    print(f"\n{total} registos actualizados.")
    ok = con.execute("SELECT COUNT(*) FROM entidades WHERE verificado=1").fetchone()[0]
    print(f"Verificadas na base: {ok}")


if __name__ == "__main__":
    main()
