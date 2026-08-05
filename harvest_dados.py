# -*- coding: utf-8 -*-
"""Algarve Monitor: recolha de indicadores estatisticos oficiais (modulo 4).

Acrescenta series estatisticas ao monitor.db, na tabela `indicadores`, sem
tocar no pipeline de noticias (harvest_news.py -> enrich.py -> dashboard.py).

Fontes ligadas:
  INE     API JSON publica (pindica.jsp). Turismo mensal e anual por concelho,
          constituicao de pessoas colectivas por concelho, e movimento do
          aeroporto de Faro (LPFR) por mes.
  IEFP    Desemprego registado por concelho. Ficheiros .ods mensais, lidos
          com zipfile + ElementTree (o .ods e um zip com content.xml), pelo
          que NAO e preciso openpyxl nem odfpy.
  OpenSky Chegadas e partidas diarias em Faro. Exige credenciais OAuth2:
          o acesso anonimo a voos historicos foi encerrado (a API responde
          "You cannot access historical flights"). Sem credenciais o
          conector e saltado com aviso, e o resto do lote corre na mesma.

Credenciais OpenSky (opcionais), por variaveis de ambiente:
    set OPENSKY_CLIENT_ID=...
    set OPENSKY_CLIENT_SECRET=...
Obtem-se em https://opensky-network.org/my-opensky/account (conta gratuita).
Nao ha ficheiro de segredos de proposito: nada de credenciais no repositorio.

Uso (na pasta com monitor.db):
    python harvest_dados.py fetch                 # lote completo
    python harvest_dados.py fetch --fonte ine     # so uma fonte
    python harvest_dados.py fetch --desde 2019 --meses 24
    python harvest_dados.py stats                 # estado das series
"""
import json
import os
import re
import sqlite3
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from datetime import date, datetime, timedelta, timezone
from html import unescape
from io import BytesIO
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

PASTA = Path(__file__).parent
DB = PASTA / "monitor.db"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
TIMEOUT = 90
PAUSA = 0.5          # segundos entre chamadas a mesma fonte

SCHEMA = """
CREATE TABLE IF NOT EXISTS indicadores (
    serie TEXT NOT NULL,
    ambito TEXT NOT NULL,
    periodo TEXT NOT NULL,
    valor REAL,
    unidade TEXT,
    fonte TEXT NOT NULL,
    recolhido_em TEXT NOT NULL,
    PRIMARY KEY (serie, ambito, periodo)
);
CREATE INDEX IF NOT EXISTS idx_ind_serie ON indicadores(serie);
CREATE INDEX IF NOT EXISTS idx_ind_ambito ON indicadores(ambito);
"""

# ---------------------------------------------------------------- geografia
# DICO -> nome exactamente como aparece em geo.js (o mapa do dashboard)
CONCELHOS = {
    "1500801": "Albufeira", "1500802": "Alcoutim", "1500803": "Aljezur",
    "1500804": "Castro Marim", "1500805": "Faro", "1500806": "Lagoa",
    "1500807": "Lagos", "1500808": "Loulé", "1500809": "Monchique",
    "1500810": "Olhão", "1500811": "Portimão",
    "1500812": "São Brás de Alportel", "1500813": "Silves",
    "1500814": "Tavira", "1500815": "Vila do Bispo",
    "1500816": "Vila Real de Santo António",
}
GEOCODS = list(CONCELHOS)

MESES_PT = {"janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3, "abril": 4,
            "maio": 5, "junho": 6, "julho": 7, "agosto": 8, "setembro": 9,
            "outubro": 10, "novembro": 11, "dezembro": 12}
MES_NOME = {v: k for k, v in
            [("janeiro", 1), ("fevereiro", 2), ("março", 3), ("abril", 4),
             ("maio", 5), ("junho", 6), ("julho", 7), ("agosto", 8),
             ("setembro", 9), ("outubro", 10), ("novembro", 11),
             ("dezembro", 12)]}

# ------------------------------------------------------------------- series
# Cada serie INE pode assentar em varios indicadores (varcd) encadeados:
# o INE parte as series quando muda a nomenclatura NUTS. Os codigos foram
# validados um a um contra a API antes de serem fixados aqui.
INE_MUNICIPAL = [
    # (serie, rotulo, unidade, periodicidade, [(varcd, codigo_do_total), ...])
    ("dormidas", "Dormidas em alojamento turístico", "n", "M",
     [("0012088", "T"), ("0010735", "T")]),
    ("hospedes", "Hóspedes em alojamento turístico", "n", "M",
     [("0012089", "T"), ("0010736", "T")]),
    ("constituicoes", "Constituição de pessoas colectivas", "n", "M",
     [("0012244", "TOT"), ("0008067", "TOT")]),
    # Anuais: a serie mensal municipal de turismo so comeca em 2020-01, pelo
    # que a base pre-covid de 2019 pedida na spec so existe em base anual.
    ("dormidas_anual", "Dormidas em alojamento turístico (anual)", "n", "A",
     [("0009877", "T")]),
    ("hospedes_anual", "Hóspedes em alojamento turístico (anual)", "n", "A",
     [("0009876", "T")]),
]

