"""F1 — conexão e navegação idempotente no LNC (Sistema LPT, Delphi/VCL).

Backend híbrido: win32 (painel, datas, combo, statusbar) + uia (botões da barra
do preview, itens de lista) + 1 clique por coordenada (menu lateral owner-drawn).

EXECUÇÃO CEGA: cada ação de UI loga QUAL controle/opção aciona e a POSIÇÃO em
pixels no display (retângulo + centro, ou a coordenada). Isso é o que permite ao
usuário, ao validar na VPN sem eu ver a tela, me dizer "clicou em X mas o botão
estava em Y" — diagnóstico de uma viagem só.
"""

import logging
import re
import time

from pywinauto import Application, findwindows

from src import config


# --- Cliques instrumentados (log de pixels) ------------------------------

def _clicar_controle(ctrl, descricao: str, log: logging.Logger) -> None:
    """Loga retângulo + centro em pixels e clica no controle (click_input)."""
    r = ctrl.rectangle()
    c = r.mid_point()
    log.info("CLIQUE %s -> centro=(%d,%d) ret=(L%d T%d R%d B%d)",
             descricao, c.x, c.y, r.left, r.top, r.right, r.bottom)
    ctrl.click_input()


def _clicar_xy(janela, xy, descricao: str, log: logging.Logger) -> None:
    """Loga a coordenada (cliente + absoluta na tela) e clica por posição."""
    x, y = xy
    r = janela.rectangle()
    abs_x, abs_y = r.left + x, r.top + y
    log.info("CLIQUE %s -> coord cliente=(%d,%d) tela=(%d,%d) [janela L%d T%d]",
             descricao, x, y, abs_x, abs_y, r.left, r.top)
    janela.click_input(coords=(x, y))


# --- Conexão / limpeza ----------------------------------------------------

def conectar_ou_abrir(log: logging.Logger):
    """Retorna (app_win32, janela_principal). Conecta por PID; abre o LNC se preciso."""
    cands = findwindows.find_elements(
        title_re=config.TITULO_JANELA_PRINCIPAL_RE, backend="win32"
    )
    if not cands:
        log.info("LNC não encontrado; iniciando %s", config.LNC_EXE)
        Application(backend="win32").start(config.LNC_EXE)
        fim = time.monotonic() + config.TIMEOUT_ABRIR_APP
        while not cands and time.monotonic() < fim:
            time.sleep(1.0)
            cands = findwindows.find_elements(
                title_re=config.TITULO_JANELA_PRINCIPAL_RE, backend="win32"
            )
        if not cands:
            raise RuntimeError(
                f"LNC não abriu em {config.TIMEOUT_ABRIR_APP}s ({config.LNC_EXE})"
            )
    for c in cands:
        log.info("janela principal candidata: pid=%s handle=0x%X classe=%r titulo=%r",
                 c.process_id, c.handle, c.class_name, c.name)
    pid = cands[0].process_id
    app = Application(backend="win32").connect(process=pid)
    return app, app.window(handle=cands[0].handle)


def limpar_estado(app, log: logging.Logger) -> None:
    """Fecha previews/progressos/diálogos órfãos — torna a navegação idempotente."""
    for w in app.windows():
        try:
            cls = w.class_name()
        except Exception:
            continue
        if cls in (config.CLASSE_PREVIEW, config.CLASSE_PROGRESSO, config.CLASSE_SALVAR_COMO):
            log.info("limpando janela órfã: %s %r", cls, w.window_text())
            try:
                w.close()
            except Exception:
                try:
                    w.set_focus()
                    w.type_keys("{ESC}")
                except Exception:
                    log.warning("não consegui fechar %s", cls)


# --- Navegação ------------------------------------------------------------

def _ja_no_painel(jp, log: logging.Logger) -> bool:
    """True se a aba 'Projetos Executados' já está visível (evita reclicar o menu)."""
    try:
        return jp.child_window(
            title=config.TITULO_TAB_FILTROS, class_name="TTabSheet"
        ).exists(timeout=1)
    except Exception:
        return False


