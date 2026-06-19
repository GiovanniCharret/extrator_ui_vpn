"""U4 — consolidação dos CSVs brutos numa base enxuta UC↔ODI (+ SQLite opcional).

Puro/testável no DEV: extrair_linhas (1 CSV bruto -> linhas enxutas).
Orquestração: consolidar_csv (stream de todos os brutos -> consolidado_ucs.csv),
consolidar_sqlite (carga opcional indexada), benchmark (mede volume p/ a decisão de storage).

Streaming por contrato (stdlib csv) p/ não segurar ~1M linhas na memória. NÃO há
município/UF aqui — é a base UC↔ODI; o município vem da Fase 1 (ODI→município), por ODI.
"""

import csv                                    # leitura/escrita CSV (stdlib)
import sqlite3                                # banco opcional (stdlib, sem dep)
import time                                   # cronometragem do benchmark

from ucs import config, download              # constantes + caminho_raw

# Colunas da base. Default = só UC↔ODI; cod/nome de projeto entram via --dados-projetos.
COLS_BASE = ["contrato", "odi", "uc"]
COLS_PROJETO = ["cod_projeto", "nome_projeto"]


def cabecalho_saida(incluir_projetos=False):
    """Monta o cabeçalho da base conforme a opção de dados de projeto.

    Por que existe: a saída tem 1 forma enxuta (default) e 1 com rastreio de projeto
    (--dados-projetos); centralizar evita o cabeçalho divergir do que extrair_linhas devolve.

    Lógica: Entrada incluir_projetos. Fase 1 — base + (projeto, se pedido). Saída: lista de nomes.
    """
    return COLS_BASE + (COLS_PROJETO if incluir_projetos else [])   # Fase 1/saída


def extrair_linhas(caminho, incluir_projetos=False):
    """Lê um CSV bruto do SSRS e devolve só as colunas que interessam à base.

    Por que existe: o relatório tem 30 colunas; a base de validação só precisa de ODI e
    UC (e, opcionalmente, cod/nome de projeto p/ rastreio). Seleção por NOME de coluna
    (não posição) deixa a função pura/testável e resistente a reordenação.

    Lógica, do input ao output, em fases:
      Entrada: caminho de um output_ucs/raw/<contrato>.csv (vírgula, utf-8-sig, BOM),
               incluir_projetos (anexa cod_projeto/nome_projeto).
      Fase 1 — abre o CSV e lê o header; mapeia nome-de-coluna -> índice.
      Fase 2 — exige as âncoras (UC e ODI); sem elas o arquivo é inválido.
      Fase 3 — por linha (pulando a placeholder vazia do SSRS), extrai (odi, uc) e,
               se pedido, (cod_projeto, nome_projeto).
      Saída: lista de tuplas (odi, uc[, cod_projeto, nome_projeto]).
    """
    with open(caminho, encoding=config.CSV_IN_ENCODING, newline="") as fh:  # Fase 1: abre (utf-8-sig tira BOM)
        leitor = csv.reader(fh, delimiter=config.CSV_IN_DELIMITADOR)        # vírgula como separador
        cabecalho = next(leitor, None)                 # 1ª linha = nomes das colunas
        if not cabecalho:                              # arquivo vazio => nada a extrair
            return []
        idx = {nome: i for i, nome in enumerate(cabecalho)}  # nome-de-coluna -> índice
        if config.COL_UC not in idx or config.COL_ODI not in idx:  # Fase 2: âncoras obrigatórias
            raise ValueError(
                f"{caminho}: header sem {config.COL_UC!r}/{config.COL_ODI!r} "
                f"(colunas: {cabecalho[:6]}...)")

        def pega(linha, nome):                         # helper: valor da coluna ou "" se ausente
            i = idx.get(nome)                          # índice da coluna (ou None)
            return linha[i].strip() if i is not None and i < len(linha) else ""

        linhas = []                                    # Fase 3: acumulador desta planilha
        for linha in leitor:                           # uma linha de dados por vez
            if not linha:                              # pula linhas em branco
                continue
            odi = pega(linha, config.COL_ODI)          # ODI (junção c/ a Fase 1)
            uc = pega(linha, config.COL_UC)            # número da UC
            if not odi and not uc:                     # linha-placeholder do SSRS (programa
                continue                               #   sem UCs): ODI e UC vazios => ignora
            registro = [odi, uc]                       # base enxuta (sempre)
            if incluir_projetos:                       # rastreio opcional de projeto
                registro.append(pega(linha, config.COL_COD_PROJETO))   # código do projeto
                registro.append(pega(linha, config.COL_NOME_PROJETO))  # nome do projeto
            linhas.append(tuple(registro))             # registra a linha enxuta
        return linhas                                  # saída: linhas enxutas (sem o contrato)


