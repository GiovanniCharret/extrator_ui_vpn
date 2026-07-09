# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## O que é este projeto

Automação de UI (pywinauto/pyautogui) do sistema legado **LPT — Luz Para Todos** (app
Delphi/VCL — `TfrmPrincipal`, confirmado na F1; **não** é VB6 — `Z:\LNC\LNC.exe`) para
exportar relatórios "Projetos Executados" em PDF (Microsoft Print to PDF)
e consolidar ODI/UF/Município em CSV. O laço é dirigido por `base_contratos.json`
(contratos com `vigente != "Encerrado"` **e** que **não** sejam `ECM` — estes são
contratos novos fora da base legada LPT; filtro em `contratos.carregar_vigentes`).

**Duas fases já construídas e rodando na VPN:**
- **Fase 1 (`src/`, extração LPT)** — automação de UI do LPT; plano em `planning/PLAN_part1.md`.
- **Fase 2 (`ucs/`, extração de UCs via SSRS)** — sem UI: baixa cada contrato do relatório
  SSRS `22.3-UCs_paraAprovacao` (HTTP/SSPI) e consolida ODI↔UC; plano em `planning/PLAN_part2.md`.

A **Fase 3** prevista (site que valida e reporta avanço a partir de planilhas de beneficiários)
ainda **não foi planejada** — ver `planning/PLAN_part2.md` e a nota
`planning/2026-07-08-atualizacao-diaria-entrada-site.md`.

## Arquitetura (visão rápida)

**Fase 1 — pipeline de UI (`src/`):** `main.py` (laço/CLI/estado) → `contratos.py`
(vigentes + map) → `lnc_app.py` (conexão e navegação idempotente no LNC; seleciona tipo +
programa) → `exportar_pdf.py` (1 PDF por contrato, com as esperas estruturais) →
`parse_pdf.py` (pdfplumber, faixas de X por cabeçalho; ODI alfanumérico) →
`output/consolidado.csv`.
- **`scripts/`**: `inspecionar_app.py` (dump de telas, F1; também usado em runtime p/ screenshot
  de falha — best-effort) e `gerar_mapeamento.py` (enumera o dropdown, F2). Não são o pipeline.
- Fase 1 (F0–F6) **concluída**; planos por fase em `planning/PLAN_F1_F3.md` / `PLAN_F5.md`;
  Controle de progresso em `planning/PLAN_part1.md`.

**Fase 2 — pipeline SSRS sem UI (`ucs/`):** `main.py` (laço/CLI/estado, espelha o da Fase 1) →
`ssrs_client.py` (protocolo SSRS: sessão SSPI via `requests-negotiate-sspi`, descoberta de
parâmetros por SOAP `GetItemParameters` com fallback 2005, `render_csv`) → `download.py`
(1 CSV bruto por contrato, resolvendo `codese`/`programa` pelo map) → `consolida.py`
(consolida ODI↔UC; SQLite opcional) → `output_ucs/consolidado_ucs.csv`. `recon.py` é a
recon cega (U0) que descobriu o protocolo — grava tudo em `output_ucs/recon/`.

- **Retomada por ESTADO, não por arquivo** (padrão comum às duas fases —
  `src/estado_execucao.json` e `ucs/estado_ucs.json`): `decidir_modo` escolhe sozinho
  `refresh` (re-extrai tudo = dados frescos) ou `retomar` (só o que faltou), **sem flag**; o
  estado é gravado **após cada contrato** (robusto a Ctrl+C/queda/sono) e um contrato que
  falha 3× vira `desistido`. A consolidação reprocessa todos os brutos presentes
  (`output/pdf/<contrato>.pdf` na F1; `output_ucs/raw/<contrato>.csv` na F2) e regrava a saída
  inteira (idempotente).

## Modelo de operação — LEIA ANTES DE QUALQUER COISA

- **Claude NÃO tem acesso à máquina da VPN**, onde o LPT/SSRS rodam. Desenvolvimento acontece
  aqui (DEV); a validação real é feita **pelo usuário** na VPN, via pacotes numerados, com
  resultados trazidos de volta em `vpn_resultados/`.
