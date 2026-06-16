# TESTES.md — Mapa de testes por fase + roteiros da VPN

Convenção:
- **[AUTO]** — `pytest` offline, repetível em qualquer máquina (DEV e VPN), sem depender da UI do LPT.
- **[VPN]** — roteiro numerado executado **pelo usuário** na máquina da VPN. Os scripts gravam
  tudo em `output/` (logs com traceback, dumps, screenshots); ao final o usuário roda
  `deploy\coletar.ps1` e traz o `resultados_*.zip` de volta para `vpn_resultados/` no DEV.

**Pré-condições de TODO roteiro [VPN]:** sessão RDP aberta, em foco e desbloqueada durante a
execução; drive `Z:` acessível; não usar mouse/teclado enquanto um script de automação roda
(os de inspeção podem ser usados normalmente — eles não mexem no app).

> **Não ative o venv.** A ExecutionPolicy da VPN é `Restricted` e bloqueia o `Activate.ps1`
> (visto em 12/06/2026 — `bug_fix/erro_levantar_venv.jpg`). Por isso todos os comandos dos
> roteiros chamam `.venv\Scripts\python.exe` (um `.exe`, que a política não bloqueia) pelo
> caminho completo, sempre **a partir da raiz do projeto**, e os `.ps1` rodam com
> `powershell -ExecutionPolicy Bypass -File ...`.

---

## Mapa por fase

| Fase | Tipo | Como testar | Status |
|---|---|---|---|
| F0 | [AUTO] | `pytest tests/test_f0_ambiente.py -v` (DEV e VPN) | verde no DEV e na VPN em 12/06/2026 |
| F0 | [VPN] | Roteiro 1, parte A (instalação) | **concluído** em 12/06/2026 (pacote v2, uv) |
| F1 | [AUTO] | `pytest tests/test_f1_inspecao.py -v` (dump contra janela Tk local) | verde no DEV em 12/06/2026 |
| F1 | [VPN] | Roteiro 1, parte B (inspeção das telas) | **concluída** em 16/06/2026 (B1–B5; seletores em `src/config.py`) |
| F1 | [VPN] | Roteiro 2 (smoke navegação, `python -m src.lnc_app`) | **concluído** em 16/06/2026 (navegação idempotente) |
| F3 | [VPN]+[AUTO] | Roteiro 3 (exportar 1 PDF 2×) + `pytest tests/test_f3_pdf_valido.py` | **concluído** em 16/06/2026 (PDF 53 págs, sobrescrita OK) |
| F2 | [VPN]+[AUTO] | Roteiro 4 (`gerar_mapeamento.py`) + `pytest tests/test_f2_mapeamento.py` | aguarda escrever F2 |
| F4 | [AUTO] | `pytest tests/test_f4_parse_pdf.py` (fixture real em tests/fixtures/) | a desenvolver no DEV |
| F5 | [AUTO]+[VPN] | `pytest tests/test_f5_consolidacao.py` + roteiro (a escrever) | aguarda F3/F4 |
| F6 | [VPN] | PowerShell limpo: `.\run.ps1 --dry-run` → `--contratos "X"` | aguarda F5 |

---

## Roteiro 1 — Instalação + inspeção do LPT (cobre F0-VPN e F1)

**Objetivo:** validar o ambiente Python na VPN e tirar um "raio-X" de cada tela do LPT
(dumps de controles + screenshots) para o Claude fixar os seletores reais em `src/config.py`.

### Parte A — Instalação do ambiente · ✅ CONCLUÍDA em 12/06/2026

Feita com o `pacote_v2.zip` (extração + comando do `LEIA-ME_PRIMEIRO.txt` +
`powershell -ExecutionPolicy Bypass -File deploy\instalar.ps1`). Resultado: uv baixou o
CPython 3.12.13, dependências instaladas, teste F0 **5/5 verde** na VPN
(`tests/status_testes.pacote_V2.jpg`). Não precisa repetir — só refaça a parte A se o
ambiente for apagado ou um novo `pacote_vN.zip` for enviado (extrair por cima + restaurar
nomes + rodar `instalar.ps1` de novo; ele reaproveita o `.venv` existente).

