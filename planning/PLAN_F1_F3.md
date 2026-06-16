# Plano de implementação — `lnc_app.py` (F1) + `exportar_pdf.py` (F3)

> **Para revisão do usuário antes de codar.** Versão visual: `planning/PLAN_F1_F3.html`.
> Steps usam checkbox (`- [ ]`) para acompanhamento. Contexto-mãe: `planning/PLAN.md`
> (seções 4–5) e os seletores reais em `src/config.py` (fixados das viagens B1–B5).

**Goal:** navegar o LNC até o preview de "Projetos Executados" e exportar **1 PDF** de um
programa, de ponta a ponta, com esperas estruturais — destravando a F2 e a F3.

**Architecture:** dois módulos em `src/`. `lnc_app.py` conecta/abre o LNC e faz a navegação
**idempotente** (limpeza de estado → painel → filtros → preview pronto), reusável por F2 e F3.
`exportar_pdf.py` parte do preview pronto e dirige imprimir → salvar PDF → esperar geração →
arquivo estável. Backend híbrido **win32** (painel, datas, combo, statusbar, diálogo de salvar)
+ **uia** (botões da barra do preview, itens de lista) + **1 clique por coordenada** (botão
imprimir da toolbar do preview, cuja posição saiu do tooltip "Print" no dump B5).

**Tech Stack:** Python 3.12, pywinauto (win32+uia), pytest. Sem libs novas.

**Restrição de teste (modelo DEV↔VPN):** o grosso é automação de UI — só valida na VPN. O que
**é** testável offline (helpers puros) segue TDD aqui no DEV; cada bloco de UI vira um **passo
de validação [VPN]** com auto-dump em falha (o script grava dumps+screenshot+traceback em
`output/` e o usuário traz o zip). Convenção: **[AUTO]** = pytest no DEV; **[VPN]** = roteiro
na VPN.

---

## Resumo

| | |
|---|---|
| Módulos novos | `src/lnc_app.py`, `src/exportar_pdf.py` |
| Helper offline | `src/contratos.py` (só `sanitizar_nome` nesta fase) |
| Testes [AUTO] novos | `tests/test_f1_lnc_app.py`, `tests/test_f3_exportar.py`, `tests/test_f3_pdf_valido.py` |
| Backends | win32 + uia + 1 coordenada (botão imprimir) |
| Entrega da fase | `python -m src.exportar_pdf --programa "AES SUL - 2ª Tranche"` gera 1 PDF válido na VPN |
| Desacoplamento | CLI aceita `--programa` (texto exato do dropdown) → **não depende da F2** ainda |

## Estrutura de arquivos

- **`src/lnc_app.py`** (novo) — conexão e navegação idempotente. Funções: `conectar_ou_abrir`,
  `limpar_estado`, `navegar_para_painel`, `selecionar_programa`, `conferir_filtros_padrao`,
  `abrir_preview`. CLI de smoke (`python -m src.lnc_app --programa "X"`) que para no preview e
  dumpa o estado.
- **`src/exportar_pdf.py`** (novo) — `exportar(programa_texto, destino_pdf)` + CLI. Usa `lnc_app`
  para chegar ao preview, depois dirige imprimir→salvar→geração→arquivo estável.
- **`src/contratos.py`** (novo, mínimo) — só `sanitizar_nome(programa) -> str` nesta fase
  (resto de contratos/map fica para F5). Mantido separado porque é a única peça **pura**.
- **`src/config.py`** (existente) — acrescentar 2 constantes de coordenada/menu (Tarefa 1).
- **`tests/`** — um arquivo por módulo, só com as partes offline + fixture do PDF real.

## Decisões herdadas dos dumps (não re-decidir)

- Janela principal: `class_name="TfrmPrincipal"`, conexão **por PID** (pode haver janelas
  homônimas — `ElementAmbiguousError`, já tratado em `inspecionar_app.conectar`).
