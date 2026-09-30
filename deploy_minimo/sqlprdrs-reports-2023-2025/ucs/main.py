"""U5 — laço da extração ÚNICA 2023-2025: resolve programas, baixa por contrato, consolida.

Cópia mínima de sqlprdrs-reports/ucs/main.py. Diferenças: os contratos do ucs_map sem
código de 'programa' têm o código RESOLVIDO na VPN pelo dropdown do SSRS (resolver_programas,
casando o programa_label); sem --recon/--sqlite/--dados-projetos.
Puro (testável no DEV): casar_programa / decidir_modo / planejar / atualizar_estado.
Rede (só na VPN): resolver_programas, executar (laço que dirige download.baixar), sessão SSPI.

Retomada AUTOMÁTICA por ESTADO (ucs/estado_ucs.json): rodada anterior completa => 'refresh'
(re-baixa tudo = dados frescos); incompleta => 'retomar' (só o que faltou). `--refresh` força tudo.
Estado gravado APÓS CADA contrato (robusto a Ctrl+C). Falha 3× => 'desistido'.
"""

import argparse                              # CLI
import difflib                               # similaridade de nomes de programa
import json                                  # estado/auditoria em JSON
import logging                               # log arquivo + console
import re                                    # nº da tranche no nome do programa
import sys                                   # utf-8 no stdout / exit code
import traceback                             # tracebacks completos (execução cega)
import unicodedata                           # remoção de acentos na comparação de nomes
from datetime import datetime                # timestamps do estado/log

from ucs import config, consolida, download, municipios, ssrs_client  # módulos da fase


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


# --- Resolução de programas (contratos sem código no ucs_map) ------------

def _normalizar(texto):
    """Normaliza um nome de programa p/ comparação (sem acento, ª/º, caixa e espaços extras).

    Por que existe: o nome da lista 2023-2025 (= LNC) e o rótulo do dropdown SSRS diferem
    em caixa/acento ("Boa Vista Energia" × "BOA VISTA ENERGIA"); comparar cru falharia.

    Lógica: Entrada texto. Fase 1 — tira ª/º. Fase 2 — decompõe e descarta acentos.
    Fase 3 — maiúsculas e espaços colapsados. Saída: string normalizada.
    """
    texto = texto.replace("ª", "").replace("º", "")    # Fase 1: "9ª"/"9º" -> "9"
    texto = unicodedata.normalize("NFKD", texto)        # Fase 2: separa letra de acento
    texto = texto.encode("ascii", "ignore").decode()    # ...e descarta o acento
    return " ".join(texto.upper().split())              # Fase 3/saída: caixa + espaços


def _tranche(texto_normalizado):
    """Extrai o número da tranche ("CEMAR 11 TRANCHE ..." -> "11"), ou None.

    Por que existe: dois programas da mesma concessionária diferem às vezes SÓ no número
    da tranche (CEMAR 10ª × 11ª) e ficam muito parecidos p/ o difflib; exigir o mesmo
    número impede casar a tranche errada por aproximação.

    Lógica: Entrada nome normalizado. Fase 1 — busca "<n> TRANCHE". Saída: "<n>" ou None.
    """
    m = re.search(r"(\d+)\s*TRANCHE", texto_normalizado)   # Fase 1: número antes de TRANCHE
    return m.group(1) if m else None                       # saída


