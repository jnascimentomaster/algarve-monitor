# -*- coding: utf-8 -*-
"""Gera a base de dados de entidades do Algarve Monitor.

Saidas: entidades.db (SQLite), entidades_seed.sql, entidades.csv
Todos os URLs de recolha estao marcados verificado=0 ate o passo de
validacao de feeds correr (equivalente ao harvest.py check do sistema
LinkedIn). Nao assumir que funcionam.
"""
import csv
import sqlite3
from pathlib import Path

OUT = Path(__file__).parent

# (nome, tipo, ambito, municipio, website, metodo, url_recolha, camadas, prioridade, notas)
E = []

# --- Camaras municipais (16) -------------------------------------------------
camaras = [
    ("Câmara Municipal de Albufeira", "Albufeira", "https://www.cm-albufeira.pt"),
    ("Câmara Municipal de Alcoutim", "Alcoutim", "https://www.cm-alcoutim.pt"),
    ("Câmara Municipal de Aljezur", "Aljezur", "https://www.cm-aljezur.pt"),
    ("Câmara Municipal de Castro Marim", "Castro Marim", "https://www.cm-castromarim.pt"),
    ("Câmara Municipal de Faro", "Faro", "https://www.cm-faro.pt"),
    ("Câmara Municipal de Lagoa", "Lagoa", "https://www.cm-lagoa.pt"),
    ("Câmara Municipal de Lagos", "Lagos", "https://www.cm-lagos.pt"),
    ("Câmara Municipal de Loulé", "Loulé", "https://www.cm-loule.pt"),
    ("Câmara Municipal de Monchique", "Monchique", "https://www.cm-monchique.pt"),
    ("Câmara Municipal de Olhão", "Olhão", "https://www.cm-olhao.pt"),
    ("Câmara Municipal de Portimão", "Portimão", "https://www.cm-portimao.pt"),
    ("Câmara Municipal de São Brás de Alportel", "São Brás de Alportel", "https://www.cm-sbras.pt"),
    ("Câmara Municipal de Silves", "Silves", "https://www.cm-silves.pt"),
    ("Câmara Municipal de Tavira", "Tavira", "https://www.cm-tavira.pt"),
    ("Câmara Municipal de Vila do Bispo", "Vila do Bispo", "https://www.cm-viladobispo.pt"),
    ("Câmara Municipal de Vila Real de Santo António", "Vila Real de Santo António", "https://www.cm-vrsa.pt"),
]
for nome, mun, site in camaras:
    E.append((nome, "camara_municipal", "municipal", mun, site, "rss",
              site + "/feed", "noticias,eventos", 2,
              "Testar /feed e pagina de noticias; muitas camaras nao tem RSS e passam a scrape"))

# --- Instituicoes regionais e agencias --------------------------------------
E += [
    ("CCDR Algarve", "agencia_publica", "regional", None, "https://www.ccdr-alg.pt",
     "rss", "https://www.ccdr-alg.pt/feed", "noticias,financiamento", 1,
     "Fundos regionais, avisos PT2030, noticias institucionais"),
    ("AMAL - Comunidade Intermunicipal do Algarve", "agencia_publica", "regional", None,
     "https://www.amal.pt", "scrape", None, "noticias", 2, None),
    ("Turismo do Algarve (RTA)", "agencia_publica", "regional", None,
     "https://www.turismodoalgarve.pt", "scrape", None, "noticias,turismo,eventos", 1,
     "Inclui Observatorio de Turismo Sustentavel (relatorios anuais)"),
    ("Universidade do Algarve", "universidade", "regional", "Faro", "https://www.ualg.pt",
     "rss", "https://www.ualg.pt/rss", "noticias,eventos,investigacao", 1,
     "Noticias e agenda; producao cientifica via OpenAlex, nao daqui"),
    ("CRIA - Divisão de Empreendedorismo e Transferência de Tecnologia (UAlg)", "incubadora",
     "regional", "Faro", "https://www.ualg.pt/cria", "scrape", None,
     "noticias,empresas", 1, "Spinoffs e projectos incubados alimentam o directorio"),
    ("DRAP Algarve", "agencia_publica", "regional", None, "https://www.drapalgarve.gov.pt",
     "scrape", None, "noticias", 3, "Agroalimentar; prioridade baixa no v1"),
]

