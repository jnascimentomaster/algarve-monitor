# NOTAS_dados.md — fontes de dados estatísticos para o Algarve Monitor

Levantamento de 5 de Agosto de 2026. Todos os URL citados foram confirmados com
pedido HTTP real nessa data. As três primeiras secções são investigação, não
implementação. A quarta regista o que ficou implementado em `harvest_dados.py`
e as decisões que se afastaram da spec.

Nota transversal sobre esforço: o projecto corre em stdlib. A biblioteca padrão
resolve HTTP e JSON com `urllib.request` e `json`, resolve HTML de forma
sofrível com `html.parser`, e não lê PDF de todo. Sempre que uma fonte só
existe em PDF o esforço em stdlib puro é alto por definição, e a estimativa
desce para médio se se aceitar `pdfplumber`. Assinalo os dois valores onde a
distinção pesa.

## 1. OTSA, observe.ualg.pt e monitur.ualg.pt

São três coisas distintas que costumam ser confundidas, e só duas estão vivas.

**observe.ualg.pt está em baixo.** O domínio resolve para 193.136.227.151 mas o
servidor não responde: em HTTPS a ligação é fechada pelo peer, em HTTP devolve
503 com mensagem de proxy. O domínio alternativo `observe.pt`, divulgado pela
própria UAlg, nem sequer resolve. O OBSERVE foi uma acção de 24 meses
cofinanciada pelo CRESC Algarve 2020, ou seja, infraestrutura de projecto
terminado. Sobrevive apenas a página institucional `www.ualg.pt/projeto-observe`
(200), que é narrativa e não tem dados. Marcar como morto para não voltar a
consumir tempo.

**O OTSA vive no site do Turismo do Algarve**, não em domínio ualg.pt, em
`www.turismodoalgarve.pt/pt/menu/814/observatorio.aspx` (200). Resulta de um
protocolo entre RTA, CCDR Algarve, UAlg e Turismo de Portugal, e pertence à rede
INSTO da Organização Mundial do Turismo desde 2020. O produto extraível é a
série de relatórios anuais, alojados em `cms.visitalgarve.pt`, seis edições, de
2020 a 2026, todas confirmadas a 200 e todas com camada de texto nativa. O
prefixo comum é
`https://cms.visitalgarve.pt//upload_files/client_id_1/website_id_3/Projetos/Observat%C3%B3rio/`
e a barra dupla é literal, faz parte do caminho.

A cadência é anual e o relatório do ano N reporta dados de N-1: a sexta edição
intitula-se "2026 Annual Report (Data 2025)". Há uma descontinuidade de
numeração entre a segunda edição (2021) e a terceira (2023), sem edição
rotulada 2022.

O conteúdo é substancialmente tabular, não apenas prosa. O sexto relatório tem
40 páginas, cerca de 95 mil caracteres de texto extraível, 16 figuras e 16
tabelas. A Tabela 1 define 35 indicadores numerados I1 a I35, organizados pelas
onze áreas obrigatórias do ETIS e cruzados com o quadro DPSIR e os ODS.
Interessam ao monitor, entre outros: sazonalidade e dormidas mensais, taxa de
sazonalidade, quota dos mercados emissores, emprego turístico, RevPAR, estada
média, receitas de alojamento, voltas de golfe, consumo energético e de água,
produção e separação de resíduos, visitantes de áreas protegidas, repartição
modal de chegada, pegada de carbono, passageiros desembarcados no Aeroporto de
Faro, satisfação dos residentes, camas por mil residentes, e densidade e
intensidade turística. As fontes primárias declaradas são o TravelBI do Turismo
de Portugal, o INE e inquéritos próprios a residentes, turistas e empresas.

Teste de extracção real: com `pdfplumber`, 13 das 40 páginas devolvem tabelas
com grelha limpa, incluindo as de emprego e de consumo energético por CAE, já
separadas por coluna. É dos PDF melhor comportados que se encontram neste tipo
de fonte.

**monitur.ualg.pt está vivo e é a melhor via técnica das três.** É um WordPress
com a REST API aberta: `https://monitur.ualg.pt/wp-json/` responde 200 e expõe
`wp/v2` com 10 artigos, 46 páginas e 817 itens de media, dos quais 384 são PDF.
O projecto MONITUR está formalmente concluído e o conteúdo próprio congela em
2023, mas o site continua a servir de repositório: os PDF mais recentes são de
13 de Junho de 2025 e são precisamente os relatórios de inquérito do OTSA de
2024 e 2025, que não estão listados na página do Turismo do Algarve. O corpus
reparte-se em 182 fact sheets por município, 82 por mercado emissor, e cerca de
92 relatórios. As fact sheets municipais, testadas com o exemplar de Faro de
época alta de 2023, têm camada de texto com rótulo e valor adjacentes, do género
"Impacto Global 3,44", parseáveis por expressão regular mas dependentes do
layout.

Há ainda um sistema de apoio à decisão em `moniturdss.ualg.pt` (200), uma SPA em
Vue com API Django em `moniturdss-api.ualg.pt`. Dois endpoints respondem 200 sem
autenticação: `/dashboards/all/` devolve o catálogo de 22 dashboards de
indicadores com categoria, e `/publications/all/` devolve 9 publicações. O
`/integrations/all/` responde 401 e não se insistiu. Duas limitações a registar:
estes endpoints servem metadados e não séries temporais, porque os valores ficam
na área reservada; e a API corre em produção com `DEBUG = True`, o que faz o 404
imprimir o urlconf completo do Django. Foi observado passivamente, sem qualquer
tentativa de exploração, mas convém comunicar à equipa da UAlg se houver canal
para isso.

