# Plano de implementação — `main.py` (F5): laço, retomada, CSV e relatório

> **Para revisão do usuário antes de codar.** Versão visual: `planning/PLAN_F5.html`.
> Steps usam checkbox (`- [ ]`) para acompanhamento. Contexto-mãe: `planning/PLAN.md`
> (seção 5, fase F5) e os módulos já prontos `contratos.py` / `exportar_pdf.py` / `parse_pdf.py`.

**Goal:** amarrar o pipeline de ponta a ponta — percorrer os 21 contratos vigentes, exportar 1
PDF por contrato (retomando pela existência do PDF), consolidar todos os PDFs presentes em
`output/consolidado.csv` e emitir `output/relatorio_execucao.csv` — com CLI (`--contratos`,
`--retomar`, `--somente-parse`, `--dry-run`) e log por etapa.

**Architecture:** um módulo `src/main.py`. A lógica **pura** (planejar o que fazer, consolidar
os PDFs, escrever os dois CSVs) é testável offline no DEV; o **laço de UI** (`executar`) é a
única peça que toca o LNC e valida-se na VPN — mas recebe a função de exportação por injeção,
então até o retry/registro de status são [AUTO]-testáveis com um stub. Reusa `contratos`
(vigentes + validação do map), `exportar_pdf.exportar` (1 PDF) e `parse_pdf.extrair_linhas`.

**Tech Stack:** Python 3.12, stdlib `csv`/`argparse`/`logging`, pdfplumber (via `parse_pdf`),
pywinauto/pyautogui (via `exportar_pdf`, só na VPN), pytest. Sem libs novas.

**Restrição de teste (modelo DEV↔VPN):** consolidação e planejamento são puros → TDD aqui. Só
há **1 fixture PDF** (`exemplo_projetos_executados.pdf`); o teste da consolidação **replica essa
fixture sob nomes-de-contrato** num `tmp_path` para exercitar o encanamento (laço, agrupamento,
CSV) — valida o *fluxo*, não os *dados* dos 21 (isso é VPN). Convenção: **[AUTO]** = pytest no
DEV; **[VPN]** = roteiro na VPN.

---

## Resumo

| | |
|---|---|
| Módulo novo | `src/main.py` |
| Módulo ajustado | `src/exportar_pdf.py` (nome do PDF passa a ser pelo **contrato**) |
| Testes [AUTO] novos | `tests/test_f5_consolidacao.py` |
| Teste [AUTO] ajustado | `tests/test_f3_exportar.py` (1 asserção do nome) |
| Reuso | `contratos.carregar_vigentes`/`validar_mapeamento`, `exportar_pdf.exportar`, `parse_pdf.extrair_linhas` |
| Entrega da fase | `.\run.ps1 --contratos "ECO 019/2020,ECO 021/2020"` percorre, consolida e relata na VPN |
| Atualização (produção) | **default re-exporta tudo** (dados sempre frescos); `--retomar` é opt-in para recuperar rodada interrompida |
| Nome do PDF | `output/pdf/<contrato_sanitizado>.pdf` (chave primária = contrato) |

## Estrutura de arquivos

- **`src/main.py`** (novo) — funções puras `planejar`, `consolidar`, `escrever_consolidado`,
  `escrever_relatorio`, `montar_relatorio`; laço de UI `executar` (com `exportar_fn` injetável);
  orquestração `main`/`_cli`.
- **`src/exportar_pdf.py`** (ajuste) — `caminho_saida(contrato)` nomeia pelo **contrato**;
  `exportar(programa_texto, contrato, log, destino=None)` ganha o parâmetro `contrato`; CLI passa
  a aceitar `--contrato` (resolve o `programa` pelo map). Fluxo de UI **não muda**.
- **`src/config.py`** (existente) — nada novo (já tem `CSV_CONSOLIDADO`, `CSV_RELATORIO`,
  `CSV_ENCODING`, `CSV_DELIMITADOR`, `PDF_DIR`).
