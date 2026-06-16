"""F1 [AUTO] — partes offline de contratos/lnc_app (o grosso da UI valida-se na VPN)."""

import logging
import sys
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))


def test_sanitizar_nome_programa():
    from src.contratos import sanitizar_nome

    assert sanitizar_nome("AES SUL - 2ª Tranche") == "AES_SUL_-_2a_Tranche"
    assert sanitizar_nome("ECM 004/2021") == "ECM_004_2021"
    assert sanitizar_nome("a/b\\c:d*e?") == "a_b_c_d_e"


def test_preview_pronto_so_quando_render_termina():
    """O preview reporta '0% Page 1 of 0' enquanto renderiza (bug VPN 16/06): não é pronto.
    Pronto = sem '%' (sem indicador de progresso) e total de páginas > 0."""
    from src.lnc_app import _preview_pronto

    assert _preview_pronto("Page 1 of 53") is True
    assert _preview_pronto("0% Page 1 of 0") is False   # ainda renderizando
    assert _preview_pronto("50% Page 1 of 27") is False  # ainda renderizando
    assert _preview_pronto("Page 1 of 0") is False        # total zero (defensivo)
    assert _preview_pronto("") is False


def test_conectar_ou_abrir_falha_clara(monkeypatch):
    """Sem janela 'Sistema LPT' no DEV -> tenta abrir exe inexistente -> erro nomeado."""
    from src import config, lnc_app

    monkeypatch.setattr(config, "LNC_EXE", r"Z:\NAO_EXISTE\nada.exe")
    monkeypatch.setattr(config, "TIMEOUT_ABRIR_APP", 2)
    with pytest.raises(Exception):
        lnc_app.conectar_ou_abrir(logging.getLogger("t"))