- Lista de relatórios: item literal **`"7  - Projetos Executados"`** (DOIS espaços) — `uia`
  `ListItem`.
- Painel: `RadioButton "Programa"` (win32 `TRadioButton`), combo `ProgramaComboBox`
  (`TComboBox`; embrulhar por handle), tipo `"Eletrificação Rural"` e data `"01/01/2004"`
  apenas **conferidos** (não alterados).
- Botão **"Visualizar"**: só no `uia` (`control_type="Button"`, sem HWND).
- Preview: top-level `TQRStandardPreview "Print Preview"`, **pronto** quando a `StatusBar` casa
  `r"Page \d+ of \d+"`; vai para TRÁS ao perder foco → `set_focus()` antes de agir; app acumula
  previews órfãos → `limpar_estado` fecha-os.
- Botão **imprimir** da toolbar: sem HWND/texto → **clique por coordenada** ≈ `(223, 40)`
  (centro do `Button9` uia L212–235×T29–51; confirmado pelo tooltip `THintWindow "Print"` em x≈222).
- Salvar: diálogo **`#32770 "Salvar Saída de Impressão como"`** (título real ≠ "Salvar como");
  campo `Edit` (nome) + botão `"Sa&lvar"`. Tipo já é "Documento PDF (*.pdf)".
- Progresso: `TQRProgressForm "Printing progress"` (some quando termina). Sinal de verdade =
  **arquivo PDF com tamanho estável**.

---

## Tarefa 1 — Constantes de coordenada/menu em `config.py`

**Files:**
- Modify: `src/config.py` (após o bloco do Preview, linha ~53)

- [ ] **Step 1: acrescentar as constantes** (sem teste — é configuração; coberta de fato no
  smoke [VPN] da Tarefa 4/5)

```python
# Clique por coordenada (sem HWND) — calibrados nos dumps B5
# Botão "imprimir" da toolbar do preview: centro do Button9 uia (L212-235,T29-51);
# confirmado pelo tooltip THintWindow 'Print' em x~222. Preview é maximizado
# (L-8,T-8) => coords de cliente ~ coords de tela.
PREVIEW_BTN_IMPRIMIR_XY = (223, 40)

# Menu lateral TExchangeBar (L0..76, T23..1021) é owner-drawn (sem filhos nos 2
# backends) => clique por coordenada. "Relatórios" é o 7º de 9 itens. ESTIMATIVA
# INICIAL a calibrar na 1ª viagem F3 (ver Open Questions): centro-x da barra,
# y proporcional ao índice do item.
MENU_RELATORIOS_XY = (38, 760)
```

- [ ] **Step 2: commit**

```bash
git add src/config.py
git commit -m "config: coordenadas do botao imprimir e do menu Relatorios (dumps B5)"
```

> Nota: este projeto **não é repo git** (`Is a git repository: false`). Os passos de commit
> ficam como marcadores; se/quando virar repo, valem como estão. Caso contrário, ignorar os
> `git`.

## Tarefa 2 — `contratos.sanitizar_nome` (offline, TDD)

Única peça pura desta fase: transformar o texto do programa num nome de arquivo seguro.

**Files:**
- Create: `src/contratos.py`
- Test: `tests/test_f1_lnc_app.py` (compartilhado)

- [ ] **Step 1: teste que falha**

```python
# tests/test_f1_lnc_app.py
import sys
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))


def test_sanitizar_nome_programa():
    from src.contratos import sanitizar_nome
    assert sanitizar_nome("AES SUL - 2ª Tranche") == "AES_SUL_-_2a_Tranche"
    assert sanitizar_nome("ECM 004/2021") == "ECM_004_2021"
    assert sanitizar_nome("a/b\\c:d*e?") == "a_b_c_d_e"
```

- [ ] **Step 2: rodar e ver falhar**

Run: `.venv\Scripts\python.exe -m pytest tests/test_f1_lnc_app.py::test_sanitizar_nome_programa -v`
Expected: FAIL (`ModuleNotFoundError: src.contratos`).