# --- Associacoes empresariais e do ecossistema -------------------------------
E += [
    ("Algarve Evolution", "associacao", "regional", "Faro", "https://algarveevolution.pt",
     "manual", None, "noticias,eventos,empresas", 1,
     "Fonte interna: agenda propria, rede de startups, ATH Summit"),
    ("Algarve Tech Hub", "associacao", "regional", None, "https://algarvetechhub.com",
     "scrape", None, "noticias,eventos,empresas", 1, "Confirmar estado actual do site"),
    ("Algarve STP - Science and Technology Park", "incubadora", "regional", "Loulé",
     "https://algarvestp.pt", "scrape", None, "noticias,empresas", 1,
     "Confirmar dominio e estado; historicamente ligado a UAlg/Loule"),
    ("NERA - Associação Empresarial da Região do Algarve", "associacao", "regional", "Loulé",
     "https://www.nera.pt", "rss", "https://www.nera.pt/feed", "noticias,eventos", 1, None),
    ("ACRAL - Associação do Comércio e Serviços da Região do Algarve", "associacao",
     "regional", "Faro", "https://www.acral.pt", "scrape", None, "noticias", 2, None),
    ("AHETA - Associação dos Hotéis e Empreendimentos Turísticos do Algarve", "associacao",
     "regional", None, "https://www.aheta.pt", "scrape", None, "noticias,turismo", 2,
     "Barometros mensais de ocupacao hoteleira"),
    ("AIHSA - Associação dos Industriais Hoteleiros e Similares do Algarve", "associacao",
     "regional", None, None, "manual", None, "noticias,turismo", 3, "Confirmar presenca online"),
    ("ANJE - Núcleo do Algarve", "associacao", "regional", "Faro", "https://anje.pt",
     "rss", "https://anje.pt/feed", "noticias,eventos", 2,
     "VERIFICADO 2026-08-04: Rua Mouzinho de Albuquerque 5-A, Faro; anjealgarve@anje.pt; "
     "site nacional, filtrar por Algarve; Facebook local sem recolha automatica"),
    ("Centro de Incubação e Aceleração de Faro (ANJE)", "incubadora", "municipal", "Faro",
     "https://anje.pt/linc/faro/", "manual", None, "empresas,eventos", 1,
     "VERIFICADO 2026-08-04: incubadora do nucleo Algarve da ANJE, baixa de Faro; "
     "empresas incubadas alimentam o directorio via levantamento manual"),
    ("ABC - Algarve Biomedical Center", "associacao", "regional", "Faro/Loulé",
     "https://abcmedical.pt", "scrape", None, "noticias,investigacao", 2,
     "Confirmar dominio; inclui ABC CoLAB"),
    ("Startup Portimão", "incubadora", "municipal", "Portimão", None, "manual", None,
     "noticias,empresas,eventos", 2, "Confirmar nome oficial e estado da incubadora municipal"),
    ("Incubadoras municipais (levantamento)", "incubadora", "regional", None, None,
     "manual", None, "empresas", 2,
     "Levantar via Rede Nacional de Incubadoras: Loule, Lagos, Tavira, VRSA, etc."),
]

# --- Media local -------------------------------------------------------------
media_local = [
    ("Sul Informação", "https://www.sulinformacao.pt", "https://www.sulinformacao.pt/feed", 1, None),
    ("Barlavento", "https://barlavento.sapo.pt", "https://barlavento.sapo.pt/feed", 1, None),
    ("Postal do Algarve", "https://postal.pt", "https://postal.pt/feed", 1, None),
    ("Jornal do Algarve", "https://jornaldoalgarve.pt", "https://jornaldoalgarve.pt/feed", 1, None),
    ("Região Sul", "https://regiao-sul.pt", "https://regiao-sul.pt/feed", 2, None),
    ("Mais Algarve", "https://www.maisalgarve.pt", "https://www.maisalgarve.pt/feed", 2, None),
    ("Algarve Primeiro", "https://www.algarveprimeiro.com", None, 2, "Sem RSS aparente; scrape"),
    ("Algarve Daily News", "https://algarvedailynews.com", "https://algarvedailynews.com/feed", 2,
     "Em ingles; util para comunidade estrangeira"),
    ("Portugal Resident", "https://www.portugalresident.com", "https://www.portugalresident.com/feed", 2,
     "Em ingles; seccao Algarve"),
]
for nome, site, feed, pri, notas in media_local:
    E.append((nome, "media_local", "regional", None, site,
              "rss" if feed else "scrape", feed, "noticias", pri, notas))

