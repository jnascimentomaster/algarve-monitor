# SPEC — Fase 1b: Empresas (stock and flow sectorial) + conectores secundários

Projecto: Algarve Monitor. Pré-requisito: Fase 1 (harvest_dados.py com INE
turismo/constituições, IEFP, OpenSky) concluída e critérios verificados.
NÃO tocar em harvest_news.py, enrich.py, nem nos conectores da Fase 1.

## Objectivo final (definição de "feito")

Um painel "Empresas" no dashboard com uma representação stock-and-flow ao
estilo Strategy Dynamics (Kim Warren): caixa central com o stock de empresas
activas, seta de entrada à esquerda (constituições), seta de saída à direita
(encerramentos), com filtro por sector e por concelho, mais séries de volume
de negócios, pessoal ao serviço e contribuição sectorial para o VAB regional.
Critérios de aceitação no fim.

## Tarefa 0 — higiene (fazer antes de tudo, commit próprio)

1. Renomear `gitignore` para `.gitignore` e correr
   `git rm --cached monitor.db entidades.db` (as bases ficam no disco,
   saem só do versionamento). Confirmar com `git status` limpo.
2. Confirmar que a pasta `_to_delete/` já não existe (o Jo apaga-a à mão);
   se ainda existir, reportar e seguir em frente.

## Camada A — INE anual (o retrato autoritativo)

Fonte: API JSON do INE (mesmo padrão da Fase 1; códigos varcd a descobrir no
catálogo e validar contra chamadas reais). Indicadores alvo, por município
(16 concelhos) e por secção CAE Rev.3 quando a dimensão existir:

1. Nº de empresas (SCIE), anual, município × CAE
2. Nascimentos de empresas (Demografia das Empresas), anual, município
   (× CAE se disponível)
3. Mortes de empresas (Demografia das Empresas), anual, município;
   NOTA: a morte é confirmada com ~2 anos de atraso — guardar o ano de
   referência e mostrá-lo no painel
4. Volume de negócios (SCIE), anual, município × CAE quando publicável
   (células pequenas vêm suprimidas por segredo estatístico — tolerar nulls)
5. Pessoal ao serviço (SCIE), anual, município × CAE
6. VAB por ramo de actividade, Contas Regionais, NUTS2 Algarve, anual
   (base da "contribuição de cada sector para a economia")

Backfill: desde 2015. Tabela `indicadores` da Fase 1 reutilizada, com a
convenção serie='empresas_stock', 'empresas_nascimentos', 'empresas_mortes',
'empresas_vn', 'empresas_pessoal', 'vab_sector', e o sector codificado no
campo ambito como 'Faro|J' (concelho|secção CAE) ou 'regiao|J'.

## Camada B — Portal MJ + SICAE (o pulso mensal, empresa a empresa)

Nova tabela (dados individuais por empresa, extraídos do texto da publicação
de constituição/dissolução):

```sql
CREATE TABLE IF NOT EXISTS empresas_registo (
  nipc TEXT PRIMARY KEY,
  nome TEXT NOT NULL,
  natureza TEXT,           -- 'LDA', 'SA', 'UNIPESSOAL LDA', ...
  morada TEXT,             -- sede completa tal como publicada
  concelho TEXT,
  capital_social REAL,     -- em euros, se publicado
  objeto TEXT,             -- objecto social por extenso (texto livre)
  cae TEXT,                -- código; obtido no SICAE por NIPC
  cae_seccao TEXT,         -- letra (J, I, F, ...)
  acto TEXT NOT NULL,      -- 'constituicao' | 'dissolucao'
  data_acto TEXT NOT NULL,
  relevancia_tech INTEGER, -- 0-10, atribuída pelo LLM local (ver abaixo)
  relevancia_justif TEXT,  -- uma frase do LLM
  fonte_url TEXT,
  recolhido_em TEXT NOT NULL
);
```

Recolha em publicacoes.mj.pt: pesquisa de actos de registo comercial,
distrito de Faro, por concelho e intervalo de datas; abrir o detalhe de cada
publicação e extrair os campos do texto do acto (firma, NIPC, natureza,
sede, capital, objecto). É um site ASP.NET com viewstate — inspeccionar o
formulário e replicar o POST com sessão; ritmo lento (1 pedido/segundo),
User-Agent de browser, tolerância a falhas de parsing (campos em falta
ficam NULL, nunca bloqueiam a linha).
CAE por NIPC via SICAE (sicae.pt) — validar o formulário de consulta e
guardar em cache local para nunca consultar o mesmo NIPC duas vezes.
Backfill: 12 meses. Cadência futura: semanal.