| Via | Formato | Esforço | Backfill |
|---|---|---|---|
| monitur wp-json | JSON | baixo | acervo 2022 a 2025 |
| moniturdss API aberta | JSON | baixo, só metadados | nenhum |
| relatórios anuais OTSA | PDF com texto | alto em stdlib, médio com pdfplumber | 6 pontos anuais, dados de 2019 a 2025 |
| observe.ualg.pt | morto | n/a | n/a |

## 2. CCDR Algarve

Existiram boletins de conjuntura regional, e a resposta honesta é que a série
principal está morta há mais de uma década.

A secção é `www.ccdr-alg.pt/site/info/boletins-algarve-conjuntura` (200) e
organiza-se em três blocos. O boletim trimestral **Algarve Conjuntura** teve 17
números, do n.º 1 relativo ao 3.º trimestre de 2009 até ao n.º 17 relativo ao
3.º trimestre de 2013, e parou aí. Existe um boletim anual, com edição de 2014 e
uma retrospectiva de 2007 a 2015. E há três boletins especiais Covid19, de
Agosto de 2020, Dezembro de 2020 e Outubro de 2021. Verificaram-se os extremos
por amostragem e todos respondem 200. Os trimestrais estão em
`/site/sites/ccdr-alg.pt/files/DesenvRegional/BoletinsAlgConj/`, os especiais em
`/site/sites/default/files/inline-files/`, e num deles o duplo `.pdf.pdf` no
nome é literal.

O conteúdo é exactamente a bateria que interessaria a um monitor regional. Pela
análise do n.º 17, as secções são: enquadramento nacional com PIB, procura
interna, consumo das famílias, FBCF, exportações, importações, VAB e taxa de
desemprego em variação homóloga trimestral; mercado de trabalho desdobrado em
emprego, salários e desemprego; apoios sociais; endividamento das famílias;
empresas, com constituições, dissoluções, empréstimos e crédito vencido;
turismo; construção e habitação; transportes; e políticas públicas por programa
operacional. A própria CCDR descreve a publicação como agregando dados
trimestrais dispersos, incluindo dados não publicados recolhidos junto de
empresas e entidades públicas, o que aumenta o valor arquivístico da série.

Não existe secção de estatísticas nem observatório regional. O mais próximo é o
menu Dinâmicas Regionais, que é a página do órgão de acompanhamento OADR
previsto no Decreto-Lei n.º 137/2014, puramente institucional e sem um único
documento anexo. Sob esse menu ficam três sub-secções úteis:

| Secção | URL | Estado |
|---|---|---|
| Números em Destaque | `/site/info/numeros-em-destaque` | viva, 55 PDF |
| Algarve em Destaque | `/site/info/algarve-em-destaque` | viva, 6 PDF, monitorização RIS3 |
| Estudos | `/site/info/estudos-0` | viva, 13 PDF avulso |

**Números em Destaque** é o sucessor mais próximo. Tem duas famílias. Uma é
temática e numerada, com Contas Regionais de 2017 e de 2019 a 2023, Índice
Sintético de Desenvolvimento Regional 2019, exportações de bens 2023, FEEI 2014
a 2020, população estrangeira residente 2018, indicadores Europa 2020, índice de
competitividade regional 2016 e poder de compra concelhio 2015. A edição mais
recente é o n.º 14, Contas Regionais 2023, de 18 de Fevereiro de 2025. A outra
família é a Informação Mensal do Programa Operacional do Algarve, mensal e
contínua de Janeiro de 2021 a Junho de 2024, altura em que parou. Há uma notícia
de site sobre Contas Regionais 2024 com números no corpo do texto, mas sem PDF
associado localizável.

**Algarve em Destaque** é a monitorização anual da RIS3 Algarve, com edições
referentes a 2019 a 2023, a última publicada a 26 de Dezembro de 2024. Cadência
anual com atraso de cerca de um ano.

Formato e raspabilidade: tudo é PDF servido a partir de páginas Drupal
estáticas. Não há API, não há CSV, não há XLSX. As listagens são HTML simples
com os PDF em `href` directos, portanto o índice é trivial de raspar. O problema
está a jusante. Testou-se o `20250218_CCDRALGARVE_CR2023.pdf`: 23 páginas para
apenas 10.614 caracteres de texto e zero tabelas com grelha, ou seja, é um
infográfico onde os números vivem dentro de imagens. Já o boletim trimestral
n.º 17 tem 25 páginas e 55 mil caracteres, com os valores presentes no texto mas
em tabelas sem grelha e com a ordem de leitura baralhada, do género
`PIB1 vh (%) -1,3 -3,2 -3,6`. É recuperável por extracção posicional com
coordenadas, não por leitura linear.

Esforço: alto, e alto pelas piores razões. Em stdlib puro é inviável. Mesmo com
`pdfplumber`, os Números em Destaque recentes são largamente infográficos e
exigiriam trabalho manual ou OCR, enquanto os boletins trimestrais exigem
parsing posicional caso a caso. O layout muda entre famílias e entre anos, e a
série de maior valor analítico está congelada desde 2013.

Backfill é a única virtude desta fonte: trimestral de 2009 a 2013 com dezassete
pontos, anual em 2014, retrospectiva de 2007 a 2015, Contas Regionais de 2015 a
2023, RIS3 de 2019 a 2023, e mensal do PO Algarve de 2021 a meados de 2024. Como
fonte corrente não serve. Como arquivo histórico tem valor real.

## 3. ecossistema.startupportugal.com

Existe endpoint público de dados, e é mais completo do que seria de esperar.