# --- Media nacional (filtro por palavras-chave Algarve + tech) ---------------
media_nacional = [
    ("Público", "https://www.publico.pt", "https://feeds.feedburner.com/PublicoRSS", 2),
    ("Expresso", "https://expresso.pt", "https://expresso.pt/rss", 2),
    ("ECO", "https://eco.sapo.pt", "https://eco.sapo.pt/feed", 1),
    ("Jornal de Negócios", "https://www.jornaldenegocios.pt", "https://www.jornaldenegocios.pt/rss", 2),
    ("Observador", "https://observador.pt", "https://observador.pt/feed", 2),
    ("Dinheiro Vivo", "https://www.dinheirovivo.pt", "https://www.dinheirovivo.pt/rss", 2),
    ("SAPO Tek", "https://tek.sapo.pt", "https://tek.sapo.pt/rss", 1),
    ("Exame Informática", "https://visao.pt/exameinformatica", None, 3),
    ("Jornal Económico", "https://jornaleconomico.pt", "https://jornaleconomico.pt/feed", 2),
    ("Startup Portugal", "https://startupportugal.com", None, 2),
]
for item in media_nacional:
    nome, site, feed, pri = item
    E.append((nome, "media_nacional", "nacional", None, site,
              "rss" if feed else "scrape", feed, "noticias", pri,
              "Filtrar por 'Algarve' + concelhos + entidades do directorio"))

# --- Fontes de dados estruturados -------------------------------------------
E += [
    ("INE - Instituto Nacional de Estatística", "fonte_dados", "nacional", None,
     "https://www.ine.pt", "api",
     "https://www.ine.pt/ine/json_indicador/pindica.jsp", "empresas,turismo,economia", 1,
     "API JSON por indicador; dormidas, constituicoes, desemprego, licencas por concelho"),
    ("PORDATA", "fonte_dados", "nacional", None, "https://www.pordata.pt", "manual", None,
     "economia", 3, "Backup do INE; sem API estavel"),
    ("dados.gov.pt", "fonte_dados", "nacional", None, "https://dados.gov.pt", "api",
     "https://dados.gov.pt/api/1/", "empresas,turismo,economia", 2,
     "Inclui dataset RNAL (alojamento local) e Empresa Online"),
    ("IEFP - estatísticas mensais de desemprego", "fonte_dados", "nacional", None,
     "https://www.iefp.pt/estatisticas", "scrape", None, "economia", 1,
     "Desemprego registado por concelho, mensal, ficheiros Excel"),
    ("BASE.gov.pt - contratos públicos", "fonte_dados", "nacional", None,
     "https://www.base.gov.pt", "api", "https://www.base.gov.pt/Base4/pt/resultados/",
     "financiamento", 2, "Contratos tech de entidades algarvias"),
    ("PT2030 - lista de operações aprovadas", "fonte_dados", "nacional", None,
     "https://portugal2030.pt", "scrape", None, "financiamento", 1,
     "Beneficiario + concelho + montante; publicacao periodica em CSV/Excel"),
    ("PRR - Recuperar Portugal (beneficiários)", "fonte_dados", "nacional", None,
     "https://recuperarportugal.gov.pt", "scrape", None, "financiamento", 1, None),
    ("CORDIS - Horizon Europe", "fonte_dados", "internacional", None,
     "https://cordis.europa.eu", "api", "https://cordis.europa.eu/datalab/", "financiamento,investigacao", 1,
     "Filtrar organizacoes com morada no Algarve"),
    ("OpenAlex", "fonte_dados", "internacional", None, "https://openalex.org", "api",
     "https://api.openalex.org/works?filter=institutions.ror:", "investigacao", 2,
     "Producao cientifica UAlg e afiliadas; obter ROR id da UAlg"),
    ("EPO OPS - patentes", "fonte_dados", "internacional", None, "https://www.epo.org", "api",
     "https://ops.epo.org", "investigacao", 3, "Registo gratuito; volume baixo, cadencia trimestral"),
    ("OpenSky Network - voos Faro (LPFR)", "fonte_dados", "internacional", None,
     "https://opensky-network.org", "api",
     "https://opensky-network.org/api/flights/arrival?airport=LPFR", "voos", 1,
     "Chegadas/partidas diarias; passageiros mensais via ANA/INE"),
    ("Racius - observatório de empresas", "fonte_dados", "nacional", None,
     "https://www.racius.com/observatorio/", "scrape", None, "empresas", 1,
     "Constituicoes e dissolucoes por distrito/concelho; scrape leve com cache"),
    ("TravelBI - Turismo de Portugal", "fonte_dados", "nacional", None,
     "https://travelbi.turismodeportugal.pt", "scrape", None, "turismo", 2, None),
    ("BPstat - Banco de Portugal", "fonte_dados", "nacional", None,
     "https://bpstat.bportugal.pt", "api", "https://bpstat.bportugal.pt/data/v1/", "economia", 3, None),
    ("Eurostat", "fonte_dados", "internacional", None, "https://ec.europa.eu/eurostat", "api",
     "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/", "economia", 3,
     "NUTS2 Algarve para comparacoes europeias"),
]

