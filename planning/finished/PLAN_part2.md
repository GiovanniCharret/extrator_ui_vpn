# Plano de implementação — Fase 2 (`ucs/`): extração das UCs via SSRS

> **Fase EM OPERAÇÃO desde 18/06/2026 — é o único pipeline ativo do projeto.** Versão visual:
> `planning/PLAN_part2.html`. Contexto-mãe: `planning/PLAN_part1.md` (Fase 1, extração LPT —
> **aposentada em 17/09/2026**). Este é um pacote independente (`ucs/`): não toca o LNC nem o
> `src/`. O plano abaixo é o registro do que foi decidido e construído; o **Controle de progresso**
> no fim é a fonte da verdade do andamento.

---

## Objetivo (do usuário)

1. Exportar informações de **UC (Unidade Consumidora)** para cada contrato de `config/programas_map.json`.
2. As informações de UC alimentam uma **base de validação** consolidada.
3. A extração das UCs é feita via VPN no **SSRS** (relatório `22.3-UCs_paraAprovacao`), nos endereços
   `http://sqlprdrs/Reports/Pages/Folder.aspx` /
   `…?ItemPath=%2fLPT%2fPrivados%2fDesenvolvidos%2fProjetos`.

**Para que serve (visão de fim a fim, do `Validação das obras Rurais…docx`):** o fluxo manual hoje é
(1.1) baixar Projetos Executados do LPT → **Fase 1, pronta**; (1.2) baixar a planilha de **UCs+ODI**
do SSRS → **esta Fase 2**; (1.3) receber a *planilha complementar* por e-mail
(`IdentificacaoBeneficiarios_…xlsx`); (1.4) **validar** a complementar contra as bases (ODI, UC,
município; e na complementar: CPF/CNPJ e coordenadas) → **site futuro, fora do escopo**. A Fase 2
constrói a base "ODI × UC" que, junto com a base "ODI × município" da Fase 1, torna a validação
do site possível.

**O que NÃO é desta fase:** o site de validação (Fase 3, fora de escopo); a validação AmL via
SharePoint/PROC (item 2 do docx); qualquer atualização de Power BI.

---

## Por que um pacote novo (e não dentro de `src/`)

Regra do usuário (PLAN_part2 original): *"Scripts dedicados devem viver em pastas separadas."* A
Fase 2 é **trabalho de natureza diferente** da Fase 1 — sem Delphi/VCL, sem `pywinauto`, sem PDF.
É "baixar um relatório SSRS parametrizado em CSV, por contrato, e montar uma base consultável".
Reusa os **padrões** da Fase 1 (config centralizado, retomada por estado, execução cega com tudo
logado em `output/`) mas **nenhum** de seu código de UI.

---

## Resumo

| | |
|---|---|
| Pacote novo | `ucs/` (`config.py`, `recon.py`, `ssrs_client.py`, `download.py`, `municipios.py`, `consolida.py`, `main.py`) |
| Config nova | `config/ucs_map.json` — `{contrato: {codese, concessionaria, programa, programa_label}}`; **é ele que dirige a rodada** (a Fase 2 não lê `base_contratos.json`) |
| Entrada nova | `entrada/RELATORIO_DTB_BRASIL_2024_MUNICIPIOS.csv` (DTB/IBGE) — obrigatória, viaja no pacote |
| Saídas (não versionar) | `output_ucs/` → `raw/<contrato>.csv`, **`consolidado_ucs_modelo.csv`** (`contrato;odi;uc;uf;municipio`), `ucs.db` (opcional), `logs/`, `recon/` |
| Estado da rodada | `ucs/estado_ucs.json` (espelha `src/estado_execucao.json`) |
| Runner | `run_ucs.ps1` (auto-bootstrap da venv, espelha `run.ps1`) |
| Deps novas | `requests`, `requests-negotiate-sspi` (SQLite é stdlib) |
| Método de download | **decidido na recon (U0)**: HTTP/SSPI (alvo) com fallback navegador |
| Fonte da verdade | **CSV bruto por contrato** (`raw/`) — o banco é derivado e regenerável |
| Decisão de storage | **deferida** p/ depois do benchmark com volume real (CSV × SQLite × Postgres) |
| Entrega da fase | `.\run_ucs.ps1` percorre os **23** contratos do `ucs_map.json`, baixa, resolve UF/município pelo DTB, consolida e reporta na VPN |

---

## Decisões fechadas com o usuário (não re-decidir)

- **Recon-first, Abordagem A.** Uma rodada de reconhecimento cego (U0) na VPN descobre o
  desconhecido **antes** de finalizar o código. _(18/06/2026)_