- [ ] **Step 3: implementação mínima**

```python
# src/contratos.py
"""Helpers puros de contrato/nome (offline). Resto (map, vigentes) fica para F5."""
import re
import unicodedata


def sanitizar_nome(texto: str) -> str:
    """Texto do programa -> nome de arquivo seguro (sem acento, sem char proibido)."""
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)
    )
    return re.sub(r"[^A-Za-z0-9_-]+", "_", sem_acento).strip("_")
```

- [ ] **Step 4: rodar e ver passar**

Run: `.venv\Scripts\python.exe -m pytest tests/test_f1_lnc_app.py -v`
Expected: PASS.

- [ ] **Step 5: commit** — `feat: contratos.sanitizar_nome`

## Tarefa 3 — `lnc_app.conectar_ou_abrir` + `limpar_estado`

**Files:**
- Create: `src/lnc_app.py`
- Test: `tests/test_f1_lnc_app.py` (parte [AUTO] cobre só a falha-clara sem LNC)

- [ ] **Step 1: cabeçalho + conexão** (reusa o padrão por-PID já testado em `inspecionar_app`)

```python
# src/lnc_app.py
"""F1 — conexão e navegação idempotente no LNC (Sistema LPT). Backend híbrido."""
import logging
import time

from pywinauto import Application, findwindows

from src import config


def conectar_ou_abrir(log: logging.Logger):
    """Retorna (app_win32, janela_principal). Conecta por PID; abre o LNC se preciso."""
    cands = findwindows.find_elements(
        title_re=config.TITULO_JANELA_PRINCIPAL_RE, backend="win32"
    )
    if not cands:
        log.info("LNC não encontrado; iniciando %s", config.LNC_EXE)
        Application(backend="win32").start(config.LNC_EXE)
        fim = time.monotonic() + config.TIMEOUT_ABRIR_APP
        while not cands and time.monotonic() < fim:
            time.sleep(1.0)
            cands = findwindows.find_elements(
                title_re=config.TITULO_JANELA_PRINCIPAL_RE, backend="win32"
            )
        if not cands:
            raise RuntimeError(
                f"LNC não abriu em {config.TIMEOUT_ABRIR_APP}s ({config.LNC_EXE})"
            )
    pid = cands[0].process_id
    app = Application(backend="win32").connect(process=pid)
    return app, app.window(handle=cands[0].handle)


def limpar_estado(app, log: logging.Logger) -> None:
    """Fecha previews/progressos/diálogos órfãos — torna a navegação idempotente."""
    for w in app.windows():
        try:
            cls = w.class_name()
        except Exception:
            continue
        if cls in (config.CLASSE_PREVIEW, config.CLASSE_PROGRESSO, config.CLASSE_SALVAR_COMO):
            log.info("limpando janela órfã: %s %r", cls, w.window_text())
            try:
                w.close()
            except Exception:
                try:
                    w.set_focus(); w.type_keys("{ESC}")
                except Exception:
                    log.warning("não consegui fechar %s", cls)
```

- [ ] **Step 2: teste [AUTO] de falha-clara** (sem LNC, `start` falharia — então testamos só
  que a função levanta erro nomeado quando o exe não existe; monkeypatch do caminho)

```python
# tests/test_f1_lnc_app.py  (acrescentar)
def test_conectar_ou_abrir_falha_clara(monkeypatch):
    import logging
    from src import config, lnc_app
    monkeypatch.setattr(config, "LNC_EXE", r"Z:\NAO_EXISTE\nada.exe")
    monkeypatch.setattr(config, "TIMEOUT_ABRIR_APP", 2)
    # sem janela "Sistema LPT" no DEV => tenta abrir => exe inexistente => erro
    import pytest
    with pytest.raises(Exception):
        lnc_app.conectar_ou_abrir(logging.getLogger("t"))
```