- **`tests/test_f5_consolidacao.py`** (novo) — só partes puras + fixture replicada.

## Decisões fechadas com o usuário (não re-decidir)

- **Nome do PDF = contrato** (`ECO 019/2020` → `output/pdf/ECO_019_2020.pdf`). O código do
  contrato é a chave primária do `programas_map.json`, nunca se repete; convenção **única** no
  projeto (substitui o nome-por-programa que o `exportar_pdf` usava). _(decisão 16/06/2026)_
- **Consolidação itera o map** (os contratos), não os arquivos. Para cada contrato cujo PDF
  existe, todas as linhas parseadas ficam agrupadas **sob aquele contrato**. **Não há PDFs
  órfãos** (o conjunto de contratos é fixo). _(decisão 16/06/2026)_
- **Default = re-exporta tudo** (dados frescos a cada rodada — produção chama `.\run.ps1` 1×/dia
  para atualizar). A retomada (pular PDFs já existentes) é **opt-in via `--retomar`**, só para
  recuperar uma rodada interrompida no mesmo dia. **Sem `--force`** (o default já é re-exportar).
  Motivo: a regra antiga "PDF existe ⇒ pula" como default congelaria os dados silenciosamente em
  produção (o PDF do dia 1 nunca seria refeito). A consolidação sempre reparseia o que há e
  regrava o CSV inteiro (idempotente). _(decisão 16/06/2026)_
- **Falha cedo** se o map estiver incompleto/inválido: reusa `contratos.validar_mapeamento`
  **antes** de tocar a UI.

---

## Tarefa 1 — Nome do PDF pelo contrato (ajuste cirúrgico na F3) `[AUTO]`

Alinha `exportar_pdf` à convenção decidida. O fluxo de UI (já validado na VPN) **não muda** — só
muda como o caminho do arquivo é derivado e a CLI standalone.

**Files:**
- Modify: `src/exportar_pdf.py`
- Modify: `tests/test_f3_exportar.py`

- [ ] **Step 1: ajustar o teste do helper** (passa a esperar nome-por-contrato)

```python
# tests/test_f3_exportar.py
def test_caminho_saida_usa_contrato_sanitizado(tmp_path, monkeypatch):
    from src import config, exportar_pdf
    monkeypatch.setattr(config, "PDF_DIR", tmp_path)
    destino = exportar_pdf.caminho_saida("ECO 019/2020")
    assert destino == tmp_path / "ECO_019_2020.pdf"
    assert destino.is_absolute()
```

- [ ] **Step 2: rodar e ver falhar** — `pytest tests/test_f3_exportar.py -v` → FAIL (ainda
  sanitiza o programa).

- [ ] **Step 3: ajustar `exportar_pdf.py`**

```python
def caminho_saida(contrato: str):
    """output/pdf/<contrato_sanitizado>.pdf (absoluto). Contrato = chave primária."""
    config.PDF_DIR.mkdir(parents=True, exist_ok=True)
    return config.PDF_DIR / f"{contratos.sanitizar_nome(contrato)}.pdf"


def exportar(programa_texto: str, contrato: str, log: logging.Logger, destino=None):
    """Fluxo completo (inalterado); só o destino agora deriva do contrato."""
    destino = destino or caminho_saida(contrato)
    # ... resto idêntico (delete-antes, navegação, imprimir, salvar, arquivo estável) ...
```

- [ ] **Step 4: ajustar a CLI da F3** (`--contrato`, resolve o programa pelo map)

```python
p.add_argument("--contrato", required=True, help="chave em programas_map.json (ex.: 'ECO 019/2020')")
# ...
import json
mapa = json.loads(config.PROGRAMAS_MAP.read_text(encoding="utf-8"))
programa = mapa[args.contrato]["programa"]
exportar(programa, args.contrato, log, Path(args.saida) if args.saida else None)
```

