"""F4 [AUTO] — parsing do PDF de Projetos Executados em (ODI, UF, Município).

100% offline contra a fixture (manuais/output.pdf copiado em tests/fixtures/).
"""

import re
import sys
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

UFS = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
    "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
    "SP", "SE", "TO",
}


@pytest.fixture(scope="module")
def linhas():
    from src import config
    from src.parse_pdf import extrair_linhas

    return extrair_linhas(config.FIXTURES_DIR / "exemplo_projetos_executados.pdf")


def test_extrai_muitas_linhas(linhas):
    assert len(linhas) > 50  # fixture tem ~53 págs de dados


def test_primeira_linha_spot_check(linhas):
    assert linhas[0] == ("10010263", "RS", "LAGOAO")


def test_odis_no_padrao(linhas):
    assert all(re.fullmatch(r"\d{6,}", odi) for odi, _, _ in linhas)


def test_ufs_validas(linhas):
    assert all(uf in UFS for _, uf, _ in linhas)


def test_municipios_nao_vazios(linhas):
    assert all(muni.strip() for _, _, muni in linhas)


def test_sem_lixo_de_cabecalho(linhas):
    texto_todo = " ".join(f"{o} {u} {m}" for o, u, m in linhas)
    for proibido in ("ODI", "Município", "Page ", "PROJETOS EXECUTADOS"):
        assert proibido not in texto_todo


# --- ODI alfanumérico (regressão da VPN 17/06/2026) -------------------------
# Vários programas reais usam ODI alfanumérico (ex.: ODR136PROJ019A, B0174334,
# PA2000112LPT130024PA). O regex antigo (^\d{6,}$) descartava silenciosamente
# essas linhas → 9/15 PDFs da 1ª rodada vinham com 0 linhas. Fixture: ECO_011.

@pytest.fixture(scope="module")
def linhas_alfa():
    from src import config
    from src.parse_pdf import extrair_linhas

    return extrair_linhas(config.FIXTURES_DIR / "exemplo_odi_alfanumerico.pdf")


def test_extrai_linhas_com_odi_alfanumerico(linhas_alfa):
    assert len(linhas_alfa) > 0  # antes do fix vinha 0 (ODI 'ODR136PROJ019A' rejeitado)


def test_spot_check_odi_alfanumerico(linhas_alfa):
    assert linhas_alfa[0] == ("136PROJ0032", "AP", "PORTO GRANDE")


def test_aceita_letras_no_odi(linhas_alfa):
    assert any(not odi.isdigit() for odi, _, _ in linhas_alfa)  # ao menos um ODI com letra


def test_alfa_sem_lixo_de_cabecalho(linhas_alfa):
    texto_todo = " ".join(f"{o} {u} {m}" for o, u, m in linhas_alfa)
    for proibido in ("ODI", "Município", "PROJETOS EXECUTADOS"):
        assert proibido not in texto_todo
