"""F3 [AUTO] — parte offline do exportar_pdf (o fluxo de UI valida-se na VPN)."""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))


def test_caminho_saida_usa_nome_sanitizado(tmp_path, monkeypatch):
    from src import config, exportar_pdf

    monkeypatch.setattr(config, "PDF_DIR", tmp_path)
    destino = exportar_pdf.caminho_saida("AES SUL - 2ª Tranche")
    assert destino == tmp_path / "AES_SUL_-_2a_Tranche.pdf"
    assert destino.is_absolute()