O site é uma aplicação Next.js. A página inicial responde 200 mas traz apenas
13,8 KB e nenhum conteúdo útil: o payload RSC embebido nos blocos
`self.__next_f.push` são 8.693 caracteres de árvore de componentes, sem um único
registo de dados. Os dados são carregados no cliente. Inspeccionou-se o conjunto
de chunks JavaScript que qualquer visita normal de browser carrega, com 0,5 s
entre pedidos. Não houve scraping de conteúdo nem qualquer tentativa de
contornar autenticação.

A base da API está definida como `NEXT_PUBLIC_API_URL` com fallback para
`/api/v1/`, e a variável não vem preenchida no build, pelo que a API é servida
na mesma origem. Os controladores seguem convenção .NET em PascalCase.
Confirmaram-se por pedido real, todos sem autenticação e todos a 200:

| Endpoint | Método | Devolve |
|---|---|---|
| `/api/v1/StartUp/get-startups?PageNumber=1&PageSize=25` | GET | 7.125 entidades, 285 páginas |
| `/api/v1/Search/advanced-search` | POST | pesquisa paginada sobre índice tipo Elasticsearch |
| `/api/v1/Search/autocomplete` | GET | sugestões com `entityType` |
| `/api/v1/Lookup/regions` | GET | 26 regiões NUTS III |

O `get-startups` devolve por registo: `id`, `name`, `industries[]` com id e nome
PT e EN, `fundingRound`, `revenue`, `revenueCurrency`, `revenueGrowthRate`,
`image`, `location`, `lastUpdated`, `isValidated`, `isClaimed`, `informaDBId` e
`dealRoomId`. Os dois últimos denunciam a proveniência: cadastro da Informa D&B
e enriquecimento da Dealroom, o que se confirma nos URL das imagens, alojadas em
`storage.googleapis.com/dealroom-images-production`. A família `Lookup/` expõe
dezenas de tabelas auxiliares, incluindo `district`, `verticals`, `horizontals`,
`tech-stack`, `core-technologies`, `investor-types` e `unicorns`.

Há duas limitações sérias para uso algarvio. Primeiro, o campo `location` é texto
livre, do género `Rua Manuela Porto, Carnide, Lisbon, 1600-532, Portugal`, e está
escassamente preenchido: numa página de 25 registos apenas 5 tinham morada.
Segundo, o payload da listagem não traz o identificador de região, apesar de
`Lookup/regions` existir e de o Algarve lá estar como NUTS III, o que significa
que não se confirmou parâmetro de filtro por região no endpoint de listagem. Uma
pesquisa por `q=Algarve` devolve 40 resultados, mas são correspondências de nome,
como `Algarve SunBoat` ou `ARISH SBS ALGARVE, S.A.`, e não entidades sediadas no
Algarve. É um falso atalho que convém não usar.

O endpoint de exportação em massa existe e está fechado: `GET
/api/v1/StartUp/download` devolve 401. Não há `robots.txt` declarado.

Fica registada a via institucional: pedido formal de export à Startup Portugal,
que o Jo trata por email através da Algarve Evolution, com o contacto em
`startupportugal.com/contact-us/` (200). A organização já publica análises
agregadas do ecossistema. Dado que o `download` está atrás de autenticação e que
a região não é filtrável no endpoint público, o pedido formal é provavelmente o
caminho certo para obter um recorte algarvio fiável e com termos de uso claros.

Esforço: baixo a médio, inteiramente em stdlib. `urllib.request` com
`User-Agent` de browser e cabeçalho `Referer`, `json` para desserializar, e um
ciclo de paginação sobre `PageNumber`. O trabalho real não está na recolha mas
na geocodificação: transformar morada em texto livre num concelho do Algarve
exige normalização e vai deixar buracos. Backfill não existe: isto é um registo
de estado actual, e qualquer série histórica terá de ser construída para a
frente, por snapshots periódicos.

## Recomendação de prioridade

Ordenado por rácio valor sobre esforço, não por valor absoluto.

**1.º, monitur.ualg.pt via wp-json.** Única fonte com API JSON aberta e estável a
custo praticamente nulo em stdlib. Dá de imediato o índice de 384 PDF com datas,
e é por aqui que se descobrem os relatórios de inquérito do OTSA de 2024 e 2025.
Ressalva: o projecto está concluído e o conteúdo próprio congela em 2023, pelo
que o valor é sobretudo de arranque e de acervo.

**2.º, API pública do ecossistema Startup Portugal.** Esforço baixo, JSON limpo,
e é a única das três a cobrir tecido empresarial e inovação em vez de turismo.
Perde por não ter histórico e por o recorte regional ser frágil. Recomenda-se
iniciar snapshots já, mesmo antes de resolver a geocodificação, e abrir em
paralelo o pedido formal de export.

**3.º, relatórios anuais do OTSA.** Maior valor absoluto do conjunto, com 35
indicadores estruturados em ETIS e INSTO, seis edições e cadência viva. Fica em
terceiro apenas por exigir parser de PDF, o que quebra a restrição de stdlib. Se
essa restrição for flexibilizada, passa a primeiro sem discussão: as tabelas têm
grelha, a numeração I1 a I35 é chave estável entre edições, e 13 das 40 páginas
extraem-se limpas à primeira tentativa.

**4.º, CCDR Algarve.** Esforço alto e retorno corrente baixo. Vale como projecto
separado e de baixa prioridade, com dois objectivos delimitados: recuperar o
arquivo trimestral de 2009 a 2013 para dar profundidade histórica ao monitor, e
acompanhar manualmente as Contas Regionais, que são anuais e têm poucos pontos.
Não construir automatismo de recolha contínua sobre esta fonte.

