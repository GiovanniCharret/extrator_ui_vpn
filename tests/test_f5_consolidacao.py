"""F5 [AUTO] — partes puras do main.py: estado/modo, planejar, consolidar, executar.

Offline no DEV. Só há fixtures PDF reais; os testes de consolidação replicam uma
fixture sob nomes-de-contrato em tmp_path para exercitar o encanamento (laço,
agrupamento, CSV). A corretude dos dados dos 21 contratos é validação [VPN].
"""

import logging
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

VIGENTES = {"ECO 019/2020": {}, "ECO 021/2020": {}}
MAPA = {"ECO 019/2020": {"programa": "AES SUL - 2ª Tranche", "tipo": "Eletrificação Rural"},
        "ECO 021/2020": {"programa": "CELPA 7ª TRANCHE REVISÃO 3", "tipo": "Fonte Alternativa"}}


def _estado(contratos_status):
    """Monta um estado mínimo {contratos: {c: {status, tentativas}}}."""
    return {"contratos": {c: {"status": s, "tentativas": t}
                          for c, (s, t) in contratos_status.items()}}


# --- decidir_modo -----------------------------------------------------------

def test_decidir_modo_vazio_e_refresh():
    from src import main
    assert main.decidir_modo({}, VIGENTES) == "refresh"


def test_decidir_modo_tudo_exportado_e_refresh():
    from src import main
    est = _estado({"ECO 019/2020": ("exportado", 0), "ECO 021/2020": ("exportado", 0)})
    assert main.decidir_modo(est, VIGENTES) == "refresh"


def test_decidir_modo_exportado_e_desistido_e_refresh():
    from src import main
    est = _estado({"ECO 019/2020": ("exportado", 0), "ECO 021/2020": ("desistido", 3)})
    assert main.decidir_modo(est, VIGENTES) == "refresh"


def test_decidir_modo_com_falha_e_retomar():
    from src import main
    est = _estado({"ECO 019/2020": ("exportado", 0), "ECO 021/2020": ("falha", 1)})
    assert main.decidir_modo(est, VIGENTES) == "retomar"


# --- planejar (por modo) ----------------------------------------------------

def test_planejar_refresh_exporta_todos(tmp_path):
    from src import main
    (tmp_path / "ECO_019_2020.pdf").write_bytes(b"%PDF-")  # PDF antigo presente
    est = _estado({"ECO 019/2020": ("exportado", 0)})
    planos = main.planejar(VIGENTES, MAPA, tmp_path, modo="refresh", estado=est)
    assert all(p["acao"] == "exportar" for p in planos)  # refresh ignora estado/PDF


def test_planejar_retomar_pula_exportado_e_desistido(tmp_path):
    from src import main
    est = _estado({"ECO 019/2020": ("exportado", 0), "ECO 021/2020": ("falha", 1)})
    planos = main.planejar(VIGENTES, MAPA, tmp_path, modo="retomar", estado=est)
    por = {p["contrato"]: p["acao"] for p in planos}
    assert por["ECO 019/2020"] == "pular"     # já exportado
    assert por["ECO 021/2020"] == "exportar"  # falha tentável


def test_planejar_retomar_exporta_nunca_tentado(tmp_path):
    from src import main
    est = _estado({"ECO 019/2020": ("exportado", 0)})  # ECO 021 nunca visto
    planos = main.planejar(VIGENTES, MAPA, tmp_path, modo="retomar", estado=est)
    por = {p["contrato"]: p["acao"] for p in planos}
    assert por["ECO 021/2020"] == "exportar"


def test_planejar_carrega_tipo_do_map(tmp_path):
    from src import main
    planos = main.planejar(VIGENTES, MAPA, tmp_path, modo="refresh", estado={})
    por = {p["contrato"]: p["tipo"] for p in planos}
    assert por["ECO 019/2020"] == "Eletrificação Rural"
    assert por["ECO 021/2020"] == "Fonte Alternativa"


def test_planejar_filtro_e_erro_fora_vigentes(tmp_path):
    import pytest

    from src import main
    planos = main.planejar(VIGENTES, MAPA, tmp_path, modo="refresh", estado={},
                           filtro=["ECO 021/2020"])
    assert [p["contrato"] for p in planos] == ["ECO 021/2020"]
    with pytest.raises(ValueError):
        main.planejar(VIGENTES, MAPA, tmp_path, modo="refresh", estado={},
                      filtro=["ECM 999/2099"])


# --- atualizar_estado -------------------------------------------------------

def _res(contrato, status, erro=""):
    return {"contrato": contrato, "programa": MAPA[contrato]["programa"],
            "status": status, "erro": erro}


def test_atualizar_estado_sucesso_zera_tentativas_e_marca_ok():
    from src import main
    resultados = [_res("ECO 019/2020", "exportado")]
    rows = [("ECO 019/2020", "1", "RS", "X"), ("ECO 019/2020", "2", "RS", "Y")]
    novo = main.atualizar_estado({}, {"ECO 019/2020": {}}, MAPA, resultados, rows,
                                 modo="refresh", max_tentativas=3, agora="2026-06-17T10:00:00")
    c = novo["contratos"]["ECO 019/2020"]
    assert c["status"] == "exportado" and c["tentativas"] == 0
    assert c["linhas"] == 2 and c["ultimo_ok"] == "2026-06-17T10:00:00"


