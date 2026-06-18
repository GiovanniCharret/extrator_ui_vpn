# PLAN.md — Exportação automatizada de "Projetos Executados" (Sistema LPT)

> Documento-chave do projeto. Status das fases é atualizado no **Controle de progresso** abaixo ao final de cada fase.
> Mapa de testes detalhado: `planning/TESTES.md` (criado na F0).
> Versão visual deste plano: `planning/PLAN.html`.

> **⚠️ REGRA DE DESENVOLVIMENTO:** todo o desenvolvimento do script deve seguir
> **`planning/BEHAVIORAL_GUIDELINES.md`** — pensar antes de codar (explicitar premissas,
> perguntar em vez de assumir), simplicidade primeiro (mínimo de código, sem abstrações
> especulativas), mudanças cirúrgicas (cada linha alterada rastreável ao pedido) e execução
> orientada a critérios de sucesso verificáveis (os testes de cada fase deste plano).
> Esta regra vale para TODAS as fases e será reproduzida no CLAUDE.md.

## Controle de progresso

Esta seção é a **fonte única de verdade do andamento do projeto** e tem três partes, atualizadas a cada sessão de trabalho:
1. **Status por fase** — visão geral em tabela;
2. **Próximos passos** — o que será feito na sequência (sempre apontando a ação concreta seguinte);
3. **Registro de execução** — diário do que foi feito, em ordem cronológica inversa (mais recente no topo).

Legenda (de `planning/PROJECT_BUILDING.md`): `[ ]` pendente · `[x]` concluído · `[a]` anulado · `[f]` revisão futura · `[r]` rollback/falhou

### Status por fase

| Fase | Descrição | Status | Teste passou? | Data | Observações |
|---|---|---|---|---|---|
| — | Planejamento (este documento) | `[x]` | n/a | 12/06/2026 | Aprovado pelo usuário (com modelo DEV↔VPN) |
| F0 | Setup do ambiente | `[x]` DEV / `[x]` VPN | 5/5 no DEV **e** na VPN | 12/06/2026 | VPN ok com `pacote_v2.zip` (uv baixou CPython 3.12.13 — máquina não tinha Python) |
| F1 | Inspeção (dumps de tela) | `[x]` | n/a (inspeção) | 16/06/2026 | B1–B5 coletados; todos os seletores reais fixados em `src/config.py`. Falta só o dump vivo do diálogo "Imprimir" (passa rápido) — não bloqueante (passo8.jpg + diálogo padrão) |
| F1 | `lnc_app.py` (navegação) | `[x]` DEV+VPN | offline + roteiro 3 | 16/06/2026 | navegação idempotente validada na VPN (run 2 pulou navegação); coordenada do menu confirmada |
| F3 | Exportar UM PDF | `[x]` DEV+VPN | roteiro 3 OK 2× | 16/06/2026 | **PDF real gerado (53 págs, válido), 2× seguidas (sobrescrita OK)**; diálogo "Imprimir" não aparece (vai direto ao salvar) |
| F2 | Descoberta do dropdown e mapeamento | `[x]` DEV / `[ ]` VPN | 8/8 (acceptance verde) | 16/06/2026 | **Map preenchido à mão (21 ECO, 1:1 contra o dropdown real)** → `test_mapeamento_real_quando_preenchido` deixou de pular. Falta só rodar a seleção real no LNC na VPN (roteiro 4) |
| F3 | Exportar UM PDF de ponta a ponta | `[ ]` | — | — | |
| F4 | Parsing do PDF → ODI/UF/Município | `[x]` DEV | 6/6 offline | 16/06/2026 | `parse_pdf.py` (faixas de X por cabeçalho); spot-check `("10010263","RS","LAGOAO")`; suíte total 18/18 |
| F5 | Laço completo, retomada, CSV | `[x]` DEV / `[ ]` VPN | suíte 58/58 | 17/06/2026 | `src/main.py` TDD. Pós-VPN: **auto-retomada por estado** (`src/estado_execucao.json`, gravado a cada contrato — robusto a Ctrl+C/sono; modo refresh/retomar automático; orçamento de 3 tentativas → `desistido`); **fix do parser** (ODI alfanumérico, 13.938 linhas reais); **filtro "Tipo de Projeto" por contrato** (ECO 029 = Fonte Alternativa). Nome do PDF por contrato. `pacote_v13`. Falta a viagem (Roteiro 5 com v13) |
| F6 | run.ps1 + documentação final | `[~]` parcial | — | 17/06/2026 | `run.ps1` mínimo pronto (repassa args); falta fixar "Microsoft Print to PDF" como impressora padrão + doc final. Será fechado junto da validação VPN do v13 |

### Próximos passos

1. **Validação VPN do `pacote_v13`** (Roteiro 5) — fecha a F5/F6: valida na VPN o filtro "Tipo de Projeto" (passo 5.0, ECO 029 = Fonte Alternativa), a auto-retomada, e uma rodada completa dos 21. Fixar a impressora padrão no `run.ps1` (resto da F6).
2. **Fase 2 (SQL — UCs)** — **só após decidir o local do projeto** (ver "Fases futuras"). Não planejada ainda.

> **Marco — Fase 1 (extração LPT) encerrada e commitada em 17/06/2026.** O pipeline F0–F5 está
> completo no DEV (suíte 58/58); resta a validação final na VPN com o `pacote_v13` (Roteiro 5) e o
> ajuste de impressora padrão (F6). As fases seguintes estão **registradas abaixo, não planejadas**.

### Fases futuras (registradas — NÃO planejadas)

> Informação trazida pelo usuário em 17/06/2026 para registro. **Nada planejado/projetado aqui** —
> cada fase terá seu próprio ciclo de brainstorming → plano → implementação quando chegar a vez.
> **Decisão pendente:** se estas fases vivem **neste** repositório ou num **novo projeto** (ver
> recomendação na conversa de 17/06 — separação sugerida pela diferença de stack/runtime/deploy).

- **Fase 2 — Cruzamento ODI × Unidades Consumidoras (SQL).** A partir das ODIs levantadas na
  Fase 1 (`output/consolidado.csv`), cruzar com as **UCs** de cada ODI, puxadas via SSRS:
  - `http://sqlprdrs/Reports/Pages/Folder.aspx`
  - `http://sqlprdrs/Reports/Pages/Folder.aspx?ItemPath=%2fLPT%2fPrivados%2fDesenvolvidos%2fProjetos`
- **Fase 3 (última prevista) — Site de validação + report de avanço.** Web app que recebe um
  arquivo similar a `manuais/identificacaobeneficiarios_ECx_0xx_20xx.xlsx` e:
  (a) valida **ODI, município e UC** e a ausência de células vazias;
  (b) **reporta os erros** encontrados e **só aceita o arquivo quando não houver erros**;
  (c) compara os avanços com os dados anteriores → **report de avanço de tipo de cliente por projeto**.

### Registro de execução