def navegar_para_painel(app, jp, log: logging.Logger) -> None:
    """Janela principal -> Relatórios (menu lateral, coord) -> '7 - Projetos Executados'."""
    jp.set_focus()
    if _ja_no_painel(jp, log):
        log.info("painel de filtros já visível; pulando navegação")
        return
    # menu lateral TExchangeBar é owner-drawn -> clique por coordenada (a calibrar)
    _clicar_xy(jp, config.MENU_RELATORIOS_XY, "menu lateral 'Relatórios'", log)
    time.sleep(1.0)
    # item da lista da direita só aparece no uia
    app_uia = Application(backend="uia").connect(process=app.process)
    jp_uia = app_uia.window(class_name=config.CLASSE_JANELA_PRINCIPAL)
    item = jp_uia.child_window(
        title=config.ITEM_PROJETOS_EXECUTADOS, control_type="ListItem"
    )
    # o painel carrega via SQL (medido ~29s na VPN) -> timeout generoso, não o de diálogo
    item.wait("exists enabled visible", timeout=config.TIMEOUT_PREVIEW)
    _clicar_controle(item, f"item {config.ITEM_PROJETOS_EXECUTADOS!r}", log)
    jp.child_window(title=config.TITULO_TAB_FILTROS, class_name="TTabSheet").wait(
        "exists", timeout=config.TIMEOUT_DIALOGO
    )


def selecionar_programa(jp, programa_texto: str, log: logging.Logger) -> None:
    """Marca o radio 'Programa' e seleciona o item no ComboBox; verifica o texto."""
    radio = jp.child_window(title=config.RADIO_PROGRAMA, class_name="TRadioButton")
    _clicar_controle(radio, f"radio {config.RADIO_PROGRAMA!r}", log)
    # há 4 TComboBox no painel (Região/Estado/Concessionária/Programa) -> best_match
    # pelo nome amigável (ElementAmbiguousError com class_name puro — VPN 16/06)
    combo = jp.child_window(best_match=config.COMBO_PROGRAMA_BEST_MATCH)
    r = combo.rectangle()
    log.info("SELECT combo 'Programa' = %r -> ret=(L%d T%d R%d B%d)",
             programa_texto, r.left, r.top, r.right, r.bottom)
    combo.select(programa_texto)
    lido = combo.window_text()
    if lido.strip() != programa_texto.strip():
        raise RuntimeError(f"combo ficou em {lido!r}, esperava {programa_texto!r}")
    log.info("programa selecionado OK: %r", lido)


def selecionar_tipo(jp, tipo: str, log: logging.Logger) -> None:
    """Marca o radio do grupo 'Tipo de Projeto' (TGroupButton) do tipo pedido.

    O relatório é filtrado por Programa E Tipo; cada contrato tem o seu (a maioria
    'Eletrificação Rural', mas ex.: Piauí 8ª só tem dados em 'Fonte Alternativa').
    Como o radio persiste entre iterações (não reabrimos o app), seleciona-se SEMPRE,
    para todo contrato — senão o tipo de um vaza para o próximo.
    """
    if tipo not in config.TIPOS_PROJETO:                 # erro cedo: tipo fora dos 5 radios
        raise RuntimeError(f"tipo {tipo!r} não é um dos válidos {config.TIPOS_PROJETO}")
    radio = jp.child_window(title=tipo, class_name=config.CLASSE_RADIO_TIPO)  # radio por título
    _clicar_controle(radio, f"radio Tipo de Projeto {tipo!r}", log)  # clica + loga pixels (debug cego)
    try:                                                 # verificação best-effort (some TGroupButton expõe estado)
        if hasattr(radio, "is_selected") and not radio.is_selected():
            log.warning("radio de tipo %r pode não ter marcado — conferir no log/pixels", tipo)
        else:
            log.info("tipo de projeto selecionado OK: %r", tipo)
    except Exception:
        log.info("tipo de projeto clicado: %r (estado não verificável neste backend)", tipo)


