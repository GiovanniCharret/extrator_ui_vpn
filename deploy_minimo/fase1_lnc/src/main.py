"""F5 — laço completo, retomada automática, consolidação e estado do pipeline LPT.

Puro (testável no DEV): decidir_modo / planejar / consolidar / atualizar_estado / escrever_*.
UI (só na VPN): executar (laço que dirige o exportar_pdf).
Retomada AUTOMÁTICA: o modo (refresh/retomar) é decidido lendo output/estado_execucao.json
(rodada anterior completa => refresh tudo; incompleta => retoma só o que falta). --refresh força tudo.
"""

import csv
import json
import logging
from collections import Counter

from src import config, contratos, exportar_pdf, parse_pdf


def _destino(pdf_dir, contrato):
    """Caminho do PDF de um contrato dentro de pdf_dir (mesma regra do exportar_pdf).

    Por que existe: planejar e consolidar precisam derivar o nome do PDF a partir do
    contrato exatamente como o exportar_pdf grava — um único ponto evita divergência.

    Lógica, do input ao output:
      Entrada: pdf_dir (pasta dos PDFs) e contrato (chave primária).
      Fase 1 — sanitiza o contrato em nome de arquivo seguro.
      Saída: Path pdf_dir/<contrato_sanitizado>.pdf.
    """
    return pdf_dir / f"{contratos.sanitizar_nome(contrato)}.pdf"  # Fase 1: contrato -> caminho do PDF


def decidir_modo(estado, vigentes):
    """Decide automaticamente o modo da rodada lendo o estado anterior — sem flag humana.

    Por que existe: a rodada diária deve atualizar dados (refresh) mas, se a anterior
    foi interrompida, deve retomar só o que falta — sem o usuário lembrar de --retomar.
    A decisão sai do arquivo de estado.

    Lógica, do input ao output, em fases:
      Entrada: estado (dict carregado do JSON, pode ser {}), vigentes (contratos).
      Fase 1 — sem estado anterior => primeira rodada => 'refresh'.
      Fase 2 — 'completa' se todo vigente está 'exportado' ou 'desistido' (ninguém em
               falha ainda tentável). Completa => 'refresh'; senão => 'retomar'.
      Saída: 'refresh' | 'retomar'.
    """
    contratos_est = estado.get("contratos", {})    # estado por contrato da rodada anterior
    if not contratos_est:                           # Fase 1: nunca rodou => refresh
        return "refresh"
    completa = all(                                 # Fase 2: todos resolvidos?
        contratos_est.get(c, {}).get("status") in ("exportado", "desistido")
        for c in vigentes
    )
    return "refresh" if completa else "retomar"     # saída: modo decidido


def planejar(vigentes, mapa, pdf_dir, *, modo, estado, filtro=None):
    """Decide, por contrato, o que o laço fará (exportar ou pular) — sem tocar a UI.

    Por que existe: separa a DECISÃO (pura, testável) da AÇÃO de UI (executar). Em
    'refresh' re-exporta tudo (dados frescos); em 'retomar' pula quem já está resolvido
    ('exportado'/'desistido') e refaz o resto (falha tentável + nunca-tentados).

    Lógica, do input ao output, em fases:
      Entrada: vigentes, mapa (contrato->{programa}), pdf_dir, modo, estado anterior,
               filtro (lista de contratos ou None = todos).
      Fase 1 — define os alvos: o filtro, se houver; senão todos os vigentes.
      Fase 2 — valida cada alvo (tem de ser vigente; erro cedo se não for).
      Fase 3 — decide a ação: refresh => sempre 'exportar'; retomar => 'pular' se o
               status anterior já é 'exportado'/'desistido', senão 'exportar'.
      Saída: lista de planos {contrato, programa, destino, acao}.
    """
    alvos = filtro if filtro else list(vigentes)    # Fase 1: alvos = subconjunto pedido ou todos
    contratos_est = estado.get("contratos", {})     # estado anterior por contrato
    planos = []                                     # acumulador dos planos (saída)
    for contrato in alvos:                          # percorre cada contrato-alvo
        if contrato not in vigentes:                # Fase 2: alvo precisa ser um contrato vigente
            raise ValueError(                       # erro cedo (typo no --contratos, ECM/Encerrado)
                f"contrato {contrato!r} não é vigente (ou é ECM/Encerrado)"
            )
        if modo == "refresh":                       # Fase 3a: refresh re-exporta tudo
            acao = "exportar"
        else:                                       # Fase 3b: retomar pula o que já resolveu
            status_ant = contratos_est.get(contrato, {}).get("status")
            acao = "pular" if status_ant in ("exportado", "desistido") else "exportar"
        planos.append({                             # registra o plano deste contrato
            "contrato": contrato,                   # chave primária
            "programa": mapa[contrato]["programa"],  # texto exato do dropdown (p/ a UI)
            "tipo": mapa[contrato].get("tipo", config.TIPO_PROJETO_PADRAO),  # radio Tipo de Projeto
            "destino": _destino(pdf_dir, contrato),  # caminho do PDF (nome por contrato)
            "acao": acao,                           # 'exportar' | 'pular'
        })
    return planos                                   # saída: plano da rodada