- [ ] **Step 5: rodar [AUTO]** — `pytest tests/test_f3_exportar.py -v` → PASS.
- [ ] **Step 6: commit** — `refactor(f3): nomear PDF pelo contrato (chave primaria)`

> Nota [VPN]: o roteiro 3 da F3 passa a usar `--contrato "ECO 019/2020"` em vez de
> `--programa "..."`. Atualizar a linha do roteiro no `TESTES.md` (Tarefa 7).

## Tarefa 2 — `planejar` (puro, TDD) `[AUTO]`

Decide, por contrato, o que fazer — sem tocar a UI nem ler PDF (só checa existência de arquivo).

**Files:**
- Create: `src/main.py`
- Create: `tests/test_f5_consolidacao.py`

- [ ] **Step 1: teste que falha**

```python
# tests/test_f5_consolidacao.py
import sys
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

VIGENTES = {"ECO 019/2020": {}, "ECO 021/2020": {}}
MAPA = {"ECO 019/2020": {"programa": "AES SUL - 2ª Tranche"},
        "ECO 021/2020": {"programa": "CELPA 7ª TRANCHE REVISÃO 3"}}


def test_planejar_default_reexporta_mesmo_com_pdf(tmp_path):
    from src import main
    (tmp_path / "ECO_019_2020.pdf").write_bytes(b"%PDF-")  # PDF do dia anterior
    planos = main.planejar(VIGENTES, MAPA, tmp_path, retomar=False, filtro=None)
    # default = re-exporta tudo (dados frescos), mesmo com PDF existente
    assert all(p["acao"] == "exportar" for p in planos)
    por_contrato = {p["contrato"]: p for p in planos}
    assert por_contrato["ECO 019/2020"]["programa"] == "AES SUL - 2ª Tranche"


def test_planejar_retomar_pula_pdf_existente(tmp_path):
    from src import main
    (tmp_path / "ECO_019_2020.pdf").write_bytes(b"%PDF-")
    planos = main.planejar(VIGENTES, MAPA, tmp_path, retomar=True, filtro=None)
    por_contrato = {p["contrato"]: p for p in planos}
    assert por_contrato["ECO 019/2020"]["acao"] == "pular"     # já existe + --retomar
    assert por_contrato["ECO 021/2020"]["acao"] == "exportar"  # não existe


def test_planejar_filtro_subconjunto(tmp_path):
    from src import main
    planos = main.planejar(VIGENTES, MAPA, tmp_path, retomar=False, filtro=["ECO 021/2020"])
    assert [p["contrato"] for p in planos] == ["ECO 021/2020"]
```

- [ ] **Step 2: rodar e ver falhar** — `ModuleNotFoundError: src.main`.

- [ ] **Step 3: implementação mínima**

```python
# src/main.py
"""F5 — laço completo, retomada, consolidação e relatório do pipeline LPT.

Puro (testável no DEV): planejar / consolidar / escrever_*. UI (VPN): executar.
Retomada = existência do PDF output/pdf/<contrato_sanitizado>.pdf (contrato = chave primária).
"""
import csv
import logging
from collections import Counter

from src import config, contratos, exportar_pdf, parse_pdf


def _destino(pdf_dir, contrato):
    return pdf_dir / f"{contratos.sanitizar_nome(contrato)}.pdf"


def planejar(vigentes, mapa, pdf_dir, *, retomar=False, filtro=None):
    """-> [{contrato, programa, destino, acao}].

    acao: 'exportar' por padrão (re-exporta tudo = dados frescos); 'pular' SÓ com retomar=True
    quando o PDF já existe (recuperar rodada interrompida).
    """
    alvos = filtro if filtro else list(vigentes)
    planos = []
    for contrato in alvos:
        if contrato not in vigentes:
            raise ValueError(f"contrato {contrato!r} não é vigente (ou é ECM/Encerrado)")
        destino = _destino(pdf_dir, contrato)
        acao = "pular" if (retomar and destino.exists()) else "exportar"
        planos.append({
            "contrato": contrato,
            "programa": mapa[contrato]["programa"],
            "destino": destino,
            "acao": acao,
        })
    return planos
```