- [ ] **Step 3: rodar** — `pytest tests/test_f1_lnc_app.py -v` → PASS (os 2 testes).
- [ ] **Step 4: commit** — `feat: lnc_app conectar_ou_abrir + limpar_estado`

## Tarefa 4 — `lnc_app` navegação até o preview (UI — validação [VPN])

Esta é a espinha dorsal de UI; **não há teste offline** (precisa do LNC). Escreve-se das
evidências dos dumps; valida-se com o smoke CLI na VPN (auto-dump em falha).

**Files:**
- Modify: `src/lnc_app.py`

- [ ] **Step 1: `navegar_para_painel` (idempotente)**

```python
def _ja_no_painel(jp, log) -> bool:
    """True se a aba 'Projetos Executados' já está visível (evita reclicar o menu)."""
    try:
        return jp.child_window(
            title=config.TITULO_TAB_FILTROS, class_name="TTabSheet"
        ).exists(timeout=1)
    except Exception:
        return False


def navegar_para_painel(app, jp, log: logging.Logger) -> None:
    """Janela principal -> Relatórios (menu lateral, coordenada) -> '7 - Projetos Executados'."""
    jp.set_focus()
    if _ja_no_painel(jp, log):
        log.info("painel de filtros já visível; pulando navegação")
        return
    # menu lateral TExchangeBar é owner-drawn -> clique por coordenada
    x, y = config.MENU_RELATORIOS_XY
    log.info("clicando 'Relatórios' do menu lateral em (%d,%d)", x, y)
    jp.click_input(coords=(x, y))
    time.sleep(1.0)
    # item da lista da direita só aparece no uia
    app_uia = Application(backend="uia").connect(process=app.process)
    jp_uia = app_uia.window(class_name=config.CLASSE_JANELA_PRINCIPAL)
    item = jp_uia.child_window(
        title=config.ITEM_PROJETOS_EXECUTADOS, control_type="ListItem"
    )
    item.wait("exists enabled visible", timeout=config.TIMEOUT_DIALOGO)
    item.click_input()
    jp.child_window(title=config.TITULO_TAB_FILTROS, class_name="TTabSheet").wait(
        "exists", timeout=config.TIMEOUT_DIALOGO
    )
```

- [ ] **Step 2: `selecionar_programa` + `conferir_filtros_padrao`**

```python
def selecionar_programa(jp, programa_texto: str, log: logging.Logger) -> None:
    """Marca o radio 'Programa' e seleciona o item no ComboBox; verifica o texto."""
    jp.child_window(title=config.RADIO_PROGRAMA, class_name="TRadioButton").click_input()
    combo = jp.child_window(class_name="TComboBox")  # ProgramaComboBox
    combo.select(programa_texto)
    lido = combo.window_text()
    if lido.strip() != programa_texto.strip():
        raise RuntimeError(f"combo ficou em {lido!r}, esperava {programa_texto!r}")
    log.info("programa selecionado: %r", lido)


def conferir_filtros_padrao(jp, log: logging.Logger) -> None:
    """Confere (não altera) tipo 'Eletrificação Rural' e data início padrão; só avisa."""
    try:
        data = jp.child_window(title=config.DATA_INICIO_PADRAO, class_name="TMaskEdit")
        if not data.exists(timeout=1):
            log.warning("data início padrão %r não encontrada — conferir manualmente",
                        config.DATA_INICIO_PADRAO)
    except Exception:
        log.warning("não consegui conferir a data início (seguindo)")
```

- [ ] **Step 3: `abrir_preview` (clique Visualizar + espera estrutural)**

