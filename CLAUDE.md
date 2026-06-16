# CLAUDE.md

## O que é este projeto

Automação de UI (pywinauto/pyautogui) do sistema legado **LPT — Luz Para Todos** (app
Delphi/VCL — `TfrmPrincipal`, confirmado na F1; **não** é VB6 — `Z:\LNC\LNC.exe`) para
exportar relatórios "Projetos Executados" em PDF (Microsoft Print to PDF)
e consolidar ODI/UF/Município em CSV. O laço é dirigido por `base_contratos.json`
(contratos com `vigente != "Encerrado"` **e** que **não** sejam `ECM` — estes são
contratos novos fora da base legada LPT; filtro em `contratos.carregar_vigentes`).

## Arquitetura (visão rápida)

- **Pipeline** (`src/`): `main.py` (laço/CLI/relatório) → `contratos.py` (vigentes + map) →
  `lnc_app.py` (conexão e navegação idempotente no LNC) → `exportar_pdf.py` (1 PDF por
  contrato, com as 4 esperas estruturais) → `parse_pdf.py` (pdfplumber, faixas de X por
  cabeçalho) → `output/consolidado.csv`. **Retomada = existência do PDF** em `output/pdf/`:
  consolidação reparseia todos os PDFs presentes e regrava o CSV inteiro (idempotente).
- **`scripts/`** são ferramentas pontuais por fase (inspeção F1, mapeamento F2) — não fazem
  parte do pipeline.
- O projeto é construído em fases F0–F6; **o que já existe vs. planejado está no Controle de
  progresso do `planning/PLAN.md`** (módulos e fases detalhados nas seções 4–5). Não presuma
  que um módulo citado aqui já foi escrito.

## Modelo de operação — LEIA ANTES DE QUALQUER COISA

- **Claude NÃO tem acesso à máquina da VPN**, onde o LPT roda. Desenvolvimento acontece aqui
  (DEV); a validação real é feita **pelo usuário** na VPN, via pacotes + roteiros numerados
  (`planning/TESTES.md`), com resultados trazidos de volta em `vpn_resultados/`.
- **Execução cega:** todo script deve gravar console, tracebacks completos e resultados
  estruturados em `output/` — nada pode depender de observar a tela ao vivo. Uma falha
  silenciosa desperdiça uma viagem inteira do usuário.
- Automação de UI na VPN só funciona com a **sessão RDP aberta, em foco e desbloqueada**.
- Detalhes completos: `planning/PLAN.md`, seção "Modelo de operação: DEV ↔ VPN".

## Documentação

- TODA a documentação de planejamento vive em **`planning/`**; o documento-chave é
  **`planning/PLAN.md`** (inclui o Controle de progresso — status por fase, próximos passos
  e registro de execução, que devem ser atualizados a cada sessão de trabalho).
- Mapa de testes e roteiros da VPN: `planning/TESTES.md`.
- **Siga `planning/BEHAVIORAL_GUIDELINES.md` em todo desenvolvimento**: pensar antes de codar
  (explicitar premissas, perguntar em vez de assumir), simplicidade primeiro (mínimo de código,
  sem abstrações especulativas), mudanças cirúrgicas (cada linha rastreável ao pedido),
  critérios de sucesso verificáveis.
  ** Não faça mudanças em `planning/BEHAVIORAL_GUIDELINES.md`. Fases de projeto devem viver em **`planning/PLAN.md`**

## Entradas e NÃO-entradas do pipeline

- **Entradas:** `base_contratos.json` (raiz), `config/programas_map.json`,
  `config/programas_dropdown.json`.
- **NÃO são entradas:** `minhas_notas/` (ignorar por completo), `manuais/` (apenas referência
  visual do fluxo manual + origem da fixture), `planning/` (documentação), `bug_fix/` (registros),
  `vpn_resultados/` (resultados trazidos da VPN — insumo de análise, não do pipeline).
- **Saídas:** `output/` (pdf/, logs/, inspecao/, consolidado.csv, relatorio_execucao.csv) —
  não versionar.

## Ambiente e execução

- Python via **uv**: `uv venv` → `.venv\Scripts\activate` → `uv pip install -r requirements.txt`.
  Nova dependência: `uv pip install X` + `uv pip freeze > requirements.txt` (sem BOM — usar
  `Out-File -Encoding ascii` no PowerShell).
- Testes offline (DEV ou VPN): `pytest tests/` — separados dos scripts, um arquivo por fase;
  fase única: `pytest tests/test_f0_ambiente.py -v`.
- Pacote para a VPN: `powershell -ExecutionPolicy Bypass -File deploy\fazer_pacote.ps1 -Versao N`.
  **Anti-bloqueio de e-mail:** o zip sai com `.ps1`/`.py` renomeados para `*.renomeado.txt`
  (o filtro corporativo barra zips com scripts); o `LEIA-ME_PRIMEIRO.txt` interno traz o
  comando único de restauração.
- Na VPN (usuário): `deploy\instalar.ps1` (setup) e `deploy\coletar.ps1` (zipa resultados).
- Execução do pipeline (na VPN, após F6): `.\run.ps1` (`--dry-run`, `--contratos`, `--force`,
  `--somente-parse`).

## Regras críticas

- **Não usar o botão Rel.Excel** do LPT (demora minutos; o fluxo é via Print to PDF).
- Timeouts, títulos de janela e seletores: **centralizados em `src/config.py`** — nunca
  espalhados pelo código. Esperas estruturais (janela existir/sumir, botão habilitar,
  arquivo estável), nunca sleep fixo como mecanismo principal.
- A geração do PDF desabilita o botão Imprimir e pode levar ~1 min (`TIMEOUT_GERACAO=300`).
- Arquivos sempre UTF-8 (`encoding="utf-8"`); CSV em `utf-8-sig` com `;`.
  Scripts `.ps1` em **ASCII puro** (PowerShell 5.1 sem BOM corrompe acentos).
- Mapeamento contrato → programa do dropdown é **1:1** e manual (`config/programas_map.json`);
  duplicata é erro.
