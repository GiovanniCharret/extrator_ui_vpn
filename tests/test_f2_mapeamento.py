"""F2 [AUTO] — validação e montagem do mapeamento contrato -> programa (offline).

A enumeração do dropdown é [VPN] (roteiro 4); aqui testamos as partes puras:
carregar vigentes, validar o map e montar o esqueleto com sugestões.
"""

import json
import sys
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

DROPDOWN = ["AES SUL - 2ª Tranche", "CEEE - 1ª Tranche", "RGE - 3ª Tranche"]


def test_carregar_vigentes_filtra_encerrados():
    from src.contratos import carregar_vigentes

    vigentes = carregar_vigentes()
    assert len(vigentes) > 0
    assert all(v["vigente"] != "Encerrado" for v in vigentes.values())


def test_carregar_vigentes_exclui_ecm():
    """Contratos ECM são novos, fora da base legada LPT -> fora do laço/map."""
    from src.contratos import carregar_vigentes

    vigentes = carregar_vigentes()
    assert all(not k.startswith("ECM") for k in vigentes), \
        "ECM não deve entrar no conjunto processado"
    assert len(vigentes) > 0  # restam os ECO


def test_validar_mapeamento_ok():
    from src.contratos import validar_mapeamento

    vigentes = {"C1": {}, "C2": {}}
    mapa = {
        "C1": {"programa": "AES SUL - 2ª Tranche"},
        "C2": {"programa": "CEEE - 1ª Tranche"},
    }
    assert validar_mapeamento(vigentes, DROPDOWN, mapa) == []


def test_validar_mapeamento_programa_vazio():
    from src.contratos import validar_mapeamento

    erros = validar_mapeamento({"C1": {}}, DROPDOWN, {"C1": {"programa": ""}})
    assert len(erros) == 1 and "C1" in erros[0]


def test_validar_mapeamento_programa_inexistente():
    from src.contratos import validar_mapeamento

    erros = validar_mapeamento({"C1": {}}, DROPDOWN, {"C1": {"programa": "NAO EXISTE"}})
    assert any("dropdown" in e for e in erros)


def test_validar_mapeamento_duplicata_e_erro():
    from src.contratos import validar_mapeamento

    vigentes = {"C1": {}, "C2": {}}
    mapa = {
        "C1": {"programa": "AES SUL - 2ª Tranche"},
        "C2": {"programa": "AES SUL - 2ª Tranche"},  # 1:1 violado
    }
    assert any("duplicad" in e for e in validar_mapeamento(vigentes, DROPDOWN, mapa))


def test_montar_esqueleto_preserva_preenchido():
    from scripts.gerar_mapeamento import montar_esqueleto

    vigentes = {"C1": {}, "C2": {}}
    existente = {"C1": {"programa": "RGE - 3ª Tranche"}}  # já preenchido
    novo = montar_esqueleto(vigentes, existente)

    assert novo["C1"] == {"programa": "RGE - 3ª Tranche"}  # preservado, nunca sobrescrito
    assert novo["C2"] == {"programa": ""}                  # novo entra vazio
    assert all("sugestao" not in v for v in novo.values())  # sugestão removida


def test_mapeamento_real_quando_preenchido():
    """Acceptance da F2: depois da VPN (roteiro 4) + preenchimento manual, valida os
    arquivos REAIS. Pula no DEV enquanto config/programas_*.json não existirem."""
    from src import config
    from src.contratos import carregar_vigentes, validar_mapeamento

    if not (config.PROGRAMAS_MAP.exists() and config.PROGRAMAS_DROPDOWN.exists()):
        pytest.skip("map/dropdown ainda não gerados (F2 roda na VPN)")

    dropdown = json.loads(config.PROGRAMAS_DROPDOWN.read_text(encoding="utf-8"))
    mapa = json.loads(config.PROGRAMAS_MAP.read_text(encoding="utf-8"))
    if all(not (e.get("programa") or "").strip() for e in mapa.values()):
        pytest.skip("programas_map.json ainda não preenchido (F2 pendente)")

    erros = validar_mapeamento(carregar_vigentes(), dropdown, mapa)
    assert erros == [], "\n".join(erros)
