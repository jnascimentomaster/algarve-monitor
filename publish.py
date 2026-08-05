# -*- coding: utf-8 -*-
"""Algarve Monitor: publicacao estatica (site/ -> git push -> Vercel).

O que faz, por ordem:
  1. Garante a pasta site/ com index.html (copia de dashboard.html) e geo.js
  2. Exporta dados.js directamente para site/ (reusa o dashboard.py)
  3. git add site/ + commit datado + push (se houver alteracoes)

O Vercel, ligado ao repositorio com Root Directory = site, redeploya sozinho
a cada push. Correr depois do enrich no lote diario, ou a mao.

Uso (na pasta do projecto, com git ja configurado):
    python publish.py           # exporta + commit + push
    python publish.py --dry     # exporta e mostra o que faria, sem git
"""
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
PASTA = Path(__file__).parent
SITE = PASTA / "site"


def correr(cmd):
    r = subprocess.run(cmd, cwd=PASTA, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)}\n{r.stderr.strip()}")
    return r.stdout.strip()


def exportar():
    SITE.mkdir(exist_ok=True)
    # index.html e geo.js: copiar se a origem for mais recente
    for origem, destino in [(PASTA / "dashboard.html", SITE / "index.html"),
                            (PASTA / "geo.js", SITE / "geo.js")]:
        if not origem.exists():
            raise FileNotFoundError(f"falta {origem.name} na pasta do projecto")
        if not destino.exists() or origem.stat().st_mtime > destino.stat().st_mtime:
            shutil.copyfile(origem, destino)
            print(f"copiado {origem.name} -> site/{destino.name}")
    # dados.js: exportar directamente para site/ reutilizando o dashboard.py
    import dashboard
    dashboard.SAIDA = SITE / "dados.js"
    dashboard.main()


def publicar():
    correr(["git", "add", "site"])
    sem_alteracoes = subprocess.run(
        ["git", "diff", "--cached", "--quiet"], cwd=PASTA).returncode == 0
    if sem_alteracoes:
        print("site/ sem alteracoes; nada a publicar")
        return
    msg = "publicação " + datetime.now().strftime("%Y-%m-%d %H:%M")
    correr(["git", "commit", "-m", msg])
    print(correr(["git", "push"]))
    print(f"publicado: {msg}")


if __name__ == "__main__":
    exportar()
    if "--dry" in sys.argv:
        print("(dry run: sem git)")
    else:
        publicar()
