"""U4/U6 [AUTO] — consolidação (seleção de colunas) e lookup UF/município pelo DTB.

Offline, com a fixture sintética tests/fixtures/exemplo_ucs.csv (mesmo formato do SSRS:
vírgula, BOM, decimais entre aspas). A fixture traz os DOIS formatos de código que a vida
real apresenta: 7 dígitos (com DV) e 6 dígitos (como o SSRS entrega, sem DV) — e, na
PPC_Data_Envio, uma linha preenchida e uma vazia (o relatório traz as duas situações).
A corretude dos dados dos 23 contratos é validação [VPN].
"""

import csv
import logging
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from ucs import config, consolida, download, municipios

FIXTURE = BASE_DIR / "tests" / "fixtures" / "exemplo_ucs.csv"
LOG = logging.getLogger("test")
# DTB mínima para os testes, nas duas chaves — como carregar_dtb monta a real.
DTB = {"1100015": ("Rondônia", "Alta Floresta D'Oeste"),
       "110001": ("Rondônia", "Alta Floresta D'Oeste"),
       "1600550": ("Amapá", "Pracuúba"),
       "160055": ("Amapá", "Pracuúba")}


# --- U6: normalização do código e carga do DTB --------------------------

def test_normalizar_codigo_tolera_espaco_e_decimal():
    assert municipios.normalizar_codigo(" 1600550 ") == "1600550"   # espaços nas pontas
    assert municipios.normalizar_codigo("1600550.0") == "1600550"   # sufixo decimal do Excel
    assert municipios.normalizar_codigo("160055") == "160055"       # 6 dígitos (formato SSRS)
    assert municipios.normalizar_codigo("") == ""                   # vazio continua vazio
    assert municipios.normalizar_codigo("16.00550") == ""           # não-numérico não vira código


def test_carregar_dtb_indexa_7_e_6_digitos():
    """O SSRS entrega 6 dígitos e o DTB tem 7 — as duas chaves têm de resolver."""
    dtb = municipios.carregar_dtb()
    assert dtb["1600550"] == ("Amapá", "Pracuúba")       # código completo (com DV)
    assert dtb["160055"] == ("Amapá", "Pracuúba")        # prefixo sem DV (o que o SSRS manda)
    assert len(dtb) == 2 * 5571                          # 5.571 municípios × 2 chaves, sem colisão


def test_carregar_dtb_arquivo_ausente_falha_alto(tmp_path):
    """DTB ausente tem de QUEBRAR a rodada (18/09/2026: faltou e a base saiu em branco)."""
    try:
        municipios.carregar_dtb(tmp_path / "nao_existe.csv")
        assert False, "deveria ter levantado FileNotFoundError"
    except FileNotFoundError as exc:
        assert "DTB" in str(exc)


# --- U4: extração das colunas -------------------------------------------

def test_extrair_linhas_traz_codigo_normalizado_e_data_envio():
    linhas = consolida.extrair_linhas(FIXTURE)
    # a fixture tem 2 linhas reais + 1 linha-placeholder vazia (do SSRS) -> 2
    assert len(linhas) == 2
    assert linhas[0] == ("10090247", "111", "1100015", "15/07/2026")   # (odi, uc, código, data)
    # data_envio em branco no relatório segue em branco na base (não vira placeholder)
    assert linhas[1] == ("10090248", "222", "160055", "")


def test_extrair_linhas_com_dados_projetos():
    linhas = consolida.extrair_linhas(FIXTURE, incluir_projetos=True)
    assert linhas[0] == ("10090247", "111", "1100015", "15/07/2026",
                         "374944", "PROJ TESTE A, COM VIRGULA")


def test_extrair_linhas_ignora_placeholder_vazio():
    for odi, uc, *_ in consolida.extrair_linhas(FIXTURE):
        assert odi or uc


def test_extrair_linhas_header_sem_ancora_falha(tmp_path):
    ruim = tmp_path / "ruim.csv"
    ruim.write_text("a,b,c\n1,2,3\n", encoding="utf-8")
    try:
        consolida.extrair_linhas(ruim)
        assert False, "deveria ter falhado sem as âncoras"
    except ValueError as exc:
        assert config.COL_LOCALIZACAO in str(exc)   # a mensagem lista o que faltou


# --- U4: consolidação ----------------------------------------------------

def _raw_com(tmp_path, *contratos):
    """Cria um raw/ com a fixture replicada sob cada nome-de-contrato dado."""
    raw = tmp_path / "raw"
    raw.mkdir()
    for c in contratos:
        (raw / f"{download.sanitizar_nome(c)}.csv").write_bytes(FIXTURE.read_bytes())
    return raw