```python
def abrir_preview(app, log: logging.Logger):
    """Clica 'Visualizar' (uia) e espera o preview ficar PRONTO. Retorna a janela win32."""
    app_uia = Application(backend="uia").connect(process=app.process)
    jp_uia = app_uia.window(class_name=config.CLASSE_JANELA_PRINCIPAL)
    jp_uia.child_window(title=config.BOTAO_VISUALIZAR, control_type="Button").click_input()

    fim = time.monotonic() + config.TIMEOUT_PREVIEW
    import re
    while time.monotonic() < fim:
        prev = app.window(class_name=config.CLASSE_PREVIEW)
        if prev.exists():
            try:
                sb = prev.child_window(class_name="TStatusBar")
                textos = " ".join(sb.texts())
                if re.search(config.PREVIEW_STATUS_PRONTO_RE, textos):
                    prev.set_focus()
                    log.info("preview pronto: %s", textos.strip())
                    return prev
            except Exception:
                pass
        time.sleep(1.0)
    raise RuntimeError(f"preview não ficou pronto em {config.TIMEOUT_PREVIEW}s")
```

- [ ] **Step 4: CLI de smoke** (para a validação [VPN])

```python
def _smoke():
    import argparse, sys, traceback
    from datetime import datetime
    p = argparse.ArgumentParser()
    p.add_argument("--programa", required=True)
    args = p.parse_args()
    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    logging.basicConfig(
        level=logging.INFO,
        handlers=[logging.FileHandler(config.LOGS_DIR / f"lnc_app_{ts}.log", encoding="utf-8"),
                  logging.StreamHandler()],
        format="%(asctime)s %(levelname)s %(message)s",
    )
    log = logging.getLogger("lnc_app")
    try:
        app, jp = conectar_ou_abrir(log)
        limpar_estado(app, log)
        navegar_para_painel(app, jp, log)
        selecionar_programa(jp, args.programa, log)
        conferir_filtros_padrao(jp, log)
        abrir_preview(app, log)
        log.info("=== SMOKE OK: preview pronto para %r ===", args.programa)
    except Exception:
        log.error("SMOKE FALHOU:\n%s", traceback.format_exc())
        # auto-dump do estado para a viagem render render render
        try:
            import scripts.inspecionar_app as insp  # reusa o dumper
            insp.dump_desktop("lnc_app_falha", log)
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    _smoke()
```

- [ ] **Step 5: validação [VPN]** — roteiro 2 (abaixo). Critério: log termina com `SMOKE OK`
  e o preview do programa abre. Em falha, o zip traz log+dump+screenshot.
- [ ] **Step 6: commit** — `feat: lnc_app navegação até o preview`

## Tarefa 5 — `exportar_pdf.exportar` (UI — validação [VPN]) + teste do PDF

**Files:**
- Create: `src/exportar_pdf.py`
- Test: `tests/test_f3_pdf_valido.py` ([AUTO], roda contra o PDF trazido da VPN ou a fixture),
  `tests/test_f3_exportar.py` ([AUTO], só o helper de caminho)

- [ ] **Step 1: teste [AUTO] do helper de caminho de saída**

```python
# tests/test_f3_exportar.py
import sys
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))


def test_caminho_saida_usa_nome_sanitizado(tmp_path, monkeypatch):
    from src import config, exportar_pdf
    monkeypatch.setattr(config, "PDF_DIR", tmp_path)
    destino = exportar_pdf.caminho_saida("AES SUL - 2ª Tranche")
    assert destino == tmp_path / "AES_SUL_-_2a_Tranche.pdf"
    assert destino.is_absolute()
```

- [ ] **Step 2: rodar e ver falhar** — `pytest tests/test_f3_exportar.py -v` → FAIL (sem módulo).

- [ ] **Step 3: implementar `exportar_pdf.py`**