def consolidar(vigentes, mapa, pdf_dir, log):
    """Reúne num só lugar os dados de todos os PDFs já exportados.

    Por que existe: o pipeline gera 1 PDF por contrato; para entregar um CSV único
    (contrato;odi;uf;municipio) é preciso reabrir cada PDF presente e juntar tudo,
    sempre prefixando o contrato (chave primária). Isolar aqui mantém a etapa pura e
    reexecutável (idempotente), sem depender da UI — a base da retomada/atualização.

    Lógica, do input ao output, em fases:
      Entrada: vigentes (dict de contratos), mapa (não usado nos dados, mantido por
               simetria de assinatura com planejar), pdf_dir, log.
      Fase 1 — percorre cada contrato vigente (a ordem do CSV segue a dos vigentes).
      Fase 2 — calcula o caminho do PDF; se não existe, o contrato ainda não foi
               exportado nesta rodada => pula (nada a consolidar para ele).
      Fase 3 — parseia o PDF (parse_pdf) em linhas (odi, uf, municipio).
      Fase 4 — prefixa o contrato em cada linha e acumula no resultado.
      Saída: lista de tuplas (contrato, odi, uf, municipio) de todos os PDFs presentes.
    """
    rows = []                                       # acumulador de todas as linhas (saída final)
    for contrato in vigentes:                       # Fase 1: um contrato por vez, na ordem dos vigentes
        destino = _destino(pdf_dir, contrato)       # caminho esperado output/pdf/<contrato>.pdf
        if not destino.exists():                    # Fase 2: PDF ausente => contrato não exportado ainda
            log.info("sem PDF para %s — fora da consolidação", contrato)  # rastro do pulo (execução cega)
            continue                                # segue para o próximo contrato
        linhas = parse_pdf.extrair_linhas(destino)  # Fase 3: PDF -> [(odi, uf, municipio)]
        log.info("%s: %d linhas", contrato, len(linhas))  # rastro do volume por contrato
        rows.extend(                                # Fase 4: prefixa o contrato em cada linha
            (contrato, odi, uf, muni) for odi, uf, muni in linhas
        )
    return rows                                     # saída: todas as linhas, agrupáveis por contrato


def escrever_consolidado(rows, caminho):
    """Grava as linhas consolidadas no CSV final (contrato;odi;uf;municipio).

    Por que existe: separa a ESCRITA do arquivo da LÓGICA de consolidação — assim o
    formato (utf-8-sig, delimitador ';') fica num único lugar e é testável isoladamente.

    Lógica, do input ao output, em fases:
      Entrada: rows (lista de tuplas contrato,odi,uf,municipio) e caminho do CSV.
      Fase 1 — abre o arquivo em utf-8-sig (Excel lê acentos) e cria o writer com ';'.
      Fase 2 — escreve o cabeçalho fixo.
      Fase 3 — escreve todas as linhas de uma vez.
      Saída: arquivo CSV gravado em `caminho` (sem retorno).
    """
    with open(caminho, "w", newline="", encoding=config.CSV_ENCODING) as f:  # Fase 1: arquivo + encoding
        w = csv.writer(f, delimiter=config.CSV_DELIMITADOR)  # writer com ';' (config)
        w.writerow(["contrato", "odi", "uf", "municipio"])   # Fase 2: cabeçalho
        w.writerows(rows)                                    # Fase 3: todas as linhas de dados