def casar_programa(alvo, opcoes, *, excluir=(), minimo=config.SIMILARIDADE_MIN_PROGRAMA):
    """Escolhe, no dropdown de programas, o que corresponde ao nome alvo (ou None).

    Por que existe: 7 contratos da extração 2023-2025 não têm o código de programa no
    ucs_map; o código só existe no SSRS da VPN. Casar pelo nome, com regra estrita e
    pura (testável no DEV), evita uma viagem extra de recon.

    Lógica, do input ao output, em fases:
      Entrada: alvo (programa_label), opcoes [(rótulo, código)], excluir (códigos já
               usados por outros contratos), minimo (similaridade p/ aproximação).
      Fase 1 — descarta opções excluídas; normaliza alvo e rótulos.
      Fase 2 — nome exato (normalizado): aceita se houver exatamente 1.
      Fase 3 — senão, aproximação: mesma tranche e similaridade >= minimo; aceita se 1.
      Saída: (rótulo, código, critério) ou None (nenhum/ambíguo).
    """
    alvo_n = _normalizar(alvo)                           # Fase 1: alvo normalizado
    validas = [(r, c) for r, c in opcoes if c not in excluir]  # sem códigos já usados
    exatos = [(r, c) for r, c in validas if _normalizar(r) == alvo_n]  # Fase 2: nome igual
    if len(exatos) == 1:                                 # único exato => aceito
        return exatos[0][0], exatos[0][1], "exato"
    if exatos:                                           # >1 exato => ambíguo
        return None
    proximos = []                                        # Fase 3: candidatos aproximados
    for r, c in validas:                                 # compara cada rótulo
        r_n = _normalizar(r)                             # rótulo normalizado
        if _tranche(r_n) != _tranche(alvo_n):            # tranche diferente => descarta
            continue
        razao = difflib.SequenceMatcher(None, alvo_n, r_n).ratio()  # similaridade 0-1
        if razao >= minimo:                              # parecido o bastante
            proximos.append((r, c, razao))
    if len(proximos) == 1:                               # único aproximado => aceito
        r, c, razao = proximos[0]
        return r, c, f"aproximado ({razao:.2f})"
    return None                                          # saída: nenhum ou ambíguo