- **Execução cega:** todo script deve gravar console, tracebacks completos e resultados
  estruturados em `output/` (F1) / `output_ucs/` (F2) — nada pode depender de observar a tela
  ao vivo. Uma falha silenciosa desperdiça uma viagem inteira do usuário.
- Automação de UI na VPN (Fase 1) só funciona com a **sessão RDP aberta, em foco e desbloqueada**.
  A Fase 2 (SSRS) usa a credencial da sessão Windows via SSPI — sem UI.
- Detalhes completos: `planning/PLAN_part1.md`, seção "Modelo de operação: DEV ↔ VPN".

## Documentação

- TODA a documentação de planejamento vive em **`planning/`**; os documentos-chave são
  **`planning/PLAN_part1.md`** (Fase 1) e **`planning/PLAN_part2.md`** (Fase 2), cada um com
  seu Controle de progresso (status, próximos passos, registro de execução — atualizar a cada
  sessão de trabalho).
- **Siga `planning/BEHAVIORAL_GUIDELINES.md` em todo desenvolvimento**: pensar antes de codar
  (explicitar premissas, perguntar em vez de assumir), simplicidade primeiro (mínimo de código,
  sem abstrações especulativas), mudanças cirúrgicas (cada linha rastreável ao pedido),
  critérios de sucesso verificáveis.
- **Não altere `planning/BEHAVIORAL_GUIDELINES.md` nem `planning/PROJECT_BUILDING.md`** (meta-docs
  do usuário). Fases e progresso vivem nos `PLAN_part*.md`.
- **Convenção de documentação do código** (obrigatória em código novo — toda a Fase 2 segue): toda
  função com docstring explicando *por que existe* + a lógica do input ao output *em fases
  numeradas*; e toda linha de lógica comentada. Exemplo no topo do `PLAN_F5.md`.

## Entradas e NÃO-entradas do pipeline

- **Entradas F1:** `base_contratos.json` (raiz), `config/programas_map.json`,
  `config/programas_dropdown.json`.
- **Entradas F2:** `base_contratos.json` (mesma base de contratos vigentes) + `config/ucs_map.json`
  (contrato → `{codese, concessionaria, programa, programa_label}`; auto-casado 21/21 na recon).
- **NÃO são entradas:** `minhas_notas/` (ignorar por completo), `manuais/` (apenas referência
  visual do fluxo manual + origem da fixture), `planning/` (documentação), `bug_fix/` (registros),
  `vpn_resultados/` (resultados trazidos da VPN — insumo de análise, não do pipeline).
- **Saídas F1:** `output/` (pdf/, logs/, inspecao/, consolidado.csv) — não versionar.
  **Saídas F2:** `output_ucs/` (raw/, logs/, recon/, consolidado_ucs.csv, ucs.db) — não versionar.
- O **estado de cada rodada** (`src/estado_execucao.json`, `ucs/estado_ucs.json` — dirigem a
  auto-retomada; ficam fora de `output*/` p/ não confundir com resultados) também não é versionado.

## Ambiente e execução

- Python via **uv**: `uv venv` → `.venv\Scripts\activate` → `uv pip install -r requirements.txt`.
  Nova dependência: `uv pip install X` + `uv pip freeze > requirements.txt` (sem BOM — usar
  `Out-File -Encoding ascii` no PowerShell).
- Testes offline (DEV ou VPN): `pytest tests/` — separados dos scripts; F1 = `test_f0..f5`,
  F2 = `test_ucs_*`. Fase única: `pytest tests/test_ucs_ssrs.py -v`.
- Pacote para a VPN: `powershell -ExecutionPolicy Bypass -File deploy\fazer_pacote.ps1 -Versao N`
  (F1); `fazer_pacote_ucs.ps1` / `fazer_pacote_recon.ps1` (F2); `fazer_pacote_completo.ps1`
  (as duas fases, a partir de `deploy_minimo/`). **Anti-bloqueio de e-mail:** o zip sai com
  `.ps1`/`.py` renomeados para `*.renomeado.txt` (o filtro corporativo barra zips com scripts);
  o `LEIA-ME_PRIMEIRO.txt` interno traz o comando único de restauração.
- Na VPN (usuário): `deploy\instalar.ps1` (setup) e `deploy\coletar.ps1` (zipa `output/` +
  `src/estado_execucao.json` em `resultados_<data>.zip`).