## 4. O que ficou implementado, e onde se desviou da spec

### 4.1 INE, o conector que funcionou como previsto

A API JSON responde bem e os metadados em
`pindicaMeta.jsp?varcd=CODIGO&lang=PT` dão tudo o que é preciso antes de pedir
dados: periodicidade, primeiro e último período, unidade, e os códigos válidos
de cada dimensão. O `harvest_dados.py` lê sempre os metadados primeiro e só pede
os períodos que existem, porque um único código inválido em `Dim1` faz falhar o
lote inteiro com `Cod=4`.

Códigos fixados, todos validados contra chamada real antes de entrarem no
código:

| Série | varcd | Cobertura | Total |
|---|---|---|---|
| dormidas | 0012088 + 0010735 | 2020-01 a 2026-05, mensal, municipal | `Dim3=T` |
| hospedes | 0012089 + 0010736 | 2020-01 a 2026-05, mensal, municipal | `Dim3=T` |
| constituicoes | 0012244 + 0008067 | 2008-01 a 2026-06, mensal, municipal | `Dim3=TOT` |
| dormidas_anual | 0009877 | 2017 a 2025, anual, municipal | `Dim3=T` |
| hospedes_anual | 0009876 | 2017 a 2025, anual, municipal | `Dim3=T` |
| voos_aterrados | 0000865 | 1963-01 a 2026-05, mensal, LPFR | `Dim2=LPFR` |
| voos_descolados | 0000864 | idem | `Dim2=LPFR` |
| passageiros_desembarcados | 0000862 | idem | `Dim2=LPFR` |

Cada série assenta em mais de um indicador porque o INE parte as séries quando
muda a nomenclatura NUTS. O indicador corrente é pedido primeiro e o histórico
só preenche os períodos que faltam. Verificou-se que nos meses de sobreposição
os valores são idênticos, portanto o encadeamento é seguro.

Armadilhas confirmadas na prática, todas tratadas no parser:

A raiz da resposta é uma lista com um objecto, e `Dados` é um dicionário
indexado pelo rótulo textual do período em português, "Junho de 2024", não pelo
código `S3A202406` que se enviou. A ordem das linhas não é estável, por isso
indexa-se sempre por `geocod` e nunca por posição. Quando o dado é confidencial
a chave `valor` simplesmente não existe, e o parser usa `.get("valor")`. O campo
`valor` usa ponto decimal e sem separador de milhares, e é esse que se lê; o
`ind_string` usa vírgula e espaço e é só formatação para ecrã. Os códigos
geográficos municipais do Algarve são 1500801 a 1500816, mas existe um
`2004201 Lagoa` nos Açores, por isso filtra-se por prefixo `15008` e nunca por
nome. Passar `Dim2` e `Dim3` reduz a resposta de 7,4 MB para 3,3 KB, cerca de
2200 vezes menos tráfego.

**Desvio à spec, backfill desde 2019.** A spec pedia turismo mensal por
município desde 2019. Não existe. Os únicos indicadores mensais com desagregação
municipal começam em Janeiro de 2020. Os antecessores mensais (0001542, 0009808,
0009812) têm 11 a 13 categorias geográficas, param em NUTS II e não têm um único
município. Resolveu-se com duas séries anuais adicionais, `dormidas_anual` e
`hospedes_anual`, com dados municipais desde 2017, o que dá a base pré-covid de
2019 que era o objectivo declarado. As `constituicoes` e as séries do aeroporto
cobrem 2019 em base mensal sem problema.

Notas de qualidade: os últimos meses do turismo são provisórios ou preliminares
e são revistos, pelo que vale a pena re-recolher os meses recentes em cada
corrida, coisa que o upsert já faz de graça. O lag de publicação do INE é de
cerca de 45 a 60 dias.

### 4.2 IEFP, ficheiros .ods e não .xlsx

**Desvio à spec, formato e dependência.** A spec previa xlsx e autorizava
`openpyxl` como excepção. O IEFP publica `.ods`, que o openpyxl não lê. Como o
`.ods` é um zip com um `content.xml` lá dentro, lê-se com `zipfile` e
`xml.etree.ElementTree`, ambos da stdlib. **Não foi instalada nenhuma
dependência**, o que deixa o projecto mais limpo do que a spec permitia.

Os URL não se constroem, raspam-se. A página `www.iefp.pt/estatisticas` traz
num bloco `<script>` inline um objecto `var publications = {...}` com o catálogo
completo e todos os links de download, o que dispensa o endpoint AJAX. A
publicação relevante é a `publicationId` 287082, "Estatísticas Mensais por
Concelhos", dentro da chave `monthly`. O JSON vem com entidades HTML escapadas,
por isso faz-se `html.unescape` antes, e extrai-se por contagem de chavetas, que
é seguro, e não por regex, que é frágil.

Construir os URL à mão seria um erro: o identificador de pasta muda por ano e
não é derivável (2026 é 13482465, 2025 é 13014940, 2024 é 12563215, e assim por
diante até 2013), e há pelo menos seis meses com excepções de capitalização no
nome do ficheiro, do género "Desemprego **Registado**" em Novembro de 2020 e
Março de 2019. Dentro da janela de 24 meses o padrão é consistente, mas raspar
custa o mesmo e não parte.