- **CSV bruto por contrato = fonte da verdade.** O banco (SQLite/Postgres) é **derivado** e
  regenerável a partir dos brutos → a escolha do storage é barata e adiável. _(18/06/2026)_
- **Storage final = SQLite (decidido pelo benchmark VPN 18/06).** Volume real **muito menor que o
  temido**: 21 contratos = **145.391 linhas**, CSV **11,55 MB**, SQLite **18,35 MB**, lookup por ODI
  **0,14 ms** (indexado). Postgres seria injustificado (não há multiusuário/escrita concorrente nem
  dezenas de milhões de linhas) e **SQLAlchemy** idem (a carga é ~20 linhas de stdlib, isolada em
  `consolida.consolidar_sqlite`). Handoff p/ o site = o arquivo `ucs.db`. Se o cenário mudar
  (multiusuário/Postgres), a migração toca só o loader. _(18/06/2026)_
- **Método de download decidido na recon.** Alvo = HTTP/SSPI (URL access do SSRS, sem navegador);
  fallback = navegador automatizado, só se o servidor bloquear URL access. _(18/06/2026)_
- **Pacote separado `ucs/`**, Fase 1 intocada; **`config/ucs_map.json` novo**. _(18/06/2026)_
- **Saídas em `output_ucs/`, não em `manuais/`.** `manuais/` é referência-only por convenção; a
  cópia de handoff para o site (se necessária) é um passo de export explícito. _(18/06/2026)_
- **Numeração:** etapas da Fase 2 = **U0 (recon) → U5**.

---

## Convenção de documentação do código (vale para TODO o `ucs/`) `[regra]`

Conforme `planning/PROJECT_BUILDING.md`, **todo** código novo da Fase 2 segue esta regra:

1. **Toda função tem docstring**, explicando **nesta ordem**:
   - **Por que a função existe** — o problema que ela resolve / o motivo de ser uma função separada;
   - **A lógica do input ao output, em fases numeradas** — `Entrada → Fase 1 → Fase 2 → … → Saída`,
     descrevendo **o que cada bloco transforma** (não só o tipo de retorno).
2. **Toda linha de código é comentada** — inclusive as que parecem óbvias.

Os sketches de código deste plano são abreviados; a implementação real segue o estilo completo
acima em **todas** as funções.

---

## O que sabemos hoje (das telas `manuais/export1.jpg` / `export2.jpg`)

- **Relatório:** `22.3-UCs_paraAprovacao`, em `/LPT/Privados/Desenvolvidos/Projetos`.
- **Dois parâmetros em cascata:** `Concessionária` (ex. `COELBA`) → `Programa` (ex.
  `COELBA 11ª TRANCHE REVISÃO 2`; tem opção `Todos` e `<Selecione um Valor>`). O texto do
  `Programa` é **próximo, mas não idêntico** ao do dropdown da LNC, e há um **eixo novo**
  (`Concessionária`) que a LNC não tinha.
- **Exportação oferece CSV diretamente** ("CSV (delimitado por vírgula)"), além de Excel/XML/PDF.
- O grid já traz **UC + ODI + projeto + status/datas** por linha → o relatório **já casa UC↔ODI**
  (não precisamos alimentar ODIs da Fase 1 para baixar).

## O que ainda NÃO sabemos (e a recon U0 vai responder)

1. Se **HTTP URL-access** (render direto via `/ReportServer`) funciona com auth Windows/SSPI.
2. Os **nomes internos** dos parâmetros (por trás dos rótulos "Concessionária"/"Programa").
3. A **enumeração completa** dos dois dropdowns (toda concessionária → seus programas) — insumo do
   `ucs_map.json`.
4. O **layout exato do CSV** (header + amostra) → quais colunas são UC, ODI, município, IBGE, UF.

---

## Arquitetura (visão rápida)

```
ucs/
  config.py        # URL ReportServer, ItemPath do relatório, nomes dos params, timeouts, paths, encoding
  recon.py         # U0: testa HTTP/SSPI, descobre params, enumera dropdowns, salva CSV amostra → output_ucs/recon/
  ssrs_client.py   # ponto ÚNICO do "como baixar": render_csv(concessionaria, programa) -> bytes (SSPI)
  download.py      # por contrato: resolve map → render → grava raw/<contrato>.csv (+ valida header)
  municipios.py    # U6: DTB do IBGE → {código: (uf, município)}, indexado por 7 E 6 dígitos
  consolida.py     # streaming dos brutos + DTB → consolidado_ucs_modelo.csv (+ SQLite opcional)
  main.py          # laço/CLI/estado (refresh|retomar), espelha src/main.py
```

