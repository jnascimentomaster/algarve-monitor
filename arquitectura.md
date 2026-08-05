# Algarve Monitor: arquitectura do sistema

Versão 0.1, 2026-08-04. Decisões já tomadas na conversa: caminho B (build leve,
sem fork do World Monitor), LLM local para processamento de volume, Claude API
só para síntese, cadência diária em vez de "live", directório de startups como
peça central.

## Princípios de desenho

1. **Volume baixo é a realidade.** 30 a 100 itens/dia no total. O produto é um
   brief diário + camadas de dados + directório cumulativo, não um feed live.
2. **Local-first na recolha.** Tudo o que recolhe corre na máquina Windows do Jo
   via Task Scheduler, pelo mesmo motivo do sistema LinkedIn: fontes que
   bloqueiam IPs de datacenter, e LLM local sem custos de token.
3. **Supabase como fonte de verdade.** Os scripts locais escrevem no Postgres
   do Supabase; o front-end só lê. A base local SQLite serve apenas de buffer
   quando não há rede.
4. **Custo alvo: < €10/mês.** Supabase free tier, Vercel free tier, Ollama
   grátis, Claude API só no brief diário.
5. **O directório acumula, as notícias passam.** Cada item processado alimenta
   o directório de entidades/startups; o valor composto está aí.

## Diagrama

```
MÁQUINA LOCAL (Windows, Task Scheduler)
┌─────────────────────────────────────────────────────────┐
│  1. RECOLHA                                             │
│     harvest_news.py    RSS/scrape (entidades.db)        │
│     harvest_dados.py   conectores: INE, OpenSky,        │
│                        PT2030/PRR, CORDIS, Racius,      │
│                        IEFP, RNAL, BASE.gov             │
│           │                                             │
│           ▼  staging SQLite (buffer offline)            │
│  2. ENRIQUECIMENTO (Ollama, qwen2.5:14b)                │
│     enrich.py    por item:                              │
│       categoria  (tech|inovação|negócios|turismo|       │
│                   regional)                             │
│       entidades  (empresas, pessoas, organizações)      │
│       município  (1 de 16, ou "região")                 │
│       relevância (0-10) + resumo de 1 frase             │
│  3. RESOLUÇÃO DE ENTIDADES                              │
│     resolve.py   liga menções ao directório             │
│                  (fuzzy match + confirmação manual      │
│                  em fila de revisão)                    │
└───────────────┬─────────────────────────────────────────┘
                ▼ upsert
        SUPABASE (Postgres + RLS leitura pública)
        itens · entidades · startups · eventos ·
        indicadores · briefs
                │
   ┌────────────┴───────────────┐
   ▼                            ▼
4. SÍNTESE (1×/dia)        5. FRONT-END (Vercel, estático)
   brief.py                    mapa MapLibre (16 concelhos)
   Claude API: brief           painéis: brief do dia,
   diário a partir dos         notícias por categoria,
   itens já classificados      indicadores, eventos,
   grava em `briefs`           directório pesquisável
```

## Componentes

### 1. Recolha (`harvest_news.py`, `harvest_dados.py`)

- Lê a tabela `entidades` (a base criada hoje) e itera pelas fontes activas
  com `metodo_acesso` rss/api/scrape.
- Reutiliza os padrões do `harvest.py` do sistema LinkedIn: User-Agent de
  browser, tratamento de CDATA, deduplicação por URL, `check` como comando de
  validação de fontes.
- Conectores de dados são módulos independentes com contrato comum:
  `fetch() -> list[Indicador]`. Cadências distintas: voos diário, Racius
  semanal, INE/IEFP mensal, PT2030/PRR/CORDIS semanal.
- Filtro Algarve nas fontes nacionais: concelhos + gentílicos + entidades do
  directório como lista de termos, mantida na própria BD.

### 2. Enriquecimento (`enrich.py`, Ollama local)

- Modelo: `qwen2.5:14b` (Q4) como principal; `llama3.1:8b` como alternativa
  rápida. Decisão final após teste comparativo no mesmo lote real.
- Saída JSON estrita validada com Pydantic; item que falhe validação 2× vai
  para fila de revisão, não bloqueia o lote.
- Prompt de classificação com as 5 categorias fechadas + extracção de
  entidades tipadas (empresa, pessoa, organização, evento).