Estrutura do ficheiro: cinco folhas, `Quadro_I` a `Quadro_V`, estáveis nos meses
testados a 24 meses de distância. O `Quadro_I` é o que serve, com desemprego
registado por género, tempo de inscrição e situação face ao emprego. A
desagregação geográfica é NUTS II, com o Algarve como código de região 5, em
bloco contíguo com os 16 concelhos por ordem alfabética. Os índices de linha não
são estáveis entre meses, porque o número de linhas em branco varia, por isso o
parser filtra por nome de concelho normalizado e nunca por posição. A coluna 12
é o total, com validação de que total é igual a homens mais mulheres.

Cadência e lag: o ficheiro do mês M sai por volta do dia 20 de M+1. A 5 de
Agosto de 2026 o mês mais recente disponível era Junho de 2026. Recolheram-se
24 meses, de Julho de 2024 a Junho de 2026, 384 pontos, 24 por 16 concelhos,
sem uma única falha.

Nota substantiva para o monitor: a sazonalidade é brutal e não é ruído.
Albufeira passa de 821 desempregados registados em Julho de 2024 para 5.604 em
Dezembro do mesmo ano, um factor de 6,8. O padrão confirma-se em dois Dezembros
distintos. Qualquer leitura desta série tem de ser homóloga, nunca mês contra
mês, e é por isso que o painel do dashboard mostra variação homóloga e não
variação em cadeia.

### 4.3 OpenSky, o conector que não pôde ficar completo

**Desvio à spec, e é o único que fica por fechar.** A spec assumia acesso
anónimo com janelas de sete dias e limite de cerca de 100 chamadas por dia. Esse
acesso deixou de existir. Testado a 5 de Agosto de 2026:

| Janela pedida | Resposta |
|---|---|
| últimas 3 h e 6 h | `[]`, vazio |
| 12 h, 24 h, 36 h, 48 h atrás | `You cannot access historical flights` |

As janelas recentes vêm vazias porque as chegadas são calculadas por um processo
em lote nocturno, e as janelas com dados estão fechadas a anónimos. O resultado
líquido do acesso anónimo é zero pontos, não uma recolha degradada.

O OpenSky migrou para OAuth2 client credentials e retirou a autenticação básica.
O endpoint de token é
`https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token`,
com o realm `opensky-network` e não `opensky`, que devolve 404. Sem credenciais
responde 401 `invalid_client`, o que confirma que o endpoint está de pé.

O conector está implementado e testado até onde é possível sem conta. Lê
`OPENSKY_CLIENT_ID` e `OPENSKY_CLIENT_SECRET` do ambiente, pede o token, e
recolhe chegadas e partidas dia a dia, começando em ontem, porque o lote
nocturno não disponibiliza o próprio dia. Sem credenciais no ambiente escreve um
aviso e devolve zero, sem travar o resto do lote. Não há ficheiro de segredos de
propósito, para não haver credenciais a passar perto do repositório.

**Acção necessária do Jo**, quando quiser a série diária: criar conta gratuita
em opensky-network.org, ir a `/my-opensky/account`, criar um API client, e pôr
as duas variáveis no ambiente antes de correr o `fetch`. Um utilizador standard
tem 4.000 créditos diários; um backfill de 30 dias de chegadas e partidas custa
cerca de 1.800, e o incremental diário custa 60, portanto cabe com folga. O
teste decisivo, assim que houver credenciais, é repetir com `Bearer` uma janela
histórica: se devolver JSON está resolvido, se devolver 403 então o OpenSky
fechou o histórico a todos os escalões gratuitos.

**Mitigação já implementada.** Para o critério de aceitação não ficar
dependente de uma conta externa, acrescentaram-se três séries mensais do INE
para o aeroporto de Faro (LPFR): aeronaves aterradas, aeronaves descoladas e
passageiros desembarcados, com 89 meses cada desde Janeiro de 2019, sem
autenticação e com lag de cerca de 45 dias. Vale a pena mantê-las mesmo depois
de o OpenSky funcionar, porque são o denominador oficial contra o qual calibrar
a contagem do OpenSky, que é sempre parcial e depende da cobertura ADS-B.

Alternativa avaliada e descartada por agora: o Eurostat tem o dataset
`avia_paoa` com o aeroporto `PT_LPFR`, mensal, de 2004 a 2025, JSON aberto e sem
conta. Bate certo com o INE. Fica como redundância caso o INE mude de esquema,
mas o lag de sete a oito meses torna-o inútil como fonte corrente.

### 4.4 Pendentes

Uma coisa fora do âmbito deste módulo, encontrada pelo caminho e deixada por
tocar de propósito: o ficheiro de exclusões do repositório chama-se `gitignore`
e não `.gitignore`, pelo que o git nunca o leu. Como consequência, `monitor.db`
e `entidades.db` estão versionados e a spec parte de um pressuposto que não se
verifica. O `publish.py` só faz `git add site`, portanto nada disto é agravado
pelo trabalho deste módulo, mas convém decidir o que fazer, e a spec pedia
explicitamente para não mexer no ficheiro.

---

# Fase 1b: empresas e conectores secundários

Levantamento de 5 de Agosto de 2026, a seguir à Fase 1. Mesma regra: todos os
URL citados foram confirmados com pedido HTTP real.

## 5. Portal MJ e SICAE: o registo comercial empresa a empresa

### 5.1 publicacoes.mj.pt: não aconselhável, e a spec manda parar

O Portal das Publicações do Ministério da Justiça tem **duas camadas
anti-automação activas** no único ponto de entrada de pesquisa
(`https://publicacoes.mj.pt/Pesquisa.aspx`, HTTP 200, IIS 10 com ASP.NET):

