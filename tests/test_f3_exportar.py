"""F3 [AUTO] — parte offline do exportar_pdf (o fluxo de UI valida-se na VPN)."""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))


def test_caminho_saida_usa_contrato_sanitizado(tmp_path, monkeypatch):
    from src import config, exportar_pdf

    monkeypatch.setattr(config, "PDF_DIR", tmp_path)
    destino = exportar_pdf.caminho_saida("ECO 019/2020")
    assert destino == tmp_path / "ECO_019_2020.pdf"
    assert destino.is_absolute()
