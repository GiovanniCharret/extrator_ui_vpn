"""F3 — exporta UM PDF do preview de Projetos Executados (Microsoft Print to PDF).

Parte do preview pronto (via lnc_app) e dirige: imprimir (coord) -> "Salvar Saída
de Impressão como" -> caminho absoluto -> geração -> arquivo estável.

EXECUÇÃO CEGA: cada ação loga qual controle/opção aciona e a posição em pixels
(ver lnc_app._clicar_*). Sinal de término = PDF com tamanho estável, não a ordem
das janelas (que a 1ª viagem confirma).
"""

import logging
import time

from pywinauto import Application  # noqa: F401  (mantido p/ paridade de backend, uso futuro)

from src import config, contratos, lnc_app


def caminho_saida(programa_texto: str):
    """output/pdf/<nome_sanitizado>.pdf (absoluto)."""
    config.PDF_DIR.mkdir(parents=True, exist_ok=True)
    return config.PDF_DIR / f"{contratos.sanitizar_nome(programa_texto)}.pdf"


def _esperar_arquivo_estavel(caminho, log: logging.Logger, timeout: int) -> None:
    """Arquivo existe e com 2 leituras de tamanho iguais (spooler fecha antes de gravar)."""
    fim = time.monotonic() + timeout
    anterior = -1
    while time.monotonic() < fim:
        if caminho.exists():
            atual = caminho.stat().st_size
            if atual > 0 and atual == anterior:
                log.info("PDF estável: %d bytes -> %s", atual, caminho)
                return
            anterior = atual
        time.sleep(config.ARQUIVO_ESTAVEL_INTERVALO)
    raise RuntimeError(f"PDF não estabilizou em {timeout}s: {caminho}")


def exportar(programa_texto: str, log: logging.Logger, destino=None):
    """Fluxo completo: navega -> preview -> imprimir -> salvar -> geração -> arquivo estável."""
    destino = destino or caminho_saida(programa_texto)
    if destino.exists():
        log.info("apagando PDF antigo (evita diálogo de sobrescrita): %s", destino)
        destino.unlink()

    app, jp = lnc_app.conectar_ou_abrir(log)
    lnc_app.limpar_estado(app, log)
    lnc_app.navegar_para_painel(app, jp, log)
    lnc_app.selecionar_programa(jp, programa_texto, log)
    lnc_app.conferir_filtros_padrao(jp, log)
    preview = lnc_app.abrir_preview(app, log)

    # botão imprimir: sem HWND -> clique por coordenada (centro do Button9; tooltip 'Print')
    preview.set_focus()
    lnc_app._clicar_xy(preview, config.PREVIEW_BTN_IMPRIMIR_XY,
                       "botão imprimir da toolbar do preview", log)

    # diálogo de salvar do "Microsoft Print to PDF" (título real != "Salvar como").
    # A renderização das ~53 págs precede o diálogo => TIMEOUT_GERACAO.
    log.info("aguardando diálogo %r (#32770)...", config.TITULO_SALVAR_COMO)
    salvar = app.window(title=config.TITULO_SALVAR_COMO, class_name=config.CLASSE_SALVAR_COMO)
    salvar.wait("exists ready", timeout=config.TIMEOUT_GERACAO)
    edit = salvar.child_window(class_name=config.SALVAR_COMO_EDIT_NOME)
    log.info("digitando caminho no campo nome: %s", destino)
    edit.set_edit_text(str(destino))
    botao = salvar.child_window(title=config.SALVAR_COMO_BOTAO, class_name="Button")
    lnc_app._clicar_controle(botao, f"botão {config.SALVAR_COMO_BOTAO!r}", log)

    # diálogo intermitente de sobrescrita (deletamos antes; defesa)
    conf = app.window(title=config.TITULO_CONFIRMA_SOBRESCRITA)
    if conf.exists(timeout=config.TIMEOUT_SOBRESCRITA):
        botao_sim = conf.child_window(title="&Sim", class_name="Button")
        lnc_app._clicar_controle(botao_sim, "botão 'Sim' (sobrescrita)", log)

    # geração: arquivo estável (sinal de verdade) + progresso sumir
    _esperar_arquivo_estavel(destino, log, config.TIMEOUT_GERACAO)
    prog = app.window(class_name=config.CLASSE_PROGRESSO)
    if prog.exists():
        log.info("aguardando 'Printing progress' sumir...")
        prog.wait_not("exists", timeout=config.TIMEOUT_PROGRESSO)

    lnc_app.limpar_estado(app, log)
    log.info("=== EXPORTOU: %s ===", destino)
    return destino


def _cli():
    import argparse
    import sys
    import traceback
    from pathlib import Path

    p = argparse.ArgumentParser(description="Exporta 1 PDF de um programa.")
    p.add_argument("--programa", required=True, help="texto EXATO do dropdown")
    p.add_argument("--saida", default=None, help="caminho do PDF (default: output/pdf/<nome>.pdf)")
    args = p.parse_args()
    log = lnc_app._configurar_log()
    log.info("=== exportar_pdf --programa %r ===", args.programa)
    try:
        exportar(args.programa, log, Path(args.saida) if args.saida else None)
    except Exception:
        log.error("EXPORT FALHOU:\n%s", traceback.format_exc())
        try:
            import scripts.inspecionar_app as insp
            insp.dump_desktop("exportar_falha", log)
            insp.screenshot("exportar_falha", log)
        except Exception:
            log.error("auto-dump falhou:\n%s", traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    _cli()
