"""U5 — laço completo da Fase 2: download por contrato, retomada por estado, consolidação.

Espelha src/main.py (Fase 1), mas para o pipeline de UCs via SSRS (sem UI).
Puro (testável no DEV): decidir_modo / planejar / atualizar_estado / carregar_/escrever_estado.
Rede (só na VPN): executar (laço que dirige download.baixar) e a criação da sessão SSPI.

Retomada AUTOMÁTICA por ESTADO (ucs/estado_ucs.json): rodada anterior completa => 'refresh'
(re-baixa tudo = dados frescos); incompleta => 'retomar' (só o que faltou). `--refresh` força tudo.
Estado gravado APÓS CADA contrato (robusto a Ctrl+C). Falha 3× => 'desistido'.
"""

import argparse                              # CLI
import json                                  # estado em JSON
import logging                               # log arquivo + console
import sys                                   # utf-8 no stdout / exit code
import traceback                             # tracebacks completos (execução cega)
from datetime import datetime                # timestamps do estado/log

from ucs import config, consolida, download, ssrs_client  # módulos da fase


# --- Estado (persistência) ----------------------------------------------

def carregar_estado(caminho=config.ESTADO_UCS_JSON):
    """Lê o estado da rodada anterior (ou {} se não existe).

    Por que existe: o estado dirige a auto-retomada; precisa ser lido no início e
    tolerar a 1ª rodada (arquivo ausente).

    Lógica: Entrada caminho. Fase 1 — se não existe, {}. Fase 2 — lê JSON utf-8. Saída: dict.
    """
    if not caminho.exists():                       # Fase 1: 1ª rodada => sem estado
        return {}
    with open(caminho, encoding="utf-8") as fh:    # Fase 2: lê o JSON
        return json.load(fh)                       # saída: estado


def escrever_estado(estado, caminho=config.ESTADO_UCS_JSON):
    """Grava o estado da rodada (JSON utf-8 legível).

    Por que existe: é gravado após CADA contrato; centralizar a escrita garante formato
    consistente e cria a pasta se preciso.

    Lógica: Entrada estado, caminho. Fase 1 — garante a pasta. Fase 2 — serializa. Saída: None.
    """
    caminho.parent.mkdir(parents=True, exist_ok=True)   # Fase 1: garante ucs/
    with open(caminho, "w", encoding="utf-8") as fh:    # Fase 2: escreve
        json.dump(estado, fh, ensure_ascii=False, indent=2)


# --- Lógica pura (decisão) ----------------------------------------------

def decidir_modo(estado, contratos):
    """Decide automaticamente 'refresh' ou 'retomar' lendo o estado anterior.

    Por que existe: a rodada deve atualizar dados (refresh) mas, se a anterior foi
    interrompida, retomar só o que falta — sem flag humana (igual à Fase 1).

    Lógica, do input ao output, em fases:
      Entrada: estado (dict, pode ser {}), contratos (iterável dos códigos da rodada).
      Fase 1 — sem estado => 'refresh'.
      Fase 2 — 'completa' se todo contrato está 'baixado' ou 'desistido'.
      Saída: 'refresh' (completa/1ª vez) | 'retomar' (incompleta).
    """
    por_contrato = estado.get("contratos", {})     # estado por contrato anterior
    if not por_contrato:                           # Fase 1: nunca rodou => refresh
        return "refresh"
    completa = all(                                # Fase 2: todos resolvidos?
        por_contrato.get(c, {}).get("status") in ("baixado", "desistido")
        for c in contratos
    )
    return "refresh" if completa else "retomar"    # saída: modo


def planejar(contratos, mapa, raw_dir, *, modo, estado, filtro=None):
    """Decide, por contrato, o que o laço fará (baixar ou pular) — sem tocar a rede.

    Por que existe: separa a DECISÃO (pura/testável) da AÇÃO de rede (executar). Em
    'refresh' baixa tudo; em 'retomar' pula quem já está 'baixado'/'desistido'.

    Lógica, do input ao output, em fases:
      Entrada: contratos, mapa, raw_dir, modo, estado anterior, filtro (lista ou None).
      Fase 1 — alvos = filtro, se houver; senão todos.
      Fase 2 — valida cada alvo (precisa estar no mapa; erro cedo se não).
      Fase 3 — define a ação por contrato conforme o modo/estado.
      Saída: lista de planos {contrato, codese, programa, destino, acao}.
    """
    alvos = filtro if filtro else list(contratos)  # Fase 1: subconjunto pedido ou todos
    por_contrato = estado.get("contratos", {})     # estado anterior por contrato
    planos = []                                    # acumulador (saída)
    for contrato in alvos:                          # percorre cada alvo
        if contrato not in mapa:                    # Fase 2: alvo precisa existir no mapa
            raise ValueError(f"contrato {contrato!r} não está no ucs_map.json")
        if modo == "refresh":                       # Fase 3a: refresh baixa tudo
            acao = "baixar"
        else:                                       # Fase 3b: retomar pula o resolvido
            status_ant = por_contrato.get(contrato, {}).get("status")
            acao = "pular" if status_ant in ("baixado", "desistido") else "baixar"
        planos.append({                             # registra o plano do contrato
            "contrato": contrato,                   # chave primária
            "codese": mapa[contrato]["codese"],     # valor do parâmetro 'codese'
            "programa": mapa[contrato]["programa"],  # valor do parâmetro 'programa'
            "destino": download.caminho_raw(contrato, raw_dir),  # output_ucs/raw/<c>.csv
            "acao": acao,                           # 'baixar' | 'pular'
        })
    return planos                                   # saída: plano da rodada