def test_atualizar_estado_falha_incrementa_tentativas():
    from src import main
    ant = _estado({"ECO 021/2020": ("falha", 1)})
    resultados = [_res("ECO 021/2020", "falha", "timeout")]
    novo = main.atualizar_estado(ant, {"ECO 021/2020": {}}, MAPA, resultados, [],
                                 modo="retomar", max_tentativas=3, agora="t")
    c = novo["contratos"]["ECO 021/2020"]
    assert c["status"] == "falha" and c["tentativas"] == 2  # 1 -> 2


def test_atualizar_estado_falha_atinge_max_vira_desistido():
    from src import main
    ant = _estado({"ECO 021/2020": ("falha", 2)})
    resultados = [_res("ECO 021/2020", "falha", "timeout")]
    novo = main.atualizar_estado(ant, {"ECO 021/2020": {}}, MAPA, resultados, [],
                                 modo="retomar", max_tentativas=3, agora="t")
    assert novo["contratos"]["ECO 021/2020"]["status"] == "desistido"  # 2+1 >= 3


def test_atualizar_estado_refresh_zera_contador_antes_de_falhar():
    from src import main
    ant = _estado({"ECO 021/2020": ("desistido", 5)})  # vinha desistido
    resultados = [_res("ECO 021/2020", "falha", "x")]
    novo = main.atualizar_estado(ant, {"ECO 021/2020": {}}, MAPA, resultados, [],
                                 modo="refresh", max_tentativas=3, agora="t")
    assert novo["contratos"]["ECO 021/2020"]["tentativas"] == 1  # refresh reiniciou em 0 -> 1


def test_atualizar_estado_pulado_carrega_status_anterior():
    from src import main
    ant = _estado({"ECO 019/2020": ("exportado", 0)})
    resultados = [{"contrato": "ECO 019/2020", "programa": "p", "status": "pulado", "erro": ""}]
    rows = [("ECO 019/2020", "1", "RS", "X")]
    novo = main.atualizar_estado(ant, {"ECO 019/2020": {}}, MAPA, resultados, rows,
                                 modo="retomar", max_tentativas=3, agora="t")
    c = novo["contratos"]["ECO 019/2020"]
    assert c["status"] == "exportado"  # pulado mantém o status anterior
    assert c["linhas"] == 1            # mas atualiza as linhas da consolidação


# --- round-trip do estado ---------------------------------------------------

def test_escrever_e_carregar_estado(tmp_path):
    from src import main
    caminho = tmp_path / "estado.json"
    est = {"modo": "refresh", "contratos": {"ECO 019/2020": {"status": "exportado",
           "tentativas": 0, "linhas": 5, "erro": "", "ultimo_ok": "t", "programa": "Boa Vista"}}}
    main.escrever_estado(est, caminho)
    txt = caminho.read_text(encoding="utf-8")
    assert "Boa Vista" in txt                      # legível, sem escapar acentos
    assert main.carregar_estado(caminho) == est    # round-trip


def test_carregar_estado_inexistente_e_vazio(tmp_path):
    from src import main
    assert main.carregar_estado(tmp_path / "nao_existe.json") == {}


# --- consolidar + escrever_consolidado --------------------------------------

def _replicar_fixture(tmp_path, contratos_nomes):
    from src import config, contratos as c

    src_pdf = (config.FIXTURES_DIR / "exemplo_projetos_executados.pdf").read_bytes()
    for nome in contratos_nomes:
        (tmp_path / f"{c.sanitizar_nome(nome)}.pdf").write_bytes(src_pdf)


def _fakes_de_pdf(tmp_path, contratos_nomes, linhas_fake):
    from src import contratos as c

    for nome in contratos_nomes:
        (tmp_path / f"{c.sanitizar_nome(nome)}.pdf").write_bytes(b"%PDF-")
    return lambda _caminho: list(linhas_fake)


def test_consolidar_prefixa_contrato_e_agrupa(tmp_path, monkeypatch):
    from src import main

    fake = _fakes_de_pdf(tmp_path, ["ECO 019/2020", "ECO 021/2020"],
                         [("1", "RS", "X"), ("2", "RS", "Y")])
    monkeypatch.setattr(main.parse_pdf, "extrair_linhas", fake)
    rows = main.consolidar(VIGENTES, MAPA, tmp_path, logging.getLogger("t"))
    assert len(rows) == 4
    assert {r[0] for r in rows} == {"ECO 019/2020", "ECO 021/2020"}
    assert ("ECO 019/2020", "1", "RS", "X") in rows


