"""U4 [AUTO] — consolidação: extrair_linhas (seleção de colunas) e consolidar_csv.

Offline, com a fixture sintética tests/fixtures/exemplo_ucs.csv (mesmo formato do SSRS:
vírgula, BOM, decimais entre aspas). A corretude dos dados dos 21 é validação [VPN].
"""

import csv
import logging
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from ucs import config, consolida, download

FIXTURE = BASE_DIR / "tests" / "fixtures" / "exemplo_ucs.csv"
LOG = logging.getLogger("test")


def test_extrair_linhas_seleciona_colunas_certas():
    linhas = consolida.extrair_linhas(FIXTURE)
    # a fixture tem 2 linhas reais + 1 linha-placeholder vazia (do SSRS) -> 2
    assert len(linhas) == 2
    # (odi, uc, cod_projeto, nome_projeto, cod_programa)
    assert linhas[0] == ("10090247", "111", "374944", "PROJ TESTE A, COM VIRGULA", "1520")
    assert linhas[1][0] == "10090248" and linhas[1][1] == "222"


def test_extrair_linhas_ignora_placeholder_vazio():
    # nenhuma linha extraída deve ter ODI e UC ambos vazios (placeholder do SSRS)
    for odi, uc, *_ in consolida.extrair_linhas(FIXTURE):
        assert odi or uc


def test_extrair_linhas_header_sem_ancora_falha(tmp_path):
    ruim = tmp_path / "ruim.csv"
    ruim.write_text("a,b,c\n1,2,3\n", encoding="utf-8")
    try:
        consolida.extrair_linhas(ruim)
        assert False, "deveria ter falhado sem UCP_Num_UC/PPC_Odi"
    except ValueError:
        pass


def test_consolidar_csv_prefixa_contrato_e_soma(tmp_path):
    # replica a fixture sob 2 nomes-de-contrato (exercita o encanamento, não os dados)
    raw = tmp_path / "raw"
    raw.mkdir()
    conteudo = FIXTURE.read_bytes()
    (raw / "ECO_025_2021.csv").write_bytes(conteudo)
    (raw / "ECO_021_2020.csv").write_bytes(conteudo)
    mapa = {"ECO 025/2021": {"codese": "20", "programa": "1520"},
            "ECO 021/2020": {"codese": "156", "programa": "1531"}}
    saida = tmp_path / "consolidado_ucs.csv"
    total = consolida.consolidar_csv(mapa, raw, saida, LOG)
    assert total == 4  # 2 contratos x 2 linhas

    with open(saida, encoding=config.CSV_ENCODING, newline="") as fh:
        linhas = list(csv.reader(fh, delimiter=config.CSV_DELIMITADOR))
    assert linhas[0] == consolida.CABECALHO_SAIDA          # cabeçalho
    # primeira linha de dados traz o contrato prefixado
    assert linhas[1][0] == "ECO 025/2021"
    assert linhas[1][1] == "10090247" and linhas[1][2] == "111"


def test_consolidar_csv_ignora_contrato_sem_bruto(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "ECO_025_2021.csv").write_bytes(FIXTURE.read_bytes())
    mapa = {"ECO 025/2021": {"codese": "20", "programa": "1520"},
            "ECO 999/2099": {"codese": "1", "programa": "1"}}  # sem bruto
    saida = tmp_path / "out.csv"
    total = consolida.consolidar_csv(mapa, raw, saida, LOG)
    assert total == 2  # só o contrato com bruto


def test_consolidar_sqlite_e_benchmark(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "ECO_025_2021.csv").write_bytes(FIXTURE.read_bytes())
    mapa = {"ECO 025/2021": {"codese": "20", "programa": "1520"}}
    db = tmp_path / "ucs.db"
    total = consolida.consolidar_sqlite(mapa, raw, db, LOG)
    assert total == 2 and db.exists()

    saida = tmp_path / "consolidado_ucs.csv"
    consolida.consolidar_csv(mapa, raw, saida, LOG)
    metr = consolida.benchmark(saida, db, LOG)
    assert metr["csv_linhas"] == 2 and metr["db_mb"] >= 0
