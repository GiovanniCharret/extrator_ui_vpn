"""F3 [AUTO] — valida que um PDF de Projetos Executados é legível.

Roda contra a fixture (DEV) e, quando trazido da VPN, contra o PDF real exportado.
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))


def test_pdf_fixture_e_valido():
    import pdfplumber

    from src import config

    pdf = config.FIXTURES_DIR / "exemplo_projetos_executados.pdf"
    assert pdf.read_bytes()[:5] == b"%PDF-"
    with pdfplumber.open(pdf) as doc:
        assert len(doc.pages) > 0
