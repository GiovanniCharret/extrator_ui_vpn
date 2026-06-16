"""F1 — Inspeção do Sistema LPT (roda na VPN, executado pelo usuário).

Tira um "raio-X" do estado atual do app: dump de todos os controles (backends
win32 e uia), lista de janelas do desktop e screenshot. NÃO interage com o app —
a navegação até cada tela é feita manualmente pelo usuário (ver roteiro nº 1
em TESTES.md), e o script é rodado uma vez por tela, com um nome diferente.

Uso (na raiz do projeto, com o LNC já aberto na tela desejada):
    .venv\\Scripts\\python.exe scripts\\inspecionar_app.py --nome tela_inicial

Saídas (tudo em output/):
    output/inspecao/<nome>_win32_<i>_<titulo>.txt   dump de cada janela (win32)
    output/inspecao/<nome>_uia_<i>_<titulo>.txt     dump de cada janela (uia)
    output/inspecao/<nome>_desktop.txt              todas as janelas do desktop
    output/inspecao/<nome>_tela.png                 screenshot da tela inteira
    output/logs/inspecao_<nome>_<ts>.log            log completo (com tracebacks)
"""

import argparse
import ctypes
import logging
import re
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src import config  # noqa: E402


def configurar_log(nome: str) -> logging.Logger:
    # console do Windows pode estar em cp1252 — evita mojibake nos acentos
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log = logging.getLogger("inspecao")
    log.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    for handler in (
        logging.FileHandler(config.LOGS_DIR / f"inspecao_{nome}_{ts}.log", encoding="utf-8"),
        logging.StreamHandler(),
    ):
        handler.setFormatter(fmt)
        log.addHandler(handler)
    return log


def sanitizar(texto: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", texto)[:40] or "sem_titulo"


def conectar(titulo_re: str, log, timeout: int = 15):
    """Conecta ao app pela janela de título `titulo_re`, retornando (app, pid).

    Conexão por pid, não por título: pode haver MAIS DE UMA janela casando o
    título (instância duplicada do app, formulário oculto do VB6) e
    connect(title_re=...) explode com ElementAmbiguousError nesse caso
    (visto na VPN em 12/06/2026). Enumera as candidatas visíveis, loga todas
    e usa o processo da primeira, avisando se houver mais de um.
    """
    from pywinauto import Application, findwindows

    fim = time.monotonic() + timeout
    candidatas = []
    while not candidatas:
        candidatas = findwindows.find_elements(title_re=titulo_re, backend="win32")
        if not candidatas and time.monotonic() > fim:
            raise RuntimeError(f"nenhuma janela visível casou {titulo_re!r} em {timeout}s")
        if not candidatas:
            time.sleep(0.5)

    for c in candidatas:
        log.info(
            "janela candidata: pid=%s handle=0x%X classe=%r titulo=%r",
            c.process_id, c.handle, c.class_name, c.name,
        )
    pids = list(dict.fromkeys(c.process_id for c in candidatas))
    if len(pids) > 1:
        log.warning(
            "%d processos diferentes com janela casando %r (pids %s) — provável "
            "instância duplicada do app; usando o primeiro. Se o dump vier "
            "estranho, feche as instâncias extras e rode de novo.",
            len(pids), titulo_re, pids,
        )
    pid = pids[0]
    return Application(backend="win32").connect(process=pid), pid


def dump_janelas(app, backend: str, nome: str, log) -> int:
    """Dump de print_control_identifiers de cada janela top-level do processo."""
    quantos = 0
    for i, jan in enumerate(app.windows()):
        titulo = "?"
        try:
            titulo = jan.window_text()
            destino = config.INSPECAO_DIR / f"{nome}_{backend}_{i}_{sanitizar(titulo)}.txt"
            # print_control_identifiers existe em WindowSpecification, nao nos
            # wrappers de app.windows() — re-embrulha pelo handle
            app.window(handle=jan.handle).print_control_identifiers(filename=str(destino))
            log.info("[%s] janela %d %r -> %s", backend, i, titulo, destino.name)
            quantos += 1
        except Exception:
            log.error("[%s] falha no dump da janela %d %r:\n%s", backend, i, titulo, traceback.format_exc())
    return quantos


def dump_desktop(nome: str, log) -> None:
    """Lista todas as janelas top-level do desktop (acha diálogos de outros donos)."""
    from pywinauto import Desktop

    linhas = []
    for jan in Desktop(backend="win32").windows():
        try:
            if jan.is_visible():
                linhas.append(
                    f"pid={jan.process_id():<8} class={jan.class_name():<30} title={jan.window_text()!r}"
                )
        except Exception:
            pass
    destino = config.INSPECAO_DIR / f"{nome}_desktop.txt"
    destino.write_text("\n".join(linhas), encoding="utf-8")
    log.info("desktop: %d janelas visíveis -> %s", len(linhas), destino.name)


def screenshot(nome: str, log) -> None:
    import pyautogui

    destino = config.INSPECAO_DIR / f"{nome}_tela.png"
    pyautogui.screenshot(str(destino))
    log.info("screenshot -> %s", destino.name)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nome", required=True, help="rótulo desta tela (ex: tela_inicial, preview)")
    parser.add_argument(
        "--espera", type=int, default=0,
        help="segundos de espera antes de capturar (tempo para arrumar a tela e tirar as mãos)",
    )
    args = parser.parse_args()
    nome = sanitizar(args.nome)

    log = configurar_log(nome)
    config.INSPECAO_DIR.mkdir(parents=True, exist_ok=True)
    log.info("=== inspecionar_app --nome %s ===", nome)
    if args.espera:
        log.info("esperando %ds (arrume a tela e não toque em nada)...", args.espera)
        time.sleep(args.espera)

    # Screenshot ANTES dos dumps: captura o estado real da tela antes de
    # qualquer efeito colateral da enumeração (ex.: preview indo para trás)
    try:
        screenshot(nome, log)
    except Exception:
        log.error("screenshot falhou:\n%s", traceback.format_exc())

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        log.warning("SetProcessDpiAwareness indisponível (seguindo sem)")

    from pywinauto import Application

    # Conecta ao LNC já aberto (a abertura é manual — ver roteiro)
    try:
        app32, pid = conectar(config.TITULO_JANELA_PRINCIPAL_RE, log)
        log.info("conectado ao LNC (pid=%s)", pid)
    except Exception:
        log.error(
            "Não consegui conectar à janela %r. Abra o %s manualmente e rode de novo.\n%s",
            config.TITULO_JANELA_PRINCIPAL_RE,
            config.LNC_EXE,
            traceback.format_exc(),
        )
        return 1

    sucesso = 0
    sucesso += dump_janelas(app32, "win32", nome, log)

    try:
        app_uia = Application(backend="uia").connect(process=pid, timeout=5)
        sucesso += dump_janelas(app_uia, "uia", nome, log)
    except Exception:
        log.error("backend uia falhou:\n%s", traceback.format_exc())

    try:
        dump_desktop(nome, log)
    except Exception:
        log.error("dump do desktop falhou:\n%s", traceback.format_exc())

    if sucesso == 0:
        log.error("=== FIM: NENHUM dump de janela gerado — veja erros acima ===")
        return 1
    log.info("=== FIM OK: %d dumps de janela gerados em output/inspecao/ ===", sucesso)
    return 0


if __name__ == "__main__":
    sys.exit(main())