**Fluxo:** `main` → `contratos`/map (`ucs_map.json`) → `download.baixar` (1 CSV bruto por contrato,
com retomada por estado) → `consolida` (base enxuta + opcional SQLite) → `output_ucs/`.

**Retomada por ESTADO** (idêntica à Fase 1): `ucs/estado_ucs.json` gravado **após cada contrato**;
`decidir_modo` escolhe `refresh` (re-baixa tudo = dados frescos) ou `retomar` (só o que faltou);
contrato que falha 3× vira `desistido`. A consolidação reparseia todos os `raw/*.csv` presentes e
regrava a base inteira (idempotente).

---

## Etapas (U0 → U5)

Legenda: **[AUTO]** = pytest offline no DEV · **[VPN]** = roteiro executado na VPN (`TESTES.md`).

### U0 — Recon (o entregável da próxima ida à VPN) `[VPN]`

`ucs/recon.py` — execução **cega**, grava tudo em `output_ucs/recon/`:

1. **HTTP/SSPI reachability** — GET no `ReportServer` e na pasta do relatório com
   `requests-negotiate-sspi`; loga status (200/401/404…). Decide **HTTP × navegador**.
2. **Descoberta de parâmetros** — via SOAP `ReportService2010.asmx → GetItemParameters`
   (retorna `Name` interno + valores válidos + dependência em cascata). *Fallback:* render com
   chutes (`Concessionaria`/`Programa`) lendo a mensagem de erro do SSRS.
3. **Enumeração dos 2 dropdowns** — para cada `Concessionária`, obter os `Programa` dependentes →
   `output_ucs/recon/dropdowns.json` (insumo do `ucs_map.json`).
4. **Amostra CSV** — renderiza **1 contrato** (ex. COELBA 11ª) em CSV; salva o bruto + escreve
   header, nº de linhas e 3 primeiras linhas no log → define o mapeamento de colunas.
5. **Fallback documentado** — se o HTTP falhar de vez, o log emite as instruções da captura manual
   (export CSV pelo navegador + screenshots) para não desperdiçar a viagem.
6. **Saída-resumo** `output_ucs/recon/RECON.md` (ou `.json`) que o usuário traz de volta.

**Sucesso:** o usuário retorna com (a) veredito HTTP-sim/não, (b) nomes dos params, (c)
`dropdowns.json`, (d) 1 CSV amostra. *(Sem isso, U2–U4 não fecham.)*

### U1 — `ucs/config.py` + esqueleto do pacote `[AUTO]`

Centraliza: `REPORTSERVER_URL`, `ITEM_PATH` do relatório, **nomes dos params** (preenchidos pós-U0),
`TIMEOUT_RENDER`, `MAX_TENTATIVAS_CONTRATO`, paths (`OUTPUT_UCS_DIR`, `RAW_DIR`, `CSV_CONSOLIDADO_UCS`,
`ESTADO_UCS_JSON`), `CSV_ENCODING="utf-8-sig"`, `CSV_DELIMITADOR=";"`. **Sucesso:** importa limpo;
teste de fumaça das constantes.

### U2 — Mapeamento `config/ucs_map.json` + `ucs/contratos`-helpers `[AUTO]`

Da enumeração da recon, **gero um rascunho** casando por texto com os `programa` da Fase 1 (são
próximos); **o usuário confirma/corrige à mão** (como na Fase 1). `validar_mapeamento` exige os 21
contratos e que cada par `(concessionaria, programa)` exista nos valores válidos enumerados.
**Sucesso [AUTO]:** validação aprova um map completo e reprova faltas/par inválido.

### U3 — `ssrs_client.render_csv` + `download.baixar` `[AUTO]` parcial + `[VPN]`

`render_csv(concessionaria, programa) -> bytes`: monta o URL access (`rs:Command=Render&rs:Format=CSV`
+ params descobertos), auth SSPI, timeout/retries. `baixar(contrato)`: resolve map → render → grava
`raw/<contrato>.csv` → valida header não-vazio/esperado. **Sucesso [AUTO]:** construção do URL a
partir de config+map é unit-testada **sem rede**. **[VPN]:** baixa 1–2 contratos de verdade.

### U4 — `consolida` (base enxuta + SQLite opcional + benchmark) `[AUTO]`