# Aeroporto de Faro: dimensao geografica e o codigo ICAO, nao o DICO.
INE_AEROPORTO = [
    ("voos_aterrados", "Aeronaves aterradas em Faro", "n", "0000865"),
    ("voos_descolados", "Aeronaves descoladas em Faro", "n", "0000864"),
    ("passageiros_desembarcados", "Passageiros desembarcados em Faro", "n",
     "0000862"),
]

ROTULOS = {s[0]: s[1] for s in INE_MUNICIPAL}
ROTULOS.update({s[0]: s[1] for s in INE_AEROPORTO})
ROTULOS["desemprego"] = "Desemprego registado"
ROTULOS["voos_chegadas"] = "Chegadas diárias a Faro"
ROTULOS["voos_partidas"] = "Partidas diárias de Faro"


# ------------------------------------------------------------------ helpers
def log(msg):
    print(msg, flush=True)


def obter(url, dados=None, cabecalhos=None, bruto=False):
    """GET/POST com User-Agent de browser. Devolve texto ou bytes."""
    h = {"User-Agent": UA, "Accept-Language": "pt-PT,pt;q=0.9"}
    if cabecalhos:
        h.update(cabecalhos)
    corpo = dados.encode("utf-8") if isinstance(dados, str) else dados
    req = urllib.request.Request(url, data=corpo, headers=h)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        crus = r.read()
    return crus if bruto else crus.decode("utf-8", "replace")


def iso_do_rotulo(rotulo):
    """'Junho de 2024' -> '2024-06'; '2019' -> '2019'."""
    r = rotulo.strip().lower()
    m = re.fullmatch(r"(\d{4})", r)
    if m:
        return m.group(1)
    m = re.fullmatch(r"([a-zç]+)\s+de\s+(\d{4})", r)
    if m and m.group(1) in MESES_PT:
        return f"{m.group(2)}-{MESES_PT[m.group(1)]:02d}"
    return None


def iso_do_periodo_ine(rotulo):
    """Le PrimeiroPeriodo/UltimoPeriodo dos metadados INE."""
    return iso_do_rotulo(rotulo)


def meses_entre(inicio, fim):
    """inicio/fim em 'AAAA-MM'; devolve lista inclusiva."""
    a, m = int(inicio[:4]), int(inicio[5:7])
    fa, fm = int(fim[:4]), int(fim[5:7])
    out = []
    while (a, m) <= (fa, fm):
        out.append(f"{a:04d}-{m:02d}")
        m += 1
        if m == 13:
            a, m = a + 1, 1
    return out


