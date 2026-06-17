"""F2 — descobre os nomes reais do dropdown 'Programa' e gera o esqueleto do mapeamento.

Roda na VPN (roteiro 4): reusa lnc_app para chegar ao painel, lê os itens do
ComboBox 'Programa' (pywinauto lê item_texts de TComboBox win32 sem abrir o
dropdown), grava config/programas_dropdown.json e gera/mescla config/programas_map.json
para o usuário preencher à mão (copiando do dropdown). Entradas já preenchidas
NUNCA são sobrescritas (merge). Só entram contratos do laço (vigentes não-ECM).

A montagem do esqueleto (montar_esqueleto) é pura e testada offline; a enumeração
do dropdown é [VPN].
"""

import json
import logging
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src import config  # noqa: E402
from src import contratos as contratos_mod  # noqa: E402


def montar_esqueleto(vigentes: dict, mapa_existente: dict) -> dict:
    """{contrato: {'programa': '', 'tipo': <padrão>}} para preencher à mão.

    Preserva o já preenchido (merge); 'tipo' nasce com o padrão (Eletrificação Rural,
    a maioria) e é ajustado à mão quando o contrato usa outro radio (ex.: Fonte Alternativa).
    """
    esqueleto = {}
    for contrato in vigentes:
        ant = mapa_existente.get(contrato) or {}
        esqueleto[contrato] = {
            "programa": ant.get("programa", ""),               # preserva o programa já preenchido
            "tipo": ant.get("tipo", config.TIPO_PROJETO_PADRAO),  # preserva o tipo ou usa o padrão
        }
    return esqueleto


def enumerar_dropdown(log: logging.Logger) -> list:
    """[VPN] Navega até o painel, marca 'Programa' e lê os itens do ComboBox."""
    from src import lnc_app

    app, jp = lnc_app.conectar_ou_abrir(log)
    lnc_app.limpar_estado(app, log)
    lnc_app.navegar_para_painel(app, jp, log)
    radio = jp.child_window(title=config.RADIO_PROGRAMA, class_name="TRadioButton")
    lnc_app._clicar_controle(radio, f"radio {config.RADIO_PROGRAMA!r}", log)
    combo = jp.child_window(best_match=config.COMBO_PROGRAMA_BEST_MATCH)
    itens = list(combo.item_texts())
    log.info("dropdown 'Programa' tem %d itens", len(itens))
    return itens


def _gravar(dropdown: list, log: logging.Logger) -> None:
    config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config.PROGRAMAS_DROPDOWN.write_text(
        json.dumps(dropdown, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log.info("gravado %s (%d itens)", config.PROGRAMAS_DROPDOWN.name, len(dropdown))

    existente = {}
    if config.PROGRAMAS_MAP.exists():
        existente = json.loads(config.PROGRAMAS_MAP.read_text(encoding="utf-8"))
    vigentes = contratos_mod.carregar_vigentes()
    mapa = montar_esqueleto(vigentes, existente)
    config.PROGRAMAS_MAP.write_text(
        json.dumps(mapa, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    faltam = sum(1 for v in mapa.values() if not v["programa"])
    log.info("gravado %s (%d contratos, %d a preencher)",
             config.PROGRAMAS_MAP.name, len(mapa), faltam)


def _cli():
    import traceback
    from src import lnc_app

    log = lnc_app._configurar_log()
    log.info("=== gerar_mapeamento ===")
    try:
        dropdown = enumerar_dropdown(log)
        _gravar(dropdown, log)
        log.info("=== OK: preencha 'programa' em config/programas_map.json (use 'sugestao') ===")
    except Exception:
        log.error("FALHOU:\n%s", traceback.format_exc())
        try:
            import scripts.inspecionar_app as insp
            insp.dump_desktop("gerar_mapeamento_falha", log)
        except Exception:
            log.error("auto-dump falhou:\n%s", traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    _cli()