def atualizar_estado(estado_ant, resultados, *, max_tentativas, agora):
    """Atualiza o estado por contrato a partir dos resultados desta rodada.

    Por que existe: traduz os resultados (baixado/falha) em status persistente, contando
    tentativas e marcando 'desistido' após o limite — base da retomada. Contratos sem
    resultado nesta rodada (pulados) mantêm o estado anterior.

    Lógica, do input ao output, em fases:
      Entrada: estado_ant (dict), resultados (lista de dicts já processados), max_tentativas,
               agora (timestamp string).
      Fase 1 — parte de uma cópia do estado anterior por contrato.
      Fase 2 — aplica cada resultado: 'baixado' zera tentativas; 'falha' incrementa e vira
               'desistido' ao atingir o limite.
      Saída: novo estado {contratos: {...}}.
    """
    por_contrato = dict(estado_ant.get("contratos", {}))   # Fase 1: cópia do anterior
    for r in resultados:                           # Fase 2: aplica cada resultado
        contrato = r["contrato"]                    # contrato processado
        ant = por_contrato.get(contrato, {})        # estado anterior dele
        if r["status"] == "baixado":               # sucesso => zera tentativas
            por_contrato[contrato] = {
                "status": "baixado", "tentativas": 0,
                "n_linhas": r.get("n_linhas", 0), "erro": None, "ts": agora,
            }
        else:                                       # falha => incrementa e talvez desiste
            tentativas = ant.get("tentativas", 0) + 1   # conta esta falha
            por_contrato[contrato] = {
                "status": "desistido" if tentativas >= max_tentativas else "falha",
                "tentativas": tentativas,
                "n_linhas": ant.get("n_linhas", 0),
                "erro": r.get("erro"), "ts": agora,
            }
    return {"contratos": por_contrato}             # saída: novo estado


# --- Laço de rede (só VPN) ----------------------------------------------

def executar(planos, sessao, log, *, baixar_fn=download.baixar, persistir=None):
    """Percorre os planos baixando cada contrato; resiliente e com persistência incremental.

    Por que existe: é a única peça que toca a rede; isola o laço para testá-lo com um
    stub (baixar_fn injetável). Uma falha num contrato NÃO derruba a rodada; o estado é
    persistido após cada um (robusto a Ctrl+C/queda).

    Lógica, do input ao output, em fases:
      Entrada: planos, sessao, log, baixar_fn (injeção), persistir (callback após cada).
      Fase 1 — pula os planos 'pular' (já resolvidos no estado).
      Fase 2 — para cada 'baixar': tenta baixar; sucesso/falha vira resultado.
      Fase 3 — após cada contrato, chama persistir(resultados) p/ gravar o estado.
      Saída: lista de resultados {contrato, status, n_linhas?, erro?}.
    """
    resultados = []                                # acumulador (saída + base do persistir)
    for p in planos:                               # percorre o plano
        contrato = p["contrato"]                    # contrato atual
        if p["acao"] == "pular":                    # Fase 1: já resolvido => não toca a rede
            log.info("%s: pulado (já resolvido)", contrato)
            continue
        try:                                        # Fase 2: tenta baixar
            info = {"codese": p["codese"], "programa": p["programa"]}  # params p/ o cliente
            r = baixar_fn(sessao, contrato, info, log, destino=p["destino"])  # download real
            resultados.append(r)                    # registra sucesso
        except Exception as exc:                    # qualquer erro => falha (não derruba o laço)
            log.error("%s: FALHA\n%s", contrato, traceback.format_exc())
            resultados.append({"contrato": contrato, "status": "falha", "erro": repr(exc)})
        if persistir:                               # Fase 3: persiste o estado após cada contrato
            persistir(resultados)
    return resultados                              # saída: resultados da rodada


# --- Infra / orquestração -----------------------------------------------