def resolver_programas(mapa, sessao, log, *, get_param_fn=ssrs_client.get_parametros):
    """Preenche codese/programa dos contratos do mapa que estão sem código de programa.

    Por que existe: o ucs_map desta extração traz 7 contratos antigos só com o nome do
    programa (lista 2023-2025); o código vive no dropdown em cascata do SSRS. Resolver na
    própria rodada da VPN evita uma viagem de recon; tudo que foi consultado vai p/ a
    auditoria (execução cega).

    Lógica, do input ao output, em fases:
      Entrada: mapa (muta), sessao, log, get_param_fn (injeção p/ teste).
      Fase 1 — pendentes = contratos com 'programa' vazio; nenhum => retorna [].
      Fase 2 — por pendente, tenta a concessionária conhecida (codese do mapa).
      Fase 3 — sem par nela (ou sem codese), varre TODAS as concessionárias; aceita só se
               UM único par (exato tem prioridade sobre aproximado).
      Fase 4 — grava a auditoria (dropdowns + escolha/candidatos por contrato).
      Saída: lista dos contratos NÃO resolvidos (o chamador os tira da rodada).
    """
    pendentes = [c for c, info in mapa.items() if not info.get("programa")]  # Fase 1
    if not pendentes:                                    # nada a resolver
        return []
    log.info("resolvendo código de programa de %d contrato(s): %s", len(pendentes), pendentes)
    dropdowns = {}                                       # cache codese -> [(rótulo, código)]

    def programas_de(codese):                            # helper: dropdown de 1 concessionária
        if codese not in dropdowns:                      # consulta o SSRS só 1 vez por codese
            _xml, params, _c, _t = get_param_fn(         # cascata: fixa a concessionária
                sessao, config.ITEM_PATH, valores={config.PARAM_CONCESSIONARIA: codese},
                combo=config.SOAP_COMBO)
            prog = next((p for p in params if p["name"] == config.PARAM_PROGRAMA), None)
            dropdowns[codese] = [tuple(v) for v in prog["valid_values"]] if prog else []
        return dropdowns[codese]                         # (rótulo, código) dessa concessionária

    concessionarias = None                               # [(rótulo, codese)] — carregada sob demanda
    auditoria = {}                                       # contrato -> decisão (p/ o JSON)
    nao_resolvidos = []                                  # saída
    for contrato in pendentes:                           # Fase 2: um pendente por vez
        info = mapa[contrato]                            # entrada do mapa
        alvo = info["programa_label"]                    # nome a casar
        usados = {i["programa"] for i in mapa.values() if i.get("programa")}  # códigos já tomados
        escolha, codese_escolhida, conc_escolhida = None, None, info.get("concessionaria")
        if info.get("codese"):                           # concessionária conhecida => tenta ela 1º
            try:
                escolha = casar_programa(alvo, programas_de(info["codese"]), excluir=usados)
                codese_escolhida = info["codese"]        # se casou, é nesta concessionária
            except Exception as exc:                     # erro de rede nessa consulta: segue p/ a varredura
                log.warning("%s: dropdown da codese %s falhou: %r", contrato, info["codese"], exc)
        if escolha is None:                              # Fase 3: varre todas as concessionárias
            if concessionarias is None:                  # 1º nível do SOAP (uma vez só)
                _xml, params, _c, _t = get_param_fn(sessao, config.ITEM_PATH, combo=config.SOAP_COMBO)
                conc = next((p for p in params if p["name"] == config.PARAM_CONCESSIONARIA), None)
                concessionarias = [tuple(v) for v in conc["valid_values"]] if conc else []
                log.info("varredura: %d concessionárias no SSRS", len(concessionarias))
            achados = []                                 # (codese, rótulo conc, casamento)
            for rotulo_conc, codese in concessionarias:  # cada concessionária
                try:
                    r = casar_programa(alvo, programas_de(codese), excluir=usados)
                except Exception as exc:                 # uma concessionária com erro não derruba
                    log.warning("  codese %s falhou: %r", codese, exc)
                    continue
                if r:                                    # houve par nessa concessionária
                    achados.append((codese, rotulo_conc, r))
            exatos = [a for a in achados if a[2][2] == "exato"]  # exato tem prioridade
            finais = exatos or achados                   # se não há exato, os aproximados
            if len(finais) == 1:                         # único => aceito
                codese_escolhida, conc_escolhida, escolha = finais[0]
            elif len(finais) > 1:                        # ambíguo => não arrisca
                log.error("%s: %r casou em %d concessionárias: %s", contrato, alvo, len(finais),
                          [(a[0], a[1], a[2][0]) for a in finais])
        if escolha:                                      # resolvido => completa o mapa
            rotulo, codigo, criterio = escolha
            info.update(codese=codese_escolhida, programa=codigo, concessionaria=conc_escolhida)
            log.info("%s: %r -> codese=%s programa=%s (%r, %s)",
                     contrato, alvo, codese_escolhida, codigo, rotulo, criterio)
            auditoria[contrato] = {"alvo": alvo, "codese": codese_escolhida,
                                   "concessionaria": conc_escolhida, "programa": codigo,
                                   "rotulo_ssrs": rotulo, "criterio": criterio}
        else:                                            # sem par => fica fora da rodada
            todos = {r: c for opc in dropdowns.values() if isinstance(opc, list) for r, c in opc}
            parecidos = difflib.get_close_matches(alvo, list(todos), n=5, cutoff=0.5)  # dica p/ o humano
            log.error("%s: programa %r NÃO resolvido — candidatos parecidos: %s",
                      contrato, alvo, [(p, todos[p]) for p in parecidos])
            auditoria[contrato] = {"alvo": alvo, "resolvido": False,
                                   "parecidos": [[p, todos[p]] for p in parecidos]}
            nao_resolvidos.append(contrato)
    config.AUDITORIA_PROGRAMAS.parent.mkdir(parents=True, exist_ok=True)  # Fase 4: auditoria
    with open(config.AUDITORIA_PROGRAMAS, "w", encoding="utf-8") as fh:
        json.dump({"contratos": auditoria,
                   "concessionarias": concessionarias,
                   "dropdowns": dropdowns}, fh, ensure_ascii=False, indent=2)
    return nao_resolvidos                                # saída: quem ficou sem código


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
    p = argparse.ArgumentParser(description="Extração única 2023-2025 — UCs via SSRS.")
    p.add_argument("--dry-run", action="store_true", help="lista o plano e sai (sem rede)")
    p.add_argument("--contratos", default=None, help='subconjunto: "ECO 025/2021,ECO 021/2020"')
    p.add_argument("--refresh", action="store_true", help="força re-baixar todos (ignora o estado)")
    p.add_argument("--somente-consolida", action="store_true", help="não baixa; só reprocessa os brutos")
    return p.parse_args(argv)