def carregar_estado(caminho):
    """Lê o estado da rodada anterior (JSON) ou retorna {} se não existir/estiver vazio.

    Por que existe: o estado dirige a auto-retomada (decidir_modo) e guarda o contador
    de tentativas por contrato entre rodadas. Ausência de arquivo = primeira rodada.

    Lógica, do input ao output:
      Entrada: caminho do JSON.
      Fase 1 — arquivo ausente => {} (primeira rodada).
      Fase 2 — lê e desserializa; conteúdo vazio também => {}.
      Saída: dict do estado (ou {}).
    """
    if not caminho.exists():                         # Fase 1: nunca rodou
        return {}
    txt = caminho.read_text(encoding="utf-8").strip()  # Fase 2: lê o JSON
    return json.loads(txt) if txt else {}            # vazio => {}; saída: estado


def escrever_estado(estado, caminho):
    """Grava o estado/relatório da rodada em JSON (legível por humano e por máquina).

    Por que existe: substitui o antigo relatorio_execucao.csv — um único arquivo que é
    relatório (status/linhas/erro por contrato) E estado que a próxima rodada lê.

    Lógica, do input ao output:
      Entrada: estado (dict) e caminho do JSON.
      Fase 1 — garante a pasta de saída.
      Fase 2 — serializa com acentos preservados (ensure_ascii=False) e indentado.
      Saída: arquivo JSON gravado (sem retorno).
    """
    caminho.parent.mkdir(parents=True, exist_ok=True)           # Fase 1: pasta existe
    caminho.write_text(                                         # Fase 2: JSON legível
        json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def atualizar_estado(estado_ant, vigentes, mapa, resultados, rows, modo, max_tentativas, agora):
    """Calcula o novo estado a partir do anterior + desfecho desta rodada (puro).

    Por que existe: concentra a regra de transição (sucesso zera tentativas; falha
    incrementa e vira 'desistido' ao atingir o limite; refresh reinicia o contador;
    contrato pulado carrega o estado anterior). É o coração testável da auto-retomada.

    Lógica, do input ao output, em fases:
      Entrada: estado_ant (dict), vigentes, mapa, resultados (do executar), rows (da
               consolidação), modo, max_tentativas, agora (timestamp ISO).
      Fase 1 — conta linhas por contrato e indexa os resultados desta rodada.
      Fase 2 — por vigente, deriva o novo registro conforme o desfecho:
               • sem resultado ou 'pulado' => carrega o anterior (atualiza só 'linhas');
               • 'exportado' => status exportado, tentativas 0, ultimo_ok = agora;
               • 'falha' => tentativas = (0 se refresh, senão anterior) + 1; vira
                 'desistido' se atingir max_tentativas, senão 'falha'.
      Fase 3 — monta o resumo agregado.
      Saída: dict {gerado_em, modo, resumo, contratos:{...}}.
    """
    cont_linhas = Counter(r[0] for r in rows)        # Fase 1: contrato -> nº de linhas
    ant = estado_ant.get("contratos", {})            # estado anterior por contrato
    res_por = {r["contrato"]: r for r in resultados}  # resultado desta rodada por contrato
    novos = {}                                        # estado novo por contrato
    for contrato in vigentes:                         # Fase 2: um vigente por vez
        prev = ant.get(contrato, {})                 # registro anterior (pode ser {})
        res = res_por.get(contrato)                  # desfecho desta rodada (pode ser None)
        linhas = cont_linhas.get(contrato, 0)        # linhas atuais na consolidação
        programa = ((res or {}).get("programa")      # programa: do resultado, do anterior, ou do map
                    or prev.get("programa")
                    or mapa.get(contrato, {}).get("programa", ""))
        tipo = ((res or {}).get("tipo")              # tipo: do resultado, do anterior, ou do map
                or prev.get("tipo")
                or mapa.get(contrato, {}).get("tipo", ""))
        if res is None or res["status"] == "pulado":  # não processado / pulado => carrega anterior
            novos[contrato] = {
                "programa": programa, "tipo": tipo,
                "status": prev.get("status", "pendente"),  # 'pendente' = nunca exportado
                "tentativas": prev.get("tentativas", 0),
                "linhas": linhas,                    # mas atualiza as linhas da consolidação
                "erro": prev.get("erro", ""),
                "ultimo_ok": prev.get("ultimo_ok", ""),
            }
        elif res["status"] == "exportado":           # sucesso => zera tentativas, marca ok
            novos[contrato] = {
                "programa": programa, "tipo": tipo, "status": "exportado", "tentativas": 0,
                "linhas": linhas, "erro": "", "ultimo_ok": agora,
            }
        else:                                        # falha => incrementa (refresh reinicia em 0)
            base = 0 if modo == "refresh" else prev.get("tentativas", 0)
            tent = base + 1
            status = "desistido" if tent >= max_tentativas else "falha"  # parou de tentar?
            novos[contrato] = {
                "programa": programa, "tipo": tipo, "status": status, "tentativas": tent,
                "linhas": linhas, "erro": res.get("erro", ""),
                "ultimo_ok": prev.get("ultimo_ok", ""),  # falha não atualiza o último ok
            }
    resumo = {                                        # Fase 3: agregado p/ o resumo da rodada
        "exportado": sum(1 for c in novos.values() if c["status"] == "exportado"),
        "falha": sum(1 for c in novos.values() if c["status"] == "falha"),
        "desistido": sum(1 for c in novos.values() if c["status"] == "desistido"),
        "linhas": sum(c["linhas"] for c in novos.values()),
    }
    return {"gerado_em": agora, "modo": modo, "resumo": resumo, "contratos": novos}


def _screenshot_falha(contrato, log):
    """Tira um screenshot de diagnóstico quando um contrato falha (best-effort).

    Por que existe: na execução cega da VPN, um screenshot do momento da falha é a
    evidência que poupa uma viagem. Mas o screenshot nunca pode derrubar a rodada,
    então toda falha do próprio screenshot é engolida com aviso.

    Lógica, do input ao output:
      Entrada: contrato (p/ nomear o arquivo) e log.
      Fase 1 — tenta reusar o screenshot do inspecionar_app (grava em output/).
      Fase 2 — se indisponível (ex.: DEV sem tela), só avisa e segue.
      Saída: nenhuma (efeito colateral: arquivo de imagem, se possível).
    """
    try:                                                # Fase 1: melhor esforço
        import scripts.inspecionar_app as insp          # reusa o dumper já existente
        insp.screenshot(f"falha_{contratos.sanitizar_nome(contrato)}", log)  # nome por contrato
    except Exception:                                   # Fase 2: nunca derruba a rodada
        log.warning("screenshot de falha indisponível para %s (seguindo)", contrato)


def executar(planos, log, *, exportar_fn=exportar_pdf.exportar, persistir=None):
    """Percorre o plano e exporta cada contrato (a única parte que toca a UI do LNC).

    Por que existe: é o laço de produção. `exportar_fn` é injetável para que a lógica
    de pular/retry/registro de status seja testável no DEV com um stub — só a chamada
    real (exportar_pdf.exportar) precisa da VPN. Uma falha de contrato nunca aborta a
    rodada: registra e segue. `persistir` (opcional) é chamado APÓS CADA contrato com o
    acumulado — assim um Ctrl+C/queda/sono no meio deixa o estado gravado e a próxima
    rodada retoma de onde parou (sem ele, só o fim de main gravaria o estado).

    Lógica, do input ao output, em fases:
      Entrada: planos (de planejar), log, exportar_fn (real ou stub), persistir (callback).
      Fase 1 — para cada plano, separa os metadados (contrato/programa/tipo) do resultado.
      Fase 2 — acao 'pular' => registra 'pulado' e não toca a UI.
      Fase 3 — acao 'exportar' => tenta exportar; em falha, 1 retry (re-navega do zero,
               pois exportar recomeça por limpar_estado+navegação) com screenshot.
      Fase 4 — registra o status final e PERSISTE o acumulado (resume robusto), e segue.
      Saída: lista de resultados {contrato, programa, tipo, status, erro}.
    """
    resultados = []                                     # acumulador dos desfechos (saída)
    for p in planos:                                    # Fase 1: um contrato por vez
        base = {"contrato": p["contrato"], "programa": p["programa"], "tipo": p["tipo"]}  # metadados
        if p["acao"] == "pular":                        # Fase 2: nada de UI para os pulados
            log.info("PULANDO %s (já resolvido; modo retomar)", p["contrato"])  # rastro
            resultados.append({**base, "status": "pulado", "erro": ""})       # registra
        else:
            status, erro = "exportado", ""              # Fase 3: otimista; corrige se falhar
            for tentativa in (1, 2):                    # 1 tentativa + 1 retry
                try:
                    exportar_fn(p["programa"], p["contrato"], p["tipo"], log, destino=p["destino"])  # real/stub
                    break                               # sucesso => sai do retry
                except Exception as e:                  # falhou esta tentativa
                    log.error("EXPORT FALHOU %s (tentativa %d): %s", p["contrato"], tentativa, e)
                    _screenshot_falha(p["contrato"], log)  # evidência da falha (best-effort)
                    if tentativa == 2:                  # esgotou o retry
                        status, erro = "falha", str(e)  # marca falha com a mensagem
            resultados.append({**base, "status": status, "erro": erro})  # registra
        if persistir is not None:                       # Fase 4: grava o estado APÓS cada contrato
            persistir(resultados)                       # (resume robusto a interrupção/queda/sono)
    return resultados                                   # saída: desfecho por contrato


def _carregar_validado(log):
    """Carrega vigentes + map + dropdown e ABORTA se o mapeamento for inválido.

    Por que existe: 'falha cedo' — validar o map (reusando contratos.validar_mapeamento)
    ANTES de tocar a UI evita gastar uma rodada longa na VPN só para descobrir no fim
    que um contrato estava sem programa ou com um typo que não existe no dropdown.

    Lógica, do input ao output, em fases:
      Entrada: log (os caminhos vêm do config).
      Fase 1 — carrega os vigentes (contratos.carregar_vigentes) e lê os 2 JSONs.
      Fase 2 — valida (todo vigente com programa; programa existe no dropdown; 1:1).
      Fase 3 — se houver erros, loga cada um e levanta SystemExit (aborta a rodada).
      Saída: (vigentes, mapa) quando tudo é válido.
    """
    vigentes = contratos.carregar_vigentes()                                   # Fase 1: contratos do laço
    mapa = json.loads(config.PROGRAMAS_MAP.read_text(encoding="utf-8"))         # map contrato->{programa}
    dropdown = json.loads(config.PROGRAMAS_DROPDOWN.read_text(encoding="utf-8"))  # itens reais do dropdown
    erros = contratos.validar_mapeamento(vigentes, dropdown, mapa)             # Fase 2: regras a/b/c
    if erros:                                                                  # Fase 3: map inválido
        for e in erros:                                                        # mostra cada problema
            log.error("MAP inválido: %s", e)
        raise SystemExit(f"map inválido ({len(erros)} erro(s)) — corrija antes de rodar")
    return vigentes, mapa                                                      # saída: dados validados


def _configurar_log():
    """Configura logging para console + output/logs/run_<timestamp>.log.

    Por que existe: a execução cega exige que TUDO fique gravado em arquivo (uma falha
    sem log desperdiça uma viagem). Centraliza o setup do logger da rodada.

    Lógica, do input ao output:
      Fase 1 — garante a pasta de logs e monta o nome com timestamp.
      Fase 2 — configura handlers de arquivo (utf-8) e de console.
      Saída: logger nomeado 'run'.
    """
    import sys                                           # stdout reconfig (acentos no console Windows)
    from datetime import datetime                        # timestamp do nome do log
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # evita UnicodeEncodeError no console
    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)   # Fase 1: pasta de logs existe
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")        # carimbo de tempo da rodada
    logging.basicConfig(                                 # Fase 2: arquivo + console
        level=logging.INFO,
        handlers=[
            logging.FileHandler(config.LOGS_DIR / f"run_{ts}.log", encoding="utf-8"),  # log em arquivo
            logging.StreamHandler(),                     # log no console
        ],
        format="%(asctime)s %(levelname)s %(message)s",
    )
    return logging.getLogger("run")                      # saída: logger da rodada


