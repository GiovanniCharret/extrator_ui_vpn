"""F0 [AUTO] — valida o ambiente: dependências, entrada do pipeline e fixture.

Roda nos DOIS ambientes (DEV e VPN): `pytest tests/test_f0_ambiente.py -v`
"""

import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))


def test_imports_dependencias():
    import pdfplumber  # noqa: F401
    import pyautogui  # noqa: F401
    import pywinauto  # noqa: F401


def test_config_importa():
    from src import config

    assert config.LNC_EXE.lower().endswith("lnc.exe")
    assert config.TIMEOUT_GERACAO >= 300


def test_base_contratos_carrega_utf8():
    from src import config

    with open(config.BASE_CONTRATOS, encoding="utf-8") as f:
        contratos = json.load(f)

    assert isinstance(contratos, dict)
    assert len(contratos) > 0
    exemplo = next(iter(contratos.values()))
    for campo in ("sigla", "tranche", "uf", "vigente"):
        assert campo in exemplo


def test_existem_contratos_vigentes():
    from src import config

    with open(config.BASE_CONTRATOS, encoding="utf-8") as f:
        contratos = json.load(f)

    vigentes = {k: v for k, v in contratos.items() if v["vigente"] != "Encerrado"}
    assert len(vigentes) > 0
    # encoding correto: "1ª Tranche" tem o caractere ª
    assert any("ª" in v["tranche"] for v in vigentes.values())


def test_fixture_pdf_existe_e_e_valida():
    from src import config

    fixture = config.FIXTURES_DIR / "exemplo_projetos_executados.pdf"
    assert fixture.exists(), "Copie manuais/output.pdf para tests/fixtures/"
    assert fixture.read_bytes()[:5] == b"%PDF-"