def consolidar_csv(mapa, raw_dir, caminho_saida, log, *, incluir_projetos=False):
    """Junta todos os brutos presentes num único consolidado_ucs.csv (streaming).

    Por que existe: entrega a base plana (contrato;odi;uc[;projeto]) reabrindo cada bruto
    presente e escrevendo direto na saída — sem segurar tudo na memória. Idempotente
    (regrava o arquivo inteiro), como a consolidação da Fase 1.

    Lógica, do input ao output, em fases:
      Entrada: mapa (contratos), raw_dir, caminho_saida, log, incluir_projetos.
      Fase 1 — abre a saída (utf-8-sig, ';') e escreve o cabeçalho conforme a opção.
      Fase 2 — para cada contrato com bruto presente, extrai e escreve as linhas
               prefixando o contrato; soma o total.
      Saída: total de linhas escritas (e o arquivo em caminho_saida).
    """
    caminho_saida.parent.mkdir(parents=True, exist_ok=True)  # garante output_ucs/
    total = 0                                          # contador de linhas (saída)
    with open(caminho_saida, "w", encoding=config.CSV_ENCODING, newline="") as fh:  # Fase 1
        escritor = csv.writer(fh, delimiter=config.CSV_DELIMITADOR)  # ';' (padrão pt-BR)
        escritor.writerow(cabecalho_saida(incluir_projetos))  # cabeçalho (com/sem projeto)
        for contrato in mapa:                          # Fase 2: na ordem do mapa
            caminho = download.caminho_raw(contrato, raw_dir)  # bruto esperado
            if not caminho.exists():                   # sem bruto => contrato não baixado ainda
                log.info("sem bruto para %s — fora da consolidação", contrato)
                continue
            linhas = extrair_linhas(caminho, incluir_projetos)  # CSV -> linhas enxutas
            for t in linhas:                           # prefixa o contrato e escreve
                escritor.writerow((contrato, *t))
            total += len(linhas)                       # soma ao total
            log.info("%s: %d linhas consolidadas", contrato, len(linhas))
    log.info("consolidado_ucs.csv: %d linhas no total", total)
    return total                                       # saída: total de linhas


def consolidar_sqlite(mapa, raw_dir, db_path, log, *, incluir_projetos=False):
    """Carrega a base num SQLite indexado por ODI e UC (opcional; decisão de storage).

    Por que existe: o handoff p/ o site tende a fazer consultas pontuais (esta UC/ODI
    existe?); um SQLite com índice resolve isso sem carregar tudo na memória. É derivado
    dos brutos (regenerável), então é seguro recriá-lo do zero a cada rodada.

    Lógica, do input ao output, em fases:
      Entrada: mapa, raw_dir, db_path, log, incluir_projetos.
      Fase 1 — (re)cria a tabela 'ucs' do zero, com as colunas conforme a opção.
      Fase 2 — insere as linhas de cada bruto presente (em lote por contrato).
      Fase 3 — cria índices em odi e uc; commita.
      Saída: total de linhas inseridas (e o arquivo db_path).
    """
    colunas = cabecalho_saida(incluir_projetos)        # nomes das colunas (contrato, odi, uc[, ...])
    placeholders = ",".join("?" * len(colunas))        # ?,?,? conforme o nº de colunas
    db_path.parent.mkdir(parents=True, exist_ok=True)  # garante a pasta
    con = sqlite3.connect(db_path)                     # abre/cria o banco
    try:
        con.execute("DROP TABLE IF EXISTS ucs")        # Fase 1: recria do zero (idempotente)
        con.execute(                                   # tabela com as colunas TEXT da base
            f"CREATE TABLE ucs ({', '.join(c + ' TEXT' for c in colunas)})")
        total = 0                                      # contador (saída)
        for contrato in mapa:                          # Fase 2: por contrato
            caminho = download.caminho_raw(contrato, raw_dir)
            if not caminho.exists():                   # sem bruto => pula
                continue
            linhas = extrair_linhas(caminho, incluir_projetos)  # CSV -> linhas enxutas
            con.executemany(                           # insere em lote (contrato prefixado)
                f"INSERT INTO ucs VALUES ({placeholders})",
                [(contrato, *t) for t in linhas])
            total += len(linhas)                       # soma
        con.execute("CREATE INDEX ix_ucs_odi ON ucs(odi)")  # Fase 3: índices p/ consulta
        con.execute("CREATE INDEX ix_ucs_uc ON ucs(uc)")
        con.commit()                                   # persiste tudo
        log.info("ucs.db: %d linhas, índices em odi/uc", total)
        return total                                   # saída: total inserido
    finally:
        con.close()                                    # sempre fecha a conexão


def benchmark(caminho_csv, db_path, log):
    """Mede volume/tamanho/tempo de consulta p/ embasar a decisão CSV × SQLite × Postgres.

    Por que existe: a escolha de storage foi adiada p/ depois de ver o volume REAL; este
    helper produz os números (linhas, MB, tempo de um lookup por ODI no SQLite).

    Lógica, do input ao output, em fases:
      Entrada: caminho_csv (consolidado), db_path (SQLite, pode não existir), log.
      Fase 1 — tamanho do CSV e nº de linhas.
      Fase 2 — se há SQLite, cronometra um SELECT por ODI usando o índice.
      Saída: dict com as métricas (também logado).
    """
    metr = {}                                          # acumulador de métricas (saída)
    if caminho_csv.exists():                            # Fase 1: CSV
        metr["csv_mb"] = round(caminho_csv.stat().st_size / 1_048_576, 2)
        with open(caminho_csv, encoding=config.CSV_ENCODING) as fh:
            metr["csv_linhas"] = max(0, sum(1 for _ in fh) - 1)  # -1 do header
    if db_path.exists():                               # Fase 2: SQLite (se gerado)
        con = sqlite3.connect(db_path)                 # abre o banco
        try:
            metr["db_mb"] = round(db_path.stat().st_size / 1_048_576, 2)
            algum = con.execute("SELECT odi FROM ucs LIMIT 1").fetchone()  # uma ODI qualquer
            if algum:                                  # cronometra o lookup indexado
                t0 = time.perf_counter()
                con.execute("SELECT COUNT(*) FROM ucs WHERE odi=?", (algum[0],)).fetchone()
                metr["lookup_odi_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        finally:
            con.close()                                # sempre fecha
    log.info("benchmark: %s", metr)                    # registra as métricas
    return metr                                        # saída: métricas