Primeiro, **reCAPTCHA invisível da Google**. O `<head>` carrega
`//www.google.com/recaptcha/api.js`, o formulário tem o contentor
`divRecaptcha` com `data-sitekey="6LfWfwkTAAAAAF_tbbsmS54u0N7kpwdWF_kxp3Ks"`, e
o botão de pesquisa chama `VerifyCaptcha()` no `onclick` antes do postback.
Segundo, o controlo **NoBot do AjaxControlToolkit**, cujo propósito declarado é
distinguir humanos de bots por desafio JavaScript (`"ChallengeScript":
"eval('99+63')"`), tempo mínimo de preenchimento e frequência por IP.

Não foi submetido um único POST ao formulário, por decisão. A spec da Fase 1b
diz, literalmente, que se qualquer um dos sites bloquear ou exigir captcha se
deve PARAR, documentar e não contornar. É exactamente este o caso.

Não existe via alternativa. Verificado: `robots.txt` devolve 404 (portanto nada
proibido nem permitido explicitamente), `sitemap.xml` devolve 404, não há
endpoint JSON, feed, `.asmx` ou `.svc` referenciado nas páginas públicas, e o
`DetalhePublicacao.aspx` sem querystring devolve uma página vazia de 11 KB sem
expor parâmetro de identificação. Para chegar aos resultados seria mesmo preciso
replicar o ciclo de postbacks ASP.NET com viewstate, e derrotar o captcha.

Três ressalvas que tornam o portal mau alvo mesmo que o captcha não existisse.
A ajuda oficial (`Ajuda.aspx`) confirma que a pesquisa aceita **no máximo um
intervalo de 10 dias**, o que obriga a 3 ou 4 pesquisas por mês e por distrito,
com paginação por cima. Parte das publicações não é texto mas ficheiro PDF. E o
CAE não aparece no acto de registo, porque vive no FCPC e não no registo
comercial.

Acresce a questão de dados pessoais. As publicações contêm nomes de sócios e
gerentes, portanto uma recolha em massa é matéria de RGPD, e não apenas de
netiqueta técnica: exigiria base de licitude, avaliação de interesse legítimo e
minimização documentadas.

Enquadramento legal, para registo: o Decreto-Lei 111/2005 e a Portaria
590-A/2005 criam o regime de publicações em sítio de acesso público e gratuito.
Acesso público e gratuito não é, porém, o mesmo que autorização de recolha
automatizada em massa, e o sinal operacional que conta é o captcha.

**Volume que estaria em causa**, apurado por fonte alternativa (INE/DGPJ,
indicador 0012244, extracção real): cerca de 236 constituições e 67 dissoluções
por mês no Algarve. O problema nunca foi o volume, foi a barreira.

### 5.2 SICAE: viável, mas precisa do NIPC que o MJ não dá

O `www.sicae.pt` é o oposto. Sem captcha (zero ocorrências de `captcha`,
`recaptcha` ou `NoBot` no HTML da `Consulta.aspx`), sem `robots.txt` a proibir
(404), com base legal explícita de acesso público e gratuito na Portaria
311/2009, e com um endpoint GET trivial:

    http://www.sicae.pt/Detalhe.aspx?NIPC=<nipc>

Testado com dois NIPC de sociedades cotadas: devolve CAE principal e
secundários, e no POST à `Consulta.aspx` a designação textual do CAE vem no
atributo `title`, o que dispensa tabela de correspondência.

Duas ressalvas técnicas. O HTTPS não responde a partir de fora de Portugal (o
servidor faz reset do handshake TLS logo a seguir ao Client Hello; o HTTP
funciona), o que convém reconfirmar a partir de um IP português antes de
desenhar seja o que for, porque usar HTTP em produção é mau mesmo para dados
públicos. E não se conseguiu determinar se os códigos devolvidos são CAE Rev.3
ou Rev.4, sendo que a Rev.4 está em vigor desde 2025 e os indicadores do INE
que usamos continuam em Rev.3.

O SICAE fica documentado e por implementar, porque só serve com o NIPC em mão, e
era o Portal MJ que o daria.

### 5.3 Decisão

Decisão do Jo a 5 de Agosto de 2026: adiar a identidade das empresas. A tabela
`empresas_registo` fica criada e vazia no `monitor.db`, com o esquema da spec,
para quando houver fonte. O painel Empresas usa exclusivamente o INE. Se a
identidade voltar a ser requisito de produto, a alternativa honesta é uma fonte
comercial licenciada (Informa D&B, Racius, Iberinform), não um scraper do MJ.

Falsas pistas verificadas e descartadas: os datasets do IRN no dados.gov.pt
(`publicacoes`, `empresas`, `eol`) são agregados nacionais e param em Janeiro de
2018; e o `diariodarepublica.pt/dr/detalhe/ato-societario/<id>` é uma SPA cujo
conteúdo só chega por API interna e cobre a III Série anterior a 2006.

## 6. Camada A: o retrato anual do INE

Seis séries validadas contra chamadas reais, todas por município e por secção
CAE Rev.3, com backfill desde 2015.

| Série | varcd corrente | varcd histórico | Detalhe |
|---|---|---|---|
| empresas_stock | 0014063 (2023-2024) | 0008511 (2008-2022) | exige `Dim4=T` |
| empresas_nascimentos | 0014099 (2023-2024) | 0009703 (2008-2022) | só secções |
| empresas_mortes | 0014101 (2021-2024) | 0009705 (2008-2022) | ver nota abaixo |
| empresas_vn | 0013862 (2023-2024) | 0008513 (2008-2022) | euros absolutos |
| empresas_pessoal | 0013861 (2023-2024) | 0008512 (2008-2022) | número |
| vab_sector | 0014115 (1995-2023) | código único | NUTS2, milhões |

