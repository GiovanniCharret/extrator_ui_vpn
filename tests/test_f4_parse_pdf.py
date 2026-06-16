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