```python
# src/exportar_pdf.py
"""F3 — exporta UM PDF do preview de Projetos Executados (Microsoft Print to PDF)."""
import logging
import time

from pywinauto import Application

from src import config, contratos, lnc_app


def caminho_saida(programa_texto: str):
    config.PDF_DIR.mkdir(parents=True, exist_ok=True)
    return config.PDF_DIR / f"{contratos.sanitizar_nome(programa_texto)}.pdf"


def _esperar_arquivo_estavel(caminho, log, timeout):
    """Arquivo existe e com 2 leituras de tamanho iguais (spooler pode fechar antes)."""
    fim = time.monotonic() + timeout
    anterior = -1
    while time.monotonic() < fim:
        if caminho.exists():
            atual = caminho.stat().st_size
            if atual > 0 and atual == anterior:
                log.info("PDF estável: %d bytes", atual)
                return
            anterior = atual
        time.sleep(config.ARQUIVO_ESTAVEL_INTERVALO)
    raise RuntimeError(f"PDF não estabilizou em {timeout}s: {caminho}")


def exportar(programa_texto: str, log: logging.Logger, destino=None):
    """Fluxo completo: navega -> preview -> imprimir -> salvar -> geração -> arquivo estável."""
    destino = destino or caminho_saida(programa_texto)
    if destino.exists():
        destino.unlink()  # evita o diálogo de sobrescrita (mantido só como defesa)

    app, jp = lnc_app.conectar_ou_abrir(log)
    lnc_app.limpar_estado(app, log)
    lnc_app.navegar_para_painel(app, jp, log)
    lnc_app.selecionar_programa(jp, programa_texto, log)
    lnc_app.conferir_filtros_padrao(jp, log)
    preview = lnc_app.abrir_preview(app, log)

    # botão imprimir: sem HWND -> clique por coordenada (centro do Button9; tooltip 'Print')
    preview.set_focus()
    preview.click_input(coords=config.PREVIEW_BTN_IMPRIMIR_XY)

    # diálogo de salvar do "Microsoft Print to PDF" (título real != "Salvar como").
    # Pode demorar: a renderização das ~53 págs precede o diálogo => TIMEOUT_GERACAO.
    salvar = app.window(title=config.TITULO_SALVAR_COMO, class_name=config.CLASSE_SALVAR_COMO)
    salvar.wait("exists ready", timeout=config.TIMEOUT_GERACAO)
    edit = salvar.child_window(class_name=config.SALVAR_COMO_EDIT_NOME)
    edit.set_edit_text(str(destino))           # caminho ABSOLUTO no campo do nome
    salvar.child_window(title=config.SALVAR_COMO_BOTAO, class_name="Button").click_input()

    # diálogo intermitente de sobrescrita (deletamos antes; defesa)
    conf = app.window(title=config.TITULO_CONFIRMA_SOBRESCRITA)
    if conf.exists(timeout=config.TIMEOUT_SOBRESCRITA):
        conf.child_window(title="&Sim", class_name="Button").click_input()

    # geração: esperar o arquivo estabilizar (sinal de verdade) + progresso sumir
    _esperar_arquivo_estavel(destino, log, config.TIMEOUT_GERACAO)
    prog = app.window(class_name=config.CLASSE_PROGRESSO)
    if prog.exists():
        prog.wait_not("exists", timeout=config.TIMEOUT_PROGRESSO)

    # fecha o preview e volta ao estado limpo
    lnc_app.limpar_estado(app, log)
    log.info("=== EXPORTOU: %s ===", destino)
    return destino


def _cli():
    import argparse, sys, traceback
    from datetime import datetime
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--programa", required=True, help="texto EXATO do dropdown")
    p.add_argument("--saida", default=None, help="caminho do PDF (default: output/pdf/<nome>.pdf)")
    args = p.parse_args()
    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    logging.basicConfig(
        level=logging.INFO,
        handlers=[logging.FileHandler(config.LOGS_DIR / f"exportar_{ts}.log", encoding="utf-8"),
                  logging.StreamHandler()],
        format="%(asctime)s %(levelname)s %(message)s",
    )
    log = logging.getLogger("exportar")
    from pathlib import Path
    try:
        exportar(args.programa, log, Path(args.saida) if args.saida else None)
    except Exception:
        log.error("EXPORT FALHOU:\n%s", traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    _cli()
```

- [ ] **Step 4: rodar [AUTO]** — `pytest tests/test_f3_exportar.py -v` → PASS.