Streaming (stdlib `csv`, baixa memória) dos `raw/*.csv` → seleção das **colunas enxutas** →
`consolidado_ucs_modelo.csv`. _(Forma final, 18/09/2026: `contrato;odi;uc;uf;municipio`, com
`;cod_projeto;nome_projeto` sob `--dados-projetos`; uf/município resolvidos pelo DTB — ver U6.)_ Carga **opcional** em
`ucs.db` (sqlite3) com índice em ODI/UC. **Helper de benchmark** reporta linhas/tamanho/tempo de
query → decide CSV × SQLite × Postgres com número real. **Sucesso [AUTO]:** fixture (amostra da U0)
→ base esperada; spot-check de uma `(contrato, odi, uc)` conhecida.

### U5 — `main.py` + `run_ucs.ps1` + roteiros VPN `[AUTO]` + `[VPN]`

`python -m ucs.main`: auto refresh/retomar; flags `--dry-run`, `--contratos`, `--refresh`,
`--somente-consolida`, `--recon`. Estado/retomada **idêntico à Fase 1** (persistência incremental).
`run_ucs.ps1` auto-bootstrap (espelha `run.ps1`; adiciona as 2 deps). `planning/TESTES.md` ganha o
**Roteiro recon (U0)** e o **Roteiro rodada completa**; pacote via `deploy/fazer_pacote.ps1`.
**Sucesso:** `--dry-run` lista o plano; `[VPN]` rodada completa dos 21 com estado/retomada.

---

## Critérios de sucesso da fase

1. `pytest tests/test_ucs_*.py` verde (U1, U2, U3-URL, U4 — offline).
2. `[VPN]` recon (U0) traz params + dropdowns + 1 CSV amostra.
3. `[VPN]` rodada completa: um `raw/<contrato>.csv` por contrato do map (**23** em 18/09/2026) +
   `consolidado_ucs_modelo.csv`; zero falhas (ou
   `desistido` registrado com motivo); retomada após interrupção funciona.
4. Benchmark registra volume real → decisão de storage documentada no Controle de progresso.

---

## Riscos / questões em aberto

| Risco | Sev. | Mitigação |
|---|---|---|
| URL access (HTTP) desativado no SSRS | médio | Fallback navegador (Playwright); recon decide cedo, sem retrabalho |
| Nomes de params/colunas diferentes do esperado | médio | Recon U0 captura tudo antes de finalizar U2–U4; raw guarda **todas** as colunas |
| Volume real estoura desempenho do CSV único | médio | Fonte = raw por contrato; benchmark decide SQLite/Postgres; migração trivial |
| Texto do `Programa` no SSRS ≠ LNC | baixo | `ucs_map.json` é **novo** e confirmado à mão; não depende do map da Fase 1 |
| Auth SSPI não disponível fora da sessão Windows | baixo | Roda na VPN com sessão Windows ativa (mesma premissa da Fase 1) |
| PII no relatório | baixo | `22.3` parece ter cód. projeto/UC/ODI/status (não CPF/nome); `output_ucs/` fora do git e local |

---

## Controle de progresso (Fase 2)

> Atualizar a cada sessão. Legenda: `[ ]` pendente · `[x]` concluído · `[~]` parcial · `[f]` revisão futura.

| Etapa | O quê | Status | Testes | Data | Notas |
|---|---|---|---|---|---|
| U0 | Recon SSRS (HTTP, params, dropdowns, CSV amostra) | `[x]` VPN | 10/10 offline | 18/06/2026 | **SUCESSO** na 4ª ida: HTTP/SSPI OK; params `codese`+`programa`; SOAP 2010+omit; **199 concessionárias / 563 programas** enumerados; **amostra CSV 200 (1,38 MB, 30 colunas)** |
| U1 | `ucs/config.py` (nomes/combo/colunas) | `[x]` DEV | — | 18/06/2026 | fixados `PARAM_CONCESSIONARIA='codese'`, `PARAM_PROGRAMA='programa'`, `SOAP_COMBO=(2010,omit)`, CSV de entrada (vírgula/utf-8-sig) e colunas-alvo (UC/ODI/...) |
| U2 | `config/ucs_map.json` + validação | `[x]` DEV | parte do suite | 18/06/2026 | **21/21 contratos casados**; `download.validar_mapeamento` + teste do map real |
| U3 | `ssrs_client` + `download` | `[x]` DEV | em test_ucs_* | 18/06/2026 | `download.baixar` (render CSV por codese/programa + validação + grava bruto); render já provado na recon |
| U4 | `consolida` + SQLite opcional + benchmark | `[x]` DEV | 5 testes | 18/06/2026 | `extrair_linhas`/`consolidar_csv` (streaming) + `consolidar_sqlite` + `benchmark`; base UC↔ODI (sem município — vem da Fase 1) |
| U5 | `main` + `run_ucs.ps1` | `[x]` DEV+VPN | 11 testes | 18/06/2026 | laço/estado/retomada (espelha Fase 1) + CLI (`--dry-run/--contratos/--refresh/--somente-consolida/--sqlite/--recon`); `run_ucs.ps1` auto-bootstrap; pacote `fazer_pacote_ucs.ps1` |
| U6 | `ucs/municipios.py` — UF/município pelo DTB | `[x]` DEV+VPN | 4 testes | 18/09/2026 | O 22.3 só traz o **código IBGE** (`PPC_COD_LOCALIZACAO`); UF/município vêm do DTB. **O SSRS entrega 6 dígitos (sem DV) e o DTB tem 7** → `carregar_dtb` indexa as DUAS chaves (0 colisões em 2024). Regra tudo-ou-nada: código sem par ⇒ relatório completo no log e a rodada **não grava** (escreve `.tmp` e só promove no fim) |
| U7 | Pacote `extrator_sqlprdrs.zip` (só Fase 2) | `[x]` VPN | — | 18/09/2026 | Fase 1 fora do pacote; pasta `deploy_minimo/sqlprdrs-reports/` (ex-`fase2_ucs`) com `entrada/` dentro; `executar.bat` chama `run_tudo_com_uv_install.ps1 2 --refresh`. Rodada validada pelo usuário |