| Data | O que foi feito |
|---|---|
| 18/06/2026 | **Deploy mínimo + `run.ps1` auto-suficiente.** Criado `deploy_minimo/` (conjunto mínimo runnable: 6 `.py` de runtime + `inspecionar_app.py` p/ diagnóstico + dados + `run.ps1` + `requirements.txt` runtime-only + `COMO_RODAR.html`). Removido `src/__init__.py` (vazio; projeto roda como namespace package — suíte 58/58 confirma). **`run.ps1` agora faz bootstrap da venv** se ela não existir (`uv venv` + `uv pip install --python .venv\… -r requirements.txt`) — antes só exigia a venv e apontava p/ `instalar.ps1` (ausente no pacote mínimo). **Verificado de ponta a ponta** num temp do zero: cria venv, instala, `--dry-run` lista 21. `.gitignore` ganhou exceção `!deploy_minimo/COMO_RODAR.html`. |
| 17/06/2026 | **🏁 Fase 1 (extração LPT) encerrada e commitada.** Pipeline F0–F5 completo no DEV (suíte 58/58): conexão/navegação idempotente no LNC, exportação de PDF, parsing ODI/UF/Município, laço com auto-retomada por estado, consolidação e filtro Tipo de Projeto. Resta validação VPN do `pacote_v13` (Roteiro 5) + impressora padrão (F6). **Fases futuras registradas** (Fase 2 SQL/UCs, Fase 3 site de validação) na seção "Fases futuras" — **não planejadas**; decisão pendente sobre repo próprio vs. este. |
| 17/06/2026 | **F5 — persistência incremental do estado + estado movido para `src/`**. (1) `estado_execucao.json` agora é gravado **após cada contrato** (`executar` ganhou callback `persistir` injetável; `main` passa uma closure que regrava o estado parcial a cada passo) → Ctrl+C/queda/sono no meio da rodada deixa o estado salvo e a próxima chamada de `run.ps1` retoma de onde parou (antes só o fim de `main` gravava → interrupção dura não retomava). Smoke: estado parcial (A exportado, B/C pendentes) → `retomar` pula A, refaz B/C. (2) Caminho mudou de `output/` para **`src/estado_execucao.json`** (pedido do usuário: não confundir com resultados); `.gitignore` + `coletar.ps1` (passa a incluí-lo no zip) + `fazer_pacote.ps1` (passa a EXCLUÍ-lo, p/ não sobrescrever o estado da VPN) ajustados. Roteiro 5.5 agora é verídico. **Suíte 58/58.** Docs sincronizados; `pacote_v13`. |
| 17/06/2026 | **F5 — filtro "Tipo de Projeto" por contrato (Tarefa 9, 2ª rodada VPN)**. Descoberto que o relatório filtra por Programa **e** pelo radio "Tipo de Projeto" (5 opções); o código só controlava o Programa. ECO 029 (Piauí 8ª) só tem dados em **Fonte Alternativa** → vinha 0 linhas. Como o radio persiste entre iterações, é selecionado **para todo contrato**. Mudanças: `tipo` por contrato no `programas_map.json` (explícito nos 21; ECO 029=Fonte Alternativa; **ECO 029 tinha sumido do map por edição acidental — restaurado**), `config.TIPOS_PROJETO`/`TIPO_PROJETO_PADRAO`/`CLASSE_RADIO_TIPO`, `validar_mapeamento` exige `tipo` válido, `lnc_app.selecionar_tipo` [VPN] + smoke `--tipo`, `exportar(programa,contrato,tipo,...)`, `main` propaga o tipo (grava no estado). ECO 039/042 com 0 linhas = sem dados cadastrados (não é bug). **Suíte 57/57.** Risco: seletores dos 4 tipos não-default só confirmam na viagem. PLAN_F5 Tarefa 9 + TESTES sincronizados. Pendente: `pacote_v12`. |
| 17/06/2026 | **F5 — auto-retomada por estado + orçamento de tentativas (Tarefa 8, pós-VPN)**. Decisão: `run.ps1` sem flag **decide o modo sozinho** lendo `output/estado_execucao.json` (JSON que **substitui** o `relatorio_execucao.csv` — é relatório humano E estado). `decidir_modo` (rodada anterior completa→`refresh`; incompleta→`retomar`), `planejar(modo,estado)`, `atualizar_estado` (sucesso zera tentativas+`ultimo_ok`; falha incrementa, vira `desistido` ao atingir `MAX_TENTATIVAS_CONTRATO=3`; refresh reinicia contador; pulado carrega anterior), `carregar`/`escrever_estado` (JSON). "Completa" = status de exportação (não nº de linhas), então relatório vazio legítimo (ECO_036) não trava. Limite de tentativas evita que 1 contrato quebrado (ECO 029) congele o refresh dos demais. CLI: default automático, `--refresh` força tudo, **removido `--retomar`/`montar`/`escrever_relatorio`(CSV)**. TDD: 15 testes novos (decidir_modo/planejar-modo/atualizar_estado/round-trip) + smoke de integração (sem estado→refresh; estado c/ 1 falha→retomar pula 20). **Suíte 54/54.** Docs (PLAN_F5 Tarefa 8, TESTES Roteiro 5, CLAUDE, run.ps1) sincronizados. Pendente: gerar `pacote_v11` p/ a próxima viagem. |
| 17/06/2026 | **1ª rodada VPN (Roteiro 5) + fix crítico do parser**. `resultados_20260617_1008.zip`: 15 PDFs gerados, mas a análise revelou 3 problemas. **(1) CRÍTICO [resolvido no DEV]:** `parse_pdf.RE_ODI` (`^\d{6,}$`) só aceitava ODI numérico; ODIs reais são alfanuméricos (`ODR136PROJ019A`, `B0174334`, `PA2000112LPT130024PA`…) → **9/15 PDFs vinham com 0 linhas** e até "ok" perdiam dados (ECO 019: 10→217). Fix: `RE_ODI=^[A-Za-z0-9]+$` (guarda de UF do município barra lixo). Fixture nova `exemplo_odi_alfanumerico.pdf` (ECO_011) + 4 testes TDD. Reparse dos 15 PDFs reais: **13.938 linhas** (era 3.718). **Suíte 45/45.** ECO_036 rende só 1 linha (conferir). **(2) máquina LOCAL (cliente RDP) dormiu** ~16 min na rodada → ECO 039–043 falharam com "no active desktop" (não é a VM; é ops na estação local — plano de energia). **(3) ECO 029** travou o preview em `0% Page 1 of 0` 2× (erro do LNC; usuário vai checar com engenheiros). Pendente: semântica do auto-`--retomar` no `run.ps1` (a decidir) + possível refactor do relatório p/ JSON. |
| 17/06/2026 | **F5 — parte DEV pronta (TDD, plano `PLAN_F5.md`+`.html` aprovado)**. `src/main.py`: `planejar` (default re-exporta tudo = dados frescos; `--retomar` opt-in pula PDF existente — **decisão para a atualização diária em produção**, evita congelar dados), `consolidar` (itera o map, prefixa o contrato; sem órfãos), `montar_relatorio`/`escrever_consolidado`/`escrever_relatorio` (CSVs utf-8-sig `;`), `executar` (laço de UI com `exportar_fn` injetável ⇒ pular/retry/status [AUTO]-testáveis; 1 retry + screenshot, laço continua), `main`/`_cli` (`--contratos/--retomar/--somente-parse/--dry-run`, validação cedo do map). Ajuste cirúrgico na F3: **nome do PDF = contrato** (`ECO_019_2020.pdf`, chave primária), CLI `--contrato`. Convenção de doc da F5: docstring por-fase + toda linha comentada. `run.ps1` mínimo (ASCII, repassa args). `--dry-run` lista os 21. Roteiro 5 escrito no TESTES.md. **Suíte 41/41** (15 novos em `test_f5_consolidacao.py`; teste do nome do PDF migrado p/ contrato). PLAN.md/PLAN_F5/TESTES sincronizados. Falta só a viagem (Roteiro 5). |
| 16/06/2026 | **F2 — map preenchido (DEV, sem viagem)**. `config/programas_map.json` preenchido à mão com os 21 contratos ECO (`programa` = texto exato do dropdown `config/programas_dropdown.json`). `contratos.validar_mapeamento` confirma: todo vigente com programa, programa existe literal no dropdown, 1:1 sem duplicata. `test_mapeamento_real_quando_preenchido` **deixou de pular** → F2 DEV fechada (8/8). **Suíte total 26/26.** (Recuperação: VSCode fechou no meio da edição e o contexto se perdeu; estado reconstruído a partir do map salvo + testes.) Resta só a validação [VPN] da seleção real no LNC (roteiro 4). |
| 16/06/2026 | **Ajustes na F2 (pedido do usuário)**: (1) removido o campo `sugestao` do `programas_map.json` — `montar_esqueleto(vigentes, mapa_existente)` agora gera só `{contrato: {programa: ""}}` (difflib/sugestao removidos). (2) **Regra de domínio nova**: contratos `ECM` são novos, **fora da base legada LPT** → excluídos do laço/map; `carregar_vigentes` filtra `Encerrado` **e** prefixo `ECM` (const `PREFIXO_FORA_DO_LACO`). Impacto: 38 vigentes → **21 ECO** processados (17 ECM cortados). Enumeração do dropdown já fora feita na VPN (`config/programas_dropdown.json` com nomes reais); `programas_map.json` **regenerado limpo** (21 entradas, sem ECM, sem sugestao) a partir do dropdown existente — **não precisa nova viagem** para isso, só preencher à mão. Acceptance test agora pula enquanto o map está vazio. CLAUDE.md atualizado (driver do laço). Suíte 25 pass + 1 skip. |
| 16/06/2026 | **F2 — parte DEV pronta (TDD)**. `contratos.carregar_vigentes` (filtra Encerrado) e `contratos.validar_mapeamento` (a: todo vigente com programa; b: programa existe literal no dropdown; c: 1:1, duplicata=erro) — puros, testados. `scripts/gerar_mapeamento.py`: `montar_esqueleto` (merge que preserva preenchido + sugestão difflib por 'sigla - tranche', puro/testado) + `enumerar_dropdown` (reusa lnc_app, lê `ComboBox.item_texts()` — [VPN]) + CLI que grava os 2 JSONs e auto-dump em falha. Acceptance `test_mapeamento_real_quando_preenchido` pula no DEV (arquivos ainda não existem), vira verde após o roteiro 4 + preenchimento. **Suíte 24 pass + 1 skip.** Roteiro 4 escrito no TESTES.md. `pacote_v9.zip` gerado. |
| 16/06/2026 | **F4 — `parse_pdf.py` pronta (DEV, TDD)**. `extrair_linhas(pdf)` → `[(odi, uf, municipio)]`: faixas de X derivadas dos cabeçalhos da 1ª página (Projeto/Município/Data Início — nunca hardcoded), linha válida = token `\d{6,}` à esquerda da coluna Projeto (descarta cabeçalho/rodapé/totais), município `"UF - NOME"` separado no 1º `" - "` com UF validada contra as 27 (inválida = warning). Testado contra a fixture: spot-check `("10010263","RS","LAGOAO")`, ODIs/UFs/municípios válidos, sem lixo de cabeçalho. Teste com fixture module-scoped (parse 1×: suíte caiu de 49s→12s). **Suíte total 18/18.** `.gitignore` ampliado (IDE/OS/python caches + `*.zip.txt`) p/ o commit. |
| 16/06/2026 | **🎯 F1+F3 FECHADAS na VPN — 1 PDF exportado de ponta a ponta, 2×** (`resultados_20260616_1356.zip`). Com o fix do `_preview_pronto`, o log mostrou o render subir (0%→25%→55%→85%→`Page 1 of 53`) e só então clicar imprimir → diálogo de salvar em 1,5s → caminho absoluto via `set_edit_text` → `Sa&lvar` → PDF estável (668 KB) → `EXPORTOU`. Run 2 (sobrescrita): "apagando PDF antigo" + **"painel já visível; pulando navegação"** (idempotência validada). PDF real validado no DEV: pdfplumber abre, **53 páginas**, cabeçalho ODI, linha `10010263 ... RS - LAGOAO ...` (formato UF - MUNICÍPIO confirmado p/ F4). Open questions resolvidas: menu-coord OK; **diálogo "Imprimir" não existe** no fluxo (vai direto ao salvar); `set_edit_text` aceita caminho absoluto. Próximo: F4 (parse) no DEV; F2 (mapeamento) na próxima viagem. |
| 16/06/2026 | **Roteiro 2 OK e roteiro 3 falhou no clique de imprimir** (`resultados_20260616_1306.zip`). Navegação+combo+preview agora rodam limpos (correção do combo validada). Causa da falha do export: `abrir_preview` deu o preview como pronto com `status='0% Page 1 of 0'` — o QuickReport ainda **renderizava** (regex `Page \d+ of \d+` casava "of 0"); clicou imprimir cedo, a toolbar não respondeu (no-op) e esperou 5 min o diálogo de salvar. Correção TDD: extraído `_preview_pronto(textos)` puro (pronto = **sem '%'** e total>0), testado com as strings reais ('0% Page 1 of 0'→False, 'Page 1 of 53'→True); `abrir_preview` agora loga "ainda renderizando" e só clica quando pronto. Suíte **12/12**. Coordenada do imprimir (223,40) confirmada certa (mouse pousou no botão). 2º achado menor: `pyautogui` screenshot do auto-dump deu `OSError: screen grab failed` (transiente; desktop dump e screenshot manual do usuário OK) — não bloqueante. `pacote_v8.zip` gerado. |
| 16/06/2026 | **Roteiro 2 (1ª tentativa) — navegação OK, falhou no combo** (`resultados_20260616_1154.zip`). Vitória: a **coordenada do menu "Relatórios" acertou de primeira** (open question 1 resolvida — `MENU_RELATORIOS_XY=(38,760)` validado); navegou Relatórios→"7 - Projetos Executados"→radio Programa corretamente (log de pixels funcionou lindamente). Falha: `ElementAmbiguousError` em `combo.rectangle()` — o painel tem **4 TComboBox** (Região/Estado/Concessionária/Programa) e o seletor usava `class_name="TComboBox"` puro. Correção: usar `best_match="ProgramaComboBox"` (constante já existia no config, faltava usar). +2 robustez evidenciadas pelo mesmo log: `wait` do item da lista subiu p/ `TIMEOUT_PREVIEW` (carga SQL levou 29s, perto do limite de 30s) e data com `found_index=0` (múltiplos TMaskEdit). Suíte 11/11. `pacote_v7.zip` gerado — refazer roteiros 2+3. |
| 16/06/2026 | **Plano F1+F3 aprovado e codado (parte DEV)**. `src/contratos.py` (`sanitizar_nome`, TDD), `src/lnc_app.py` (conectar_ou_abrir/limpar_estado/navegar_para_painel/selecionar_programa/conferir_filtros_padrao/abrir_preview + smoke CLI) e `src/exportar_pdf.py` (exportar + CLI). Pedido do usuário incorporado: **todo clique/seleção loga o controle + posição em pixels** (helpers `_clicar_controle`/`_clicar_xy` logam retângulo+centro ou coord cliente/tela) — para debug cego ([[ui-logging-pixels]]). Suíte **11/11 verde** no DEV (test_f1_lnc_app, test_f3_exportar, test_f3_pdf_valido novos). UI não testável offline → roteiros 2 e 3 no `pacote_v6.zip`. Auto-dump (desktop+screenshot) em falha de ambos os CLIs. |
| 16/06/2026 | **Plano de implementação F1+F3 escrito para revisão** (`planning/PLAN_F1_F3.md` + `PLAN_F1_F3.html`, estilo do template `16-implementation-plan`). Cobre `lnc_app.py` (conectar/limpar/navegar/selecionar/preview) e `exportar_pdf.py` (imprimir→salvar→geração→arquivo estável), + helper puro `contratos.sanitizar_nome`. CLI usa `--programa` (texto do dropdown) ⇒ **desacopla da F2**. 5 tarefas: T1–T3 testáveis/parciais no DEV (TDD), T4–T5 validadas por roteiros [VPN] 2 e 3 com auto-dump. Coordenada do botão imprimir (223,40) confirmada pelo tooltip; coordenada do menu "Relatórios" é estimativa a calibrar (open question 1). `config.py`: cabeçalho atualizado (seletores confirmados) + 2 coordenadas a adicionar na T1. Nenhum código de UI escrito ainda — aguardando revisão. |
| 16/06/2026 | **B5 capturada — inspeção da F1 concluída** (`resultados_20260616_1042.zip`). Dumps obtidos: diálogo de salvar `#32770` **'Salvar Saída de Impressão como'** (título REAL — `config.py` tinha "Salvar como" errado, corrigido) com campo Edit do nome + botão **'Sa&lvar'** + tipo 'Documento PDF (*.pdf)'; janela de progresso `TQRProgressForm 'Printing progress'` (TProgressBar + botão 'Cancel') = alvo da Espera 4; tooltip do botão imprimir = THintWindow 'Print'. **Diálogo "Imprimir" (passo8.jpg) não capturado** — usuário relata que passa rápido demais; ordem observada por ele: define nome do PDF → depois "Printing progress". Não bloqueante (diálogo padrão do Windows + passo8.jpg); ordem exata das esperas será confirmada na 1ª execução real da F3. Seletores do salvar/progresso fixados no `config.py`. **F1-inspeção fecha aqui**; próximo = escrever `lnc_app.py` + `exportar_pdf.py` (com plano para revisão do usuário antes). |
| 16/06/2026 | **Tentativa de B5 não capturou os diálogos** (`resultados_20260616_1020.zip`): as 2 execuções rodaram `--nome preview` (uma com typo `tela_iniciacls`) e recapturaram o preview — nenhum diálogo "Imprimir"/"Salvar como" estava aberto (ausentes do `preview_desktop.txt`); `--espera` não foi usado. Previews órfãos subiram para **4** (reforça necessidade de limpeza + reabrir o LNC). Usuário optou por **mais 1 viagem de inspeção** (vs. partir para o código). Roteiro da B5 reescrito no TESTES.md: reabrir LNC limpo; clicar o mesmo botão de imprimir do fluxo manual; diálogos são modais e NÃO fecham ao focar o PowerShell ⇒ abrir o diálogo e só então rodar a captura; alerta de typo no `--nome`; Alt+Tab caso o diálogo abra atrás; `--espera 30` como plano B. **Pacote v5 continua válido** (não precisa novo pacote). |
| 12/06/2026 | **B4 coletada — preview decifrado** (`resultados_20260612_1552.zip`): o "voltar para a tela anterior" reportado pelo usuário é o preview maximizado indo para **trás** da janela principal ao perder o foco (desktop.txt do fim ainda o lista visível) — o dump win32 o capturou populado: `TQRStandardPreview 'Print Preview'` com StatusBar **"Page 1 of 53"** (⇒ sinal de pronto: regex `Page \d+ of \d+`). Toolbar sem texto/HWND; identificação por posição via uia rects + `manuais/passo7.jpg` (zoom×3, nav×4, printer setup, **imprimir**, salvar, abrir, Close). `manuais/passo8.jpg` revelou passo ausente do plano: imprimir abre **diálogo "Imprimir"** (escolha de impressora + OK) antes da geração/Salvar como ⇒ F3 ganha etapa e a B5 virou B5a (dialogo_imprimir) + B5b (dialogo_salvar). App mantém previews antigos vivos (2 TQRStandardPreview) ⇒ rotina de limpeza confirmada como necessária. `inspecionar_app.py` melhorado: screenshot ANTES dos dumps + `--espera N`; suíte 7/7; seletores do preview no config.py; `pacote_v5.zip` gerado. |
| 12/06/2026 | **B3 coletada e validada** (`resultados_20260612_1545.zip`): combo com programa selecionado aparece no win32 como `window_text` (`ComboBox - 'AES SUL - 2ª Tranche'`) ⇒ a F3 ganha verificação defensiva barata (ler o texto do combo antes de Visualizar); formato dos itens do dropdown confirmado (`CONCESSIONÁRIA - Nª Tranche`); datas padrão intocadas. No uia o valor do combo NÃO aparece — leitura sempre via win32. Aguardando B4 (preview) e B5 (diálogo Salvar). |
| 12/06/2026 | **B2 coletada e analisada** (`resultados_20260612_1539.zip` — dump win32 de 91 KB + uia 30 KB + PNG da tela). Seletores reais fixados em `src/config.py`: janela `TfrmPrincipal`; item da lista direita `"7  - Projetos Executados"` (**dois espaços** após o 7); `TTabSheet "Projetos Executados"`; radio `Programa` (TRadioButton) + `ProgramaComboBox` (TComboBox — exigirá `ComboBoxWrapper(handle)` explícito no F2, classe não casa o wrapper automático); radio tipo `Eletrificação Rural` (TGroupButton); datas `TMaskEdit` 01/01/2004→hoje confirmadas. **Botões da barra (Visualizar/Imprimir/Rel.Excel) não têm HWND — só existem no backend uia**; itens das listas idem ⇒ estratégia híbrida win32+uia no `lnc_app.py`. Menu lateral segue opaco (coordenadas). PNG veio normal neste zip (mistério do B1 era limpeza da pasta, não e-mail). Obs.: `output\` da VPN foi limpa entre coletas — pedido ao usuário para não limpar até fechar a F1. **Faltam B3–B5.** |
| 12/06/2026 | **Primeiros dumps reais analisados** (`vpn_resultados/resultados_20260612_1515.zip`, só a tela B1): script v4 rodou limpo ("FIM OK: 11 dumps", conexão por PID, processo único). Descobertas: (1) o LPT é **Delphi**, não VB6 (`TfrmPrincipal`, `TApplication`, `TfrmAbertura`) — segue win32 nativo, pywinauto ok; (2) **risco 5 confirmado**: o menu lateral é um `TExchangeBar` owner-drawn **sem filhos** no win32 e no uia ⇒ navegação até "Relatórios" será por coordenada relativa (screenshot vira insumo); (3) janela principal: `class_name="TfrmPrincipal"`, título `Sistema LPT - Luz Para Todos`. Pendências da viagem: **faltam B2–B5** (usuário parou após B1) e o `tela_inicial_tela.png` não veio no zip apesar de logado como gravado (verificar na VPN se o arquivo existe — suspeita de remoção no e-mail). |
| 12/06/2026 | **2º bug do inspecionar_app na VPN — corrigido com TDD**: ao refazer B1, crash `ElementAmbiguousError: There are 2 elements that match {'title_re': 'Sistema LPT.*'}` (`bug_fix/tela_inicial_crash.jpg`) — duas janelas casando o título (provável instância duplicada do LNC; `connect()` procura até janelas ocultas). Correção: nova função `conectar()` — enumera candidatas visíveis via `find_elements`, loga todas (pid/handle/classe/título), conecta **por PID** e, com >1 processo, avisa e usa o primeiro em vez de morrer. Teste novo reproduziu (2 janelas Tk de mesmo título em 2 processos) e validou; aprendizado de teste: `python.exe` de venv no Windows é launcher (PID do `Popen` ≠ PID da janela). Suíte **7/7 verde**. `pacote_v4.zip` gerado; TESTES.md atualizado (usar v4; fechar instâncias extras do LNC). |
| 12/06/2026 | **Bug do inspecionar_app na VPN — corrigido com TDD**: na parte B do roteiro 1, todas as janelas falharam com `AttributeError: 'DialogWrapper'/'UIAWrapper' object has no attribute 'print_control_identifiers'` (evidência: `vpn_resultados/programa_selecionado.jpg`; desktop.txt e screenshot foram gravados — a execução cega funcionou). Causa raiz: `app.windows()` retorna **wrappers**, e `print_control_identifiers()` só existe em **WindowSpecification**. Reproduzido no DEV com teste novo (`tests/test_f1_inspecao.py`: janela Tk local + `dump_janelas` ⇒ falhou igual à VPN); correção: re-embrulhar pelo handle (`app.window(handle=jan.handle)`); suíte 6/6 verde. `pacote_v3.zip` gerado; TESTES.md atualizado (refazer B1–B7 com o v3; não precisa reinstalar). |
| 12/06/2026 | **ExecutionPolicy da VPN é `Restricted`**: usuário tentou ativar o venv e o `Activate.ps1` foi bloqueado (`bug_fix/erro_levantar_venv.jpg`). Sem correção de código — o roteiro já usa `.venv\Scripts\python.exe` direto (não requer ativação) e `.ps1` com `-ExecutionPolicy Bypass`. Nota destacada adicionada às pré-condições do TESTES.md. |
| 12/06/2026 | **F0 verde na VPN**: 2ª tentativa com `pacote_v2.zip` funcionou — ramo uv da escada instalou CPython 3.12.13 e as deps; `pytest tests/test_f0_ambiente.py` **5/5 PASSED** em 8.87s na VPN (evidência: `tests/status_testes.pacote_V2.jpg`; log na VPN: `output/logs/instalar_20260612_113203.log`). F0 totalmente concluída (DEV + VPN). Próximo: passos 5–11 do roteiro 1 (inspeções F1). |
| 12/06/2026 | **Viagem 1 falhou no passo 3 — VPN sem Python**: `instalar.ps1` v1 (do `pacote_v1.zip`) só tentava `py`/`python` e abortava (evidência: `bug_fix/status_deploy.png`, transcript funcionou). Solução (sugestão do usuário: uv): `instalar.ps1` v2 com escada de 3 ramos — py/python → uv existente → **instala uv sem admin** (astral.sh, TLS 1.2) e `uv venv --python 3.12` (baixa CPython do GitHub); venv do uv não tem pip ⇒ deps via `uv pip install --python`. Sintaxe validada no parser PS 5.1. Roteiro 1 do TESTES.md atualizado (pacote v2, expectativa do passo 3 com aviso de demora e mensagem de falha do plano C). `pacote_v2.zip` gerado. Risco residual: proxy corporativo bloquear astral.sh/GitHub ⇒ plano C (Python embeddable no pacote). |
| 12/06/2026 | **Anti-bloqueio de e-mail**: o filtro corporativo barrou o `pacote_v1.zip` (zips com `.ps1`/`.py` são tratados como executáveis). `fazer_pacote.ps1` reescrito: gera o pacote com os 7 scripts renomeados para `*.renomeado.txt`, remove `__pycache__`, e inclui `LEIA-ME_PRIMEIRO.txt` com o comando único de restauração. Restauração **testada no DEV** (extração simulada → comando do LEIA-ME → 7 arquivos restaurados, 0 sobras). Roteiro 1 do TESTES.md atualizado (novo passo 2; passos renumerados 1–11). Pacote v1 regenerado (636 KB). |
| 12/06/2026 | **F0 executada no DEV**: `.venv` (Python 3.12.13, uv), deps instaladas (pywinauto 0.6.9, pdfplumber 0.11.9, pyautogui, pytest) + `requirements.txt` (ASCII, sem BOM); árvore de pastas; `.gitignore`; `CLAUDE.md`; `src/config.py` (timeouts/títulos); fixture copiada para `tests/fixtures/`; kit de deploy (`fazer_pacote.ps1`, `instalar.ps1`, `coletar.ps1`); `planning/TESTES.md` com roteiro 1. Teste F0: **5/5 verde no DEV**. **F1 parcial**: `inspecionar_app.py` escrito (dumps win32+uia+desktop+screenshot por tela, execução cega) e smoke-testado (falha graciosa sem o LNC, log com traceback, exit 1). `pacote_v1.zip` gerado (640 KB). Aguardando Viagem 1 do usuário. |
| 12/06/2026 | Usuário aprovou avançar para F0 e definiu a restrição operacional: **sem acesso direto à VPN** — desenvolvimento no DEV, validação por roteiros executados pelo usuário na VPN com ida-e-volta de pacotes (transferência por e-mail/drive; internet na VPN confirmada; Python na VPN desconhecido). PLAN.md reestruturado: seção "Modelo de operação DEV↔VPN", testes [SEMI] renomeados para [VPN], kit de deploy adicionado à F0, estrutura ganhou `deploy/` e `vpn_resultados/`. |
| 12/06/2026 | Usuário respondeu as 4 questões em aberto (sem senha; impressora padrão pode ser fixada; fixture `manuais/output.pdf` adicionada; mapeamento 1:1) e reportou 2 comportamentos ausentes do passo-a-passo (botão Imprimir desabilitado durante a geração; geração pode levar ~1 min). Plano atualizado: passo "Printer setup" eliminado, Espera 2 da F3 criada com `TIMEOUT_GERACAO=300s`, teste F2 endurecido (duplicata = erro), F4 destravada. Seções de controle de progresso e destaque das BEHAVIORAL_GUIDELINES adicionadas. |
| 11/06/2026 | Exploração do projeto (passo-a-passo, 10 capturas, base_contratos.json, convenções de planning/). Decisões confirmadas com o usuário: mapeamento manual do dropdown, fluxo via PDF (Rel.Excel lento), saída CSV, pywinauto+fallback. `planning/PLAN.md` e `planning/PLAN.html` escritos. |

## Modelo de operação: DEV ↔ VPN (sem acesso direto à VPN)

**Restrição central do projeto:** o desenvolvimento acontece nesta máquina (**DEV**), mas a validação real só acontece na máquina da VPN (**VPN**), operada **pelo usuário** — Claude possivelmente nunca terá acesso direto. Todo teste que depende do sistema LPT funciona em ciclos de ida-e-volta:

```
DEV (Claude)                          VPN (usuário)
────────────                          ─────────────
1. Desenvolve código + testes [AUTO]
2. Gera pacote_vX.zip (fazer_pacote.ps1)
   + roteiro numerado no TESTES.md
                    ──── e-mail/drive ────▶
                                      3. Executa instalar.ps1 / roteiro
                                      4. Scripts gravam TUDO em output/
                                         (logs, dumps, screenshots, tracebacks)
                                      5. coletar.ps1 → resultados_<data>.zip
                    ◀─── e-mail/drive ────
