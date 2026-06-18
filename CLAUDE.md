# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## O que é este projeto

Automação de UI (pywinauto/pyautogui) do sistema legado **LPT — Luz Para Todos** (app
Delphi/VCL — `TfrmPrincipal`, confirmado na F1; **não** é VB6 — `Z:\LNC\LNC.exe`) para
exportar relatórios "Projetos Executados" em PDF (Microsoft Print to PDF)
e consolidar ODI/UF/Município em CSV. O laço é dirigido por `base_contratos.json`
(contratos com `vigente != "Encerrado"` **e** que **não** sejam `ECM` — estes são
contratos novos fora da base legada LPT; filtro em `contratos.carregar_vigentes`).

**Escopo deste repositório = Fase 1 (extração LPT)** — encerrada e commitada em 17/06/2026
(pendente só a validação VPN final do `pacote_v13`). As **fases futuras** previstas pelo usuário
(Fase 2: cruzar ODIs com Unidades Consumidoras via SQL/SSRS; Fase 3: site que valida e reporta
avanço a partir de planilhas de beneficiários) estão **registradas em `planning/PLAN.md` → "Fases
futuras"**, **ainda não planejadas**. Há uma **decisão pendente** sobre se elas vivem aqui ou num
projeto novo (recomendação: separar — stack/runtime/deploy diferentes do pipeline de UI).

## Arquitetura (visão rápida)

- **Pipeline** (`src/`): `main.py` (laço/CLI/estado) → `contratos.py` (vigentes + map) →
  `lnc_app.py` (conexão e navegação idempotente no LNC; seleciona tipo + programa) →
  `exportar_pdf.py` (1 PDF por contrato, com as esperas estruturais) → `parse_pdf.py`
  (pdfplumber, faixas de X por cabeçalho; ODI alfanumérico) → `output/consolidado.csv`.
- **Retomada é por ESTADO, não por arquivo** (`src/estado_execucao.json`): `main.decidir_modo`
  escolhe sozinho `refresh` (re-exporta tudo = dados frescos) ou `retomar` (só o que faltou),
  **sem flag**; o estado é gravado **após cada contrato** (robusto a Ctrl+C/queda/sono) e um
  contrato que falha 3× vira `desistido`. A consolidação reparseia todos os PDFs presentes
  (`output/pdf/<contrato>.pdf`) e regrava o CSV inteiro (idempotente).
- **`scripts/`**: `inspecionar_app.py` (dump de telas, F1; também usado em runtime p/ screenshot
  de falha — best-effort) e `gerar_mapeamento.py` (enumera o dropdown, F2). Não são o pipeline.
- Fase 1 (F0–F6) **concluída**; histórico/detalhes por fase no Controle de progresso do
  `planning/PLAN.md` (planos por fase em `PLAN_F1_F3.md`/`PLAN_F5.md`).

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
- **Não altere `planning/BEHAVIORAL_GUIDELINES.md` nem `planning/PROJECT_BUILDING.md`** (meta-docs
  do usuário). Fases e progresso vivem em `planning/PLAN.md`.
- **Convenção de documentação do código** (vale para a F5 e código novo): toda função com docstring
  explicando *por que existe* + a lógica do input ao output *em fases numeradas*; e toda linha de
  lógica comentada. Exemplo no topo do `PLAN_F5.md`.

## Entradas e NÃO-entradas do pipeline

- **Entradas:** `base_contratos.json` (raiz), `config/programas_map.json`,
  `config/programas_dropdown.json`.
- **NÃO são entradas:** `minhas_notas/` (ignorar por completo), `manuais/` (apenas referência
  visual do fluxo manual + origem da fixture), `planning/` (documentação), `bug_fix/` (registros),
  `vpn_resultados/` (resultados trazidos da VPN — insumo de análise, não do pipeline).
- **Saídas:** `output/` (pdf/, logs/, inspecao/, consolidado.csv) — não versionar. O **estado
  da rodada** (`src/estado_execucao.json` — dirige a auto-retomada; fora de `output/` p/ não
  confundir com resultados) também não é versionado.

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
- Na VPN (usuário): `deploy\instalar.ps1` (setup) e `deploy\coletar.ps1` (zipa `output/` +
  `src/estado_execucao.json` em `resultados_<data>.zip`).
- Execução do pipeline (na VPN): `.\run.ps1` — **modo automático** (refresh/retomar pelo estado);
  flags `--dry-run`, `--contratos "A,B"`, `--refresh` (força tudo), `--somente-parse`. O `run.ps1`
  **cria a venv sozinho na 1ª execução** (basta ter o `uv`).
- **`deploy_minimo/`**: snapshot do conjunto mínimo runnable (6 `.py` + dados + `run.ps1` +
  `COMO_RODAR.html`) — referência/versionamento; o builder canônico do pacote é `deploy\fazer_pacote.ps1`.

## Regras críticas

- **Não usar o botão Rel.Excel** do LPT (demora minutos; o fluxo é via Print to PDF).
- Timeouts, títulos de janela e seletores: **centralizados em `src/config.py`** — nunca
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