### Próximos passos

1. **Convergir o repo com o pacote `legado.zip`** (versão que rodou na VPN em julho/2026 e nunca
   voltou ao repositório). Dele já vieram o `municipios.py` e a consolidação com `.tmp`; falta
   diffar o resto — o legado ainda difere no **bootstrap** (Python do sistema + `pip` +
   `extrair_ucs.bat`, que instala o Python, em vez do `uv`), traz `uvicorn` no requirements e
   documentação de operador (`LEIA-ME.txt`, quadro "EXTRACAO OK / TERMINOU COM ERRO").
   **Decisão pendente do usuário:** bootstrap fica no `uv` ou converge para o `.bat` do legado?
2. **Nome do arquivo entregue ao site.** A saída agora é `consolidado_ucs_modelo.csv`, mas o site
   espera `entrada/lpt/consolidado_ucs.csv` — alinhar o nome (ou renomear no envio).
3. **Sync DEV→VPS.** O `run_sync.ps1` saiu do `deploy_minimo/`; hoje o envio dos CSVs ao VPS é
   manual. Definir onde essa peça passa a viver.
4. **Bug conhecido (aberto):** se o `uv venv` for interrompido, sobra um `.venv` parcial e toda
   execução seguinte morre com `A directory already exists at: .venv`. Fix: detectar venv sem
   `python.exe` e recriar com `--clear`.
5. **`ECO 034/2026`** (ÂMBAR / Amazonas 11ª) baixa 0 linhas — provável contrato ainda sem UCs,
   como `ECO 042/2025`. É o único mapeamento sem confirmação visual do usuário.

### Registro de execução (mais recente no topo)

- **18/09/2026 (tarde)** — **BUG DO MUNICÍPIO RESOLVIDO: o SSRS manda 6 dígitos, o DTB tem 7.**
  As rodadas (2) e (3) vieram com uf/município vazios em **100%** das linhas. O usuário trouxe o
  `legado.zip` — o pacote que gerou o modelo bom, que rodou na VPN em julho/2026 e **nunca voltou
  ao repositório**. Nele está o `ucs/municipios.py` com a regra que faltava: o código do município
  vem **sem o dígito verificador** (6 dígitos), então o DTB precisa ser indexado pelas duas chaves.
  Adotado o legado nessa parte (mais maduro que a minha versão): normalização do código (espaços,
  `.0` do Excel), detecção de colisão de prefixo, escrita em `.tmp` com promoção atômica e
  relatório completo dos códigos órfãos. Validado no pacote com um bruto de 6 dígitos
  (`160055` → Amapá/Pracuúba) e **confirmado pelo usuário na VPN**. Suíte 94/97 (as 3 vermelhas
  são da Fase 1 aposentada). Pacote `extrator_sqlprdrs.zip`.
- **18/09/2026 (manhã)** — **UF/município entram na base + renomeações.** Regra do cruzamento
  recuperada pelo usuário: `PPC_COD_LOCALIZACAO` × coluna **H** do DTB. Conferência: os **1.010**
  pares (uf, município) do modelo existem todos no DTB. A base passa a
  `contrato;odi;uc;uf;municipio`; saída renomeada para **`consolidado_ucs_modelo.csv`**; pasta do
  pacote `fase2_ucs` → **`sqlprdrs-reports`**; zip → **`extrator_sqlprdrs.zip`**; `entrada/` (DTB)
  passa a viajar dentro da pasta da fase. **Erro meu corrigido no caminho:** a DTB estava como
  opcional (avisava no log e seguia) — entrada obrigatória ausente virava base inteira em branco
  com exit 0 e "CONCLUIDO COM SUCESSO" na tela; agora falha alto.
