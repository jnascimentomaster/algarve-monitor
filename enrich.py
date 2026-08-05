# -*- coding: utf-8 -*-
"""Algarve Monitor: classificacao de itens (modulo 2 do pipeline).

Processa itens com estado='novo' do monitor.db via Ollama (qwen3:30b-instruct)
com structured outputs. Correccoes face ao teste de 2026-08-04:
  - municipio e um enum fechado (16 concelhos + regiao + fora_do_algarve +
    indeterminado); acabou o "Sines" e o "Bordeira"
  - entidades excluem toponimos e so sao extraidas se relevancia >= 3
  - itens de fora do Algarve ou irrelevantes ficam marcados e saem da frente

Uso (na pasta com monitor.db, Ollama a correr):
    python enrich.py run              # processa toda a fila
    python enrich.py run --limit 20   # processa 20 (para testar)
    python enrich.py stats            # distribuicoes apos classificacao
"""
import json
import sqlite3
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

PASTA = Path(__file__).parent
DB = PASTA / "monitor.db"
OLLAMA = "http://localhost:11434/api/chat"
MODELO = "qwen3:30b-instruct"
MAX_TENTATIVAS = 2

CONCELHOS = ["Albufeira", "Alcoutim", "Aljezur", "Castro Marim", "Faro",
             "Lagoa", "Lagos", "Loulé", "Monchique", "Olhão", "Portimão",
             "São Brás de Alportel", "Silves", "Tavira", "Vila do Bispo",
             "Vila Real de Santo António"]

SCHEMA = {
    "type": "object",
    "properties": {
        "categoria": {"type": "string",
                      "enum": ["tech", "inovacao", "negocios", "turismo",
                               "regional", "irrelevante"]},
        "relevancia": {"type": "integer", "minimum": 0, "maximum": 10},
        "municipio": {"type": "string",
                      "enum": CONCELHOS + ["regiao", "fora_do_algarve",
                                           "indeterminado"]},
        "entidades": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "nome": {"type": "string"},
                "tipo": {"type": "string",
                         "enum": ["empresa", "pessoa", "organizacao", "evento"]}},
            "required": ["nome", "tipo"]}},
        "sinal": {"type": "string",
                  "enum": ["investimento", "financiamento_publico",
                           "aquisicao", "nova_empresa_ou_abertura",
                           "expansao_ou_contratacao", "encerramento_ou_saida",
                           "parceria", "nomeacao", "evento_anunciado",
                           "dados_ou_estudo", "nenhum"]},
        "montante_eur": {"type": ["number", "null"]},
        "resumo": {"type": "string"},
    },
    "required": ["categoria", "relevancia", "municipio", "entidades",
                 "sinal", "montante_eur", "resumo"],
}

PROMPT = (
    "Es o classificador do Algarve Monitor, um observatorio do ecossistema de "
    "inovacao e economia do Algarve.\n"
    "categoria (uma so): tech (tecnologia, software, digital), inovacao (I&D, "
    "universidades, patentes, projectos de startups), negocios (empresas, "
    "investimento, financiamento, emprego, imobiliario comercial), turismo "
    "(hotelaria, alojamento, aviacao, restauracao enquanto sector economico), "
    "regional (politica local, infraestrutura, ambiente, sociedade), "
    "irrelevante (desporto, crime, meteorologia, cultura sem dimensao "
    "economica).\n"
    "relevancia (interesse para quem acompanha inovacao e economia regional). "
    "Ancoras: 0-2 nenhum (crime, desporto, meteorologia, festas, comunicados "
    "sem substancia); 3-5 contexto (formacoes e cursos, eventos solidarios, "
    "sessoes de esclarecimento, politica nacional relacionada com a regiao, "
    "comunicados institucionais de actividade corrente); 6-8 relevante "
    "(financiamento aprovado a entidade da regiao, empresa a expandir ou a "
    "contratar, novo projecto de I&D com parceiros e verba, dados economicos "
    "novos da regiao); 9-10 essencial (grande investimento, nova empresa ou "
    "infraestrutura relevante, decisao com impacto estrutural no ecossistema). "
    "Na duvida entre dois niveis escolhe o mais baixo; num dia normal a "
    "maioria das noticias fica entre 2 e 5.\n"
    "municipio: o concelho do Algarve a que a noticia respeita; usa o concelho "
    "mesmo quando o texto refere uma freguesia ou localidade (ex.: Bordeira -> "
    "Aljezur, Quarteira e Vilamoura -> Loulé, Altura -> Castro Marim). "
    "'regiao' APENAS quando o assunto e especificamente o Algarve no seu "
    "conjunto (varios concelhos, entidades regionais, dados da regiao). "
    "REGRA POR OMISSAO: se o titulo e o texto nao mencionarem explicitamente "
    "o Algarve, um concelho algarvio ou uma entidade algarvia, entao NAO e "
    "'regiao' nem um concelho: e 'fora_do_algarve'. Noticias sobre Portugal "
    "no seu todo, organismos nacionais ou rankings nacionais sao "
    "'fora_do_algarve' (ex.: 'Portugal no top 5 dos startup hubs' -> "
    "fora_do_algarve; 'Startup Portugal lanca programa' -> fora_do_algarve; "
    "nomeacao do presidente do Turismo de Portugal -> fora_do_algarve; "
    "Alentejo, Sines, Lisboa -> fora_do_algarve). "
    "'indeterminado' se nao der para saber.\n"
    "entidades: apenas empresas, pessoas, organizacoes e eventos mencionados "
    "explicitamente no texto. NUNCA incluas lugares, ruas, paises ou cidades "
    "como entidades. Se relevancia <= 2, devolve entidades como lista vazia.\n"
    "sinal: o acontecimento concreto que a noticia reporta, se existir: "
    "investimento (privado anunciado ou concretizado), financiamento_publico "
    "(fundos PT2030/PRR/europeus atribuidos), aquisicao (compra e venda de "
    "empresas ou activos), nova_empresa_ou_abertura (empresa, hotel, unidade, "
    "campus novos), expansao_ou_contratacao, encerramento_ou_saida, parceria "
    "(acordos entre organizacoes), nomeacao (lideranca de entidade relevante), "
    "evento_anunciado (conferencia, summit, feira futura), dados_ou_estudo "
    "(estatisticas, rankings, relatorios novos), nenhum (opiniao, contexto, "
    "actividade corrente). Escolhe 'nenhum' sempre que nao ha acontecimento "
    "concreto.\n"
    "montante_eur: o valor em euros mencionado, convertido para numero "
    "(ex.: '11 M\u20ac' -> 11000000, '750 mil euros' -> 750000); null se nao "
    "houver valor. Nao converta valores noutras moedas: null.\n"
    "resumo: uma frase em portugues europeu.\n"
    "Responde apenas com o JSON pedido."
)