Quatro descobertas que mudaram o código.

**As mortes de 2021 e 2022 têm de vir do indicador novo.** O 0014101 recua até
2021 e cria dois anos de sobreposição com o 0009705, e os valores não batem
certo: 421 de 576 células divergem, e a soma dos 16 municípios em 2022 passa de
9 259 para 10 047, mais 8,5%. Não é quebra de nomenclatura NUTS, é a revisão de
provisório para definitivo, visível nos `sinal_conv`: no indicador antigo 2021
está marcado como provisório e 2022 como estimativa, no novo ambos são
definitivos. O último ano com mortes definitivas é 2022, o que confirma o atraso
de cerca de dois anos que a spec antecipava.

**O `Dim4=T` é obrigatório na prática** no indicador de número de empresas.
Sem ele vêm as três formas jurídicas (total, empresa individual, sociedade) e as
linhas triplicam.

**O `Potencia10` importa e não se assume.** É 0 nos indicadores SCIE, que vêm em
euros absolutos, e 6 no VAB das Contas Regionais, que vem em milhões. O
harvester converte o VAB para euros ao gravar, para bater com o volume de
negócios.

**A supressão detecta-se com `'valor' not in linha`, nunca pela presença de
`sinal_conv`.** Os sinais de dado provisório, estimativa e dado rectificado vêm
acompanhados de valor normal; só o dado confidencial e o dado nulo é que não
trazem a chave.

**Segredo estatístico, medido.** Nas 272 combinações de 16 municípios por 17
secções, a supressão afecta 11,0% em 2020, 7,7% em 2022 e 5,9% em 2024, e
concentra-se em secções marginais no Algarve: extractivas, electricidade, água e
resíduos, agricultura. O total `TOT` nunca é suprimido, nem nenhuma das secções
que interessam à região (alojamento e restauração, comércio, construção). O
número de empresas e a demografia não têm supressão nenhuma; só o volume de
negócios e o pessoal ao serviço, que partilham exactamente a mesma máscara.

**Agregação sectorial: um desvio deliberado à spec.** A spec pedia tech = J mais
as divisões 62 e 63 mais M72, e turismo = I mais N79. Os indicadores de
demografia das empresas só publicam secções, sem divisões, portanto M72 e N79
não são separáveis lá. Optou-se por definir todos os sectores ao nível de
secção, de forma coerente entre stock e fluxos, porque é isso que permite fechar
a identidade contabilística por sector. As divisões 62 e 63 já estavam dentro de
J, portanto a perda real é M72 (investigação e desenvolvimento), N79 (agências
de viagens) e C10-C11 (indústrias alimentares). Fica documentado no próprio
painel.

**Coerência do stock-and-flow, verificada no dashboard.** Para o Algarve em
2024: 93 838 empresas em 2023, mais 15 625 nascimentos, menos 12 160 mortes, dá
97 303, contra um stock publicado de 98 598, ou seja um desvio de +1,3%. O
desvio é esperado e está explicado no painel: nascimentos e mortes contam
empresas com actividade económica no ano, o stock conta as activas a 31 de
Dezembro, e as mortes do último ano ainda são provisórias.

**Dois cross-checks independentes.** O número de empresas do Algarve em 2024
(98 598) e o pessoal ao serviço (233 462) coincidem exactamente com os valores
que o BeAlgarve publica na sua matriz de indicadores.

**Nota de leitura importante para o painel.** As setas trazem duas medidas que
não são comparáveis nem somáveis: nascimentos e mortes são demografia de
empresas do INE, anual, e incluem empresários em nome individual; constituições
e dissoluções são actos de registo de pessoas colectivas do INE/DGPJ, mensais, e
por isso muito menores (15 625 nascimentos contra 2 827 constituições em 2024).
A caixa central e a identidade contabilística usam apenas a série anual.

## 7. Conectores secundários

### 7.1 E-Redes, consumo de electricidade por concelho: implementado

A melhor das fontes secundárias, e território virgem, porque o BeAlgarve não tem
um único indicador de energia na matriz.

Portal OpenDataSoft em `e-redes.opendatasoft.com`, dataset
`3-consumos-faturados-por-municipio-ultimos-10-anos`, sem chave e sem
autenticação. O export CSV traz o distrito de Faro inteiro numa chamada:

    https://e-redes.opendatasoft.com/api/explore/v2.1/catalog/datasets/
    3-consumos-faturados-por-municipio-ultimos-10-anos/exports/csv
    ?where=coddistrito%3D%2208%22&delimiter=%3B

Campos úteis: `data` (AAAA-MM), `concelho`, `coddistritoconcelho` (DICO, 0801 a
0816), `nivel_de_tensao`, `energia_ativa_kwh`. Granularidade de origem: mensal
por freguesia e por nível de tensão; o harvester agrega ao concelho.

Três armadilhas. O nome do dataset diz dez anos mas são cinco e meio, de
Novembro de 2020 a Abril de 2026, medido. O filtro de distrito por nome exige
`"Faro"` em title case, `"FARO"` devolve zero. E o endpoint `/records` tem
tectos de 100 por página e 10 000 no total, que o `/exports/csv` não tem, por
isso é o export que se usa.

Existe um bucket `coddistritoconcelho = "08--"`, com o rótulo `OUTROS FARO`, que
são consumos que o RGPD impede de atribuir a freguesia. Na recolha real pesa
0,1% do total do distrito, e o harvester ignora-o e reporta a percentagem.

### 7.2 INE, preços da habitação por concelho: implementado

`varcd=0012239`, valor mediano das vendas de alojamentos familiares em euros por
metro quadrado, trimestral, de 2019 Q1 a 2026 Q1, com os 16 concelhos.