6. Analisa vpn_resultados/, itera código
```

**Consequências de desenho (valem para todo o código):**
- **Execução cega:** nenhum script pode depender de alguém me relatando a tela. Todo script grava console + traceback completo em `output/logs/`, e resultados estruturados em arquivos (JSON/TXT/screenshot). Falha tem que ser autoexplicativa *no arquivo*.
- **Transferência:** ida = `pacote_vX.zip` pequeno (só código; dependências instaladas na VPN via pip — internet confirmada). Volta = `resultados_<data>.zip` gerado por `deploy/coletar.ps1`. Se o e-mail bloquear `.zip`, renomear para `.zip.txt` (documentado no roteiro).
- **Python na VPN:** desconhecido. O roteiro 0 verifica (`python --version`); plano B preparado: Python embeddable incluído num pacote alternativo (~15 MB, sem admin).
- **Resultados trazidos de volta** ficam em `vpn_resultados/` aqui no DEV (não versionar) — é o insumo das minhas iterações.
- **Economia de viagens:** cada pacote agrupa o máximo de fases prontas (ex.: o 1º pacote leva F0 + o script de inspeção da F1) e cada roteiro tem passos numerados com "o que copiar de volta".

## 1. Contexto e objetivo

O sistema legado **LPT — Luz Para Todos** (app VB6 de 2004, `Z:\LNC\LNC.exe`) roda numa máquina Windows acessada via VPN/RDP. Não tem API: o acesso é só por teclado/mouse. Dele precisamos extrair, para cada contrato ativo, o relatório **"7 - Projetos Executados"**, exportado em PDF via Microsoft Print to PDF (fluxo manual documentado em `planning/passo-a-passo.md` e `manuais/passo1..10.jpg`).

De cada PDF, extrair as colunas **ODI** e **Município**. O Município vem no formato `"RS - LAGOAO"` (`UF - NOME`): separamos a UF e mantemos só o nome do município. Tudo é acumulado numa tabela com a coluna do contrato e exportado num **CSV consolidado único** ao final do laço.

O laço é dirigido por `base_contratos.json` (raiz do projeto): disparam o fluxo os contratos com `["vigente"] != "Encerrado"` (hoje ~38, com valores "Andamento" e "Encerramento" — a contagem é calculada em runtime, nunca hardcoded).

## 2. Decisões confirmadas

| Decisão | Resolução |
|---|---|
| Mapeamento contrato → dropdown "Programa" | Os nomes do dropdown **não** correspondem a `sigla - tranche` do JSON. Um script de descoberta enumera os itens reais do ComboBox e gera `config/programas_map.json` com sugestões (difflib) para validação manual. |
| Rel.Excel vs PDF | O botão Rel.Excel funciona mas demora **muitos minutos** por export; o PDF leva 10–15s. **Fluxo via PDF.** |
| Formato de saída | **CSV** (`utf-8-sig`, delimitador `;` — abre direto no Excel pt-BR). |
| Automação de UI | **pywinauto (backend win32)** primário — app VB6 tem controles win32 nativos. Fallback **pyautogui** (imagem/coordenadas) só onde controles não forem detectáveis. |
| Lançador | `run.ps1` na raiz: ativa o `.venv` e repassa argumentos ao `src/main.py`. |
| Ambiente | `uv` (`uv venv`, `uv pip install`, `uv pip freeze > requirements.txt`), conforme `planning/PROJECT_BUILDING.md`. |
| Login do LNC | **Não há senha** — `conectar_ou_abrir()` não precisa de passo de autenticação. |
| Impressora padrão | **Confirmado**: pode fixar "Microsoft Print to PDF" como impressora padrão do Windows (feito uma vez no `run.ps1`) — **elimina o passo "Printer setup" da UI** em cada iteração. |
| Geração do PDF é lenta | O botão **Imprimir fica desabilitado (acinzentado)** enquanto o relatório é gerado — esse estado é o sinal de espera primário. O documento pode levar **~1 minuto** para ficar pronto para salvar (medido com `manuais/output.pdf`). Timeouts dimensionados para isso (ver F3). |
| Mapeamento é 1:1 | Cada `[UF][nº da tranche]` refere-se **exclusivamente** a um contrato — não existem dois contratos no mesmo programa do dropdown. O teste F2 trata duplicata como **erro** (não warning). |
| Fixture para o parser | `manuais/output.pdf` (exportação real, ~53 págs) já disponível — copiar para `tests/fixtures/` na F0; **a F4 pode rodar em paralelo a F1–F3**. |

## 3. Decisões técnicas

| Tema | Escolha | Por quê |
|---|---|---|
| Parsing de PDF | **pdfplumber** | O PDF do Microsoft Print to PDF é texto vetorial. `extract_words()` dá coordenadas (x, top), permitindo recortar as colunas ODI e Município pelas faixas de X dos cabeçalhos — robusto contra células vazias. Alternativas descartadas: pypdf (sem posição), camelot (pesado, Ghostscript), PyMuPDF (licença AGPL; velocidade irrelevante aqui). |
| Tabela/CSV | stdlib `csv` + `json` | Simplicidade primeiro (BEHAVIORAL_GUIDELINES). Sem pandas. |
| Estratégia de PDF | **1 PDF por contrato** em `output/pdf/<contrato_sanitizado>.pdf` | (1) Retomada: PDF existe ⇒ pula a etapa de UI (a parte cara e frágil); (2) reprocessar o parsing sem refazer a UI; (3) auditoria por contrato; (4) quase elimina o diálogo de sobrescrita. |
| Consolidação | Reparsear **todos** os PDFs presentes a cada rodada e regravar o CSV inteiro | Idempotente e simples; o estado de retomada é a própria existência do PDF. |
| Esperas | Estruturais: janelas existir/sumir, `wait_cpu_usage_lower` (cursor "ampulheta SQL" = processo ocupado), tamanho de arquivo estável | Nunca `sleep` fixo como mecanismo principal. Timeouts generosos e centralizados em `src/config.py`. |

**Dependências:** `pywinauto`, `pyautogui`, `pdfplumber`, `pytest` (testes). Nada mais.

## 4. Estrutura de arquivos

```
atualizacao_clientes/
├── CLAUDE.md                      # F0 (finalizado na F6)
├── run.ps1                        # F6
├── requirements.txt               # F0
├── .gitignore                     # F0 — output/, .venv/
├── base_contratos.json            # EXISTENTE — entrada do pipeline
├── config/
│   ├── programas_dropdown.json    # F2: snapshot dos itens do ComboBox
│   └── programas_map.json         # F2: {contrato: texto exato do dropdown} — validado à mão
├── src/
│   ├── config.py                  # caminhos, timeouts, títulos de janela, seletores
│   ├── contratos.py               # carrega JSON + map; filtra vigentes; sanitiza nomes
│   ├── lnc_app.py                 # conexão/abertura do LNC, navegação idempotente
│   ├── exportar_pdf.py            # exportação de UM PDF (todas as esperas/diálogos)
│   ├── parse_pdf.py               # pdfplumber → [(odi, uf, municipio)]
│   └── main.py                    # laço, retomada, CSV, relatório, logging, CLI
├── scripts/
│   ├── inspecionar_app.py         # F1: dump de controles → output/inspecao/
│   └── gerar_mapeamento.py        # F2: enumera dropdown, gera esqueleto do map
├── deploy/
│   ├── fazer_pacote.ps1           # F0 (roda no DEV): gera pacote_vX.zip para levar à VPN
│   ├── instalar.ps1               # F0 (roda na VPN): verifica Python, cria venv, pip install
│   └── coletar.ps1                # F0 (roda na VPN): zipa output/ → resultados_<data>.zip
├── vpn_resultados/                # resultados trazidos da VPN (insumo de análise — não versionar)
├── tests/
│   ├── fixtures/                  # PDF real de exemplo (copiado na F3)
│   ├── test_f0_ambiente.py
│   ├── test_f2_mapeamento.py
│   ├── test_f3_pdf_valido.py
│   ├── test_f4_parse_pdf.py
│   └── test_f5_consolidacao.py
├── planning/                      # documentação (PLAN.md = key document, TESTES.md)
├── output/                        # SAÍDAS — não versionar
│   ├── pdf/                       # 1 PDF por contrato
│   ├── inspecao/                  # dumps de controles (F1)
│   ├── logs/                      # run_<ts>.log + screenshots de falha
│   ├── consolidado.csv
│   └── relatorio_execucao.csv
├── manuais/                       # referência visual do fluxo manual — NÃO é entrada
└── minhas_notas/                  # NÃO é entrada
```

## 5. Fases

Convenção de testes: **[AUTO]** = pytest offline, repetível em qualquer máquina (DEV e VPN), sem depender da UI. **[VPN]** = roteiro numerado em `planning/TESTES.md` executado **pelo usuário** na máquina da VPN; os scripts gravam todos os resultados em `output/` e o usuário traz o `resultados_<data>.zip` de volta (ver "Modelo de operação"). Os testes vivem em `tests/`, separados dos scripts.

### F0 — Setup do ambiente `[ ]`

**Entregáveis:**
- `.venv` via `uv venv`; `uv pip install pywinauto pyautogui pdfplumber pytest`; `uv pip freeze > requirements.txt`
- Árvore de pastas (`src/`, `scripts/`, `tests/`, `config/`, `output/{pdf,inspecao,logs}`)
- `.gitignore` (output/, .venv/)
- `CLAUDE.md` inicial (seção 8 abaixo)
- `planning/TESTES.md` (esqueleto + roteiro VPN nº 1)
- `src/config.py` com constantes iniciais (caminho do exe, timeouts, títulos de janela conforme capturas)
- Copiar `manuais/output.pdf` → `tests/fixtures/exemplo_projetos_executados.pdf` (fixture da F4)
- **Kit de deploy** (modelo DEV↔VPN): `deploy/fazer_pacote.ps1` (DEV: gera `pacote_vX.zip`), `deploy/instalar.ps1` (VPN: verifica Python → cria venv → pip install → roda `pytest tests/test_f0_ambiente.py` → grava tudo em `output/logs/`), `deploy/coletar.ps1` (VPN: zipa `output/` → `resultados_<data>.zip`)

**Pronto quando:** (DEV) `pytest tests/test_f0_ambiente.py` verde no venv local **e** pacote gerado; (VPN) usuário roda `instalar.ps1` lá e o `resultados.zip` trazido de volta mostra o mesmo teste verde.
**Teste [AUTO]:** `pytest tests/test_f0_ambiente.py` — imports ok; `base_contratos.json` carrega em UTF-8; contagem de vigentes > 0. Roda nos DOIS ambientes.
**Teste [VPN]:** roteiro nº 1 do TESTES.md — levar `pacote_v1.zip`, rodar `instalar.ps1`, rodar `coletar.ps1`, trazer `resultados.zip`. (O 1º pacote já inclui o `inspecionar_app.py` da F1 para economizar uma viagem.)

### F1 — Conexão, inspeção e navegação até o painel de filtros `[ ]`

**Entregáveis:**
- `scripts/inspecionar_app.py`: conecta (ou inicia) `Z:\LNC\LNC.exe`, faz `print_control_identifiers()` da janela principal → `output/inspecao/main_window.txt`. Rodar de novo com o preview aberto para capturar `print_preview.txt` e os diálogos. Esse dump é o insumo para fixar os seletores reais (class_name, índices) em `src/config.py`.
- `src/lnc_app.py`: `conectar_ou_abrir()`, `navegar_para_relatorios()`, `selecionar_projetos_executados()` (item "7 - Projetos Executados" no ListBox "Projetos"), `painel_filtros()` retornando referências ao radio "Programa", ao ComboBox adjacente e ao botão "Visualizar". Navegação **idempotente** + rotina de limpeza (fecha previews/diálogos órfãos no início de cada iteração).

**Pronto quando:** o script roda na máquina da VPN, acha/abre o app, deixa o painel de filtros visível e loga os controles encontrados.
**Teste [VPN]:** roteiro em TESTES.md — executar `python scripts/inspecionar_app.py`; asserts internos (`combo.exists()`) falham ruidosamente; conferir visualmente o painel aberto; guardar o dump como evidência.

### F2 — Descoberta do dropdown e geração do mapeamento `[ ]`

**Entregáveis:**
- `scripts/gerar_mapeamento.py`: chega ao painel (F1), marca o radio "Programa", lê `ComboBox.item_texts()` (pywinauto lê itens de ComboBox win32 sem abrir o dropdown), grava a lista bruta em `config/programas_dropdown.json` e gera/mescla `config/programas_map.json`:
  ```json
  { "ECM 004/2021": { "programa": "", "sugestao": "AES SUL - 2ª Tranche" } }
  ```
  `sugestao` via `difflib.get_close_matches(f"{sigla} - {tranche}", itens)`. Entradas já preenchidas **nunca** são sobrescritas (merge).
- Validação manual: usuário preenche `programa` para todos os contratos vigentes.

**Pronto quando:** `programas_map.json` tem todos os vigentes com `programa` não vazio.
**Teste [AUTO]:** `pytest tests/test_f2_mapeamento.py` — offline, só lê os JSONs: (a) todo contrato vigente tem `programa` não vazio; (b) cada `programa` existe **literalmente** na lista enumerada (pega typo/encoding antes de tocar a UI); (c) dois contratos no mesmo programa = **erro** (confirmado: o mapeamento é 1:1 — cada `[UF][tranche]` pertence a um único contrato).

### F3 — Exportar UM PDF de ponta a ponta `[ ]`

**Entregáveis:** `src/exportar_pdf.py` com `exportar(programa_texto, destino)` e CLI `python -m src.exportar_pdf --contrato "ECM 004/2021"`. Sequência:

1. Navegação idempotente até o painel; **conferir** (não alterar) datas padrão (01/01/2004 → hoje) e "Eletrificação Rural" marcado.
2. Radio "Programa" → `ComboBox.select(programa_texto)`. Fallback: foco no combo + setas, com a quantidade vinda do índice na lista enumerada na F2.
3. Clicar "Visualizar". **Espera 1:** janela top-level "Print Preview" existir + `wait('ready')` + `wait_cpu_usage_lower(threshold=5)` (cobre o cursor "ampulheta SQL"); timeout 180s configurável.
4. ~~Printer setup na UI~~ **Eliminado**: "Microsoft Print to PDF" é fixada como impressora padrão do Windows uma única vez no `run.ps1` (confirmado pelo usuário). Manter apenas uma verificação defensiva: se o diálogo de impressão exibir outra impressora, abortar o contrato com erro claro.
5. Clicar Imprimir. **Espera 2 (geração do relatório):** o botão **Imprimir fica desabilitado (acinzentado)** enquanto o documento de impressão é gerado — esperar `botao.is_enabled()` voltar a `True` (pywinauto lê o estado do controle; fallback: cor do pixel do botão). **Pode levar ~1 minuto** (medido com `manuais/output.pdf`); `TIMEOUT_GERACAO = 300s` configurável.
6. **Espera 3:** diálogo "Salvar como"; digitar o **caminho absoluto completo** no campo Nome (`...\output\pdf\ECM_004_2021.pdf`) → Salvar.
7. **Diálogo intermitente** "Confirmar Salvar como" (sobrescrita): esperar ~3s; se aparecer, clicar "Sim". Não aparecer **não é erro**.
8. **Espera 4:** janela "Printing progress" sumir (não aparecer também é ok — pode ser rápida demais) + arquivo existir com **tamanho estável** (2 stats iguais com 1s de intervalo — o spooler pode fechar o diálogo antes de terminar a gravação).
9. "Close" do preview; confirmar retorno à janela principal.

> Nota de timing: a estimativa de 10–15s por contrato vale para relatórios pequenos; relatórios
> grandes (~53 págs) levam **~1 min só na geração** do documento de impressão. A ordem das esperas
> (botão desabilitado → Salvar como → progresso → arquivo estável) será confirmada empiricamente
> na primeira execução da F3 — o sinal exato de cada etapa sai da observação real.

**Pronto quando:** uma execução gera PDF válido para um contrato real, inclusive rodando 2× seguidas (cenário de sobrescrita).
**Teste [VPN]:** rodar a CLI 2× para o mesmo contrato + `pytest tests/test_f3_pdf_valido.py` (arquivo existe, header `%PDF`, pdfplumber abre, páginas > 0).

### F4 — Parsing do PDF → ODI / UF / Município `[ ]`

**Entregáveis:** `src/parse_pdf.py` com `extrair_linhas(pdf_path) -> list[tuple[odi, uf, municipio]]`:
- Por página: `page.extract_words()`; faixas de X das colunas calculadas pelos cabeçalhos "ODI" e "Município" da 1ª página (o cabeçalho seguinte, "Data Início", delimita o fim de Município). **Nunca hardcoded** — recalculadas por PDF.
- Agrupar palavras por linha (tolerância em `top`); linha válida = token na faixa do ODI casando `^\d{6,}$` (descarta cabeçalhos repetidos por página, título, "Page N of M", totais).
- Município: concatenar palavras da faixa; separar no **primeiro** `" - "` → (`uf`, `municipio`); UF validada contra as 27 UFs (linha inválida = warning logado, não exceção).

**Fixture:** já disponível — `manuais/output.pdf` (exportação manual real, ~53 págs); copiada para `tests/fixtures/` na F0. **A F4 não depende mais da F3** e pode ser desenvolvida em paralelo às fases de UI.

**Pronto quando:** teste com a fixture passa + conferência visual amostral (5 linhas do PDF vs. saída).
**Teste [AUTO]:** `pytest tests/test_f4_parse_pdf.py` — 100% offline com a fixture: ODIs no padrão; UFs válidas; municípios não vazios; spot-checks literais (ex.: 1ª linha do exemplo = `("10010263", "RS", "LAGOAO")`); ausência de strings de cabeçalho nos resultados.

### F5 — Laço completo, retomada, CSV consolidado e relatório `[ ]`

> **Plano de implementação detalhado + decisões: `planning/PLAN_F5.md` (+ `.html`), aprovado 16/06/2026.**
> Decisões que ajustam o texto abaixo: (a) **nome do PDF = contrato** (`ECO_011_2018.pdf`, chave primária), alinhando `exportar_pdf`; (b) **default re-exporta tudo** (dados frescos p/ a atualização diária) — a retomada vira **`--retomar`** opt-in, sem `--force`; (c) convenção de doc exaustiva (docstring por-fase + toda linha comentada) nos arquivos da F5.

**Entregáveis:** `src/main.py` com CLI: `--contratos "A,B"` (subconjunto), `--retomar` (pula PDF existente p/ recuperar rodada interrompida), `--somente-parse` (pula a UI), `--dry-run` (lista o plano sem tocar a UI):

1. Carrega vigentes + map; **falha cedo** se o map estiver incompleto (reusa a validação da F2).
2. Por contrato: **default exporta** (re-exporta mesmo se o PDF existir = dados frescos); com `--retomar`, PDF existe → status `pulado`. `try/except` por contrato: falha → screenshot pyautogui em `output/logs/` + re-navegação do zero (nova chamada a `exportar`) + **1 retry**; o laço continua.
3. Ao final: parseia todos os PDFs presentes → `output/consolidado.csv` (`contrato;odi;uf;municipio`, utf-8-sig).
4. `output/relatorio_execucao.csv` (contrato, status exportado/pulado/falha, nº de linhas extraídas, erro) + resumo no console.
5. `logging` para console + `output/logs/run_<timestamp>.log` (1 linha por etapa/contrato, com durações).

**Pronto quando:** rodada completa termina com relatório coerente; interromper no meio e re-rodar retoma de onde parou.
**Teste [AUTO]:** `pytest tests/test_f5_consolidacao.py` — partes puras: sanitização (`ECM 004/2021` → `ECM_004_2021`), lógica de skip (tmp_path), escrita do CSV com fixtures, formato do relatório.
**Teste [VPN]:** (a) `--dry-run`; (b) rodada com 2 contratos via `--contratos`; (c) matar no meio e re-rodar (retomada); (d) rodada completa supervisionada.

### F6 — Empacotamento `run.ps1` + documentação final `[ ]`

**Entregáveis:** `run.ps1` (verifica/ativa `.venv`, **fixa "Microsoft Print to PDF" como impressora padrão** — confirmado pelo usuário —, repassa argumentos: `.\run.ps1 --dry-run`); versões finais de `CLAUDE.md` e `planning/TESTES.md`; status das fases atualizado no Controle de progresso deste PLAN.md.
**Pronto quando:** `.\run.ps1 --dry-run` funciona num PowerShell limpo.
**Teste [VPN]:** PowerShell novo → `.\run.ps1 --dry-run` → `.\run.ps1 --contratos "X"` → conferir saídas. (Se ExecutionPolicy bloquear, documentar `powershell -ExecutionPolicy Bypass -File run.ps1` no CLAUDE.md.)

## 6. Riscos e mitigações

| # | Risco | Sev | Mitigação |
|---|---|---|---|
| 1 | **Sessão RDP:** automação de UI exige sessão interativa ativa, focada e **desbloqueada**. Minimizar a janela RDP, desconectar ou deixar a tela travar quebra `SendInput`, foco e screenshots. | ALTA | Documentar com destaque no CLAUDE.md/TESTES.md: rodar com RDP aberto, em foco, sem bloqueio de tela. Se precisar fechar o RDP: `tscon <id> /dest:console`. Rodadas curtas (~10–15 min) ⇒ execução assistida é o caminho simples. |
| 2 | Timing da UI (query SQL lenta no Visualizar, spooler do PDF) | ALTA | Esperas estruturais (item 3 das decisões); timeouts generosos centralizados em `src/config.py`. |
| 3 | Nomes do dropdown ≠ `sigla - tranche` | MÉD | F2: enumeração programática + mapeamento manual + teste offline de existência literal. Re-rodar a enumeração quando surgirem programas novos. |
| 4 | Diálogo de sobrescrita intermitente | MÉD | PDFs por contrato + deleção prévia do PDF antigo em `exportar` (antes de salvar); espera condicional de ~3s por "Confirmar Salvar como" como defesa. |
| 5 | Controles owner-drawn não detectáveis pelo win32 (toolbar do preview) | MÉD | O dump da F1 revela cedo; fallbacks: teclado (tab/setas com índice conhecido) e pyautogui por imagem. |
| 6 | Resolução/DPI (pyautogui por imagem é sensível) | MÉD | Preferir pywinauto (insensível); `SetProcessDpiAwareness` no início; imagens de referência capturadas na própria máquina da VPN; fixar resolução/escala da sessão RDP e documentar. |
| 7 | Foco roubado / uso concorrente da máquina | MÉD | `set_focus()` antes de cada bloco; preferir ações por mensagem (`select`, `click`) a `click_input` quando possível; não usar mouse/teclado durante a rodada; em falha: screenshot + re-navegação + 1 retry. |
| 8 | Estado residual da UI entre iterações (preview/diálogo pendurado) | MÉD | Rotina de limpeza no início de cada iteração + navegação idempotente desde a janela principal. |
| 9 | Encoding ("ª", acentos; console Windows é cp1252) | BAIXA | Todo I/O com `encoding="utf-8"` (CSV `utf-8-sig`); comparações do dropdown usam strings lidas do próprio app (F2), nunca digitadas à mão. |
| 10 | `Z:` indisponível / LNC já aberto | BAIXA | `conectar_ou_abrir()` tenta `connect()` antes de `start()`; falha cedo com mensagem clara. (Login: confirmado que **não há senha**.) |
| 11 | Layout do PDF variar entre programas (larguras de coluna) | BAIXA | Faixas de X recalculadas por PDF a partir dos cabeçalhos; adicionar fixture extra ao teste F4 se surgirem variações. |

## 7. Ordem e dependências

```
F0 → F1 → F2 → F3 → F4 → F5 → F6
```

- **F4 já está destravada**: a fixture `manuais/output.pdf` existe — o parser pode ser desenvolvido em paralelo a F1–F3.
- F0, F4 e todos os testes [AUTO] rodam em qualquer máquina; F1–F3, F5–F6 exigem a máquina da VPN com sessão RDP ativa.

## 8. CLAUDE.md (conteúdo a criar na F0)

- **O que é:** automação de UI (pywinauto/pyautogui) do sistema legado LPT para exportar relatórios em PDF e consolidar ODI/UF/Município em CSV. Roda **apenas** na máquina Windows da VPN, com sessão RDP ativa e desbloqueada.
- **Documentação:** toda em `planning/`; documento-chave `planning/PLAN.md`; mapa de testes `planning/TESTES.md`; seguir `planning/BEHAVIORAL_GUIDELINES.md` (simplicidade primeiro, mudanças cirúrgicas, perguntar antes de assumir).
- **Entradas do pipeline:** `base_contratos.json`, `config/programas_map.json`, `config/programas_dropdown.json`.
- **NÃO-entradas:** `minhas_notas/` (ignorar), `manuais/` (só referência visual), `planning/` (docs), `bug_fix/` (registros).
- **Saídas:** `output/` — não versionar.
- **Ambiente:** uv (`uv venv`; `.venv\Scripts\activate`; `uv pip install -r requirements.txt`; novas deps → freeze).
- **Execução:** `.\run.ps1` (`--dry-run`, `--contratos`, `--retomar`, `--somente-parse`); testes offline `pytest tests/`; testes de UI via roteiros do TESTES.md.
- **Regras críticas:** não usar Rel.Excel; timeouts/seletores centralizados em `src/config.py`; arquivos sempre UTF-8; CSV utf-8-sig com `;`.

## 9. Verificação fim a fim

1. `pytest tests/` verde (F0, F2, F4, F5 — offline).
2. Na VPN: `inspecionar_app.py` (F1) → `gerar_mapeamento.py` + preenchimento do map (F2) → `python -m src.exportar_pdf --contrato "X"` 2× (F3) → `.\run.ps1 --contratos "A,B"` → interromper/retomar → rodada completa (F5/F6).
3. Conferir `output/consolidado.csv` (amostra de 5 linhas vs. PDF aberto) e `output/relatorio_execucao.csv` (todos os contratos com status exportado/pulado, zero falhas).

## 10. Questões em aberto

Todas as questões da revisão inicial foram **respondidas pelo usuário em 12/06/2026**:

| Questão | Resposta | Efeito no plano |
|---|---|---|
| O LNC exige login ao abrir? | **Não tem senha.** | `conectar_ou_abrir()` sem passo de autenticação (risco 10 simplificado). |
| O preview respeita a impressora padrão do Windows? | **Sim — pode fixar Microsoft Print to PDF como padrão.** | Passo "Printer setup" eliminado da UI; fixação única no `run.ps1` (F6); verificação defensiva na F3. |
| Existe um PDF já exportado manualmente? | **Sim — `manuais/output.pdf`.** | F4 destravada em paralelo a F1–F3; fixture copiada na F0. |
| Dois contratos no mesmo programa do dropdown? | **Não — cada `[UF][nº da tranche]` é exclusivo de um contrato.** | Teste F2 trata duplicata como **erro**, não warning. |

**Informações adicionais do usuário (faltavam no `passo-a-passo.md`):**
- A geração do PDF demora e o **botão Imprimir fica desabilitado (acinzentado)** até o documento ficar pronto — incorporado como Espera 2 da F3.
- O documento de impressão pode demorar: `manuais/output.pdf` levou **~1 minuto** para imprimir e ficar disponível para salvar — `TIMEOUT_GERACAO = 300s` na F3.
