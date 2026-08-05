# -*- coding: utf-8 -*-
"""Algarve Monitor: recolha de noticias (modulo 1 do pipeline).

Le as fontes RSS verificadas de entidades.db e acumula itens em monitor.db,
prontos para o passo de classificacao (enrich.py).

Regras:
  - So fontes com metodo_acesso='rss', verificado=1 e camada 'noticias'.
  - Fontes nacionais: so entram itens que mencionem o Algarve (concelhos,
    gentilicos, termos regionais). Fontes regionais entram todas; o filtro
    de relevancia e feito depois pelo classificador.
  - Deduplicacao dupla: por URL e por titulo normalizado (apanha o mesmo
    artigo vindo do feed directo e do Google News, cujos links sao redirects).

Uso (na pasta com entidades.db):
    python harvest_news.py fetch    # recolher
    python harvest_news.py stats    # estado do arquivo
"""
import hashlib
import re
import sqlite3
import sys
import time
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

PASTA = Path(__file__).parent
DB_ENT = PASTA / "entidades.db"
DB_MON = PASTA / "monitor.db"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
TIMEOUT = 30

# Termos que qualificam um item de fonte nacional como "do Algarve"
TERMOS_ALGARVE = [
    "algarve", "algarvi",  # algarvio/a/os/as
    "albufeira", "alcoutim", "aljezur", "castro marim", "faro", "lagoa",
    "lagos", "loulé", "loule", "monchique", "olhão", "olhao", "portimão",
    "portimao", "são brás de alportel", "sao bras de alportel", "silves",
    "tavira", "vila do bispo", "vila real de santo antónio",
    "vila real de santo antonio", "quarteira", "vilamoura", "albufeira",
    "universidade do algarve", "ualg",
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS itens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fonte_id INTEGER NOT NULL,
    fonte_nome TEXT,
    url TEXT NOT NULL UNIQUE,
    hash_titulo TEXT NOT NULL,
    titulo TEXT NOT NULL,
    descricao TEXT,
    publicado_em TEXT,
    recolhido_em TEXT NOT NULL,
    estado TEXT NOT NULL DEFAULT 'novo'
        CHECK (estado IN ('novo','classificado','erro','descartado')),
    classificacao TEXT
);
CREATE INDEX IF NOT EXISTS idx_itens_estado ON itens(estado);
CREATE UNIQUE INDEX IF NOT EXISTS idx_itens_hash ON itens(hash_titulo);
"""


def limpar_html(texto: str) -> str:
    texto = re.sub(r"<!\[CDATA\[|\]\]>", "", texto or "")
    texto = re.sub(r"<[^>]+>", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def normalizar(texto: str) -> str:
    """minusculas, sem acentos, sem pontuacao: base do hash de titulo."""
    t = unicodedata.normalize("NFKD", texto.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]", "", t).strip()


def hash_titulo(titulo: str, google_news: bool = False) -> str:
    if google_news:
        # O Google News acrescenta " - Publicacao" ao titulo; remover para
        # que o hash coincida com o do feed directo do mesmo artigo
        titulo = re.sub(r"\s+-\s+[^-]+$", "", titulo)
    return hashlib.sha1(normalizar(titulo).encode()).hexdigest()


def menciona_algarve(texto: str) -> bool:
    t = normalizar(texto)
    return any(normalizar(term) in t for term in TERMOS_ALGARVE)


def data_iso(texto: str):
    if not texto:
        return None
    try:
        return parsedate_to_datetime(texto).astimezone(timezone.utc).isoformat()
    except Exception:
        return None


def obter_feed(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        raiz = ET.fromstring(r.read())
    itens = []
    for item in raiz.iter("item"):  # RSS
        itens.append({
            "titulo": limpar_html(item.findtext("title", "")),
            "url": (item.findtext("link", "") or "").strip(),
            "descricao": limpar_html(item.findtext("description", ""))[:600],
            "publicado_em": data_iso(item.findtext("pubDate", "")),
        })
    if not itens:  # Atom
        ns = {"a": "http://www.w3.org/2005/Atom"}
        for e in raiz.findall("a:entry", ns):
            link = e.find("a:link", ns)
            itens.append({
                "titulo": limpar_html(e.findtext("a:title", "", ns)),
                "url": link.get("href", "").strip() if link is not None else "",
                "descricao": limpar_html(e.findtext("a:summary", "", ns))[:600],
                "publicado_em": e.findtext("a:updated", None, ns),
            })
    return [i for i in itens if i["titulo"] and i["url"]]


def fontes_rss(con_ent):
    return con_ent.execute(
        "SELECT id, nome, ambito, url_recolha FROM entidades "
        "WHERE metodo_acesso='rss' AND verificado=1 AND activo=1 "
        "AND camadas LIKE '%noticias%'").fetchall()


def fetch():
    con_ent = sqlite3.connect(DB_ENT)
    con = sqlite3.connect(DB_MON)
    con.executescript(SCHEMA)
    agora = datetime.now(timezone.utc).isoformat()

    fontes = fontes_rss(con_ent)
    print(f"{len(fontes)} fontes RSS a recolher...\n")
    tot_novos = tot_dup = tot_filtrados = 0
    for fid, nome, ambito, url in fontes:
        try:
            itens = obter_feed(url)
        except Exception as e:
            print(f"--  {nome[:44]:44} ERRO: {str(e)[:60]}")
            continue
        gn = "news.google.com" in (url or "")
        novos = dup = filtrados = 0
        for it in itens:
            # Feeds Google News ja vem filtrados pela propria query (que
            # pesquisa o corpo do artigo, invisivel no RSS); o filtro por
            # titulo+descricao so se aplica aos feeds nacionais directos
            if ambito == "nacional" and not gn and not menciona_algarve(
                    it["titulo"] + " " + it["descricao"]):
                filtrados += 1
                continue
            try:
                con.execute(
                    "INSERT INTO itens (fonte_id, fonte_nome, url, hash_titulo,"
                    " titulo, descricao, publicado_em, recolhido_em)"
                    " VALUES (?,?,?,?,?,?,?,?)",
                    (fid, nome, it["url"], hash_titulo(it["titulo"], gn),
                     it["titulo"], it["descricao"], it["publicado_em"], agora))
                novos += 1
            except sqlite3.IntegrityError:
                dup += 1
        con.commit()
        print(f"OK  {nome[:44]:44} {novos:3d} novos, {dup:3d} dup, "
              f"{filtrados:3d} sem Algarve")
        tot_novos += novos
        tot_dup += dup
        tot_filtrados += filtrados
        time.sleep(0.5)
    print(f"\nTotal: {tot_novos} novos, {tot_dup} duplicados, "
          f"{tot_filtrados} filtrados (sem mencao ao Algarve)")


def stats():
    if not DB_MON.exists():
        print("monitor.db ainda nao existe; corre 'fetch' primeiro.")
        return
    con = sqlite3.connect(DB_MON)
    total = con.execute("SELECT COUNT(*) FROM itens").fetchone()[0]
    print(f"{total} itens no arquivo")
    for estado, n in con.execute(
            "SELECT estado, COUNT(*) FROM itens GROUP BY estado"):
        print(f"  {estado}: {n}")
    print("\nPor fonte (top 15):")
    for nome, n in con.execute(
            "SELECT fonte_nome, COUNT(*) FROM itens GROUP BY fonte_nome "
            "ORDER BY 2 DESC LIMIT 15"):
        print(f"  {n:4d}  {nome}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "fetch"
    {"fetch": fetch, "stats": stats}.get(cmd, fetch)()