**O prefixo trimestral do INE é `S5A`**, no formato `S5A` + AAAA + trimestre
(por exemplo `S5A20261`). Completa a série que já conhecíamos: mensal `S3A`,
anual `S7A`.

A dimensão 3 é o domicílio fiscal do comprador, e usamos o total `T`. Vale a
pena registar que os códigos `2` (estrangeiro), `21` (União Europeia) e `22`
(restantes países) existem, e para o Algarve dão o preço pago por compradores
estrangeiros ao concelho, que é material interessante para uma fase posterior.

Cobertura real da recolha: 400 dos 464 pontos possíveis. As faltas são
supressão em concelhos com poucas transacções, sobretudo Monchique, que só tem 5
dos 29 trimestres, seguido de Aljezur e Vila do Bispo.

Códigos despistados: `0012227` e `0012228` são também trimestrais em euros por
metro quadrado mas a geografia é por cidade, não por concelho.

### 7.3 MONITUR via wp-json: viável, mas sem séries

A REST API do WordPress responde e está aberta, mas a verificação foi
inequívoca: `wp/v2/types` devolve 11 tipos, todos nativos, **zero custom post
types**; as 129 rotas são todas do core mais `oembed`; as taxonomias são só
`category` e `post_tag`, e não se aplicam a media; e a página das fact sheets
municipais tem zero elementos `<table>` e 36 links para PDF.

O valor real é um índice bibliográfico de 386 PDF com id, data, título, URL e
tamanho, obtenível em
`monitur.ualg.pt/wp-json/wp/v2/media?per_page=100&page=N&media_type=application`,
com os totais nos cabeçalhos `X-WP-Total` e `X-WP-TotalPages`. Extrair números
de dentro dos PDF é outro projecto e sai da stdlib.

Ressalva de conteúdo que desqualifica a fonte para o nosso uso: as fact sheets
municipais **agrupam os concelhos pequenos** (Alcoutim com Castro Marim e São
Brás; Aljezur com Monchique e Vila do Bispo). Nunca se obtêm os 16 concelhos
separados a partir do MONITUR.

Fica adiado. É um índice de acervo, não uma série.

### 7.4 DGEEC, inscritos na UAlg: viável, mas caro; adiado

Os dados são excelentes e o ficheiro é parseável em stdlib, mas a descoberta dos
identificadores não é.

O ficheiro de 2024/2025 está em `https://www.dgeec.medu.pt/api/ficheiros/`
`68f89c06c82132f5733ead7b`, confirmado HTTP 200, formato ODS de 9,7 MB (há
também `.xlsb`, que é binário proprietário e impossível em stdlib). Duas folhas,
cabeçalho na linha 2, 38 colunas, 173 644 linhas. A UAlg isola-se pelo código de
estabelecimento `0200` e desagrega-se por CNAEF a três níveis. Total apurado
para 2024/2025: 10 551 inscritos, com Faro 10 155 e Portimão 396.

Duas ressalvas pesadas. O `content.xml` descomprime para **851 MB**, o que
obriga a parsing em streaming e não a `ET.parse()`, e cada ano leva cerca de 70
segundos. E o site é uma SPA React cuja API devolve **JSON cifrado em AES-256-CBC**
(chave em claro no bundle público, portanto ofuscação de conteúdo público e não
autenticação), o que impede um cliente de descoberta em stdlib. A recomendação é
codificar a tabela de 21 anos para identificador de ficheiro e revê-la uma vez
por ano em Outubro ou Dezembro; o `/api/ficheiros/<id>` não é cifrado.

Nota de comparabilidade: o BeAlgarve publica 11 763 estudantes "no Algarve" para
2024/2025, contra os 10 551 apurados para a Universidade do Algarve. A diferença
são estabelecimentos privados na região. Definir bem qual dos dois se quer.

O `dados.gov.pt` está podre para este dataset: os 14 recursos param em 2017/2018
e apontam para hosts mortos.

### 7.5 BeAlgarve: nunca por código

Verificado com seis pedidos: é PHP renderizado no servidor, não é SPA, e **não
consome nenhum endpoint de dados**. Zero ocorrências de `fetch(`,
`XMLHttpRequest` ou `axios` em todos os chunks; zero referências a `/api/`, a
`.json` ou a `.csv`. O directório filtra no cliente sobre HTML já presente, via
atributos `data-directory-*`, e as entidades vêm embebidas pelo PHP. Extrair
significaria fazer parsing de marcação que pode mudar sem aviso. Não
implementar. A via é institucional, via NERA.

**A matriz deles serve de checklist**, e está em
`bealgarve.pt/pt/informacao-estatistica/`: 9 dimensões, 53 indicadores, 48
séries carregadas. Três leituras úteis. Primeiro, os indicadores de habitação e
de ensino superior deles são exactamente as fontes que validámos, e nós
conseguimos produzi-los ao concelho enquanto eles só publicam ao nível Algarve.
Segundo, não há um único indicador de energia na matriz. Terceiro, o único
indicador semanal deles é o volume armazenado nas barragens (APA/SNIRH), que é o
sinal mais vivo de toda a matriz e vale a pena considerar.

## 8. Higiene do repositório

A tarefa 0 da Fase 1b ficou feita: o ficheiro de exclusões passou de `gitignore`
para `.gitignore`, e `monitor.db` e `entidades.db` saíram do versionamento com
`git rm --cached`, mantendo-se em disco. Confirmado com `git check-ignore -v`,
que agora aponta os dois ficheiros para a regra `*.db` da linha 2.