def main(argv=None):
    """Ponto de entrada do pipeline: planeja, exporta (ou pula a UI), consolida e relata.

    Por que existe: amarra todas as peças numa rodada com CLI. O modo (refresh/retomar)
    é decidido AUTOMATICAMENTE lendo o estado anterior (sem decisão humana); --refresh
    força rodada completa. Sempre grava consolidado.csv + estado_execucao.json (JSON que
    é relatório e estado) e um resumo no console.

    Lógica, do input ao output, em fases:
      Entrada: argv (None = sys.argv) com --contratos/--refresh/--somente-parse/--dry-run.
      Fase 1 — parseia os argumentos e configura o log.
      Fase 2 — carrega+valida (falha cedo), lê o estado e DECIDE o modo; monta o plano.
      Fase 3 — --dry-run: mostra o modo e o plano e retorna (não toca a UI).
      Fase 4 — executa o laço de UI (ou pula tudo com --somente-parse).
      Fase 5 — consolida os PDFs presentes -> consolidado.csv; atualiza e grava o estado JSON.
      Fase 6 — imprime o resumo (exportado/falha/desistido/linhas).
      Saída: nenhuma (efeitos: PDFs, consolidado.csv, estado_execucao.json e logs em output/).
    """
    import argparse                                      # CLI
    from datetime import datetime                         # timestamp do estado

    p = argparse.ArgumentParser(description="Pipeline LPT: exporta, consolida e relata.")  # Fase 1
    p.add_argument("--contratos", default=None, help="subconjunto separado por vírgula")
    p.add_argument("--refresh", action="store_true",
                   help="força re-exportar TODOS (ignora o estado); sem ele o modo é automático")
    p.add_argument("--somente-parse", action="store_true", help="pula a UI; só consolida o que há")
    p.add_argument("--dry-run", action="store_true", help="mostra o modo e o plano; não toca a UI")
    args = p.parse_args(argv)                            # parseia (None => sys.argv)

    log = _configurar_log()                              # log da rodada (console + arquivo)
    vigentes, mapa = _carregar_validado(log)             # Fase 2: carrega+valida (aborta se inválido)
    estado_ant = carregar_estado(config.ESTADO_JSON)     # estado da rodada anterior (ou {})
    modo = "refresh" if args.refresh else decidir_modo(estado_ant, vigentes)  # automático
    log.info("MODO da rodada: %s", modo)
    filtro = [c.strip() for c in args.contratos.split(",")] if args.contratos else None  # --contratos
    planos = planejar(vigentes, mapa, config.PDF_DIR, modo=modo, estado=estado_ant, filtro=filtro)

    if args.dry_run:                                     # Fase 3: só mostra modo + plano
        log.info("DRY-RUN (modo=%s) — %d contrato(s):", modo, len(planos))
        for pl in planos:                                # uma linha por contrato
            log.info("PLANO %s -> %s (%s)", pl["contrato"], pl["acao"], pl["programa"])
        return                                           # não toca a UI nem escreve nada

    agora = datetime.now().isoformat(timespec="seconds")  # carimbo do estado desta rodada

    if args.somente_parse:                               # Fase 4a: pula a UI por completo
        resultados = [                                   # status 'pulado' p/ todos (só reconsolida)
            {"contrato": pl["contrato"], "programa": pl["programa"], "tipo": pl["tipo"],
             "status": "pulado", "erro": "(somente-parse)"}
            for pl in planos
        ]
    else:                                                # Fase 4b: laço de UI (exporta de verdade)
        def _persistir_parcial(resultados_ate_agora):    # grava o estado APÓS cada contrato
            # estado interino: status/tentativas corretos; 'linhas' (=[] aqui) só no fim.
            # Se a rodada morrer (Ctrl+C/queda/sono), este arquivo já permite retomar.
            try:
                parcial = atualizar_estado(estado_ant, vigentes, mapa, resultados_ate_agora,
                                           [], modo, config.MAX_TENTATIVAS_CONTRATO, agora)
                escrever_estado(parcial, config.ESTADO_JSON)
            except Exception as e:                       # nunca derruba a rodada por causa do estado
                log.warning("não consegui gravar estado parcial (seguindo): %s", e)
        resultados = executar(planos, log, persistir=_persistir_parcial)

    rows = consolidar(vigentes, mapa, config.PDF_DIR, log)        # Fase 5: reparseia os PDFs presentes
    escrever_consolidado(rows, config.CSV_CONSOLIDADO)           # grava consolidado.csv (dados)
    estado_novo = atualizar_estado(estado_ant, vigentes, mapa, resultados, rows,  # estado final c/ linhas
                                   modo, config.MAX_TENTATIVAS_CONTRATO, agora)  # transição de estado
    escrever_estado(estado_novo, config.ESTADO_JSON)            # grava estado/relatório JSON

    r = estado_novo["resumo"]                            # Fase 6: resumo no console
    log.info("=== RESUMO [%s]: %d exportado, %d falha, %d desistido; %d linhas ===",
             modo, r["exportado"], r["falha"], r["desistido"], r["linhas"])


if __name__ == "__main__":
    main()
