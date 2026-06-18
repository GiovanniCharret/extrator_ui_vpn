"""Helpers puros de contrato/nome (offline): sanitização, vigentes e validação do map."""

import json
import re
import unicodedata

from src import config


def sanitizar_nome(texto: str) -> str:
    """Texto do programa -> nome de arquivo seguro (sem acento, sem char proibido)."""
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)
    )
    return re.sub(r"[^A-Za-z0-9_-]+", "_", sem_acento).strip("_")


# Prefixo de contrato fora do laço: ECM são contratos novos, NÃO alimentados pela
# base legada LPT (não têm Programa no dropdown) — informado pelo usuário 16/06/2026.
PREFIXO_FORA_DO_LACO = "ECM"


def carregar_vigentes(caminho=None) -> dict:
    """Contratos que o pipeline processa: vigente != 'Encerrado' E não-ECM.

    ECM ficam fora do laço (e do programas_map): são contratos novos, fora da base
    legada — não existem no dropdown de Programas do LPT.
    """
    caminho = caminho or config.BASE_CONTRATOS
    with open(caminho, encoding="utf-8") as f:
        todos = json.load(f)
    return {
        k: v for k, v in todos.items()
        if v.get("vigente") != "Encerrado" and not k.startswith(PREFIXO_FORA_DO_LACO)
    }


def validar_mapeamento(vigentes: dict, dropdown: list, mapa: dict) -> list:
    """Lista de erros (vazia = ok): (a) todo vigente com programa; (b) programa existe
    literalmente no dropdown; (c) mapeamento 1:1 (programa duplicado = erro); (d) todo
    vigente com 'tipo' preenchido e dentro dos tipos válidos (config.TIPOS_PROJETO)."""
    erros = []
    dropdown_set = set(dropdown)
    vistos = {}
    for contrato in vigentes:
        entry = mapa.get(contrato) or {}
        # (d) tipo de projeto: obrigatório e dentro dos 5 radios válidos
        tipo = (entry.get("tipo") or "").strip()
        if not tipo:
            erros.append(f"contrato {contrato!r} sem 'tipo' preenchido")
        elif tipo not in config.TIPOS_PROJETO:
            erros.append(f"contrato {contrato!r}: tipo {tipo!r} não é válido {config.TIPOS_PROJETO}")
        programa = entry.get("programa", "").strip()
        if not programa:
            erros.append(f"contrato {contrato!r} sem 'programa' preenchido")
            continue
        if programa not in dropdown_set:
            erros.append(f"contrato {contrato!r}: programa {programa!r} não existe no dropdown")
        if programa in vistos:
            erros.append(
                f"programa {programa!r} duplicado: {vistos[programa]!r} e {contrato!r} (deve ser 1:1)"
            )
        else:
            vistos[programa] = contrato
    return erros