def test_consolidar_spot_check_fixture_real(tmp_path):
    from src import main

    _replicar_fixture(tmp_path, ["ECO 019/2020"])
    rows = main.consolidar({"ECO 019/2020": {}}, MAPA, tmp_path, logging.getLogger("t"))
    assert rows[0] == ("ECO 019/2020", "10010263", "RS", "LAGOAO")
    assert len(rows) > 50


def test_consolidar_pula_contrato_sem_pdf(tmp_path, monkeypatch):
    from src import main

    fake = _fakes_de_pdf(tmp_path, ["ECO 019/2020"], [("1", "RS", "X")])
    monkeypatch.setattr(main.parse_pdf, "extrair_linhas", fake)
    rows = main.consolidar(VIGENTES, MAPA, tmp_path, logging.getLogger("t"))
    assert {r[0] for r in rows} == {"ECO 019/2020"}


def test_escrever_consolidado_formato(tmp_path):
    from src import config, main

    caminho = tmp_path / "consolidado.csv"
    main.escrever_consolidado([("ECO 019/2020", "10010263", "RS", "LAGOAO")], caminho)
    txt = caminho.read_text(encoding=config.CSV_ENCODING)
    assert txt.splitlines()[0] == "contrato;odi;uf;municipio"
    assert "ECO 019/2020;10010263;RS;LAGOAO" in txt


# --- executar (laço de UI; exportar_fn injetável) ---------------------------

def _plano(contrato, acao, destino=None, tipo="Eletrificação Rural"):
    return {"contrato": contrato, "programa": f"prog {contrato}", "tipo": tipo,
            "destino": destino, "acao": acao}


def test_executar_pula_e_exporta_registrando_status(tmp_path):
    from src import main

    planos = [_plano("A", "pular", tmp_path / "A.pdf"),
              _plano("B", "exportar", tmp_path / "B.pdf", tipo="Fonte Alternativa")]
    chamadas = []
    def fake_export(programa, contrato, tipo, log, destino=None):
        chamadas.append((contrato, tipo))
    res = main.executar(planos, logging.getLogger("t"), exportar_fn=fake_export)
    por = {r["contrato"]: r for r in res}
    assert por["A"]["status"] == "pulado" and all(c[0] != "A" for c in chamadas)
    assert por["B"]["status"] == "exportado"
    assert chamadas == [("B", "Fonte Alternativa")]  # tipo repassado ao exportar


def test_executar_faz_um_retry_e_continua():
    from src import main

    estado = {"n": 0}
    def flaky(programa, contrato, tipo, log, destino=None):
        estado["n"] += 1
        if estado["n"] == 1:
            raise RuntimeError("falha transitória")
    res = main.executar([_plano("B", "exportar")], logging.getLogger("t"), exportar_fn=flaky)
    assert estado["n"] == 2
    assert res[0]["status"] == "exportado"


def test_executar_persiste_apos_cada_contrato():
    from src import main

    planos = [_plano("A", "exportar"), _plano("B", "pular"), _plano("C", "exportar")]
    snapshots = []
    def fake_export(programa, contrato, tipo, log, destino=None):
        pass
    def persistir(resultados):  # chamado após CADA contrato, com o acumulado
        snapshots.append([r["contrato"] for r in resultados])
    main.executar(planos, logging.getLogger("t"), exportar_fn=fake_export, persistir=persistir)
    assert snapshots == [["A"], ["A", "B"], ["A", "B", "C"]]  # estado salvo a cada passo


def test_executar_falha_apos_retry_e_segue_o_laco():
    from src import main

    def sempre_falha(programa, contrato, tipo, log, destino=None):
        raise RuntimeError("LNC travou")
    planos = [_plano("B", "exportar"), _plano("C", "exportar")]
    res = main.executar(planos, logging.getLogger("t"), exportar_fn=sempre_falha)
    por = {r["contrato"]: r for r in res}
    assert por["B"]["status"] == "falha" and "LNC travou" in por["B"]["erro"]
    assert por["C"]["status"] == "falha"


# --- _carregar_validado (falha cedo) ----------------------------------------

def test_carregar_validado_aborta_se_map_invalido(tmp_path, monkeypatch):
    import pytest

    from src import config, contratos, main
    monkeypatch.setattr(contratos, "carregar_vigentes", lambda: {"ECO 019/2020": {}})
    dropdown = tmp_path / "dropdown.json"
    dropdown.write_text('["AES SUL - 2ª Tranche"]', encoding="utf-8")
    monkeypatch.setattr(config, "PROGRAMAS_DROPDOWN", dropdown)
    mapa = tmp_path / "map.json"
    mapa.write_text('{"ECO 019/2020": {"programa": ""}}', encoding="utf-8")
    monkeypatch.setattr(config, "PROGRAMAS_MAP", mapa)
    with pytest.raises(SystemExit):
        main._carregar_validado(logging.getLogger("t"))


def test_carregar_validado_ok_com_arquivos_reais():
    from src import main

    vigentes, mapa = main._carregar_validado(logging.getLogger("t"))
    assert len(vigentes) > 0
    assert all(c in mapa for c in vigentes)