def main(argv=None):
    """Orquestra a rodada: resolve programas, valida o map, planeja, baixa e consolida.

    Por que existe: ponto de entrada único (`python -m ucs.main`) que amarra resolução,
    estado, download e consolidação, sempre gravando estado/logs para execução cega.

    Lógica, do input ao output, em fases:
      Entrada: argv (CLI; None => sys.argv).
      Fase 1 — log + CLI.
      Fase 2 — carrega o mapa; define o filtro. --dry-run lista o plano (sem rede) e sai.
      Fase 3 — se não for --somente-consolida: cria a sessão, resolve os programas sem
               código (não resolvidos saem da rodada), valida, decide modo, planeja e
               executa o laço com persistência incremental.
      Fase 4 — carrega o DTB e consolida os brutos no CSV com uf/município/status.
      Saída: código de saída (0 = tudo certo; 1 = consolidação abortada OU algum contrato
             sem programa resolvido — o consolidado dos demais é gravado mesmo assim).
    """
    args = _cli(argv if argv is not None else sys.argv[1:])  # Fase 1: CLI
    log = _configurar_log()                        # logging
    log.info("=== Extração 2023-2025 (UCs) === args=%s", vars(args))

    mapa = download.carregar_map()                 # Fase 2: carrega o mapa
    filtro = [c.strip() for c in args.contratos.split(",")] if args.contratos else None
    nao_resolvidos = []                             # contratos sem código de programa

    if args.dry_run:                                # --dry-run: mostra o plano e sai (sem rede)
        for c in (filtro or mapa):                  # contratos da rodada
            info = mapa[c]                          # entrada do mapa
            log.info("  %s -> codese=%s programa=%s (%s)", c, info["codese"],
                     info["programa"] or "A RESOLVER", info["programa_label"])
        return 0

    if not args.somente_consolida:                 # Fase 3: etapa de download
        sessao = ssrs_client.criar_sessao()         # sessão autenticada (SSPI)
        nao_resolvidos = resolver_programas(mapa, sessao, log)  # completa codese/programa
        for c in nao_resolvidos:                    # sem código => fora da rodada
            del mapa[c]
        if filtro:                                  # filtro só com contratos ainda no mapa
            filtro = [c for c in filtro if c in mapa]
        download.validar_mapeamento(mapa)           # falha cedo se ainda houver lacuna
        contratos = list(mapa)                      # conjunto de trabalho = chaves do mapa
        estado = carregar_estado()                  # estado anterior
        modo = "refresh" if args.refresh else decidir_modo(estado, contratos)  # modo
        planos = planejar(contratos, mapa, config.RAW_DIR, modo=modo, estado=estado, filtro=filtro)
        log.info("modo=%s | %d planos (%d a baixar)", modo, len(planos),
                 sum(1 for p in planos if p["acao"] == "baixar"))
        agora = datetime.now().isoformat(timespec="seconds")  # timestamp da rodada
        def persistir(resultados):                  # callback: grava estado após cada contrato
            escrever_estado(atualizar_estado(
                estado, resultados, max_tentativas=config.MAX_TENTATIVAS_CONTRATO, agora=agora))
        resultados = executar(planos, sessao, log, persistir=persistir)  # laço
        log.info("rodada: %d baixados, %d falhas",
                 sum(1 for r in resultados if r["status"] == "baixado"),
                 sum(1 for r in resultados if r["status"] == "falha"))

    try:                                            # Fase 4: consolidação (entradas obrigatórias)
        dtb = municipios.carregar_dtb()             # DTB em memória (falha cedo se faltar)
        log.info("DTB: %d chaves (7 e 6 dígitos) de %s",  # execução cega: tamanho no log
                 len(dtb), config.DTB_CSV.name)
        total = consolida.consolidar_csv(           # base plana (uf/município/status)
            mapa, config.RAW_DIR, config.CSV_CONSOLIDADO_UCS, log, dtb)
    except (FileNotFoundError, ValueError) as exc:  # DTB ausente/inválido ou código sem par:
        log.error("CONSOLIDAÇÃO ABORTADA: %s", exc)  #   falha ALTA (o operador não pode ver
        return 1                                    #   "sucesso" com a base sem localização)
    log.info("=== Extração 2023-2025 concluída — %d linhas em %s ===",
             total, config.CSV_CONSOLIDADO_UCS.name)
    if nao_resolvidos:                              # consolidado saiu, mas incompleto
        log.error("ATENÇÃO: %d contrato(s) sem programa resolvido, FORA do consolidado: %s "
                  "(candidatos em %s)", len(nao_resolvidos), nao_resolvidos,
                  config.AUDITORIA_PROGRAMAS.name)
        return 1                                    # saída: incompleto
    return 0                                        # saída: sucesso


if __name__ == "__main__":                         # permite `python -m ucs.main`
    sys.exit(main())                               # propaga o código de saída