def _configurar_log():
    """Configura logging para arquivo (output_ucs/logs) e console, em utf-8 (igual à Fase 1)."""
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # console aceita acento
    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)           # garante a pasta de logs
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")               # carimbo de tempo
    logging.basicConfig(
        level=logging.INFO,
        handlers=[
            logging.FileHandler(config.LOGS_DIR / f"ucs_{ts}.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
        format="%(asctime)s %(levelname)s %(message)s",
    )
    return logging.getLogger("ucs.main")


def _cli(argv):
    """Parseia os argumentos da CLI (espelha as flags da Fase 1, adaptadas à Fase 2)."""
    p = argparse.ArgumentParser(description="Pipeline Fase 2 — extração das UCs via SSRS.")
    p.add_argument("--dry-run", action="store_true", help="lista o plano e sai (sem rede)")
    p.add_argument("--contratos", default=None, help='subconjunto: "ECO 025/2021,ECO 021/2020"')
    p.add_argument("--refresh", action="store_true", help="força re-baixar todos (ignora o estado)")
    p.add_argument("--somente-consolida", action="store_true", help="não baixa; só reprocessa os brutos")
    p.add_argument("--dados-projetos", action="store_true",
                   help="inclui cod_projeto/nome_projeto na base (default: só contrato;odi;uc)")
    p.add_argument("--sqlite", action="store_true", help="também carrega ucs.db (SQLite) + benchmark")
    p.add_argument("--recon", action="store_true", help="roda a recon (U0) em vez do pipeline")
    return p.parse_args(argv)


def main(argv=None):
    """Orquestra a rodada: valida o map, planeja, baixa (com retomada) e consolida.

    Por que existe: ponto de entrada único (`python -m ucs.main`) que amarra estado,
    download e consolidação, sempre gravando estado/logs para execução cega.

    Lógica, do input ao output, em fases:
      Entrada: argv (CLI; None => sys.argv).
      Fase 1 — log + CLI; se --recon, delega à recon e sai.
      Fase 2 — carrega/valida o mapa; define o conjunto de contratos e o filtro.
      Fase 3 — se não for --somente-consolida: decide modo, planeja; --dry-run sai aqui;
               senão cria a sessão e executa o laço com persistência incremental.
      Fase 4 — consolida os brutos no CSV (e, com --sqlite, no banco + benchmark).
      Saída: código de saída do processo (0 em sucesso).
    """
    args = _cli(argv if argv is not None else sys.argv[1:])  # Fase 1: CLI
    log = _configurar_log()                        # logging
    log.info("=== Fase 2 (UCs) === args=%s", vars(args))
    if args.recon:                                 # atalho: roda a recon (U0)
        from ucs import recon                       # import tardio (recon é etapa à parte)
        return recon.main()

    mapa = download.carregar_map()                 # Fase 2: carrega o mapa
    download.validar_mapeamento(mapa)              # falha cedo se inválido
    contratos = list(mapa)                          # conjunto de trabalho = chaves do mapa
    filtro = [c.strip() for c in args.contratos.split(",")] if args.contratos else None

    if not args.somente_consolida:                 # Fase 3: etapa de download
        estado = carregar_estado()                  # estado anterior
        modo = "refresh" if args.refresh else decidir_modo(estado, contratos)  # modo
        planos = planejar(contratos, mapa, config.RAW_DIR, modo=modo, estado=estado, filtro=filtro)
        log.info("modo=%s | %d planos (%d a baixar)", modo, len(planos),
                 sum(1 for p in planos if p["acao"] == "baixar"))
        if args.dry_run:                            # --dry-run: mostra o plano e sai
            for p in planos:
                log.info("  %s -> %s (codese=%s programa=%s)",
                         p["contrato"], p["acao"], p["codese"], p["programa"])
            return 0
        sessao = ssrs_client.criar_sessao()         # sessão autenticada (SSPI)
        agora = datetime.now().isoformat(timespec="seconds")  # timestamp da rodada
        def persistir(resultados):                  # callback: grava estado após cada contrato
            escrever_estado(atualizar_estado(
                estado, resultados, max_tentativas=config.MAX_TENTATIVAS_CONTRATO, agora=agora))
        resultados = executar(planos, sessao, log, persistir=persistir)  # laço
        log.info("rodada: %d baixados, %d falhas",
                 sum(1 for r in resultados if r["status"] == "baixado"),
                 sum(1 for r in resultados if r["status"] == "falha"))

    total = consolida.consolidar_csv(               # Fase 4: base plana (com/sem dados de projeto)
        mapa, config.RAW_DIR, config.CSV_CONSOLIDADO_UCS, log, incluir_projetos=args.dados_projetos)
    if args.sqlite:                                 # opcional: banco + benchmark
        consolida.consolidar_sqlite(
            mapa, config.RAW_DIR, config.UCS_DB, log, incluir_projetos=args.dados_projetos)
        consolida.benchmark(config.CSV_CONSOLIDADO_UCS, config.UCS_DB, log)
    log.info("=== Fase 2 concluída — %d linhas em %s ===", total, config.CSV_CONSOLIDADO_UCS.name)
    return 0                                        # saída: sucesso


if __name__ == "__main__":                         # permite `python -m ucs.main`
    sys.exit(main())                               # propaga o código de saída