- [ ] **Step 5: teste [AUTO] de PDF válido** (vale para a fixture e para o PDF trazido da VPN)

```python
# tests/test_f3_pdf_valido.py
import sys
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))


def test_pdf_fixture_e_valido():
    import pdfplumber
    from src import config
    pdf = config.FIXTURES_DIR / "exemplo_projetos_executados.pdf"
    assert pdf.read_bytes()[:5] == b"%PDF-"
    with pdfplumber.open(pdf) as doc:
        assert len(doc.pages) > 0
```

- [ ] **Step 6: rodar suíte inteira** — `pytest tests/ -v` → tudo verde.
- [ ] **Step 7: validação [VPN]** — roteiro 3 (abaixo): rodar a CLI 2× para o mesmo programa
  (testa sobrescrita), `pytest tests/test_f3_pdf_valido.py`.
- [ ] **Step 8: commit** — `feat: exportar_pdf exporta 1 PDF de ponta a ponta`

---

## Roteiros [VPN] desta fase (entram no próximo pacote)

**Roteiro 2 (valida Tarefa 4 — navegação):** com o LNC aberto e na tela inicial, rodar
`.venv\Scripts\python.exe -m src.lnc_app --programa "AES SUL - 2ª Tranche"`. Esperado: o app
sozinho abre Relatórios → Projetos Executados → marca Programa+combo → Visualizar → preview do
relatório; log termina `SMOKE OK`. Em falha: `coletar.ps1` e trazer o zip.

**Roteiro 3 (valida Tarefa 5 — exportação):** rodar
`.venv\Scripts\python.exe -m src.exportar_pdf --programa "AES SUL - 2ª Tranche"` **2×**
seguidas. Esperado: `output\pdf\AES_SUL_-_2a_Tranche.pdf` gerado nas duas (2ª testa o
delete-antes/sobrescrita); log termina `EXPORTOU`. Trazer o zip **com o PDF** — ele alimenta
`test_f3_pdf_valido.py` e a F4 no DEV.

## Riscos & mitigações

| Risco | Sev | Mitigação |
|---|---|---|
| Coordenada do menu "Relatórios" errada (estimativa) | ALTA | Auto-dump+screenshot em falha; calibrar na 1ª viagem (Open Question 1); `_ja_no_painel` evita reclicar se já aberto. |
| Ordem real imprimir↔salvar↔progresso diferente do suposto | MÉD | Sinal de verdade = **arquivo PDF estável** (não a ordem das janelas); timeouts generosos; 1ª viagem confirma a ordem. |
| `combo.select(texto)` falhar por encoding/acento | MÉD | Texto vem **literal do dropdown** (nunca digitado à mão); verificação `window_text()` após selecionar aborta cedo com erro claro. |
| Diálogo "Imprimir" (passo8) aparecer e travar o fluxo | MÉD | Se aparecer, é padrão (OK/Enter); 1ª viagem revela; adicionar tratamento só se ocorrer (YAGNI). |
| `click_input` por coordenada sensível a DPI/resolução | MÉD | `SetProcessDpiAwareness` no início; preview maximizado (coords estáveis); fixar resolução do RDP. |

## Open questions (decidir/calibrar)

1. **Coordenada do item "Relatórios" no menu lateral** — `MENU_RELATORIOS_XY=(38,760)` é
   estimativa (7º de 9 itens na barra T23–1021). A 1ª execução do roteiro 2 confirma; se errar,
   o screenshot de falha mostra onde clicou e ajusto a constante. *Calibrar na viagem 2.*
2. **Existe o diálogo "Imprimir" no fluxo real?** O usuário relata que "passa rápido". Se ele
   parar e exigir OK, trato no `exportar_pdf` (1 linha). *Confirmar na viagem 3.*
3. **`set_edit_text` cola o caminho com acento corretamente no campo?** O destino é ASCII
   (nome sanitizado), então sem risco; mas confirmar que o campo aceita caminho absoluto longo.
   *Confirmar na viagem 3.*
