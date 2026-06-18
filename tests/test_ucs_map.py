"""U2 [AUTO] — validação do ucs_map.json (estrutura) e helpers de download.

Offline. Confere também que o ucs_map.json REAL (gerado da recon) tem os 21 contratos
com codese/programa preenchidos.
"""

import json
import sys
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from ucs import config, download


def test_validar_mapeamento_ok():
    mapa = {"ECO 025/2021": {"codese": "20", "programa": "1520"}}
    assert download.validar_mapeamento(mapa) is True


def test_validar_mapeamento_vazio_falha():
    with pytest.raises(ValueError):
        download.validar_mapeamento({})


def test_validar_mapeamento_sem_codese_falha():
    with pytest.raises(ValueError):
        download.validar_mapeamento({"ECO 025/2021": {"programa": "1520"}})


def test_validar_mapeamento_sem_programa_falha():
    with pytest.raises(ValueError):
        download.validar_mapeamento({"ECO 025/2021": {"codese": "20"}})


def test_sanitizar_e_caminho_raw():
    assert download.sanitizar_nome("ECO 011/2018") == "ECO_011_2018"
    assert download.caminho_raw("ECO 011/2018", Path("/x")).name == "ECO_011_2018.csv"


def test_ucs_map_real_tem_21_contratos_validos():
    # o arquivo gerado a partir da recon deve estar completo e válido
    mapa = json.load(open(config.UCS_MAP, encoding="utf-8"))
    assert len(mapa) == 21
    assert download.validar_mapeamento(mapa) is True