def classificar(titulo: str, descricao: str):
    pedido = {
        "model": MODELO, "stream": False, "format": SCHEMA,
        "options": {"temperature": 0},
        "messages": [
            {"role": "system", "content": PROMPT},
            {"role": "user", "content": f"Titulo: {titulo}\nTexto: {descricao or '(sem texto)'}"},
        ],
    }
    req = urllib.request.Request(
        OLLAMA, data=json.dumps(pedido).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        resposta = json.loads(r.read())
    return json.loads(resposta["message"]["content"])


from harvest_news import menciona_algarve


def guarda_geografica(out: dict, titulo: str, descricao: str) -> dict:
    """O modelo so pode afirmar geografia algarvia se o texto visivel a
    suportar. Sem termo algarvio no titulo+descricao, 'regiao' ou concelho
    passam a 'indeterminado' (o artigo pode ser do Algarve no corpo, que
    nao vemos; 'indeterminado' e o estado honesto)."""
    if out.get("municipio") not in ("fora_do_algarve", "indeterminado") \
            and not menciona_algarve(f"{titulo} {descricao or ''}"):
        out["municipio"] = "indeterminado"
        out["geo_forcado"] = True
    return out


def run():
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])
    con = sqlite3.connect(DB)
    fila = con.execute(
        "SELECT id, titulo, descricao FROM itens WHERE estado='novo' "
        "ORDER BY id" + (f" LIMIT {limit}" if limit else "")).fetchall()
    print(f"{len(fila)} itens a classificar com {MODELO}...\n")
    t_ini, feitos, erros = time.time(), 0, 0
    for iid, titulo, descricao in fila:
        out, erro = None, None
        for _ in range(MAX_TENTATIVAS):
            try:
                out = guarda_geografica(classificar(titulo, descricao),
                                        titulo, descricao)
                break
            except Exception as e:
                erro = str(e)[:200]
        agora = datetime.now(timezone.utc).isoformat()
        if out:
            con.execute(
                "UPDATE itens SET estado='classificado', classificacao=? "
                "WHERE id=?", (json.dumps(out, ensure_ascii=False), iid))
            feitos += 1
            print(f"{iid:5d} [{out['categoria']:>11}] rel={out['relevancia']} "
                  f"mun={out['municipio'][:22]:22} {titulo[:52]}")
        else:
            con.execute("UPDATE itens SET estado='erro', classificacao=? "
                        "WHERE id=?", (json.dumps({"erro": erro, "em": agora}), iid))
            erros += 1
            print(f"{iid:5d} ERRO: {erro[:80]}")
        con.commit()
        if feitos and feitos % 25 == 0:
            media = (time.time() - t_ini) / (feitos + erros)
            resta = media * (len(fila) - feitos - erros) / 60
            print(f"--- {feitos} feitos, media {media:.1f}s/item, "
                  f"~{resta:.0f} min restantes ---")
    dur = (time.time() - t_ini) / 60
    print(f"\n{feitos} classificados, {erros} erros, {dur:.1f} min")


def stats():
    con = sqlite3.connect(DB)
    print("Estados:")
    for e, n in con.execute("SELECT estado, COUNT(*) FROM itens GROUP BY estado"):
        print(f"  {e}: {n}")
    linhas = con.execute("SELECT classificacao FROM itens "
                         "WHERE estado='classificado'").fetchall()
    if not linhas:
        return
    cats, muns, rel_alta = {}, {}, 0
    for (c,) in linhas:
        d = json.loads(c)
        cats[d["categoria"]] = cats.get(d["categoria"], 0) + 1
        muns[d["municipio"]] = muns.get(d["municipio"], 0) + 1
        if d["relevancia"] >= 6:
            rel_alta += 1
    print("\nCategorias:")
    for k, v in sorted(cats.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")
    print(f"\nRelevancia >= 6: {rel_alta} de {len(linhas)}")
    print("\nMunicipios (top 10):")
    for k, v in sorted(muns.items(), key=lambda x: -x[1])[:10]:
        print(f"  {k}: {v}")


def reset():
    """Volta a por os classificados na fila (para reclassificar apos
    alteracao do prompt). Nao mexe nos que deram erro."""
    con = sqlite3.connect(DB)
    cur = con.execute("UPDATE itens SET estado='novo', classificacao=NULL "
                      "WHERE estado='classificado'")
    con.commit()
    print(f"{cur.rowcount} itens de volta a fila 'novo'")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    {"run": run, "stats": stats, "reset": reset}.get(cmd, run)()