> **Anti-bloqueio de e-mail (vale para qualquer pacote):** os scripts `.ps1`/`.py` vão
> renomeados para `*.renomeado.txt` dentro do zip; o comando único do `LEIA-ME_PRIMEIRO.txt`
> restaura tudo. Se o próprio anexo for bloqueado, renomeie o zip para `.zip.txt` antes de
> enviar e desfaça lá.

### Parte B — Inspeção das 5 telas do LPT · ⬅ VOCÊ ESTÁ AQUI

> **⚠️ Use o `pacote_v4.zip`.** As tentativas anteriores da parte B (12/06/2026) falharam
> por dois bugs do `inspecionar_app.py`, ambos corrigidos e cobertos por teste no v4:
> (1) dump de controles quebrado em todas as janelas (`AttributeError ...
> print_control_identifiers` — `vpn_resultados/programa_selecionado.jpg`); (2) crash
> `ElementAmbiguousError` ao conectar quando há **duas** janelas "Sistema LPT"
> (`bug_fix/tela_inicial_crash.jpg` — instância duplicada do LNC; agora o script conecta
> por PID e só avisa). Antes de refazer: extraia o `pacote_v4.zip` **por cima** da pasta
> do projeto na VPN e rode o comando do `LEIA-ME_PRIMEIRO.txt` (restaura os nomes). Não
> precisa reinstalar nada (o `.venv` continua válido). Dica: feche instâncias extras do
> LNC antes (deixe só uma aberta). Refaça **todas** as telas B1–B5.
>
> **Status 16/06/2026:** B1–B4 OK; seletores fixados em `src/config.py`. **Falta só a B5**
> (diálogos "Imprimir" + "Salvar como"). Tentativa de 16/06 recapturou o preview por engano
> (`--nome preview`/`tela_iniciacls`) — nenhum diálogo estava aberto no momento da captura.
> Refazer só a B5, seguindo os passos abaixo. Não limpar `output\` na VPN até a F1 fechar.
>
> **Preparação da B5 (importante):** já há **4 janelas "Print Preview" órfãs** acumuladas.
> Antes de começar, **feche o LNC e reabra** (zera os previews); chegue de novo ao preview:
> Relatórios → "7 - Projetos Executados" → radio Programa + item → **Visualizar** → espere
> o relatório aparecer. Lembre: o di&aacute;logo "Imprimir" e o "Salvar como" são **modais mas
> NÃO fecham** quando você clica no PowerShell — dá para abrir o diálogo e só depois rodar o
> comando de captura, sem pressa.
>
> **B5a — Diálogo "Imprimir":**
> 1. No preview, clique no **mesmo botão de imprimir que você usou para gerar o
>    `manuais/output.pdf` manualmente** (ícone de impressora na toolbar). Abre o diálogo
>    "Imprimir" (com "Microsoft Print to PDF", Propriedades, Cópias, OK/Cancelar — igual ao
>    `manuais/passo8.jpg`). *Se ao clicar nada aparecer, o diálogo pode ter aberto ATRÁS do
>    preview — use Alt+Tab e procure a janela "Imprimir".*
> 2. Com o diálogo "Imprimir" **aberto e visível**, vá ao PowerShell e rode:
>    `.venv\Scripts\python.exe scripts\inspecionar_app.py --nome dialogo_imprimir`
> 3. Confira no console: deve terminar com `FIM OK`. (Confira o `--nome`: tem que ser
>    `dialogo_imprimir`, não `preview`.)
>
> **B5b — Diálogo "Salvar como":**
> 1. No diálogo "Imprimir", confirme **Microsoft Print to PDF** e clique **OK**.
> 2. **Aguarde ~1 min** a geração; o diálogo **"Salvar como"** abre sozinho. **Não salve.**
> 3. Com o "Salvar como" **aberto**, rode:
>    `.venv\Scripts\python.exe scripts\inspecionar_app.py --nome dialogo_salvar`
> 4. Depois do `FIM OK`: **Cancelar** o diálogo, fechar o preview (botão **Close** da
>    toolbar) e coletar: `powershell -ExecutionPolicy Bypass -File deploy\coletar.ps1`.
>
> *Plano B se um diálogo teimar em sumir:* use `--espera 30` (ex.:
> `... --nome dialogo_imprimir --espera 30`) — rode o comando PRIMEIRO, depois abra o
> diálogo e não toque em nada até o script terminar (ele espera 30s antes de capturar).

**Como funciona:** o `inspecionar_app.py` **não mexe no LPT** — ele só fotografa a tela e
grava num arquivo a lista de controles da janela aberta. **Você navega manualmente** com o
mouse até cada tela e roda o script uma vez por tela, mudando só o `--nome`.

**Antes de começar:**
- Abra o PowerShell na **raiz do projeto** (ex.: `C:\Users\charret\Documents\extrator_lnc_pr.exec`).
  Todos os comandos abaixo rodam dessa pasta — **não** entre em `.venv\Scripts` nem ative o venv.
- Sessão RDP aberta, em foco e sem bloquear a tela enquanto um comando roda.
- Entre um comando e outro pode usar o mouse normalmente.

| # | No LPT (manual, com o mouse) | Depois rode no PowerShell | O que esperar |
|---|---|---|---|
| B1 | Abra `Z:\LNC\LNC.exe` e deixe na **tela inicial** (a azul "LPT"), sem clicar em nada. | `.venv\Scripts\python.exe scripts\inspecionar_app.py --nome tela_inicial` | Termina com `FIM OK: N dumps...` |
| B2 | Clique em **Relatórios** (menu lateral) → no painel "Projetos" à direita, clique em **7 - Projetos Executados** (abre o painel de filtros). | `.venv\Scripts\python.exe scripts\inspecionar_app.py --nome painel_filtros` | `FIM OK` |
| B3 | Marque o radio **Programa** e selecione **qualquer item** no dropdown ao lado. | `.venv\Scripts\python.exe scripts\inspecionar_app.py --nome programa_selecionado` | `FIM OK` |
| B4 | Clique **Visualizar** e **espere o Print Preview carregar por completo** (a consulta pode demorar). | `.venv\Scripts\python.exe scripts\inspecionar_app.py --nome preview` | `FIM OK` |
| B5 | No preview, clique em **imprimir**. O botão fica **cinza por até ~1 min** (gerando) — espere. Quando o diálogo **"Salvar como"** abrir, **não salve**: deixe-o aberto. | `.venv\Scripts\python.exe scripts\inspecionar_app.py --nome dialogo_salvar` — depois do `FIM OK`, clique **Cancelar** no diálogo e feche o preview (**Close**). | `FIM OK` |
| B6 | Pode fechar o LPT. | `powershell -ExecutionPolicy Bypass -File deploy\coletar.ps1` | Gera `resultados_<data>.zip` na raiz. |
| B7 | — | Traga o `resultados_*.zip` para o DEV, em `vpn_resultados\`. Se o e-mail bloquear, renomeie para `.zip.txt`. | — |

**O que volta para o Claude:** o zip inteiro (contém `output\logs\` e `output\inspecao\` com
dumps win32/uia, lista de janelas do desktop e screenshots de cada tela).

**Se algo falhar no meio:** continue os passos seguintes mesmo assim (cada um é independente)
e traga o zip — os logs de erro são exatamente o que eu preciso para corrigir.

---

## Roteiro 2 — Smoke da navegação automática (valida `lnc_app.py`, F1) · `pacote_v8.zip`

**Objetivo:** o script navega **sozinho** da tela inicial até o preview de um programa. Nenhum
PDF é gerado — só verifica que a automação acha os controles certos. **Calibra a coordenada do
menu "Relatórios"** (única incógnita) — em falha, o log traz o pixel clicado e o screenshot
mostra onde caiu.

**Antes:** extrair `pacote_v8.zip` por cima + restaurar nomes (LEIA-ME). Abrir o LNC e deixar
na **tela inicial**; fechar previews/instâncias extras. PowerShell na raiz do projeto, RDP em foco.

| # | Passo | O que esperar |
|---|---|---|
| 2.1 | `.venv\Scripts\python.exe -m src.lnc_app --programa "AES SUL - 2ª Tranche"` | O app sozinho: clica Relatórios → seleciona "7 - Projetos Executados" → marca Programa + combo → Visualizar → o preview do relatório abre. Log termina `=== SMOKE OK ===`. |
| 2.2 | Se terminar com `SMOKE FALHOU`: **não mexa em nada** | O script já gravou `output\inspecao\lnc_app_falha_*` (dump + screenshot) e o log com o **pixel de cada clique**. |
| 2.3 | `powershell -ExecutionPolicy Bypass -File deploy\coletar.ps1` → trazer o zip para `vpn_resultados\` | — |

> **Leitura do log (é o ponto do pedido):** cada clique sai como
> `CLIQUE <o quê> -> centro=(x,y) ret=(...)` ou `... coord cliente=(x,y) tela=(x,y)`. Se o menu
> "Relatórios" errar, me diga o pixel que aparece e onde o botão **realmente** está na tela —
> ajusto `MENU_RELATORIOS_XY` numa tacada.

## Roteiro 3 — Exportar 1 PDF de ponta a ponta (valida `exportar_pdf.py`, F3) · `pacote_v8.zip`

**Objetivo:** gerar 1 PDF real, **2× seguidas** (a 2ª testa o delete-antes/sobrescrita). Só faça
depois do roteiro 2 passar.

| # | Passo | O que esperar |
|---|---|---|
| 3.1 | `.venv\Scripts\python.exe -m src.exportar_pdf --programa "AES SUL - 2ª Tranche"` | Navega → imprime → preenche o nome no "Salvar Saída de Impressão como" → aguarda a geração → log `=== EXPORTOU: ...AES_SUL_-_2a_Tranche.pdf ===`. Pode levar ~1–2 min. |
| 3.2 | Rode **o mesmo comando de novo** (testa sobrescrita) | Mesmo resultado; o log mostra "apagando PDF antigo" no começo. |
| 3.3 | Confira que `output\pdf\AES_SUL_-_2a_Tranche.pdf` existe e abre num leitor de PDF | PDF do relatório (≈53 págs). |
| 3.4 | `powershell -ExecutionPolicy Bypass -File deploy\coletar.ps1` → trazer o zip | O zip leva o **PDF** (alimenta `test_f3_pdf_valido.py` e a F4 no DEV) + os logs. |

> Em falha: o CLI grava `output\inspecao\exportar_falha_*` (dump+screenshot) e o log com pixels.
> Traga o zip mesmo assim. A ordem real imprimir↔salvar↔progresso será confirmada por esses logs.

## Roteiro 4 — Descoberta do dropdown e mapeamento (F2) · `pacote_v9.zip`

**Objetivo:** enumerar os nomes **reais** do dropdown "Programa" e gerar o esqueleto de
`config/programas_map.json`. Depois **você preenche à mão** o `programa` de cada contrato
vigente (usando o campo `sugestao` como pista) e o teste [AUTO] valida.

**Antes:** extrair `pacote_v9.zip` por cima + LEIA-ME. LNC aberto na tela inicial (uma instância).

| # | Passo | O que esperar |
|---|---|---|
| 4.1 | `.venv\Scripts\python.exe -m scripts.gerar_mapeamento` | Navega até o painel, marca Programa, lê o dropdown. Gera `config\programas_dropdown.json` (lista crua) e `config\programas_map.json` (esqueleto). Log: `OK: preencha 'programa'...` |
| 4.2 | `powershell -ExecutionPolicy Bypass -File deploy\coletar.ps1` → trazer o zip para `vpn_resultados\` | O zip leva `config\` (os 2 JSONs) + logs. |

**No DEV (eu + você), depois da viagem:**
| # | Passo | O que esperar |
|---|---|---|
| 4.3 | Copiar `config\programas_dropdown.json` e `programas_map.json` do zip para `config\` no DEV | — |
| 4.4 | **Você preenche** o campo `programa` de cada contrato no `programas_map.json` (texto EXATO do dropdown; a `sugestao` é só pista, confira 1:1) | todos os vigentes com `programa` não vazio |
| 4.5 | `.venv\Scripts\python.exe -m pytest tests\test_f2_mapeamento.py -v` | `test_mapeamento_real_quando_preenchido` deixa de pular e fica **verde** (todo vigente tem programa; existe no dropdown; sem duplicata) |

> Em falha do 4.1: o script grava `output\inspecao\gerar_mapeamento_falha_*` + log com pixels.

## Roteiros futuros (quando as fases fecharem)

- **Roteiro 5 (F5):** `--dry-run` → 2 contratos → interromper/retomar → rodada completa.
- **Roteiro 6 (F6):** `.\run.ps1` em PowerShell limpo.

## Para repetir um teste de UI do zero

Feche o LNC, apague o PDF alvo em `output\pdf\` e re-execute o roteiro correspondente.