- **17/09/2026** — **Contratos novos + Fase 1 aposentada.** Recon rodada de novo na VPN: achados
  `ENERGISA TOCANTINS`=994 / `Tocantins 7ª Tranche - Metas Excepcionais`=1544 (`ECO 045/2026`) e
  `AMAZONAS ENERGIA`=1026 / `Amazonas 11ª Tranche`=1534 (`ECO 034/2026`); os 21 antigos
  reconferidos sem desvio → `ucs_map.json` com **23 contratos**. O usuário informou que o scraping
  do LNC **não é mais usado** (ODIs e UCs vêm todas do SQL/SSRS) → o pacote passou a levar só a
  Fase 2. Teste obsoleto (`len(mapa) == 21`) virou invariante de cobertura: todo contrato vigente
  precisa estar no map — teria pego o `ECO 034/2026` ausente.
- **15–16/09/2026** — **Fase 2 parada por credencial do SSRS, não por bug nosso.** Todos os
  contratos falhavam com HTTP 500 + página HTML. O Report Manager revelou a cadeia
  `rsProcessingAborted` → `rsErrorImpersonatingUser` → `rsLogonFailed` no data source **`LNC_EXT`**
  (credencial armazenada expirada). Corrigido pelos engenheiros do SSRS; nada mudou do nosso lado.
  **Lição:** a exceção truncava o corpo do erro em 300 bytes, que só continham o `<head>` — a
  mensagem real ficava invisível. Se a Fase 2 falhar em bloco de novo, suspeitar disto primeiro.
- **19/06/2026** — **Stack rodando na VPN (32 bits) OK.** Último ajuste: a Fase 1 não criava
  `output/pdf/` numa pasta nova/limpa — o `mkdir` morava em `exportar_pdf.caminho_saida()`, que é
  **pulado** quando o `main` passa o `destino` pronto; o diálogo Print-to-PDF então caía na última
  pasta usada (a anterior). **Fix:** `exportar_pdf.exportar` faz `destino.parent.mkdir(...)` sempre.
  Mesma classe de bug coberta no `scripts/inspecionar_app.py` (screenshot/dump de falha agora
  criam `INSPECAO_DIR`). Suíte 93/93. `pacote_completo_v3.zip`.
- **19/06/2026** — **CAUSA RAIZ FINAL: VPN é Windows 32 bits + regressão minha no requirements.**
  O Fix C (forçar 64 bits) era ERRADO: o PC da VPN é **Windows 32 bits** → Python 64 bits não roda
  (`os error 216`), e ainda quebrou a Fase 2 que funcionava. O problema real da Fase 1: o
  `deploy_minimo/fase1_lnc/requirements.txt` que criei ficou **sem pin**, então o uv puxava
  `cryptography==49` — que **não tem wheel p/ Windows 32 bits** → tentava compilar (Rust/MSVC) e
  falhava. (O `requirements.txt` original do repo já tinha `cryptography==48.0.1`, por isso o
  pacote_v13 funcionava.) **Fix definitivo:** (a) **revertido o forçar-64-bits** em todos os run
  scripts (volta a `uv venv`, que escolhe Python compatível com o SO — 32 ou 64); (b) **fixado
  `cryptography==48.0.1`** (última com wheel win32) no fase1 requirements. Confirmado via PyPI que
  48.0.1/pillow 12.2/pypdfium2 5.10 têm wheel win32; `uv pip compile` resolve sem conflito (sem
  compilar). `pacote_completo_v2.zip` gerado. Portátil p/ 32 **e** 64 bits.
- **19/06/2026** — **Falha recorrente era cópia parcial na VPN.** Os fixes (A/B/C) estavam certos no
  repo (`run.ps1` 2067 bytes), mas a VPN seguia com o `run.ps1` antigo (1658 bytes) — ao copiar por
  cima da pasta existente, o `.venv` travado fazia o script velho sobrar. **Solução:** builder
  `deploy/fazer_pacote_completo.ps1` gera `pacote_completo_v1.zip` (deploy_minimo inteiro,
  consistente, scripts renomeados) com `LEIA-ME` mandando **apagar a pasta/venv antiga antes de
  extrair**. Fim do risco de versão misturada.