def lotes(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def gravar(con, linhas):
    """Upsert idempotente. linhas: (serie, ambito, periodo, valor, unid, fonte)"""
    agora = datetime.now(timezone.utc).isoformat(timespec="seconds")
    con.executemany(
        "INSERT OR REPLACE INTO indicadores "
        "(serie, ambito, periodo, valor, unidade, fonte, recolhido_em) "
        "VALUES (?,?,?,?,?,?,?)",
        [(s, a, p, v, u, f, agora) for s, a, p, v, u, f in linhas])
    con.commit()
    return len(linhas)


# --------------------------------------------------------------------- INE
INE_META = "https://www.ine.pt/ine/json_indicador/pindicaMeta.jsp"
INE_DADOS = "https://www.ine.pt/ine/json_indicador/pindica.jsp"


def ine_meta(varcd):
    url = f"{INE_META}?varcd={varcd}&lang=PT"
    d = json.loads(obter(url))
    time.sleep(PAUSA)
    if not isinstance(d, list) or not d:
        raise ValueError(f"metadados vazios para {varcd}")
    return d[0]


def ine_dados(varcd, dim1, extra=None):
    """dim1: lista de codigos de periodo. extra: {'Dim2': '...', 'Dim3': '...'}"""
    q = {"op": "2", "varcd": varcd, "Dim1": ",".join(dim1), "lang": "PT"}
    if extra:
        q.update(extra)
    url = INE_DADOS + "?" + urllib.parse.urlencode(q, safe=",")
    txt = obter(url)
    time.sleep(PAUSA)
    d = json.loads(txt)
    bloco = d[0] if isinstance(d, list) and d else {}
    if "Dados" not in bloco:
        falso = bloco.get("Sucesso", {}).get("Falso", [{}])
        raise ValueError(falso[0].get("Msg", "resposta INE sem Dados"))
    return bloco["Dados"]


def ine_codigo_periodo(periodo):
    """'2024-06' -> 'S3A202406'; '2019' -> 'S7A2019'."""
    if len(periodo) == 4:
        return "S7A" + periodo
    return "S3A" + periodo.replace("-", "")


def recolher_ine_municipal(con):
    total = 0
    for serie, rotulo, unidade, perio, indicadores in INE_MUNICIPAL:
        vistos = set()
        for varcd, cod_total in indicadores:
            try:
                meta = ine_meta(varcd)
            except Exception as e:
                log(f"  ! {serie}/{varcd}: metadados falharam ({e})")
                continue
            p1 = iso_do_periodo_ine(meta.get("PrimeiroPeriodo", ""))
            p2 = iso_do_periodo_ine(meta.get("UltimoPeriodo", ""))
            if not p1 or not p2:
                log(f"  ! {serie}/{varcd}: intervalo ilegivel "
                    f"({meta.get('PrimeiroPeriodo')} .. {meta.get('UltimoPeriodo')})")
                continue
            if perio == "A":
                periodos = [str(a) for a in range(max(int(p1), INICIO_ANO),
                                                 int(p2) + 1)]
            else:
                arranque = max(p1, f"{INICIO_ANO}-01")
                if arranque > p2:
                    continue
                periodos = meses_entre(arranque, p2)
            # o indicador corrente vem primeiro; nao repetir periodos ja obtidos
            periodos = [p for p in periodos if p not in vistos]
            if not periodos:
                continue
            n = 0
            for lote in lotes(periodos, 24):
                codigos = [ine_codigo_periodo(p) for p in lote]
                try:
                    dados = ine_dados(varcd, codigos,
                                      {"Dim2": ",".join(GEOCODS),
                                       "Dim3": cod_total})
                except Exception as e:
                    log(f"  ! {serie}/{varcd} {lote[0]}..{lote[-1]}: {e}")
                    continue
                linhas = []
                for rot, registos in dados.items():
                    periodo = iso_do_rotulo(rot)
                    if not periodo:
                        continue
                    for reg in registos:
                        geo = reg.get("geocod", "")
                        if geo not in CONCELHOS:
                            continue
                        val = reg.get("valor")      # ausente = confidencial
                        if val in (None, ""):
                            continue
                        linhas.append((serie, CONCELHOS[geo], periodo,
                                       float(val), unidade, "INE"))
                    vistos.add(periodo)
                n += gravar(con, linhas)
            log(f"  {serie} [{varcd}]: {n} pontos "
                f"({periodos[0]}..{periodos[-1]})")
            total += n
    return total


def recolher_ine_aeroporto(con):
    total = 0
    for serie, rotulo, unidade, varcd in INE_AEROPORTO:
        try:
            meta = ine_meta(varcd)
        except Exception as e:
            log(f"  ! {serie}/{varcd}: metadados falharam ({e})")
            continue
        p1 = iso_do_periodo_ine(meta.get("PrimeiroPeriodo", ""))
        p2 = iso_do_periodo_ine(meta.get("UltimoPeriodo", ""))
        if not p1 or not p2:
            log(f"  ! {serie}/{varcd}: intervalo ilegivel")
            continue
        periodos = meses_entre(max(p1, f"{INICIO_ANO}-01"), p2)
        n = 0
        for lote in lotes(periodos, 24):
            codigos = [ine_codigo_periodo(p) for p in lote]
            try:
                dados = ine_dados(varcd, codigos,
                                  {"Dim2": "LPFR", "Dim3": "T", "Dim4": "T"})
            except Exception as e:
                log(f"  ! {serie}/{varcd} {lote[0]}..{lote[-1]}: {e}")
                continue
            linhas = []
            for rot, registos in dados.items():
                periodo = iso_do_rotulo(rot)
                if not periodo:
                    continue
                for reg in registos:
                    if reg.get("geocod") != "LPFR":
                        continue
                    if reg.get("dim_3") != "T" or reg.get("dim_4") != "T":
                        continue
                    val = reg.get("valor")
                    if val in (None, ""):
                        continue
                    linhas.append((serie, "regiao", periodo, float(val),
                                   unidade, "INE"))
            n += gravar(con, linhas)
        log(f"  {serie} [{varcd}]: {n} pontos ({periodos[0]}..{periodos[-1]})")
        total += n
    return total


# -------------------------------------------------------------------- IEFP
IEFP_INDICE = "https://www.iefp.pt/estatisticas"
IEFP_PUBLICACAO = "287082"      # "Estatisticas Mensais por Concelhos"
ABREV_MES = {"jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
             "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12}


def _bloco_json(texto, marcador):
    """Extrai o objecto JSON que se segue a `marcador`, por contagem de chavetas."""
    i = texto.find(marcador)
    if i < 0:
        return None
    i = texto.find("{", i)
    if i < 0:
        return None
    nivel, j, em_texto, escape = 0, i, False, False
    while j < len(texto):
        c = texto[j]
        if escape:
            escape = False
        elif c == "\\":
            escape = True
        elif c == '"':
            em_texto = not em_texto
        elif not em_texto:
            if c == "{":
                nivel += 1
            elif c == "}":
                nivel -= 1
                if nivel == 0:
                    return texto[i:j + 1]
        j += 1
    return None


def iefp_indice():
    """Devolve {'AAAA-MM': url_ods} a partir do catalogo embebido na pagina."""
    html = unescape(obter(IEFP_INDICE))
    time.sleep(PAUSA)
    cru = _bloco_json(html, "var publications")
    if not cru:
        raise ValueError("catalogo 'var publications' nao encontrado na pagina")
    cat = json.loads(cru)
    alvo = None
    for pub in cat.get("monthly", []):
        if str(pub.get("publicationId")) == IEFP_PUBLICACAO:
            alvo = pub
            break
    if alvo is None:
        raise ValueError(f"publicacao {IEFP_PUBLICACAO} ausente do catalogo")
    out = {}
    for rel in alvo.get("releases", []):
        ano = str(rel.get("year", "")).strip()
        if not re.fullmatch(r"\d{4}", ano):
            continue
        for m in rel.get("months", []):
            link = m.get("odsLink")
            nm = ABREV_MES.get(str(m.get("month", "")).strip().lower()[:3])
            if link and nm:
                out[f"{ano}-{nm:02d}"] = urllib.parse.urljoin(IEFP_INDICE, link)
    return out


NS_TABLE = "urn:oasis:names:tc:opendocument:xmlns:table:1.0"
NS_OFFICE = "urn:oasis:names:tc:opendocument:xmlns:office:1.0"
NS_TEXT = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"


def ler_ods(dados, nome_folha):
    """Le uma folha de um .ods (zip + content.xml) com a stdlib. -> lista de listas."""
    with zipfile.ZipFile(BytesIO(dados)) as z:
        xml = z.read("content.xml")
    raiz = ET.fromstring(xml)
    folha = None
    for t in raiz.iter(f"{{{NS_TABLE}}}table"):
        if t.get(f"{{{NS_TABLE}}}name") == nome_folha:
            folha = t
            break
    if folha is None:
        raise ValueError(f"folha {nome_folha} ausente")
    linhas = []
    for lin in folha.findall(f"{{{NS_TABLE}}}table-row"):
        rep_l = int(lin.get(f"{{{NS_TABLE}}}number-rows-repeated", 1) or 1)
        celulas = []
        for cel in lin.findall(f"{{{NS_TABLE}}}table-cell"):
            rep_c = int(cel.get(f"{{{NS_TABLE}}}number-columns-repeated", 1) or 1)
            tipo = cel.get(f"{{{NS_OFFICE}}}value-type")
            if tipo == "float":
                v = cel.get(f"{{{NS_OFFICE}}}value")
                val = float(v) if v is not None else None
            else:
                partes = ["".join(p.itertext())
                          for p in cel.findall(f"{{{NS_TEXT}}}p")]
                val = " ".join(partes).strip() or None
            if rep_c > 200:      # cauda de celulas vazias no fim da linha
                rep_c = 1 if val is None else rep_c
            celulas.extend([val] * rep_c)
        if rep_l > 50:           # cauda de linhas vazias
            rep_l = 1
        for _ in range(rep_l):
            linhas.append(list(celulas))
    return linhas


def normalizar_nome(t):
    t = unicodedata.normalize("NFKD", (t or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z ]", " ", t).strip()


NOME_POR_CHAVE = {normalizar_nome(n): n for n in CONCELHOS.values()}


def iefp_extrair(dados_ods):
    """Quadro_I -> {concelho: total}. Filtra pelos 16 concelhos do Algarve."""
    linhas = ler_ods(dados_ods, "Quadro_I")
    out = {}
    for lin in linhas:
        if len(lin) < 13:
            continue
        nome = lin[4] if isinstance(lin[4], str) else None
        if not nome:
            continue
        chave = normalizar_nome(nome)
        alvo = NOME_POR_CHAVE.get(chave)
        if not alvo:
            continue
        # coluna 12 = Total; tolera desalinhamento procurando o ultimo numero
        val = lin[12] if isinstance(lin[12], float) else None
        if val is None:
            nums = [c for c in lin[5:] if isinstance(c, float)]
            val = nums[-1] if nums else None
        if val is not None:
            out[alvo] = float(val)
    return out


def recolher_iefp(con, n_meses):
    try:
        indice = iefp_indice()
    except Exception as e:
        log(f"  ! IEFP: indice indisponivel ({e})")
        return 0
    disponiveis = sorted(indice)
    if not disponiveis:
        log("  ! IEFP: catalogo sem ficheiros .ods")
        return 0
    alvo = disponiveis[-n_meses:]
    log(f"  IEFP: {len(indice)} ficheiros no catalogo; a recolher "
        f"{len(alvo)} ({alvo[0]}..{alvo[-1]})")
    total, falhas = 0, []
    for periodo in alvo:
        try:
            crus = obter(indice[periodo], bruto=True)
            time.sleep(PAUSA)
            valores = iefp_extrair(crus)
        except Exception as e:
            falhas.append(f"{periodo}: {e}")
            continue
        if len(valores) < 16:
            falhas.append(f"{periodo}: so {len(valores)}/16 concelhos")
        if not valores:
            continue
        linhas = [("desemprego", c, periodo, v, "pessoas", "IEFP")
                  for c, v in valores.items()]
        total += gravar(con, linhas)
    if falhas:
        log(f"  ! IEFP: {len(falhas)} meses com problemas -> "
            + "; ".join(falhas[:5]))
    log(f"  desemprego: {total} pontos")
    return total


# ----------------------------------------------------------------- OpenSky
OS_TOKEN = ("https://auth.opensky-network.org/auth/realms/opensky-network"
            "/protocol/openid-connect/token")
OS_API = "https://opensky-network.org/api/flights/"


def opensky_token():
    cid = os.environ.get("OPENSKY_CLIENT_ID")
    seg = os.environ.get("OPENSKY_CLIENT_SECRET")
    if not cid or not seg:
        return None
    corpo = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": cid, "client_secret": seg})
    txt = obter(OS_TOKEN, dados=corpo,
                cabecalhos={"Content-Type": "application/x-www-form-urlencoded"})
    return json.loads(txt).get("access_token")


def recolher_opensky(con, n_dias):
    try:
        token = opensky_token()
    except Exception as e:
        log(f"  ! OpenSky: falha a obter token ({e})")
        return 0
    if not token:
        log("  - OpenSky: sem OPENSKY_CLIENT_ID/OPENSKY_CLIENT_SECRET no "
            "ambiente. O acesso anonimo a voos historicos foi encerrado pelo "
            "OpenSky, por isso a serie diaria de voos fica por recolher. "
            "Conta gratuita em opensky-network.org/my-opensky/account.")
        return 0
    cab = {"Authorization": f"Bearer {token}"}
    hoje = date.today()
    total, falhas = 0, 0
    for d in range(1, n_dias + 1):          # so a partir de ontem: batch nocturno
        dia = hoje - timedelta(days=d)
        t0 = int(datetime(dia.year, dia.month, dia.day,
                          tzinfo=timezone.utc).timestamp())
        t1 = t0 + 86400
        linhas = []
        for sentido, serie in (("arrival", "voos_chegadas"),
                               ("departure", "voos_partidas")):
            url = (f"{OS_API}{sentido}?airport=LPFR&begin={t0}&end={t1}")
            try:
                txt = obter(url, cabecalhos=cab)
                time.sleep(PAUSA)
                voos = json.loads(txt)
            except Exception as e:
                falhas += 1
                log(f"  ! OpenSky {serie} {dia}: {e}")
                continue
            if not isinstance(voos, list):
                falhas += 1
                continue
            linhas.append((serie, "regiao", dia.isoformat(), float(len(voos)),
                           "n", "OpenSky"))
        if linhas:
            total += gravar(con, linhas)
    log(f"  voos: {total} pontos ({falhas} chamadas falhadas)")
    return total


# =========================================================== FASE 1b: EMPRESAS
# Camada A do SPEC_fase1b: retrato anual autoritativo do tecido empresarial,
# por concelho e por seccao CAE Rev.3. Convencao de ambito: 'Concelho|SECCAO'
# (ex.: 'Faro|J'), ou 'regiao|SECCAO' para as series so disponiveis a NUTS2.

INICIO_EMPRESAS = 2015

# Seccoes CAE Rev.3 tal como a SCIE e a Demografia das Empresas as publicam.
# K, O, T e U nao existem nestes indicadores (a SCIE nao cobre financeiras,
# administracao publica, familias empregadoras nem organismos internacionais).
SECCOES_SCIE = ["TOT", "A", "B", "C", "D", "E", "F", "G", "H", "I", "J",
                "L", "M", "N", "P", "Q", "R", "S"]
# As Contas Regionais (VAB, agregado A21) tem as 21 seccoes completas.
SECCOES_A21 = SECCOES_SCIE + ["K", "O", "T", "U"]

# Agregacao sectorial para o painel. Definida ao nivel de SECCAO, de proposito:
# a spec pedia tech = J + 62/63 + M72 e turismo = I + N79, mas os indicadores de
# Demografia das Empresas (nascimentos e mortes) so publicam seccoes, sem
# divisoes. Manter tudo a seccao e o que garante que a identidade contabilistica
# stock(n) ~ stock(n-1) + nascimentos - mortes fecha por sector. As divisoes 62 e
# 63 ja estao dentro de J; ficam de fora M72 (I&D), N79 (agencias de viagens) e
# C10-C11 (industrias alimentares), que nao sao separaveis a este nivel.
SECTORES = {
    "tech": ["J"],
    "turismo": ["I"],
    "construcao": ["F", "L"],
    "comercio": ["G"],
    "agro_mar": ["A"],
    "outros": ["B", "C", "D", "E", "H", "M", "N", "P", "Q", "R", "S"],
}
SECTOR_ROTULOS = {
    "todos": "Todos os sectores", "tech": "Tecnologia (CAE J)",
    "turismo": "Turismo (CAE I)", "construcao": "Construção e imobiliário",
    "comercio": "Comércio", "agro_mar": "Agro-alimentar e mar",
    "outros": "Outros sectores",
}

# (serie, unidade, [(varcd, ano_min, ano_max ou None)], extras, factor)
# O indicador corrente vem primeiro. As mortes de 2021 e 2022 vem do 0014101 e
# NAO do 0009705: no indicador antigo eram provisorias/estimativa e divergem ate
# 8,5% dos valores definitivos publicados em 2025.
INE_EMPRESAS = [
    ("empresas_stock", "n",
     [("0014063", 2023, None), ("0008511", INICIO_EMPRESAS, 2022)],
     {"Dim4": "T"}, 1.0),
    ("empresas_nascimentos", "n",
     [("0014099", 2023, None), ("0009703", INICIO_EMPRESAS, 2022)], {}, 1.0),
    ("empresas_mortes", "n",
     [("0014101", 2021, None), ("0009705", INICIO_EMPRESAS, 2020)], {}, 1.0),
    ("empresas_vn", "eur",
     [("0013862", 2023, None), ("0008513", INICIO_EMPRESAS, 2022)], {}, 1.0),
    ("empresas_pessoal", "n",
     [("0013861", 2023, None), ("0008512", INICIO_EMPRESAS, 2022)], {}, 1.0),
]
# VAB por ramo, Contas Regionais: so existe ate NUTS2. Potencia10=6, ou seja os
# valores vem em milhoes de euros; convertemos para euros para bater com o VN.
INE_VAB = ("vab_sector", "eur", "0014115", 1e6)

# Fluxo mensal por seccao CAE (o pulso, ja que o registo empresa a empresa do
# Portal MJ esta fechado a automacao - ver NOTAS_dados.md).
INE_EMPRESAS_MENSAL = [
    ("constituicoes_mes", "n", "0012244"),
    ("dissolucoes_mes", "n", "0012245"),
]

# Tabela de registo individual. Fica criada e VAZIA: a decisao de 2026-08-05 foi
# adiar a identidade das empresas, porque o publicacoes.mj.pt tem reCAPTCHA e
# NoBot no unico ponto de pesquisa e a propria spec manda parar nesse caso.
SCHEMA_EMPRESAS = """
CREATE TABLE IF NOT EXISTS empresas_registo (
    nipc TEXT PRIMARY KEY,
    nome TEXT NOT NULL,
    natureza TEXT,
    morada TEXT,
    concelho TEXT,
    capital_social REAL,
    objeto TEXT,
    cae TEXT,
    cae_seccao TEXT,
    acto TEXT NOT NULL,
    data_acto TEXT NOT NULL,
    relevancia_tech INTEGER,
    relevancia_justif TEXT,
    fonte_url TEXT,
    recolhido_em TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_emp_concelho ON empresas_registo(concelho);
CREATE INDEX IF NOT EXISTS idx_emp_data ON empresas_registo(data_acto);
"""


def ine_codigos_validos(meta, dim_num):
    """Codigos realmente aceites numa dimensao. Evita rebentar o lote inteiro:
    um unico codigo invalido em Dim faz a API devolver Cod=4 para tudo."""
    # Formato real: Dimensoes.Categoria_Dim e uma lista com um unico dicionario
    # cujas chaves sao 'Dim_Num<N>_<cat_id>' e os valores listas de categorias.
    out = set()
    for bloco in meta.get("Dimensoes", {}).get("Categoria_Dim", []):
        if not isinstance(bloco, dict):
            continue
        for chave, cats in bloco.items():
            if not chave.startswith(f"Dim_Num{dim_num}_"):
                continue
            for c in (cats if isinstance(cats, list) else [cats]):
                if str(c.get("dim_num")) == str(dim_num):
                    out.add(str(c.get("categ_cod")))
    return out


def _anos(meta, ano_min, ano_max):
    p2 = iso_do_periodo_ine(meta.get("UltimoPeriodo", "")) or ""
    p1 = iso_do_periodo_ine(meta.get("PrimeiroPeriodo", "")) or ""
    if not p1[:4].isdigit() or not p2[:4].isdigit():
        return []
    lo = max(int(p1[:4]), ano_min)
    hi = int(p2[:4]) if ano_max is None else min(int(p2[:4]), ano_max)
    return [str(a) for a in range(lo, hi + 1)]


def _gravar_cae(con, serie, unidade, dados, seccoes, factor, ambito_fixo=None):
    linhas = []
    for rot, registos in dados.items():
        periodo = iso_do_rotulo(rot)
        if not periodo:
            continue
        for reg in registos:
            geo = reg.get("geocod", "")
            if ambito_fixo:
                if geo != "15":
                    continue
                base = ambito_fixo
            else:
                if geo not in CONCELHOS:
                    continue
                base = CONCELHOS[geo]
            sec = reg.get("dim_3")
            if sec not in seccoes:
                continue
            val = reg.get("valor")       # ausente = segredo estatistico
            if val in (None, ""):
                continue
            linhas.append((serie, f"{base}|{sec}", periodo,
                           float(val) * factor, unidade, "INE"))
    return gravar(con, linhas)


def recolher_ine_empresas(con):
    total = 0
    # --- Camada A: series por concelho e seccao CAE
    for serie, unidade, indicadores, extras, factor in INE_EMPRESAS:
        n, feitos = 0, set()
        for varcd, ano_min, ano_max in indicadores:
            try:
                meta = ine_meta(varcd)
            except Exception as e:
                log(f"  ! {serie}/{varcd}: metadados falharam ({e})")
                continue
            anos = [a for a in _anos(meta, ano_min, ano_max) if a not in feitos]
            if not anos:
                continue
            secs = ine_codigos_validos(meta, 3) or set(SECCOES_SCIE)
            usar = [s for s in SECCOES_SCIE if s in secs]
            for lote in lotes(anos, 10):
                extra = {"Dim2": ",".join(GEOCODS), "Dim3": ",".join(usar)}
                extra.update(extras)
                try:
                    dados = ine_dados(varcd,
                                      [ine_codigo_periodo(a) for a in lote],
                                      extra)
                except Exception as e:
                    log(f"  ! {serie}/{varcd} {lote[0]}..{lote[-1]}: {e}")
                    continue
                n += _gravar_cae(con, serie, unidade, dados, set(usar), factor)
                feitos.update(lote)
        log(f"  {serie}: {n} pontos ({len(feitos)} anos)")
        total += n
    # --- VAB sectorial, so NUTS2 Algarve
    serie, unidade, varcd, factor = INE_VAB
    try:
        meta = ine_meta(varcd)
        anos = _anos(meta, INICIO_EMPRESAS, None)
        secs = ine_codigos_validos(meta, 3) or set(SECCOES_A21)
        usar = [s for s in SECCOES_A21 if s in secs]
        n = 0
        for lote in lotes(anos, 12):
            dados = ine_dados(varcd, [ine_codigo_periodo(a) for a in lote],
                              {"Dim2": "15", "Dim3": ",".join(usar)})
            n += _gravar_cae(con, serie, unidade, dados, set(usar), factor,
                             ambito_fixo="regiao")
        log(f"  {serie}: {n} pontos ({anos[0]}..{anos[-1]} em euros)")
        total += n
    except Exception as e:
        log(f"  ! {serie}/{varcd}: {e}")
    # --- Fluxo mensal por seccao CAE
    for serie, unidade, varcd in INE_EMPRESAS_MENSAL:
        try:
            meta = ine_meta(varcd)
        except Exception as e:
            log(f"  ! {serie}/{varcd}: metadados falharam ({e})")
            continue
        p1 = iso_do_periodo_ine(meta.get("PrimeiroPeriodo", ""))
        p2 = iso_do_periodo_ine(meta.get("UltimoPeriodo", ""))
        if not p1 or not p2:
            log(f"  ! {serie}/{varcd}: intervalo ilegivel")
            continue
        secs = ine_codigos_validos(meta, 3) or set(SECCOES_SCIE)
        usar = [s for s in SECCOES_SCIE if s in secs]
        periodos = meses_entre(max(p1, f"{INICIO_EMPRESAS}-01"), p2)
        n = 0
        for lote in lotes(periodos, 12):
            try:
                dados = ine_dados(varcd,
                                  [ine_codigo_periodo(p) for p in lote],
                                  {"Dim2": ",".join(GEOCODS),
                                   "Dim3": ",".join(usar)})
            except Exception as e:
                log(f"  ! {serie}/{varcd} {lote[0]}..{lote[-1]}: {e}")
                continue
            n += _gravar_cae(con, serie, unidade, dados, set(usar), 1.0)
        log(f"  {serie}: {n} pontos ({periodos[0]}..{periodos[-1]})")
        total += n
    return total


# ------------------------------------------------- INE: precos da habitacao
INE_HABITACAO = ("preco_habitacao", "eur_m2", "0012239")


def recolher_habitacao(con):
    serie, unidade, varcd = INE_HABITACAO
    try:
        meta = ine_meta(varcd)
    except Exception as e:
        log(f"  ! {serie}/{varcd}: metadados falharam ({e})")
        return 0
    # Dim1 trimestral: 'S5A' + AAAA + T. Ler os codigos reais dos metadados
    # evita o Cod=4 que rebenta o lote quando se pede um trimestre inexistente.
    codigos = sorted(c for c in ine_codigos_validos(meta, 1)
                     if c.startswith("S5A") and c[3:7].isdigit()
                     and int(c[3:7]) >= INICIO_ANO)
    if not codigos:
        log(f"  ! {serie}: sem periodos trimestrais nos metadados")
        return 0
    n = 0
    for lote in lotes(codigos, 20):
        try:
            dados = ine_dados(varcd, lote,
                              {"Dim2": ",".join(GEOCODS), "Dim3": "T"})
        except Exception as e:
            log(f"  ! {serie} {lote[0]}..{lote[-1]}: {e}")
            continue
        linhas = []
        for rot, registos in dados.items():
            periodo = trimestre_para_iso(rot)
            if not periodo:
                continue
            for reg in registos:
                geo = reg.get("geocod", "")
                if geo not in CONCELHOS or reg.get("dim_3") != "T":
                    continue
                val = reg.get("valor")
                if val in (None, ""):
                    continue
                linhas.append((serie, CONCELHOS[geo], periodo, float(val),
                               unidade, "INE"))
        n += gravar(con, linhas)
    log(f"  {serie}: {n} pontos")
    return n


def trimestre_para_iso(rotulo):
    """'1.º Trimestre de 2026' -> '2026-T1'."""
    m = re.search(r"(\d)\D*\s*Trimestre\s+de\s+(\d{4})", rotulo, re.I)
    return f"{m.group(2)}-T{m.group(1)}" if m else None


# ----------------------------------------------------------------- E-Redes
EREDES_DATASET = "3-consumos-faturados-por-municipio-ultimos-10-anos"
EREDES_URL = ("https://e-redes.opendatasoft.com/api/explore/v2.1/catalog/"
              f"datasets/{EREDES_DATASET}/exports/csv"
              "?where=coddistrito%3D%2208%22&delimiter=%3B")
DICO_CONCELHO = {c[3:]: n for c, n in CONCELHOS.items()}   # '0801' -> 'Albufeira'


def recolher_eredes(con):
    """Consumo facturado de electricidade por concelho e mes (kWh)."""
    import csv
    import io
    try:
        crus = obter(EREDES_URL, bruto=True)
    except Exception as e:
        log(f"  ! E-Redes: export indisponivel ({e})")
        return 0
    texto = crus.decode("utf-8", "replace")
    leitor = csv.DictReader(io.StringIO(texto), delimiter=";")
    soma, residual, linhas_lidas = {}, 0.0, 0
    for lin in leitor:
        linhas_lidas += 1
        dico = (lin.get("coddistritoconcelho") or "").strip()
        periodo = (lin.get("data") or "").strip()[:7]
        try:
            kwh = float(lin.get("energia_ativa_kwh") or 0)
        except ValueError:
            continue
        if len(periodo) != 7:
            continue
        nome = DICO_CONCELHO.get(dico)
        if not nome:
            residual += kwh          # bucket '08--' OUTROS FARO (RGPD)
            continue
        soma[(nome, periodo)] = soma.get((nome, periodo), 0.0) + kwh
    if not soma:
        log(f"  ! E-Redes: {linhas_lidas} linhas lidas, nenhuma reconhecida")
        return 0
    linhas = [("consumo_electrico", nome, periodo, kwh, "kwh", "E-Redes")
              for (nome, periodo), kwh in soma.items()]
    n = gravar(con, linhas)
    total_kwh = sum(soma.values())
    pct = 100 * residual / (total_kwh + residual) if total_kwh else 0
    periodos = sorted({p for _, p in soma})
    log(f"  consumo_electrico: {n} pontos ({periodos[0]}..{periodos[-1]}); "
        f"nao atribuido a concelho ('OUTROS FARO'): {pct:.1f}% do total")
    return n


# ------------------------------------------------------------------ comandos
INICIO_ANO = 2019


def abrir():
    con = sqlite3.connect(DB)
    con.executescript(SCHEMA)
    con.executescript(SCHEMA_EMPRESAS)
    con.commit()
    return con


def cmd_fetch(args):
    global INICIO_ANO
    fonte = "todas"
    n_meses, n_dias = 24, 30
    for i, a in enumerate(args):
        if a == "--fonte" and i + 1 < len(args):
            fonte = args[i + 1].lower()
        elif a == "--desde" and i + 1 < len(args):
            INICIO_ANO = int(args[i + 1])
        elif a == "--meses" and i + 1 < len(args):
            n_meses = int(args[i + 1])
        elif a == "--dias" and i + 1 < len(args):
            n_dias = int(args[i + 1])
    con = abrir()
    antes = con.execute("SELECT COUNT(*) FROM indicadores").fetchone()[0]
    log(f"monitor.db: {antes} pontos antes do lote")
    total = 0
    if fonte in ("todas", "ine"):
        log("INE (concelhos)...")
        try:
            total += recolher_ine_municipal(con)
        except Exception as e:
            log(f"  ! INE municipal abortou: {e}")
        log("INE (aeroporto de Faro)...")
        try:
            total += recolher_ine_aeroporto(con)
        except Exception as e:
            log(f"  ! INE aeroporto abortou: {e}")
    if fonte in ("todas", "iefp"):
        log("IEFP (desemprego registado)...")
        try:
            total += recolher_iefp(con, n_meses)
        except Exception as e:
            log(f"  ! IEFP abortou: {e}")
    if fonte in ("todas", "empresas"):
        log("INE (empresas: stock, nascimentos, mortes, VN, pessoal, VAB)...")
        try:
            total += recolher_ine_empresas(con)
        except Exception as e:
            log(f"  ! INE empresas abortou: {e}")
    if fonte in ("todas", "habitacao"):
        log("INE (preços da habitação por concelho)...")
        try:
            total += recolher_habitacao(con)
        except Exception as e:
            log(f"  ! INE habitação abortou: {e}")
    if fonte in ("todas", "eredes"):
        log("E-Redes (consumo de electricidade por concelho)...")
        try:
            total += recolher_eredes(con)
        except Exception as e:
            log(f"  ! E-Redes abortou: {e}")
    if fonte in ("todas", "opensky"):
        log("OpenSky (voos em Faro)...")
        try:
            total += recolher_opensky(con, n_dias)
        except Exception as e:
            log(f"  ! OpenSky abortou: {e}")
    depois = con.execute("SELECT COUNT(*) FROM indicadores").fetchone()[0]
    log(f"\n{total} pontos escritos; tabela passou de {antes} para {depois} "
        f"linhas ({depois - antes:+d}).")
    con.close()


def cmd_stats(args):
    con = abrir()
    linhas = con.execute(
        "SELECT serie, fonte, COUNT(DISTINCT ambito), MIN(periodo), "
        "MAX(periodo), COUNT(*) FROM indicadores "
        "GROUP BY serie, fonte ORDER BY fonte, serie").fetchall()
    if not linhas:
        log("tabela indicadores vazia; corre primeiro: python harvest_dados.py fetch")
        return
    cab = ("série", "fonte", "âmbitos", "de", "até", "pontos")
    larg = [max(len(str(l[i])) for l in linhas + [cab]) for i in range(6)]
    fmt = "  ".join("{:<%d}" % w for w in larg)
    log(fmt.format(*cab))
    log("  ".join("-" * w for w in larg))
    for l in linhas:
        log(fmt.format(*[str(x) for x in l]))
    tot = con.execute("SELECT COUNT(*) FROM indicadores").fetchone()[0]
    amb = con.execute(
        "SELECT COUNT(DISTINCT ambito) FROM indicadores").fetchone()[0]
    todos = [r[0] for r in con.execute(
        "SELECT DISTINCT ambito FROM indicadores ORDER BY ambito")]
    bases = sorted({a.split("|")[0] for a in todos})
    seccoes = sorted({a.split("|")[1] for a in todos if "|" in a})
    log(f"\n{len(linhas)} séries · {amb} âmbitos distintos · {tot} pontos")
    log("âmbitos base: " + ", ".join(bases))
    if seccoes:
        log(f"secções CAE cruzadas com o âmbito ({len(seccoes)}): "
            + ", ".join(seccoes))
    n_emp = con.execute("SELECT COUNT(*) FROM empresas_registo").fetchone()[0]
    log(f"empresas_registo: {n_emp} linhas"
        + ("" if n_emp else "  (identidade das empresas adiada; ver NOTAS_dados.md)"))
    con.close()


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "fetch":
        cmd_fetch(sys.argv[2:])
    elif cmd == "stats":
        cmd_stats(sys.argv[2:])
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