- Corre em lote nocturno; a 4-8 tok/s em CPU, 100 itens ≈ 30-60 min.

### 3. Resolução de entidades (`resolve.py`)

- Match fuzzy (rapidfuzz) entre entidades extraídas e o directório.
- Score alto: liga automaticamente. Score médio: fila de revisão (interface
  mínima: CSV ou página admin simples). Score baixo: cria candidato novo.
- É este passo que faz o directório de startups crescer sozinho.

### 4. Síntese (`brief.py`, Claude API)

- 1 chamada/dia (Haiku ou Sonnet): recebe os itens classificados das últimas
  24h + indicadores que mudaram, devolve brief de 200-400 palavras em PT com
  secções por categoria. Custo estimado: < €3/mês.
- Guardado na tabela `briefs`; o front-end mostra o mais recente e o arquivo.

### 5. Front-end (Vercel, estático + Supabase JS)

- Página única, MapLibre com os 16 concelhos, pins de startups/eventos/itens
  geocodificados ao concelho (não a morada exacta no v1).
- Painéis: brief do dia, últimas notícias por categoria, 3 indicadores
  (constituições de empresas, voos/dormidas, financiamento aprovado),
  próximos eventos, directório pesquisável.
- Leitura via chave anon do Supabase com RLS só-leitura nas tabelas públicas.
- Design: tratar com a skill frontend-design quando lá chegarmos.

## Modelo de dados (Supabase)

```sql
entidades      -- a base criada hoje (fontes de recolha + actores do ecossistema)
itens          -- id, entidade_fonte_id, url UNIQUE, titulo, publicado_em,
               -- categoria, municipio, relevancia, resumo, raw, processado_em
mencoes        -- item_id, entidade_id, tipo_mencao (liga itens ao directório)
startups       -- id, nome, municipio, sector, estagio, ano_fundacao, site,
               -- fonte_origem (seed_manual | extraccao), entidade_id
eventos        -- id, nome, data_inicio, municipio, organizador_id, url
indicadores    -- serie, concelho, periodo, valor, fonte_id, recolhido_em
briefs         -- data, texto_md, itens_incluidos (json)
fila_revisao   -- pendentes de resolução de entidades / falhas de parsing
```

Nota: `startups` arranca com seed manual (rede Algarve Evolution, spinoffs
CRIA, participantes ATH Summit) antes de qualquer automatismo. O seed manual
é a âncora de qualidade do fuzzy match.

## Agendamento (Task Scheduler)

| Tarefa | Cadência | Hora |
|---|---|---|
| harvest_news + enrich + resolve | diária | 06:00 |
| brief (Claude API) | diária | 07:30 |
| harvest_dados: voos | diária | 07:00 |
| harvest_dados: Racius, PT2030/PRR, CORDIS, BASE | semanal (2ª) | 06:30 |
| harvest_dados: INE, IEFP, RNAL | mensal (dia 15) | 06:30 |
| check de fontes (relatório de feeds mortos) | semanal (dom) | 20:00 |

## Faseamento

- **v0 (validação):** base de entidades revista pelo Jo → check de feeds →
  harvest de notícias a funcionar → teste de classificação Ollama num lote
  real. Sem front-end.
- **v1:** + enriquecimento completo, Supabase, 3 camadas de dados
  (financiamento, constituições, voos/turismo), brief diário, front-end mínimo
  com mapa e directório (seed manual).
- **v2:** resolução automática de entidades, camadas restantes (contratos
  públicos, investigação, emprego tech), arquivo de briefs, página por
  concelho.

## Riscos e decisões em aberto

1. **Feeds por validar.** As 71 entidades têm `verificado=0`; o check vai
   matar alguns URLs e revelar câmaras sem RSS (esperado: a maioria).
2. **Scraping de câmaras:** 16 sites diferentes; no v1 só entram as que
   tiverem RSS ou HTML estável. As restantes ficam para v2.
3. **Qualidade do 14B em extracção de entidades PT:** a validar no teste;
   fallback é subir para 32B (cabe nos 64 GB, mais lento) ou usar Claude
   Haiku só na extracção.
4. **Racius/scraping:** respeitar robots.txt e cache agressiva; se o
   observatório bloquear, o INE mensal cobre a mesma série com atraso.
5. **Nome do produto:** em aberto, decisão barata, no fim.