- [ ] **Step 4: rodar e ver passar** — `pytest tests/test_f5_consolidacao.py -v` → PASS.
- [ ] **Step 5: commit** — `feat(f5): main.planejar (default re-exporta; --retomar opt-in)`

## Tarefa 3 — `consolidar` + `escrever_consolidado` (puro, fixture replicada) `[AUTO]`

Reparseia todos os PDFs presentes, agrupando cada linha sob o **contrato**, e grava o CSV.

**Files:**
- Modify: `src/main.py`
- Modify: `tests/test_f5_consolidacao.py`

- [ ] **Step 1: teste que falha** (replica a fixture única sob 2 nomes-de-contrato)

```python
def _replicar_fixture(tmp_path, contratos_nomes):
    from src import config, contratos as c
    src_pdf = (config.FIXTURES_DIR / "exemplo_projetos_executados.pdf").read_bytes()
    for nome in contratos_nomes:
        (tmp_path / f"{c.sanitizar_nome(nome)}.pdf").write_bytes(src_pdf)


def test_consolidar_prefixa_contrato_e_agrupa(tmp_path):
    from src import main, config, parse_pdf
    _replicar_fixture(tmp_path, ["ECO 019/2020", "ECO 021/2020"])
    n = len(parse_pdf.extrair_linhas(config.FIXTURES_DIR / "exemplo_projetos_executados.pdf"))
    rows = main.consolidar(VIGENTES, MAPA, tmp_path, logging.getLogger("t"))
    assert len(rows) == 2 * n                      # 2 cópias da fixture
    assert {r[0] for r in rows} == {"ECO 019/2020", "ECO 021/2020"}
    assert rows[0] == ("ECO 019/2020", "10010263", "RS", "LAGOAO")  # spot-check


def test_escrever_consolidado_formato(tmp_path):
    from src import main, config
    caminho = tmp_path / "consolidado.csv"
    main.escrever_consolidado([("ECO 019/2020", "10010263", "RS", "LAGOAO")], caminho)
    txt = caminho.read_text(encoding=config.CSV_ENCODING)
    assert txt.splitlines()[0] == "contrato;odi;uf;municipio"
    assert "ECO 019/2020;10010263;RS;LAGOAO" in txt
```

(`import logging` no topo do arquivo de teste.)

- [ ] **Step 2: rodar e ver falhar.**

- [ ] **Step 3: implementação**

```python
def consolidar(vigentes, mapa, pdf_dir, log):
    """Itera os contratos; para cada PDF presente, parseia e prefixa o contrato."""
    rows = []
    for contrato in vigentes:
        destino = _destino(pdf_dir, contrato)
        if not destino.exists():
            log.info("sem PDF para %s — fora da consolidação (ainda não exportado)", contrato)
            continue
        linhas = parse_pdf.extrair_linhas(destino)
        log.info("%s: %d linhas", contrato, len(linhas))
        rows.extend((contrato, odi, uf, muni) for odi, uf, muni in linhas)
    return rows


def escrever_consolidado(rows, caminho):
    """CSV utf-8-sig com ';' — contrato;odi;uf;municipio."""
    with open(caminho, "w", newline="", encoding=config.CSV_ENCODING) as f:
        w = csv.writer(f, delimiter=config.CSV_DELIMITADOR)
        w.writerow(["contrato", "odi", "uf", "municipio"])
        w.writerows(rows)
```

- [ ] **Step 4: rodar e ver passar.**
- [ ] **Step 5: commit** — `feat(f5): consolidar PDFs presentes -> consolidado.csv`

## Tarefa 4 — `montar_relatorio` + `escrever_relatorio` (puro, TDD) `[AUTO]`

