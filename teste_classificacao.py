# -*- coding: utf-8 -*-
"""Teste de classificacao Algarve Monitor.

1. Descarrega o feed RSS do Sul Informacao (valida a fonte a partir da tua rede).
2. Classifica os 10 itens mais recentes com dois modelos Ollama, usando
   structured outputs (JSON schema estrito): categoria fechada, entidades
   tipadas, municipio, relevancia.
3. Imprime resultados e tempos por modelo.

Requisitos: Python 3.9+, Ollama a correr (ollama serve arranca sozinho no
Windows). Sem dependencias externas.

Uso (PowerShell):
    python teste_classificacao.py
"""
import json
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET

sys.stdout.reconfigure(encoding="utf-8")

FEED_URL = "https://www.sulinformacao.pt/feed"
OLLAMA = "http://localhost:11434/api/chat"
MODELOS = ["qwen3:30b-instruct", "qwen3:8b"]
N_ITENS = 10

SCHEMA = {
    "type": "object",
    "properties": {
        "categoria": {
            "type": "string",
            "enum": ["tech", "inovacao", "negocios", "turismo", "regional", "irrelevante"],
        },
        "relevancia": {"type": "integer", "minimum": 0, "maximum": 10},
        "municipio": {
            "type": ["string", "null"],
            "description": "Um dos 16 concelhos do Algarve, 'regiao' se for regional, null se nao aplicavel",
        },
        "entidades": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "nome": {"type": "string"},
                    "tipo": {"type": "string",
                             "enum": ["empresa", "pessoa", "organizacao", "evento"]},
                },
                "required": ["nome", "tipo"],
            },
        },
        "resumo": {"type": "string", "description": "Uma frase em portugues"},
    },
    "required": ["categoria", "relevancia", "municipio", "entidades", "resumo"],
}

PROMPT_SISTEMA = (
    "Es um classificador de noticias para um monitor do ecossistema de inovacao "
    "do Algarve. Classificas cada noticia numa unica categoria: "
    "tech (tecnologia, software, digital), inovacao (I&D, universidades, patentes, "
    "startups em fase de projecto), negocios (empresas, investimento, financiamento, "
    "emprego), turismo (hotelaria, alojamento, viagens, restauracao como negocio), "
    "regional (politica local, infraestrutura, sociedade), ou irrelevante "
    "(desporto, crime, meteorologia, cultura sem dimensao economica). "
    "relevancia mede o interesse para quem acompanha inovacao e economia regional: "
    "0-2 irrelevante, 3-5 contexto, 6-8 relevante, 9-10 essencial. "
    "Extrai apenas entidades explicitamente mencionadas no texto. "
    "Responde apenas com o JSON pedido."
)


def limpar_html(texto: str) -> str:
    texto = re.sub(r"<!\[CDATA\[|\]\]>", "", texto or "")
    texto = re.sub(r"<[^>]+>", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def obter_feed():
    req = urllib.request.Request(
        FEED_URL,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                               "AppleWebKit/537.36 (KHTML, like Gecko) "
                               "Chrome/126.0 Safari/537.36"})
    with urllib.request.urlopen(req, timeout=30) as r:
        corpo = r.read()
    raiz = ET.fromstring(corpo)
    itens = []
    for item in raiz.iter("item"):
        titulo = limpar_html(item.findtext("title", ""))
        desc = limpar_html(item.findtext("description", ""))
        if titulo:
            itens.append({"titulo": titulo, "desc": desc[:400]})
    return itens


def classificar(modelo: str, item: dict):
    pedido = {
        "model": modelo,
        "stream": False,
        "format": SCHEMA,
        "options": {"temperature": 0},
        "messages": [
            {"role": "system", "content": PROMPT_SISTEMA},
            {"role": "user",
             "content": f"Titulo: {item['titulo']}\nTexto: {item['desc']}"},
        ],
    }
    if modelo == "qwen3:8b":
        pedido["think"] = False  # desligar thinking no modelo hibrido
    dados = json.dumps(pedido).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA, data=dados, headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=600) as r:
        resposta = json.loads(r.read())
    dt = time.time() - t0
    return json.loads(resposta["message"]["content"]), dt


def main():
    print(f"A descarregar {FEED_URL} ...")
    try:
        itens = obter_feed()
    except Exception as e:
        print(f"FALHA no feed: {e}")
        print("Regista este resultado: a fonte precisa de outro metodo de acesso.")
        sys.exit(1)
    print(f"Feed OK: {len(itens)} itens. A usar os primeiros {N_ITENS}.\n")
    itens = itens[:N_ITENS]

    resultados = {}
    for modelo in MODELOS:
        print(f"=== {modelo} ===")
        tempos, saidas, falhas = [], [], 0
        for i, item in enumerate(itens, 1):
            try:
                out, dt = classificar(modelo, item)
                tempos.append(dt)
                saidas.append(out)
                ents = ", ".join(f"{e['nome']}({e['tipo']})"
                                 for e in out.get("entidades", [])) or "-"
                print(f"{i:2d}. [{out['categoria']:>11}] rel={out['relevancia']} "
                      f"mun={out['municipio']} {dt:5.1f}s | {item['titulo'][:60]}")
                print(f"    entidades: {ents}")
            except Exception as e:
                falhas += 1
                print(f"{i:2d}. ERRO: {e} | {item['titulo'][:60]}")
        if tempos:
            total = sum(tempos)
            print(f"\n{modelo}: {len(tempos)} ok, {falhas} falhas, "
                  f"media {total/len(tempos):.1f}s/item, total {total:.0f}s\n")
        resultados[modelo] = saidas

    # Divergencias de categoria entre modelos, para avaliar onde o 8b se perde
    a, b = (resultados.get(m, []) for m in MODELOS)
    if a and b:
        div = [(i, x["categoria"], y["categoria"])
               for i, (x, y) in enumerate(zip(a, b), 1)
               if x["categoria"] != y["categoria"]]
        print(f"Divergencias de categoria 30b vs 8b: {len(div)} de {min(len(a), len(b))}")
        for i, ca, cb in div:
            print(f"  item {i}: 30b={ca} vs 8b={cb} | {itens[i-1]['titulo'][:60]}")


if __name__ == "__main__":
    main()