- **19/06/2026** — **CAUSA RAIZ do "pywinauto": venv de 32 bits.** O Fix A revelou o erro real do
  `uv pip install` da Fase 1: o `uv` criava a venv com **Python 32 bits** (`i686-pc-windows-msvc`),
  e a `cryptography` (transitiva de `pdfplumber`→`pdfminer-six`) **não tem wheel p/ Windows 32 bits**
  → tentava compilar (Rust/maturin) e falhava em `link.exe not found`. Como o install abortava, NADA
  era instalado — daí o `ModuleNotFoundError: pywinauto` (sintoma, não causa). **Fix C:** todos os
  run scripts (repo + `deploy_minimo`) passam a forçar **Python 64 bits managed**
  (`uv venv --python cpython-3.12-windows-x86_64-none`). Validado no DEV: venv 64 bits instala
  `pdfplumber`+`cryptography 49`+`pywinauto` via wheel, sem compilar. **Na VPN: apagar a `.venv`
  de 32 bits antes de re-rodar** (o `uv venv` só recria se ausente).
- **19/06/2026** — **Bug de bootstrap do `run.ps1` (Fase 1) + orquestrador.** Na VPN, o
  `run_tudo.ps1 ambas` quebrou na Fase 1: `ModuleNotFoundError: pywinauto`. Causa: o `run.ps1`
  (Fase 1) ainda tinha a lógica antiga — só instalava deps **se a venv não existisse**; o 1º
  download do pywinauto falhou (blip de rede), a venv ficou criada-porém-incompleta e as
  re-execuções **pulavam** a instalação. **Fix A:** `run.ps1` (repo + `deploy_minimo/fase1_lnc`)
  agora **sincroniza deps sempre** (idempotente), igual ao `run_ucs.ps1` — re-rodar retoma a
  instalação. **Fix B:** `deploy_minimo/run_tudo.ps1` ficou **resiliente** (falha de uma fase não
  derruba a outra). Validado no DEV: `run_tudo.ps1 2 --dry-run` cria venv, instala, lista os 21
  (exit 0), Fase 1 intocada. (A Fase 2 nunca dependeu de pywinauto.)
- **19/06/2026** — **Ajustes na base (pedido do usuário):** removida a coluna `cod_programa`
  (redundante — é o próprio código do programa do contrato, constante por contrato); `cod_projeto`/
  `nome_projeto` agora são **opcionais** via flag `--dados-projetos` (default = base enxuta
  `contrato;odi;uc`). Validado nos brutos reais: default 145.389 linhas (sem as 2 placeholders),
  CSV 10,86 MB. Suíte 93/93. Gerado `pacote_ucs_v3.zip`.
- **18/06/2026** — **VALIDAÇÃO VPN OK — pipeline completo rodou (`pacote_ucs_v1`): 21/21 baixados,
  0 falhas.** `consolidado_ucs.csv` + `ucs.db` gerados. **Benchmark:** 145.391 linhas, CSV 11,55 MB,
  SQLite 18,35 MB, lookup ODI 0,14 ms → **storage decidido = SQLite** (Postgres/SQLAlchemy
  injustificados). Achado de dados: contratos novos sem UCs (ECO 039, ECO 042) vêm com uma
  **linha-placeholder vazia** do SSRS — adicionado filtro em `extrair_linhas` (ODI e UC vazios =>
  ignora) + teste. ODI alfanumérico confirmado (ex.: `ODR142PROJ001`). Suíte 91/91. **Fase 2
  essencialmente concluída** (resta conferência de dados pelo usuário + handoff do `ucs.db`).
- **18/06/2026** — **U2–U5 implementadas e verdes no DEV.** `download.py` (carregar/validar map +
  `baixar` render CSV por codese/programa, valida e grava bruto), `consolida.py` (`extrair_linhas`
  por nome de coluna, `consolidar_csv` streaming, `consolidar_sqlite` indexado, `benchmark`),
  `main.py` (estado/retomada espelhando a Fase 1 + CLI). `run_ucs.ps1` (auto-bootstrap, sincroniza
  deps) e builder `deploy/fazer_pacote_ucs.ps1`. Fixture sintética `tests/fixtures/exemplo_ucs.csv`.
  Suíte **90/90**; `--dry-run` lista os 21 com codese/programa. Gerado `pacote_ucs_v1.zip`.
  **Aguarda validação na VPN** (`.\run_ucs.ps1`). Decisão de storage (CSV×SQLite×Postgres) sai do
  benchmark com volume real.