O relatório cruza o status de cada contrato (do laço) com a contagem de linhas (da consolidação).

**Files:**
- Modify: `src/main.py`, `tests/test_f5_consolidacao.py`

- [ ] **Step 1: teste que falha**

```python
def test_montar_relatorio_cruza_status_e_linhas():
    from src import main
    resultados = [{"contrato": "ECO 019/2020", "programa": "AES SUL - 2ª Tranche",
                   "status": "exportado", "erro": ""},
                  {"contrato": "ECO 021/2020", "programa": "CELPA 7ª TRANCHE REVISÃO 3",
                   "status": "falha", "erro": "timeout"}]
    rows = [("ECO 019/2020", "1", "RS", "X"), ("ECO 019/2020", "2", "RS", "Y")]
    rel = main.montar_relatorio(resultados, rows)
    por = {r["contrato"]: r for r in rel}
    assert por["ECO 019/2020"]["linhas"] == 2
    assert por["ECO 021/2020"]["linhas"] == 0
    assert por["ECO 021/2020"]["status"] == "falha"
```

- [ ] **Step 2: rodar e ver falhar.**

- [ ] **Step 3: implementação**

```python
def montar_relatorio(resultados, rows):
    """-> [{contrato, programa, status, linhas, erro}] (status do laço + nº de linhas do CSV)."""
    cont = Counter(r[0] for r in rows)
    return [{**res, "linhas": cont.get(res["contrato"], 0)} for res in resultados]


def escrever_relatorio(relatorio, caminho):
    """CSV utf-8-sig com ';' — contrato;programa;status;linhas;erro."""
    with open(caminho, "w", newline="", encoding=config.CSV_ENCODING) as f:
        w = csv.writer(f, delimiter=config.CSV_DELIMITADOR)
        w.writerow(["contrato", "programa", "status", "linhas", "erro"])
        for r in relatorio:
            w.writerow([r["contrato"], r["programa"], r["status"], r["linhas"], r["erro"]])
```

- [ ] **Step 4: rodar e ver passar.**
- [ ] **Step 5: commit** — `feat(f5): montar/escrever relatorio_execucao.csv`

## Tarefa 5 — `executar` (laço de UI; lógica de retry [AUTO] via injeção) `[AUTO]+[VPN]`

O laço é a única peça que toca o LNC, **mas** a função de exportação é injetável (`exportar_fn`),
então o retry e o registro de status são testáveis no DEV com um stub — sem UI. A chamada real
(`exportar_pdf.exportar`) só roda na VPN.

**Files:**
- Modify: `src/main.py`, `tests/test_f5_consolidacao.py`

- [ ] **Step 1: teste que falha** (stub que falha na 1ª e acerta na 2ª = valida o 1 retry)

```python
def test_executar_pula_e_registra(tmp_path):
    from src import main
    planos = [{"contrato": "A", "programa": "pa", "destino": tmp_path / "A.pdf", "acao": "pular"},
              {"contrato": "B", "programa": "pb", "destino": tmp_path / "B.pdf", "acao": "exportar"}]
    chamadas = []
    def fake_export(programa, contrato, log, destino=None):
        chamadas.append(contrato)
    res = main.executar(planos, logging.getLogger("t"), exportar_fn=fake_export)
    por = {r["contrato"]: r for r in res}
    assert por["A"]["status"] == "pulado" and "A" not in chamadas
    assert por["B"]["status"] == "exportado"


def test_executar_faz_um_retry_e_continua():
    from src import main
    planos = [{"contrato": "B", "programa": "pb", "destino": None, "acao": "exportar"}]
    estado = {"n": 0}
    def flaky(programa, contrato, log, destino=None):
        estado["n"] += 1
        if estado["n"] == 1:
            raise RuntimeError("falha transitória")
    res = main.executar(planos, logging.getLogger("t"), exportar_fn=flaky)
    assert estado["n"] == 2                       # 1 falha + 1 retry
    assert res[0]["status"] == "exportado"
```