- Execução na VPN — **modo automático** (refresh/retomar pelo estado); cada `run*.ps1`
  **cria a venv sozinho na 1ª execução** (basta ter o `uv`):
  - **Fase 1:** `.\run.ps1` — flags `--dry-run`, `--contratos "A,B"`, `--refresh`, `--somente-parse`.
  - **Fase 2:** `.\run_ucs.ps1` — flags `--dry-run`, `--contratos "A,B"`, `--refresh`,
    `--somente-consolida`, `--dados-projetos` (inclui cod/nome do projeto), `--sqlite`
    (também carrega `ucs.db`), `--recon` (roda a recon U0 em vez do pipeline); `.\run_recon.ps1`
    é o atalho da recon.
- **VPN é Windows 32 bits:** NÃO forçar arquitetura no `uv venv` (forçar 64 bits quebra com
  `os error 216`). `cryptography` é pinado em **`48.0.1`** (última versão com wheel win32; ≥49
  tentaria compilar com Rust/MSVC e falha). Não desfazer esses pinos.
- **`deploy_minimo/`**: snapshot do conjunto mínimo runnable, organizado em **duas fases
  autocontidas** (cada uma com seu pacote, `config/`, `requirements.txt` mínimo e `COMO_RODAR.html`):
  - `fase1_lnc/` — Fase 1 (extração LPT): `src/` + `scripts/` + `config/programas_*` +
    `base_contratos.json` + `run.ps1`.
  - `fase2_ucs/` — Fase 2 (UCs via SSRS): `ucs/` + `config/ucs_map.json` + `run_ucs.ps1` +
    `run_recon.ps1`.
  - `run_tudo.ps1` (raiz) orquestra as duas, **roteando cada argumento só para a fase que o aceita**
    (ex.: `--sqlite` só cai na Fase 2); `COMO_USAR.html` documenta o uso e cada argumento. Cada fase
    cria sua própria venv na 1ª execução.
  Referência/versionamento; os builders canônicos dos pacotes da VPN são `deploy\fazer_pacote*.ps1`
  (`fazer_pacote.ps1` = Fase 1; `fazer_pacote_ucs.ps1` / `fazer_pacote_recon.ps1` = Fase 2).

## Regras críticas

- **Não usar o botão Rel.Excel** do LPT (demora minutos; o fluxo é via Print to PDF).
- Timeouts, títulos de janela e seletores (F1) ficam **centralizados em `src/config.py`**;
  URLs/endpoints SOAP, nomes de parâmetro SSRS e caminhos (F2) em **`ucs/config.py`** — nunca
  espalhados pelo código. Esperas estruturais (janela existir/sumir, botão habilitar,
  arquivo estável), nunca sleep fixo como mecanismo principal.
- A geração do PDF desabilita o botão Imprimir e pode levar ~1 min (`TIMEOUT_GERACAO=300`).
- Arquivos sempre UTF-8 (`encoding="utf-8"`); CSV em `utf-8-sig` com `;`.
  Scripts `.ps1` em **ASCII puro** (PowerShell 5.1 sem BOM corrompe acentos).
- `config/programas_map.json` é manual: `{contrato: {programa, tipo}}`. `programa` = texto exato
  do dropdown (**1:1**, duplicata é erro); `tipo` = radio "Tipo de Projeto" (`Eletrificação Rural`
  por padrão; ex.: Piauí 8ª = `Fonte Alternativa`). O relatório filtra por programa **E** tipo, e o
  tipo é selecionado em **todo** contrato (persiste entre iterações). `contratos.validar_mapeamento`
  exige ambos (tipo ∈ `config.TIPOS_PROJETO`).
- `config/ucs_map.json` (F2) é manual/auto-casado: `{contrato: {codese, concessionaria, programa,
  programa_label}}`. `codese` e `programa` são os DOIS parâmetros em cascata do relatório SSRS
  (`22.3-UCs_paraAprovacao`) — códigos numéricos, não texto. O CSV do SSRS vem `utf-8-sig`,
  delimitado por vírgula, com decimais brasileiros entre aspas; linhas placeholder (ODI e UC
  ambos vazios = contrato sem UCs) são descartadas na consolidação.