Scoring de relevância tecnológica (LLM local, mesmo padrão do enrich.py):
para cada constituição, classificar o objecto social com o qwen3:30b-instruct
(structured output): relevancia_tech 0-10 + justificação de uma frase.
O CAE sozinho não chega — muitas empresas tech registam CAEs genéricos;
o objecto social é o melhor sinal. Empresas com relevancia_tech >= 7 entram
numa vista "candidatas ao directório" para curadoria manual do Jo.

Dados pessoais (regra obrigatória): as publicações podem conter nomes de
gerentes e sócios — NÃO extrair nem guardar nomes de pessoas singulares.
Só dados da empresa. A morada completa guarda-se na base local; o dashboard
público mostra apenas o concelho até decisão explícita do Jo em contrário.
Ética/robustez: se qualquer um dos sites bloquear ou exigir captcha,
PARAR, documentar em NOTAS_dados.md e não contornar.

## Sectores (agregação por CAE para o painel)

tech = J (informação e comunicação) + 62/63 + M72; turismo = I (alojamento e
restauração) + N79; construção e imobiliário = F + L; comércio = G;
agroalimentar e mar = A + C10-C11; outros = restantes. Tabela de mapeamento
no código, documentada, fácil de rever.

## Painel "Empresas" no dashboard

- Stock and flow: SVG inline — seta esquerda com nascimentos/ano (INE) e
  constituições últimos 12m (MJ), caixa central com stock actual e variação,
  seta direita com mortes/ano (INE) e dissoluções últimos 12m (MJ); rótulos
  com o ano de referência de cada número
- Selector de sector (tech, turismo, construção, comércio, agro/mar, outros,
  todos) e integração com o filtro de concelho do mapa
- Por baixo: barras de contribuição sectorial (VAB regiao + VN por sector no
  concelho seleccionado) e série de pessoal ao serviço
- Lista "empresas novas este mês" (da tabela empresas_registo: nome, concelho,
  CAE, capital social, badge de relevância tech), que alimenta também sinais
  tipo nova_empresa no feed; vista separada "candidatas ao directório"
  (relevancia_tech >= 7) para curadoria
- Estilo: o existente (claro, Archivo/Spline Sans Mono, variáveis CSS,
  sem bibliotecas)

## Conectores secundários (menor prioridade, mesma tabela indicadores)

- MONITUR via wp-json (prioridade 1 do NOTAS_dados.md da Fase 1, esforço
  baixo): extrair as séries identificadas na investigação
- E-Redes dados abertos: consumo de electricidade por município, mensal
  (proxy de actividade económica)
- INE: preços da habitação por município, trimestral
- DGEEC/RAIDES: inscritos na UAlg por área, anual
- BeAlgarve (bealgarve.pt): documentar o endpoint que alimenta o mapa de
  entidades (só documentar; via preferida é institucional/NERA) e usar a
  página de informação estatística como checklist de indicadores de contexto
- Startup Portugal: mantém-se a via institucional (email do Jo)

## Restrições e higiene

Iguais às da Fase 1: stdlib salvo excepção declarada, 0.5-1s entre pedidos,
erros por série não bloqueiam o lote, commits pequenos, .db fora do git,
terminar com `python publish.py --dry` limpo.

## Critérios de aceitação

1. `fetch` idempotente (2ª execução não altera contagens)
2. Camada A: ≥ 4 séries INE de empresas com dimensão município, backfill
   ≥ 2015, mais VAB sectorial regional
3. Camada B: empresas_registo com ≥ 12 meses de constituições dos 16
   concelhos; ≥ 80% com CAE via SICAE; ≥ 90% com objeto social extraído;
   relevancia_tech preenchida em todas as constituições; zero nomes de
   pessoas singulares na base
4. Painel Empresas funcional: stock and flow com números coerentes entre si
   (stock_ano_n ≈ stock_ano_n-1 + nascimentos - mortes, desvio explicado),
   selector de sector e filtro de concelho a funcionar
5. Lista de empresas novas do mês visível e com CAE
6. Site publicado no Vercel com o painel, sem partir nada do existente
7. NOTAS_dados.md actualizado (BeAlgarve endpoint, E-Redes, decisões tomadas)