- [ ] **Step 2: rodar e ver falhar.**

- [ ] **Step 3: implementação** (screenshot best-effort; re-navegação = nova chamada a
  `exportar`, que já começa por `conectar_ou_abrir`+`limpar_estado`+`navegar`)

```python
def _screenshot_falha(contrato, log):
    try:
        import scripts.inspecionar_app as insp
        insp.screenshot(f"falha_{contratos.sanitizar_nome(contrato)}", log)
    except Exception:
        log.warning("screenshot de falha indisponível (seguindo)")


def executar(planos, log, *, exportar_fn=exportar_pdf.exportar):
    """Laço de UI: exporta os 'exportar', pula os 'pular'. 1 retry por contrato; o laço continua."""
    resultados = []
    for p in planos:
        base = {"contrato": p["contrato"], "programa": p["programa"]}
        if p["acao"] == "pular":
            log.info("PULANDO %s (PDF já existe)", p["contrato"])
            resultados.append({**base, "status": "pulado", "erro": ""})
            continue
        status, erro = "exportado", ""
        for tentativa in (1, 2):
            try:
                exportar_fn(p["programa"], p["contrato"], log, destino=p["destino"])
                break
            except Exception as e:
                log.error("EXPORT FALHOU %s (tentativa %d): %s", p["contrato"], tentativa, e)
                _screenshot_falha(p["contrato"], log)
                if tentativa == 2:
                    status, erro = "falha", str(e)
        resultados.append({**base, "status": status, "erro": erro})
    return resultados
```

- [ ] **Step 4: rodar e ver passar** (DEV, sem UI).
- [ ] **Step 5: validação [VPN]** — coberta pelos roteiros da Tarefa 7 (laço real).
- [ ] **Step 6: commit** — `feat(f5): executar (laco de UI com 1 retry, status por contrato)`

## Tarefa 6 — Orquestração `main`/`_cli` + flags `[AUTO]+[VPN]`

Amarra tudo: carrega+valida (falha cedo), planeja, `--dry-run` mostra o plano, `--somente-parse`
pula a UI, sempre consolida + escreve os 2 CSVs + resumo no console. Log para
`output/logs/run_<ts>.log`. **Default re-exporta tudo**; `--retomar` pula PDFs existentes.

**Files:**
- Modify: `src/main.py`, `tests/test_f5_consolidacao.py`

- [ ] **Step 1: teste [AUTO] do carregar+validar (falha cedo)**

```python
def test_carregar_validado_falha_cedo_se_map_incompleto(tmp_path, monkeypatch):
    from src import main, config
    monkeypatch.setattr(config, "PROGRAMAS_MAP", tmp_path / "map.json")
    (tmp_path / "map.json").write_text('{"ECO 019/2020": {"programa": ""}}', encoding="utf-8")
    # vigentes/dropdown monkeypatched para um par mínimo; validar deve listar erro e abortar
    with __import__("pytest").raises(SystemExit):
        main._carregar_validado(logging.getLogger("t"))
```

(Os detalhes de monkeypatch de `carregar_vigentes`/dropdown ajustados na implementação; a
asserção-chave é **aborta** quando o map é inválido.)

- [ ] **Step 2: implementação da orquestração**