# --- Agregadores e canais indirectos ----------------------------------------
GN = "https://news.google.com/rss/search?q={}&hl=pt-PT&gl=PT&ceid=PT:pt"
gnews = [
    ("Google News: Algarve startup", "Algarve+startup"),
    ("Google News: Algarve inovação", "Algarve+inova%C3%A7%C3%A3o"),
    ("Google News: Algarve investimento OR financiamento", "Algarve+(investimento+OR+financiamento)"),
    ("Google News: Algarve tecnologia", "Algarve+tecnologia"),
    ("Google News: Algarve turismo negócios", "Algarve+turismo+neg%C3%B3cios"),
]
for nome, q in gnews:
    E.append((nome, "media_nacional", "nacional", None, "https://news.google.com",
              "rss", GN.format(q), "noticias", 1,
              "Rede de seguranca; links sao redirects (resolver URL final antes de dedupe)"))

E.append(("LinkedIn (curadoria manual via label Gmail)", "fonte_eventos", "internacional", None,
          "https://www.linkedin.com", "email", None, "noticias,empresas,eventos", 1,
          "Sem API de pesquisa; partilhar posts por email para label Gmail 'algarve-monitor', "
          "ingestao via gmail_ingest.py (padrao FirstWord); nao usar scrapers com a conta pessoal"))

# --- Fontes de eventos -------------------------------------------------------
E += [
    ("Eventbrite (pesquisa Algarve)", "fonte_eventos", "internacional", None,
     "https://www.eventbrite.pt", "api", None, "eventos", 2,
     "API exige token; alternativa scrape da pesquisa por localizacao"),
    ("Meetup (grupos Algarve)", "fonte_eventos", "internacional", None,
     "https://www.meetup.com", "scrape", None, "eventos", 3,
     "API paga desde 2023; scrape dos grupos conhecidos"),
    ("Agenda UAlg", "fonte_eventos", "regional", "Faro", "https://www.ualg.pt/agenda",
     "scrape", None, "eventos", 2, None),
    ("ATH Summit", "fonte_eventos", "regional", None, None, "manual", None, "eventos", 1,
     "Confirmar dominio do site do summit"),
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS entidades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL UNIQUE,
    tipo TEXT NOT NULL CHECK (tipo IN (
        'camara_municipal','agencia_publica','associacao','incubadora',
        'universidade','media_local','media_nacional','fonte_dados','fonte_eventos')),
    ambito TEXT CHECK (ambito IN ('municipal','regional','nacional','internacional')),
    municipio TEXT,
    website TEXT,
    metodo_acesso TEXT CHECK (metodo_acesso IN ('rss','api','scrape','manual','email')),
    url_recolha TEXT,
    camadas TEXT,            -- csv: noticias,eventos,financiamento,empresas,turismo,voos,investigacao,economia
    prioridade INTEGER DEFAULT 2,  -- 1 alta (v1), 2 media, 3 baixa (fases seguintes)
    verificado INTEGER DEFAULT 0,  -- 0 ate o check de feeds/APIs correr
    activo INTEGER DEFAULT 1,
    ultima_verificacao TEXT,
    notas TEXT
);
"""

def main():
    db = OUT / "entidades.db"
    db.unlink(missing_ok=True)
    con = sqlite3.connect(db)
    con.executescript(SCHEMA)
    con.executemany(
        """INSERT INTO entidades
           (nome, tipo, ambito, municipio, website, metodo_acesso, url_recolha,
            camadas, prioridade, notas)
           VALUES (?,?,?,?,?,?,?,?,?,?)""", E)
    con.commit()

    # SQL de seed (para migrar para Supabase/Postgres com ajustes minimos)
    with open(OUT / "entidades_seed.sql", "w", encoding="utf-8") as f:
        f.write("-- Algarve Monitor: seed de entidades. verificado=0 ate validacao.\n")
        f.write(SCHEMA + "\n")
        for row in con.execute(
            "SELECT nome,tipo,ambito,municipio,website,metodo_acesso,url_recolha,"
            "camadas,prioridade,notas FROM entidades"):
            vals = ",".join(
                "NULL" if v is None else
                str(v) if isinstance(v, int) else
                "'" + str(v).replace("'", "''") + "'" for v in row)
            f.write(f"INSERT INTO entidades (nome,tipo,ambito,municipio,website,"
                    f"metodo_acesso,url_recolha,camadas,prioridade,notas) VALUES ({vals});\n")

    # CSV para revisao humana
    with open(OUT / "entidades.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["nome","tipo","ambito","municipio","website","metodo_acesso",
                    "url_recolha","camadas","prioridade","notas"])
        w.writerows(E)

    n = con.execute("SELECT COUNT(*) FROM entidades").fetchone()[0]
    por_tipo = con.execute(
        "SELECT tipo, COUNT(*) FROM entidades GROUP BY tipo ORDER BY 2 DESC").fetchall()
    print(f"{n} entidades")
    for t, c in por_tipo:
        print(f"  {t}: {c}")

if __name__ == "__main__":
    main()
