"""U2 [AUTO] — validação do ucs_map.json (estrutura) e helpers de download.

Offline. Confere também que o ucs_map.json REAL (gerado da recon) cobre todos os contratos
vigentes do laço, com codese/programa preenchidos.
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


def test_ucs_map_real_cobre_todos_os_contratos_vigentes():
    """O ucs_map.json REAL precisa cobrir TODOS os contratos vigentes do laço.

    Por que existe: a Fase 2 itera pelas CHAVES do map (`contratos = list(mapa)`), não
    pela base — um contrato vigente ausente do map some da rodada em silêncio, sem erro
    (foi o que aconteceu com ECO 034/2026 e ECO 045/2026). Contar contratos fixos (eram
    21) só envelhecia o teste; o invariante real é a cobertura.

    Lógica, do input ao output, em fases:
      Fase 1 — lê a base e filtra os vigentes do laço (não-'Encerrado' e não-ECM, a
               mesma regra de contratos.carregar_vigentes).
      Fase 2 — exige que cada vigente tenha entrada no map.
      Fase 3 — exige que o map inteiro seja estruturalmente válido (codese/programa).
    """
    base = json.load(open(BASE_DIR / "base_contratos.json", encoding="utf-8"))  # Fase 1
    vigentes = {c for c, v in base.items()                     # regra do laço (ECM ficam fora)
                if v.get("vigente") != "Encerrado" and not c.startswith("ECM")}
    mapa = json.load(open(config.UCS_MAP, encoding="utf-8"))   # map gerado da recon
    faltando = sorted(vigentes - set(mapa))                     # Fase 2: cobertura
    assert not faltando, f"contratos vigentes fora do ucs_map.json: {faltando}"
    assert download.validar_mapeamento(mapa) is True            # Fase 3: estrutura