```python
def _carregar_validado(log):
    import json
    vigentes = contratos.carregar_vigentes()
    mapa = json.loads(config.PROGRAMAS_MAP.read_text(encoding="utf-8"))
    dropdown = json.loads(config.PROGRAMAS_DROPDOWN.read_text(encoding="utf-8"))
    erros = contratos.validar_mapeamento(vigentes, dropdown, mapa)
    if erros:
        for e in erros:
            log.error("MAP inválido: %s", e)
        raise SystemExit(f"map inválido ({len(erros)} erro(s)) — corrija antes de rodar")
    return vigentes, mapa


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser(description="Pipeline LPT: exporta, consolida e relata.")
    p.add_argument("--contratos", default=None, help="subconjunto separado por vírgula")
    p.add_argument("--retomar", action="store_true",
                   help="pula contratos cujo PDF já existe (recupera rodada interrompida); "
                        "SEM ele o default re-exporta tudo = dados frescos")
    p.add_argument("--somente-parse", action="store_true", help="pula a UI; só consolida o que há")
    p.add_argument("--dry-run", action="store_true", help="lista o plano e sai (não toca a UI)")
    args = p.parse_args(argv)

    log = _configurar_log()   # console + output/logs/run_<ts>.log (reusa o padrão do lnc_app)
    vigentes, mapa = _carregar_validado(log)
    filtro = [c.strip() for c in args.contratos.split(",")] if args.contratos else None
    planos = planejar(vigentes, mapa, config.PDF_DIR, retomar=args.retomar, filtro=filtro)

    if args.dry_run:
        for pl in planos:
            log.info("PLANO %s -> %s (%s)", pl["contrato"], pl["acao"], pl["programa"])
        return

    if args.somente_parse:
        resultados = [{"contrato": pl["contrato"], "programa": pl["programa"],
                       "status": "pulado", "erro": "(somente-parse)"} for pl in planos]
    else:
        resultados = executar(planos, log)

    rows = consolidar(vigentes, mapa, config.PDF_DIR, log)
    escrever_consolidado(rows, config.CSV_CONSOLIDADO)
    relatorio = montar_relatorio(resultados, rows)
    escrever_relatorio(relatorio, config.CSV_RELATORIO)

    ok = sum(1 for r in resultados if r["status"] == "exportado")
    pulados = sum(1 for r in resultados if r["status"] == "pulado")
    falhas = sum(1 for r in resultados if r["status"] == "falha")
    log.info("=== RESUMO: %d exportado(s), %d pulado(s), %d falha(s); %d linhas no CSV ===",
             ok, pulados, falhas, len(rows))


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: rodar [AUTO]** — `pytest tests/test_f5_consolidacao.py -v` → PASS; suíte inteira
  `pytest tests/ -q` → verde.
- [ ] **Step 4: smoke DEV do dry-run** — com o map preenchido (já está) e **sem** PDFs:
  `python -m src.main --dry-run` deve listar 21 contratos como `exportar` e **não** tocar a UI
  (no DEV não há LNC; `--dry-run`/`--somente-parse` jamais chamam `executar`). Critério: roda
  até o fim sem exceção e lista 21 planos.
- [ ] **Step 5: commit** — `feat(f5): main/_cli (flags, validacao cedo, dry-run, resumo)`

## Tarefa 7 — `run.ps1` (mínimo p/ a F5) + roteiros [VPN] + docs `[VPN]`

A F6 finaliza o `run.ps1` (fixar impressora padrão, doc final). Aqui só o suficiente para rodar
o laço na VPN e os roteiros.

**Files:**
- Create: `run.ps1` (mínimo)
- Modify: `planning/TESTES.md` (roteiros 5–7), `planning/PLAN.md` (Controle de progresso)

- [ ] **Step 1: `run.ps1` mínimo** — ativa `.venv`, repassa argumentos a `python -m src.main`
  (ASCII puro, sem BOM). A fixação da impressora padrão fica para a F6.
- [ ] **Step 2: roteiros [VPN] no TESTES.md:**
  - **Roteiro 5 (`--dry-run`)**: `.\run.ps1 --dry-run` → lista 21 planos como `exportar`, não abre o LNC.
  - **Roteiro 6 (refresh vs. retomada)**: `.\run.ps1 --contratos "ECO 019/2020,ECO 021/2020"`
    → 2 PDFs + CSV com 2 contratos. **(a) refresh:** re-rodar o mesmo comando → ambos
    **re-exportados** (PDFs regerados, dados frescos). **(b) retomada:** `.\run.ps1 --retomar
    --contratos "..."` → ambos `pulado`. **(c) interrupção:** matar no meio do 1º e rodar com
    `--retomar` → retoma sem refazer o que ficou pronto.
  - **Roteiro 7 (rodada completa supervisionada)**: `.\run.ps1` → 21 contratos (todos
    re-exportados); conferir `relatorio_execucao.csv` (status) e amostrar 5 linhas do
    `consolidado.csv` vs. um PDF aberto.
- [ ] **Step 3: atualizar roteiro 3 da F3** para `--contrato` (Tarefa 1).
- [ ] **Step 4: commit** — `feat(f5): run.ps1 minimo + roteiros VPN 5-7`
- [ ] **Step 5: validação [VPN]** — usuário roda os roteiros 5–7; traz `resultados_<data>.zip`.

---

## Roteiros [VPN] desta fase (entram no próximo pacote)

| # | Comando | Esperado | Critério |
|---|---|---|---|
| 5 | `.\run.ps1 --dry-run` | lista 21 planos; LNC intocado | 21 linhas `PLANO ... -> exportar` |
| 6a | `.\run.ps1 --contratos "A,B"` ×2 (refresh) | ambas re-exportam | PDFs regerados (dados frescos) |
| 6b | `.\run.ps1 --retomar --contratos "A,B"` | 2 `pulado` | retomada só com a flag |
| 6c | matar no meio + `.\run.ps1 --retomar` | retoma sem refazer | sem PDF duplicado |
| 7 | `.\run.ps1` (completo, supervisionado) | 21 re-exportados; 2 CSVs coerentes | relatório sem `falha`; 5 linhas conferem |

## Riscos & mitigações

| Risco | Sev | Mitigação |
|---|---|---|
| Fixture replicada não pega bug de dados entre contratos diferentes | MÉD | Limite **assumido e documentado**: o teste [AUTO] valida o encanamento; a corretude dos dados dos 21 é [VPN] (roteiro 7, amostra de 5 linhas). Trazer 2–3 PDFs reais distintos como fixtures extras quando a viagem ocorrer. |
| Falha no meio da rodada longa (21× ~1 min) deixa estado sujo | MÉD | `exportar` começa por `limpar_estado`; 1 retry por contrato; o laço **continua** após falha (não aborta a rodada). Recuperação sem refazer o pronto: `.\run.ps1 --retomar`. |
| `--somente-parse` rodar sem PDFs gera CSV vazio silenciosamente | BAIXA | Resumo no console mostra `0 linhas`; relatório lista todos como `pulado`. |
| Mudança do nome do PDF (contrato) invalida PDFs antigos nomeados por programa | BAIXA | Só há PDFs por-programa de testes da F3 na VPN; serão regerados. Documentar no roteiro 6 que a pasta `output/pdf/` pode ser limpa antes. |
| `SystemExit` no `_carregar_validado` confunde com erro de código | BAIXA | Mensagem clara + lista de erros do `validar_mapeamento` no log antes de sair. |

## Open questions (decidir/calibrar)

1. **Retry deve re-navegar do zero ou só re-tentar a etapa que falhou?** Proposta: re-navegar do
   zero (nova chamada a `exportar`, que já faz `limpar_estado`+navegação) — mais simples e
   robusto. *Confirmar comportamento na 1ª rodada [VPN] longa (roteiro 7).*
2. **`--somente-parse` deve marcar status `pulado` ou um status próprio (`consolidado`)?** Proposta:
   `pulado` com `erro="(somente-parse)"` para não inventar estado. *Decisão do usuário se quiser
   distinguir no relatório.*
3. **Ordem do `consolidado.csv`**: segue a ordem dos contratos vigentes no `base_contratos.json`
   (estável). Suficiente? *Se quiser ordenar por ODI/UF, é 1 linha — avisar.*
