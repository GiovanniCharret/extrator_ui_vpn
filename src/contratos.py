"""Helpers puros de contrato/nome (offline). Resto (map, vigentes) fica para F5."""

import re
import unicodedata


def sanitizar_nome(texto: str) -> str:
    """Texto do programa -> nome de arquivo seguro (sem acento, sem char proibido)."""
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)
    )
    return re.sub(r"[^A-Za-z0-9_-]+", "_", sem_acento).strip("_")