- **18/06/2026** — **4ª recon: SUCESSO TOTAL (U0 concluída).** Params confirmados:
  `codese` (concessionária, código) + `programa` (código); SOAP venceu com **2010 + HistoryID
  omitido**. Cascata enumerou **199 concessionárias / 563 pares (codese,programa)**; **amostra CSV
  HTTP 200, text/csv, 1,38 MB, 30 colunas**. Colunas-chave: `UCP_Num_UC` (UC), `PPC_Odi` (ODI),
  `PPC_Cod_Projeto`, `PPC_Nome_Projeto`, `PPC_Cod_Programa` — **sem coluna de município/UF** (este
  relatório é a base **UC↔ODI**; município vem da Fase 1 por ODI). CSV de entrada = vírgula +
  decimais "12,34" entre aspas + BOM. **U1** fixou nomes/combo/colunas no `config.py`; **U2** casou
  **21/21** contratos → `config/ucs_map.json` (aguarda conferência). Próximo: validar map + U3/U4/U5.
- **18/06/2026** — **3ª recon: probe revelou o nome interno real `codese`** (rótulo
  "Concessionária"); os nomes do relatório são **códigos**, não os textos da UI. SOAP ainda
  faltou: o 2005 acusou `rsParameterTypeMismatch` no `HistoryID`/`snapshotID` (forma `xsi:nil`),
  e o 2010 não fora salvo (eu guardava só a última tentativa). **Correções (v4):** (a) **omitir
  `HistoryID`** por padrão (era o que quebrava o 2005); (b) `get_parametros` tenta a **matriz**
  2010/2005 × omit/nil e **salva TODAS as tentativas** (`getparams_*.xml`); (c) **probe iterativo**
  por render descobre todos os nomes em ordem (independe do SOAP) — `descobrir_nomes_por_render`;
  (d) a amostra passa a renderizar com os **códigos válidos** colhidos na cascata (não os rótulos),
  p/ enfim trazer o header do CSV; (e) dropdowns guardam (label, value). Testes 10 (ucs) / 68
  (total). Gerado `pacote_recon_v4.zip`.
- **18/06/2026** — **2ª recon: HTTP/SSPI OK (200), mas SOAP faltou e render deu 500.**
  Achados: servidor é **SSRS 2008 R2 (10.50)**; o WSDL revela namespace
  `.../2010/03/01/`**`ReportServer`** (eu usava `ReportService` → "SOAPAction não reconhecida");
  o render com nome chutado deu `rsUnknownReportParameter` ("'Concessionaria' não está definido")
  → o nome interno do parâmetro é outro. **Correções:** namespace 2010 corrigido; **fallback
  ReportService2005** (`GetReportParameters`/`<Report>`); parser aceita `ItemParameter`/
  `ReportParameter` e dependências via `<string>`; `get_parametros` autodetecta o dialeto e o
  reusa na cascata; recon ganhou **probe sem-params** (faz o SSRS revelar o nome interno real) e
  registra o dialeto que funcionou. Testes 8 (ucs) / 66 (total). Gerado `pacote_recon_v3.zip`.
- **18/06/2026** — **1ª recon na VPN voltou vazia** (`vpn_resultados/recon.zip`): RECON.md sem
  reachability → `criar_sessao` falhou antes de qualquer rede. Causa: a venv já existia (Fase 1) e
  o `run_recon.ps1` só instalava deps quando a venv estava ausente → `requests`/
  `requests-negotiate-sspi` nunca entraram. **Correções:** (a) `run_recon.ps1` agora
  **sincroniza as deps sempre** (idempotente); (b) `recon.py` **surfaceia o erro de sessão no
  RECON.md** (run cego passa a ser auto-diagnóstico); (c) instruções pedem trazer `output_ucs/`
  inteira (recon + logs). Gerado `pacote_recon_v2.zip`.
- **18/06/2026** — **U0 (recon) implementada no DEV** (recon-first, HTTP/SSPI primeiro):
  pacote `ucs/` criado (`config.py`, `ssrs_client.py`, `recon.py`), `run_recon.ps1`
  (auto-bootstrap), deps `requests`+`requests-negotiate-sspi` no `requirements.txt`,
  `output_ucs/` + `ucs/estado_ucs.json` no `.gitignore`. Testes offline dos helpers puros
  (URL render, envelope SOAP, parse GetItemParameters) 6/6; suíte total 64/64. Princípio:
  recon grava tudo cru e parseia best-effort. **Próximo:** rodar `.\run_recon.ps1` na VPN.
- **18/06/2026** — Brainstorming da Fase 2 concluído; Abordagem A aprovada; plano escrito
  (`PLAN_part2.md` + `.html`). Confirmado: SSRS `22.3-UCs_paraAprovacao`, 2 params em cascata,
  export CSV nativo (telas `manuais/export1.jpg`/`export2.jpg`).
