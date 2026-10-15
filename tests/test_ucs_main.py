"""U5 [AUTO] — partes puras do ucs/main.py: estado/modo, planejar, atualizar_estado, executar.

Offline. O laço (executar) usa um stub de baixar_fn (sem rede). Espelha o test_f5 da Fase 1.
"""

import logging
import sys
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from ucs import main

CONTRATOS = ["ECO 025/2021", "ECO 021/2020"]
MAPA = {"ECO 025/2021": {"codese": "20", "programa": "1520"},
        "ECO 021/2020": {"codese": "156", "programa": "1531"}}
LOG = logging.getLogger("test")
RAW = Path("/raw")


def _estado(d):
    return {"contratos": {c: {"status": s, "tentativas": t} for c, (s, t) in d.items()}}


# --- decidir_modo -----------------------------------------------------------

def test_modo_vazio_e_refresh():
    assert main.decidir_modo({}, CONTRATOS) == "refresh"


def test_modo_tudo_resolvido_e_refresh():
    est = _estado({"ECO 025/2021": ("baixado", 0), "ECO 021/2020": ("desistido", 3)})
    assert main.decidir_modo(est, CONTRATOS) == "refresh"


def test_modo_incompleto_e_retomar():
    est = _estado({"ECO 025/2021": ("baixado", 0), "ECO 021/2020": ("falha", 1)})
    assert main.decidir_modo(est, CONTRATOS) == "retomar"


# --- planejar ---------------------------------------------------------------

def test_planejar_refresh_baixa_tudo():
    planos = main.planejar(CONTRATOS, MAPA, RAW, modo="refresh", estado={})
    assert [p["acao"] for p in planos] == ["baixar", "baixar"]
    assert planos[0]["codese"] == "20" and planos[0]["programa"] == "1520"


def test_planejar_retomar_pula_resolvidos():
    est = _estado({"ECO 025/2021": ("baixado", 0), "ECO 021/2020": ("falha", 1)})
    planos = main.planejar(CONTRATOS, MAPA, RAW, modo="retomar", estado=est)
    acoes = {p["contrato"]: p["acao"] for p in planos}
    assert acoes["ECO 025/2021"] == "pular"   # já baixado
    assert acoes["ECO 021/2020"] == "baixar"  # falha tentável


def test_planejar_filtro_e_contrato_invalido():
    planos = main.planejar(CONTRATOS, MAPA, RAW, modo="refresh", estado={}, filtro=["ECO 025/2021"])
    assert [p["contrato"] for p in planos] == ["ECO 025/2021"]
    with pytest.raises(ValueError):
        main.planejar(CONTRATOS, MAPA, RAW, modo="refresh", estado={}, filtro=["XPTO"])


# --- atualizar_estado -------------------------------------------------------

def test_atualizar_estado_baixado_zera_tentativas():
    res = [{"contrato": "ECO 025/2021", "status": "baixado", "n_linhas": 10}]
    novo = main.atualizar_estado({}, res, max_tentativas=3, agora="t")
    assert novo["contratos"]["ECO 025/2021"]["status"] == "baixado"
    assert novo["contratos"]["ECO 025/2021"]["tentativas"] == 0


def test_atualizar_estado_falha_incrementa_e_desiste():
    ant = _estado({"ECO 021/2020": ("falha", 2)})
    res = [{"contrato": "ECO 021/2020", "status": "falha", "erro": "x"}]
    novo = main.atualizar_estado(ant, res, max_tentativas=3, agora="t")
    # 2 + 1 = 3 => atinge o limite => desistido
    assert novo["contratos"]["ECO 021/2020"]["status"] == "desistido"
    assert novo["contratos"]["ECO 021/2020"]["tentativas"] == 3


def test_atualizar_estado_preserva_pulados():
    ant = _estado({"ECO 025/2021": ("baixado", 0)})
    novo = main.atualizar_estado(ant, [], max_tentativas=3, agora="t")
    assert novo["contratos"]["ECO 025/2021"]["status"] == "baixado"


# --- executar (laço com stub) -----------------------------------------------

def test_executar_pula_e_baixa_e_persiste():
    planos = [
        {"contrato": "ECO 025/2021", "codese": "20", "programa": "1520",
         "destino": Path("/x/a.csv"), "acao": "pular"},
        {"contrato": "ECO 021/2020", "codese": "156", "programa": "1531",
         "destino": Path("/x/b.csv"), "acao": "baixar"},
    ]
    chamadas = []

    def fake_baixar(sessao, contrato, info, log, *, destino=None):
        chamadas.append((contrato, info["codese"], info["programa"]))
        return {"contrato": contrato, "status": "baixado", "n_linhas": 5}

    persistidos = []
    res = main.executar(planos, sessao=None, log=LOG,
                        baixar_fn=fake_baixar, persistir=lambda r: persistidos.append(len(r)))
    # só o 'baixar' chamou a função; o 'pular' não tocou a rede
    assert chamadas == [("ECO 021/2020", "156", "1531")]
    assert [r["status"] for r in res] == ["baixado"]
    assert persistidos == [1]  # persistiu uma vez (após o contrato baixado)


def test_executar_falha_nao_derruba_laco():
    planos = [{"contrato": "ECO 025/2021", "codese": "20", "programa": "1520",
               "destino": Path("/x/a.csv"), "acao": "baixar"}]

    def fake_baixar(*a, **k):
        raise RuntimeError("boom")

    res = main.executar(planos, sessao=None, log=LOG, baixar_fn=fake_baixar)
    assert res[0]["status"] == "falha" and "boom" in res[0]["erro"]
