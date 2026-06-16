"""F1 [AUTO] — valida o dump de controles do inspecionar_app contra uma janela real.

Reproduz o bug visto na VPN em 12/06/2026 (`AttributeError: 'DialogWrapper' object
has no attribute 'print_control_identifiers'` — wrappers de app.windows() não têm
esse método; só WindowSpecification tem). O teste abre uma janela Tk local e exige
que dump_janelas gere >=1 arquivo não vazio — roda em qualquer máquina com desktop,
sem depender do LNC.
"""

import logging
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

TITULO = "TESTE_INSPECAO_F1"
TK_CODE = (
    "import tkinter as tk\n"
    f"r = tk.Tk(); r.title('{TITULO}')\n"
    "r.after(30000, r.destroy)\n"
    "r.mainloop()\n"
)


def test_conectar_com_titulo_duplicado():
    """Reproduz o ElementAmbiguousError da VPN (12/06/2026, bug_fix/tela_inicial_crash.jpg):
    com DUAS janelas casando o título (instância duplicada do LNC), a conexão deve
    escolher uma pelo pid em vez de explodir."""
    import logging

    from scripts import inspecionar_app

    titulo_dup = "TESTE_INSPECAO_F1_DUP"
    codigo = TK_CODE.replace(TITULO, titulo_dup)
    proc_a = subprocess.Popen([sys.executable, "-c", codigo])
    proc_b = subprocess.Popen([sys.executable, "-c", codigo])
    try:
        # nota: nao da para comparar com proc_a.pid/proc_b.pid — o python.exe de
        # venv no Windows e um launcher que dispara o interpretador como filho
        app, pid = inspecionar_app.conectar(f"{titulo_dup}.*", logging.getLogger("teste_dup"))
        titulos = [w.window_text() for w in app.windows()]
        assert any(titulo_dup in t for t in titulos), (
            f"conectou (pid={pid}) mas o processo nao tem a janela esperada: {titulos}"
        )
    finally:
        proc_a.terminate()
        proc_b.terminate()


def test_dump_janelas_gera_arquivo_nao_vazio(tmp_path, monkeypatch):
    from pywinauto import Application

    from scripts import inspecionar_app
    from src import config

    monkeypatch.setattr(config, "INSPECAO_DIR", tmp_path)

    janela_tk = subprocess.Popen([sys.executable, "-c", TK_CODE])
    try:
        app = Application(backend="win32").connect(title=TITULO, timeout=15)
        log = logging.getLogger("teste_inspecao")
        quantos = inspecionar_app.dump_janelas(app, "win32", "teste", log)

        assert quantos >= 1, "nenhum dump gerado (bug da VPN de 12/06/2026)"
        arquivos = list(tmp_path.glob("teste_win32_*.txt"))
        assert arquivos, "dump nao gravou arquivo em INSPECAO_DIR"
        assert arquivos[0].stat().st_size > 0, "arquivo de dump vazio"
    finally:
        janela_tk.terminate()
