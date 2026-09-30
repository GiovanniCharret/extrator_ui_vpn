"""U4 — consolidação dos CSVs brutos numa base enxuta UC↔ODI (+ SQLite opcional).

Puro/testável no DEV: extrair_linhas (1 CSV bruto -> linhas enxutas).
Orquestração: consolidar_csv (stream de todos os brutos -> config.CSV_CONSOLIDADO_UCS),
consolidar_sqlite (carga opcional indexada), benchmark (mede volume p/ a decisão de storage).

Streaming por contrato (stdlib csv) p/ não segurar ~1M linhas na memória. UF e município
saem do código IBGE da UC (PPC_COD_LOCALIZACAO) cruzado com o DTB — ver ucs/municipios.py.
"""

import csv                                    # leitura/escrita CSV (stdlib)
import sqlite3                                # banco opcional (stdlib, sem dep)
import time                                   # cronometragem do benchmark

from ucs import config, download, municipios  # constantes + caminho_raw + normalização DTB

# Colunas da base. Default = UC↔ODI + localização resolvida via DTB (U6); cod/nome
# de projeto entram via --dados-projetos.
COLS_BASE = ["contrato", "odi", "uc", "uf", "municipio"]
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

    Por que existe: o relatório tem 30 colunas; a base de validação só precisa de ODI,
    UC e código de localização (e, opcionalmente, cod/nome de projeto p/ rastreio).
    Seleção por NOME de coluna (não posição) deixa a função pura/testável e resistente
    a reordenação.

    Lógica, do input ao output, em fases:
      Entrada: caminho de um output_ucs/raw/<contrato>.csv (vírgula, utf-8-sig, BOM),
               incluir_projetos (anexa cod_projeto/nome_projeto).
      Fase 1 — abre o CSV e lê o header; mapeia nome-de-coluna -> índice.
      Fase 2 — exige as âncoras (UC, ODI e PPC_COD_LOCALIZACAO); sem elas o arquivo
               é inválido.
      Fase 3 — por linha (pulando a placeholder vazia do SSRS), extrai (odi, uc,
               cod_localizacao normalizado) e, se pedido, (cod_projeto, nome_projeto).
      Saída: lista de tuplas (odi, uc, cod_localizacao[, cod_projeto, nome_projeto]).
    """
    with open(caminho, encoding=config.CSV_IN_ENCODING, newline="") as fh:  # Fase 1: abre (utf-8-sig tira BOM)
        leitor = csv.reader(fh, delimiter=config.CSV_IN_DELIMITADOR)        # vírgula como separador
        cabecalho = next(leitor, None)                 # 1ª linha = nomes das colunas
        if not cabecalho:                              # arquivo vazio => nada a extrair
            return []
        idx = {nome: i for i, nome in enumerate(cabecalho)}  # nome-de-coluna -> índice
        ancoras = (config.COL_UC, config.COL_ODI, config.COL_LOCALIZACAO)  # Fase 2: obrigatórias
        faltantes = [c for c in ancoras if c not in idx]   # o que o header não tem
        if faltantes:                                      # sem âncora => arquivo inválido
            raise ValueError(
                f"{caminho}: header sem {faltantes} (colunas reais: {cabecalho})")

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
            registro = [odi, uc,                       # base enxuta (sempre)
                        municipios.normalizar_codigo(pega(linha, config.COL_LOCALIZACAO))]
            if incluir_projetos:                       # rastreio opcional de projeto
                registro.append(pega(linha, config.COL_COD_PROJETO))   # código do projeto
                registro.append(pega(linha, config.COL_NOME_PROJETO))  # nome do projeto
            linhas.append(tuple(registro))             # registra a linha enxuta
        return linhas                                  # saída: linhas enxutas (sem o contrato)


def _registrar_ausente(ausentes, codigo, contrato):
    """Acumula um código de localização sem par no DTB (compartilhado CSV/SQLite).

    Por que existe: a regra 'código sem par' vale idêntica para consolidar_csv e
    consolidar_sqlite; escrever a contabilização 1 vez garante que os dois caminhos
    nunca divirjam (decisão do usuário, 2026-07-20).

    Lógica: Entrada ausentes (dict acumulador), codigo, contrato. Fase 1 — garante a
    entrada do código. Fase 2 — soma a linha e registra o contrato. Saída: None (muta ausentes).
    """
    reg = ausentes.setdefault(codigo, {"linhas": 0, "contratos": set()})  # Fase 1: entrada
    reg["linhas"] += 1                              # Fase 2: conta a linha afetada
    reg["contratos"].add(contrato)                  # ...e o contrato afetado


def _falhar_se_ausentes(ausentes, log, alvo):
    """Loga o relatório COMPLETO de códigos sem par e falha (compartilhado CSV/SQLite).

    Por que existe: o relatório de falha (todos os códigos, linhas e contratos numa
    rodada só — decisão do design 2026-07-20) precisa ser idêntico nos dois caminhos;
    centralizar evita que o formato do log divirja.

    Lógica: Entrada ausentes, log, alvo (nome do artefato NÃO gravado). Fase 1 — vazio
    => retorna sem efeito. Fase 2 — loga o resumo e cada código ordenado. Saída: levanta
    ValueError (nunca retorna) quando há ausentes.
    """
    if not ausentes:                                # Fase 1: nada ausente => sem efeito
        return
    log.error("DTB: %d código(s) de localização sem par — %s NÃO gravado",
              len(ausentes), alvo)                  # Fase 2: resumo da falha
    for codigo, info in sorted(ausentes.items()):   # um erro por código, ordenado
        log.error("  codigo=%r: %d linha(s) em %s",
                  codigo, info["linhas"], sorted(info["contratos"]))
    # saída: aborta a consolidação
    raise ValueError(
        f"{len(ausentes)} código(s) de localização sem par no DTB (relatório no log)")


def consolidar_csv(mapa, raw_dir, caminho_saida, log, dtb, *, incluir_projetos=False):
    """Junta todos os brutos num consolidado com uf/município resolvidos pelo DTB.

    Por que existe: entrega a base plana (contrato;odi;uc;uf;municipio[;projeto])
    juntando os brutos ao DTB em memória, em streaming. Escreve num .tmp e só promove
    ao definitivo se TODOS os códigos tiverem par — uma rodada falha NUNCA corrompe o
    consolidado anterior, e o relatório de ausentes sai completo numa rodada só
    (decisões do design 2026-07-20).

    Lógica, do input ao output, em fases:
      Entrada: mapa, raw_dir, caminho_saida, log, dtb {codigo: (uf, municipio)},
               incluir_projetos.
      Fase 1 — abre o .tmp (utf-8-sig, ';') e escreve o cabeçalho novo.
      Fase 2 — por contrato com bruto presente: extrai linhas; resolve o código no dtb;
               código SEM par vai ao acumulador de ausentes (linha não é escrita).
      Fase 3 — com ausentes: loga o relatório completo (código, linhas, contratos),
               descarta o .tmp e levanta ValueError.
      Fase 4 — sem ausentes: promove o .tmp ao definitivo (rename atômico).
      Saída: total de linhas escritas.
    """
    caminho_saida.parent.mkdir(parents=True, exist_ok=True)  # garante output_ucs/
    tmp = caminho_saida.with_name(caminho_saida.name + ".tmp")  # alvo provisório da escrita
    ausentes = {}                                  # codigo -> {"linhas": n, "contratos": set}
    total = 0                                      # contador de linhas escritas (saída)
    with open(tmp, "w", encoding=config.CSV_ENCODING, newline="") as fh:  # Fase 1: abre o .tmp
        escritor = csv.writer(fh, delimiter=config.CSV_DELIMITADOR)  # ';' (padrão pt-BR)
        escritor.writerow(cabecalho_saida(incluir_projetos))  # cabeçalho (c/ uf/municipio)
        for contrato in mapa:                      # Fase 2: na ordem do mapa
            caminho = download.caminho_raw(contrato, raw_dir)  # bruto esperado
            if not caminho.exists():               # sem bruto => contrato não baixado ainda
                log.info("sem bruto para %s — fora da consolidação", contrato)
                continue
            n_contrato = 0                         # linhas escritas deste contrato
            for t in extrair_linhas(caminho, incluir_projetos):  # (odi, uc, codigo[, proj])
                par = dtb.get(t[2])                # t[2] = código normalizado -> (uf, mun)?
                if par is None:                    # sem par => acumula e NÃO escreve
                    _registrar_ausente(ausentes, t[2], contrato)  # helper compartilhado
                    continue
                escritor.writerow((contrato, t[0], t[1], par[0], par[1], *t[3:]))  # linha final
                n_contrato += 1                    # soma do contrato
            total += n_contrato                    # soma geral
            log.info("%s: %d linhas consolidadas", contrato, n_contrato)
    if ausentes:                                   # Fase 3: falha com relatório COMPLETO
        tmp.unlink()                               # descarta o parcial (nada foi promovido)
        _falhar_se_ausentes(ausentes, log, caminho_saida.name)  # loga tudo e levanta
    tmp.replace(caminho_saida)                     # Fase 4: promove o .tmp ao definitivo
    log.info("%s: %d linhas no total", caminho_saida.name, total)
    return total                                   # saída: total de linhas


def consolidar_sqlite(mapa, raw_dir, db_path, log, dtb, *, incluir_projetos=False):
    """Carrega a base (já com uf/município) num SQLite indexado por ODI e UC (opcional).

    Por que existe: consultas pontuais (esta UC/ODI existe? de que município?) sem
    carregar tudo na memória. Derivado dos brutos + DTB (regenerável) — seguro recriar
    do zero. Mesma regra de falha da consolidar_csv: código sem par => apaga o banco
    parcial e falha (o db é regenerável; nunca fica versão meio-carregada).

    Lógica, do input ao output, em fases:
      Entrada: mapa, raw_dir, db_path, log, dtb, incluir_projetos.
      Fase 1 — (re)cria a tabela 'ucs' do zero, com as colunas novas.
      Fase 2 — por contrato com bruto: resolve codigo->(uf,municipio) e insere em lote;
               código sem par vai ao acumulador de ausentes.
      Fase 3 — com ausentes: fecha, tenta apagar o db parcial (falha de apagar só gera
               warning, NUNCA engole o relatório) e levanta ValueError.
      Fase 4 — sem ausentes: cria índices em odi/uc e commita.
      Saída: total de linhas inseridas.
    """
    colunas = cabecalho_saida(incluir_projetos)    # nomes das colunas (c/ uf/municipio)
    placeholders = ",".join("?" * len(colunas))    # ?,?,... conforme o nº de colunas
    db_path.parent.mkdir(parents=True, exist_ok=True)  # garante a pasta
    ausentes = {}                                  # codigo -> {"linhas": n, "contratos": set}
    con = sqlite3.connect(db_path)                 # abre/cria o banco
    try:
        con.execute("DROP TABLE IF EXISTS ucs")    # Fase 1: recria do zero (idempotente)
        con.execute(                               # tabela TEXT com as colunas da base
            f"CREATE TABLE ucs ({', '.join(c + ' TEXT' for c in colunas)})")
        total = 0                                  # contador (saída)
        for contrato in mapa:                      # Fase 2: por contrato
            caminho = download.caminho_raw(contrato, raw_dir)  # bruto esperado
            if not caminho.exists():               # sem bruto => pula
                continue
            lote = []                              # linhas resolvidas deste contrato
            for t in extrair_linhas(caminho, incluir_projetos):  # (odi, uc, codigo[, proj])
                par = dtb.get(t[2])                # código -> (uf, municipio)?
                if par is None:                    # sem par => acumula (helper compartilhado)
                    _registrar_ausente(ausentes, t[2], contrato)  # mesma regra da CSV
                    continue
                lote.append((contrato, t[0], t[1], par[0], par[1], *t[3:]))  # linha final
            con.executemany(                       # insere o lote do contrato
                f"INSERT INTO ucs VALUES ({placeholders})", lote)
            total += len(lote)                     # soma
        if ausentes:                               # Fase 3: mesma falha da consolidar_csv
            con.close()                            # fecha antes de apagar (Windows exige)
            try:                                   # unlink pode falhar (lock transitório
                db_path.unlink()                   #   de antivírus/indexador no Windows)
            except OSError as exc:                 # falha ao apagar NÃO engole o relatório
                log.warning("não consegui apagar o ucs.db parcial: %r", exc)
            _falhar_se_ausentes(ausentes, log, "ucs.db")  # loga tudo e levanta
        con.execute("CREATE INDEX ix_ucs_odi ON ucs(odi)")  # Fase 4: índices p/ consulta
        con.execute("CREATE INDEX ix_ucs_uc ON ucs(uc)")
        con.commit()                               # persiste tudo
        log.info("ucs.db: %d linhas, índices em odi/uc", total)
        return total                               # saída: total inserido
    finally:
        try:
            con.close()                            # sempre fecha (2º close é no-op seguro)
        except sqlite3.ProgrammingError:           # já fechado na Fase 3 => ignora
            pass


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