def conferir_filtros_padrao(jp, log: logging.Logger) -> None:
    """Confere (não altera) a data início padrão; só avisa se divergir."""
    try:
        # há um TMaskEdit '01/01/2004' por aba -> found_index=0 evita ambiguidade
        data = jp.child_window(
            title=config.DATA_INICIO_PADRAO, class_name="TMaskEdit", found_index=0
        )
        if data.exists(timeout=1):
            log.info("data início padrão %r confirmada", config.DATA_INICIO_PADRAO)
        else:
            log.warning("data início padrão %r não encontrada — conferir manualmente",
                        config.DATA_INICIO_PADRAO)
    except Exception:
        log.warning("não consegui conferir a data início (seguindo)")


def _preview_pronto(textos: str) -> bool:
    """True só quando o QuickReport terminou de renderizar.

    Enquanto monta, a StatusBar mostra progresso: '0% Page 1 of 0', '50% Page 1 of 27'...
    (total ainda 0/parcial e com '%'). Pronto = sem '%' e total de páginas > 0
    (ex.: 'Page 1 of 53'). Bug da VPN 16/06: aceitávamos 'Page 1 of 0' e clicávamos cedo.
    """
    if "%" in textos:
        return False
    m = re.search(config.PREVIEW_STATUS_PRONTO_RE, textos)
    return bool(m) and int(m.group(1)) > 0


def abrir_preview(app, log: logging.Logger):
    """Clica 'Visualizar' (uia) e espera o preview ficar PRONTO. Retorna a janela win32."""
    app_uia = Application(backend="uia").connect(process=app.process)
    jp_uia = app_uia.window(class_name=config.CLASSE_JANELA_PRINCIPAL)
    botao = jp_uia.child_window(title=config.BOTAO_VISUALIZAR, control_type="Button")
    _clicar_controle(botao, f"botão {config.BOTAO_VISUALIZAR!r}", log)

    fim = time.monotonic() + config.TIMEOUT_PREVIEW
    while time.monotonic() < fim:
        prev = app.window(class_name=config.CLASSE_PREVIEW)
        if prev.exists():
            try:
                sb = prev.child_window(class_name="TStatusBar")
                textos = " ".join(sb.texts())
                if _preview_pronto(textos):
                    prev.set_focus()
                    log.info("preview PRONTO: status=%r", textos.strip())
                    return prev
                log.info("preview ainda renderizando: status=%r", textos.strip())
            except Exception:
                pass
        time.sleep(1.0)
    raise RuntimeError(f"preview não ficou pronto em {config.TIMEOUT_PREVIEW}s")


# --- CLI de smoke (validação [VPN], roteiro 2) ----------------------------

def _configurar_log():
    import sys
    from datetime import datetime
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    logging.basicConfig(
        level=logging.INFO,
        handlers=[
            logging.FileHandler(config.LOGS_DIR / f"lnc_app_{ts}.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
        format="%(asctime)s %(levelname)s %(message)s",
    )
    return logging.getLogger("lnc_app")


def _smoke():
    import argparse
    import sys
    import traceback

    p = argparse.ArgumentParser(description="Smoke: navega até o preview e para.")
    p.add_argument("--programa", required=True, help="texto EXATO do dropdown")
    p.add_argument("--tipo", default=config.TIPO_PROJETO_PADRAO,
                   help=f"radio Tipo de Projeto (default {config.TIPO_PROJETO_PADRAO!r})")
    args = p.parse_args()
    log = _configurar_log()
    log.info("=== lnc_app smoke --programa %r --tipo %r ===", args.programa, args.tipo)
    try:
        app, jp = conectar_ou_abrir(log)
        limpar_estado(app, log)
        navegar_para_painel(app, jp, log)
        selecionar_tipo(jp, args.tipo, log)
        selecionar_programa(jp, args.programa, log)
        conferir_filtros_padrao(jp, log)
        abrir_preview(app, log)
        log.info("=== SMOKE OK: preview pronto para %r ===", args.programa)
    except Exception:
        log.error("SMOKE FALHOU:\n%s", traceback.format_exc())
        try:
            import scripts.inspecionar_app as insp
            insp.dump_desktop("lnc_app_falha", log)
            insp.screenshot("lnc_app_falha", log)
        except Exception:
            log.error("auto-dump falhou:\n%s", traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    _smoke()