def test_consolidar_csv_resolve_uf_municipio_e_prefixa_contrato(tmp_path):
    raw = _raw_com(tmp_path, "ECO 025/2021", "ECO 021/2020")
    mapa = {"ECO 025/2021": {"codese": "20", "programa": "1520"},
            "ECO 021/2020": {"codese": "156", "programa": "1531"}}
    saida = tmp_path / "consolidado_ucs_modelo.csv"
    total = consolida.consolidar_csv(mapa, raw, saida, LOG, DTB)
    assert total == 4  # 2 contratos x 2 linhas

    with open(saida, encoding=config.CSV_ENCODING, newline="") as fh:
        linhas = list(csv.reader(fh, delimiter=config.CSV_DELIMITADOR))
    assert linhas[0] == ["contrato", "odi", "uc", "uf", "municipio", "data_envio"]
    # a data de envio sai VERBATIM, logo depois do município
    assert linhas[1] == ["ECO 025/2021", "10090247", "111", "Rondônia", "Alta Floresta D'Oeste",
                         "15/07/2026"]
    # a 2ª linha vem do código de 6 dígitos — o formato que o SSRS realmente entrega
    assert linhas[2] == ["ECO 025/2021", "10090248", "222", "Amapá", "Pracuúba", ""]


def test_consolidar_csv_com_dados_projetos(tmp_path):
    raw = _raw_com(tmp_path, "ECO 025/2021")
    mapa = {"ECO 025/2021": {"codese": "20", "programa": "1520"}}
    saida = tmp_path / "out.csv"
    consolida.consolidar_csv(mapa, raw, saida, LOG, DTB, incluir_projetos=True)
    with open(saida, encoding=config.CSV_ENCODING, newline="") as fh:
        linhas = list(csv.reader(fh, delimiter=config.CSV_DELIMITADOR))
    assert linhas[0] == ["contrato", "odi", "uc", "uf", "municipio", "data_envio",
                         "cod_projeto", "nome_projeto"]
    assert linhas[1] == ["ECO 025/2021", "10090247", "111", "Rondônia", "Alta Floresta D'Oeste",
                         "15/07/2026", "374944", "PROJ TESTE A, COM VIRGULA"]


def test_consolidar_csv_ignora_contrato_sem_bruto(tmp_path):
    raw = _raw_com(tmp_path, "ECO 025/2021")
    mapa = {"ECO 025/2021": {"codese": "20", "programa": "1520"},
            "ECO 999/2099": {"codese": "1", "programa": "1"}}  # sem bruto
    total = consolida.consolidar_csv(mapa, raw, tmp_path / "out.csv", LOG, DTB)
    assert total == 2  # só o contrato com bruto


def test_consolidar_csv_codigo_sem_par_falha_e_preserva_o_anterior(tmp_path):
    """Código sem par no DTB: aborta, e o consolidado da rodada anterior fica intacto."""
    raw = _raw_com(tmp_path, "ECO 025/2021")
    mapa = {"ECO 025/2021": {"codese": "20", "programa": "1520"}}
    saida = tmp_path / "consolidado_ucs_modelo.csv"
    saida.write_text("base;anterior\n", encoding=config.CSV_ENCODING)   # rodada anterior
    try:
        consolida.consolidar_csv(mapa, raw, saida, LOG, {"9999999": ("X", "Y")})
        assert False, "deveria ter levantado ValueError"
    except ValueError as exc:
        assert "sem par" in str(exc)
    # o .tmp foi descartado e o arquivo bom da rodada anterior continua lá
    assert saida.read_text(encoding=config.CSV_ENCODING) == "base;anterior\n"
    assert not saida.with_name(saida.name + ".tmp").exists()


def test_consolidar_sqlite_e_benchmark(tmp_path):
    raw = _raw_com(tmp_path, "ECO 025/2021")
    mapa = {"ECO 025/2021": {"codese": "20", "programa": "1520"}}
    db = tmp_path / "ucs.db"
    total = consolida.consolidar_sqlite(mapa, raw, db, LOG, DTB)
    assert total == 2 and db.exists()

    saida = tmp_path / "consolidado_ucs_modelo.csv"
    consolida.consolidar_csv(mapa, raw, saida, LOG, DTB)
    metr = consolida.benchmark(saida, db, LOG)
    assert metr["csv_linhas"] == 2 and metr["db_mb"] >= 0
