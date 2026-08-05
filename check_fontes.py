# -*- coding: utf-8 -*-
"""Validacao das fontes do Algarve Monitor.

Le entidades.db (na mesma pasta), testa cada fonte a partir desta maquina e
actualiza a base: verificado=1 quando ha um feed/endpoint a responder,
ultima_verificacao com a data, e nota com o resultado. Gera check_report.csv.

O que testa, por metodo de acesso:
  rss    valida que o URL devolve XML de feed com itens; se falhar, tenta
         variantes comuns (/feed/, /rss, /?feed=rss2, /noticias/feed) e,
         se alguma funcionar, corrige url_recolha na base
  api    considera alcancavel qualquer resposta HTTP < 500 (endpoints como o
         do INE exigem parametros; 400 significa servidor vivo)
  scrape testa que o website responde 200
  manual/email  ignorado (nao ha nada para testar)

Uso (PowerShell, na pasta com entidades.db):
    python check_fontes.py
"""
import concurrent.futures as cf
import csv
import datetime
import json
import sqlite3
import ssl
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

DB = Path(__file__).parent / "entidades.db"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
TIMEOUT = 25
VARIANTES_RSS = ["/feed", "/feed/", "/rss", "/?feed=rss2", "/noticias/feed"]


def pedir(url, contexto_ssl=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                               "Accept": "*/*"})
    return urllib.request.urlopen(req, timeout=TIMEOUT, context=contexto_ssl)


def obter(url):
    """Devolve (codigo_http, corpo_bytes, ssl_invalido)."""
    try:
        with pedir(url) as r:
            return r.status, r.read(400_000), False
    except urllib.error.HTTPError as e:
        return e.code, b"", False
    except (ssl.SSLError, urllib.error.URLError) as e:
        causa = getattr(e, "reason", e)
        if isinstance(causa, ssl.SSLError) or "SSL" in str(e).upper() \
                or "CERTIFICATE" in str(e).upper():
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            try:
                with pedir(url, ctx) as r:
                    return r.status, r.read(400_000), True
            except Exception as e2:
                raise RuntimeError(f"ssl e fallback falharam: {e2}") from e2
        raise


def e_feed(corpo: bytes):
    """Devolve numero de itens se for um feed RSS/Atom valido, senao None."""
    try:
        raiz = ET.fromstring(corpo)
    except ET.ParseError:
        return None
    tag = raiz.tag.lower()
    if tag.endswith("rss") or tag.endswith("rdf"):
        return sum(1 for _ in raiz.iter("item"))
    if tag.endswith("feed"):  # Atom
        return sum(1 for e in raiz.iter() if e.tag.lower().endswith("entry"))
    return None


def testar(ent):
    eid, nome, metodo, url_recolha, website = ent
    res = {"id": eid, "nome": nome, "metodo": metodo, "estado": "",
           "detalhe": "", "novo_url": None}
    try:
        if metodo == "rss":
            candidatos = []
            if url_recolha:
                candidatos.append(url_recolha)
            if website:
                base = website.rstrip("/")
                candidatos += [base + v for v in VARIANTES_RSS
                               if base + v != url_recolha]
            for i, url in enumerate(candidatos):
                try:
                    cod, corpo, ssl_inv = obter(url)
                except Exception:
                    continue
                n = e_feed(corpo) if cod == 200 else None
                if n is not None and n > 0:
                    res["estado"] = "ok_ssl_invalido" if ssl_inv else "ok"
                    res["detalhe"] = f"{n} itens em {url}"
                    if i > 0 or url != url_recolha:
                        res["novo_url"] = url
                    return res
            res["estado"] = "sem_feed"
            res["detalhe"] = f"{len(candidatos)} URLs testados, nenhum feed valido"
        elif metodo == "api":
            alvo = url_recolha or website
            cod, _, ssl_inv = obter(alvo)
            if cod < 500:
                res["estado"] = "ok_ssl_invalido" if ssl_inv else "ok"
                res["detalhe"] = f"HTTP {cod} em {alvo}"
            else:
                res["estado"] = "erro_servidor"
                res["detalhe"] = f"HTTP {cod}"
        elif metodo == "scrape":
            alvo = website or url_recolha
            if not alvo:
                res["estado"] = "sem_url"
                return res
            cod, corpo, ssl_inv = obter(alvo)
            if cod == 200:
                res["estado"] = "ok_ssl_invalido" if ssl_inv else "ok"
                res["detalhe"] = f"site responde ({len(corpo)} bytes)"
            else:
                res["estado"] = "falha"
                res["detalhe"] = f"HTTP {cod}"
        else:
            res["estado"] = "ignorado"
    except Exception as e:
        res["estado"] = "falha"
        res["detalhe"] = str(e)[:160]
    return res


def main():
    if not DB.exists():
        print(f"Nao encontro {DB}. Poe o entidades.db na mesma pasta.")
        sys.exit(1)
    con = sqlite3.connect(DB)
    ents = con.execute(
        "SELECT id, nome, metodo_acesso, url_recolha, website FROM entidades "
        "WHERE activo=1").fetchall()
    print(f"{len(ents)} entidades a testar (manual/email sao ignoradas)...\n")

    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        resultados = list(ex.map(testar, ents))

    hoje = datetime.date.today().isoformat()
    for r in sorted(resultados, key=lambda x: (x["estado"], x["nome"])):
        if r["estado"] == "ignorado":
            continue
        marca = {"ok": "OK ", "ok_ssl_invalido": "OK!"}.get(r["estado"], "-- ")
        extra = f"  -> url corrigido: {r['novo_url']}" if r["novo_url"] else ""
        print(f"{marca} [{r['estado']:>15}] {r['nome'][:48]:48} {r['detalhe'][:70]}{extra}")
        ok = r["estado"].startswith("ok")
        con.execute(
            "UPDATE entidades SET verificado=?, ultima_verificacao=?, "
            "notas=COALESCE(notas,'') || ? WHERE id=?",
            (1 if ok else 0, hoje,
             f" | check {hoje}: {r['estado']} ({r['detalhe'][:100]})", r["id"]))
        if r["novo_url"]:
            con.execute("UPDATE entidades SET url_recolha=? WHERE id=?",
                        (r["novo_url"], r["id"]))
    con.commit()

    with open(DB.parent / "check_report.csv", "w", encoding="utf-8-sig",
              newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "nome", "metodo", "estado",
                                          "detalhe", "novo_url"])
        w.writeheader()
        w.writerows(resultados)

    contagem = {}
    for r in resultados:
        contagem[r["estado"]] = contagem.get(r["estado"], 0) + 1
    print("\nResumo: " + json.dumps(contagem, ensure_ascii=False))
    print("Base actualizada e relatorio em check_report.csv")


if __name__ == "__main__":
    main()
