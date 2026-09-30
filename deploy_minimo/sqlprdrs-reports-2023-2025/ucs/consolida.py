"""U4 — consolidação dos CSVs brutos numa base enxuta UC↔ODI (extração única 2023-2025).

Puro/testável no DEV: extrair_linhas (1 CSV bruto -> linhas enxutas).
Orquestração: consolidar_csv (stream de todos os brutos -> config.CSV_CONSOLIDADO_UCS).

Streaming por contrato (stdlib csv) p/ não segurar ~1M linhas na memória. UF e município
saem do código IBGE da UC (PPC_COD_LOCALIZACAO) cruzado com o DTB — ver ucs/municipios.py.
Em relação à Fase 2 diária: +coluna "PPC Status Web Descricao"; sem SQLite/benchmark/projetos.
"""

import csv                                    # leitura/escrita CSV (stdlib)

from ucs import config, download, municipios  # constantes + caminho_raw + normalização DTB

# Colunas da base: UC↔ODI + localização resolvida via DTB (U6) + status do projeto no Web.
# O nome da última coluna foi pedido pelo usuário exatamente assim (30/09/2026).
COLS_BASE = ["contrato", "odi", "uc", "uf", "municipio", "PPC Status Web Descricao"]


def extrair_linhas(caminho):
    """Lê um CSV bruto do SSRS e devolve só as colunas que interessam à base.

    Por que existe: o relatório tem 30 colunas; a base só precisa de ODI, UC, código de
    localização e a descrição do status Web. Seleção por NOME de coluna (não posição)
    deixa a função pura/testável e resistente a reordenação.

    Lógica, do input ao output, em fases:
      Entrada: caminho de um output/raw/<contrato>.csv (vírgula, utf-8-sig, BOM).
      Fase 1 — abre o CSV e lê o header; mapeia nome-de-coluna -> índice.
      Fase 2 — exige as âncoras (UC, ODI, PPC_COD_LOCALIZACAO e PPC_Status_Web_Descricao);
               sem elas o arquivo é inválido (a coluna nova é o motivo desta extração).
      Fase 3 — por linha (pulando a placeholder vazia do SSRS), extrai (odi, uc,
               cod_localizacao normalizado, status_web_descricao).
      Saída: lista de tuplas (odi, uc, cod_localizacao, status_web_descricao).
    """
    with open(caminho, encoding=config.CSV_IN_ENCODING, newline="") as fh:  # Fase 1: abre (utf-8-sig tira BOM)
        leitor = csv.reader(fh, delimiter=config.CSV_IN_DELIMITADOR)        # vírgula como separador
        cabecalho = next(leitor, None)                 # 1ª linha = nomes das colunas
        if not cabecalho:                              # arquivo vazio => nada a extrair
            return []
        idx = {nome: i for i, nome in enumerate(cabecalho)}  # nome-de-coluna -> índice
        ancoras = (config.COL_UC, config.COL_ODI, config.COL_LOCALIZACAO,  # Fase 2: obrigatórias
                   config.COL_STATUS_WEB_DESCRICAO)
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
            odi = pega(linha, config.COL_ODI)          # ODI
            uc = pega(linha, config.COL_UC)            # número da UC
            if not odi and not uc:                     # linha-placeholder do SSRS (programa
                continue                               #   sem UCs): ODI e UC vazios => ignora
            linhas.append((odi, uc,                    # registra a linha enxuta
                           municipios.normalizar_codigo(pega(linha, config.COL_LOCALIZACAO)),
                           pega(linha, config.COL_STATUS_WEB_DESCRICAO)))  # status do projeto
        return linhas                                  # saída: linhas enxutas (sem o contrato)


def _registrar_ausente(ausentes, codigo, contrato):
    """Acumula um código de localização sem par no DTB.

    Por que existe: a contabilização dos códigos sem par (linhas e contratos afetados)
    alimenta o relatório de falha completo numa rodada só (decisão do usuário, 2026-07-20).

    Lógica: Entrada ausentes (dict acumulador), codigo, contrato. Fase 1 — garante a
    entrada do código. Fase 2 — soma a linha e registra o contrato. Saída: None (muta ausentes).
    """
    reg = ausentes.setdefault(codigo, {"linhas": 0, "contratos": set()})  # Fase 1: entrada
    reg["linhas"] += 1                              # Fase 2: conta a linha afetada
    reg["contratos"].add(contrato)                  # ...e o contrato afetado


def _falhar_se_ausentes(ausentes, log, alvo):
    """Loga o relatório COMPLETO de códigos sem par e falha.

    Por que existe: o relatório de falha (todos os códigos, linhas e contratos numa
    rodada só — decisão do design 2026-07-20) precisa sair inteiro no log (execução cega).

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


def consolidar_csv(mapa, raw_dir, caminho_saida, log, dtb):
    """Junta todos os brutos num consolidado com uf/município resolvidos pelo DTB.

    Por que existe: entrega a base plana (contrato;odi;uc;uf;municipio;PPC Status Web
    Descricao) juntando os brutos ao DTB em memória, em streaming. Escreve num .tmp e só
    promove ao definitivo se TODOS os códigos tiverem par — uma rodada falha NUNCA corrompe
    o consolidado anterior, e o relatório de ausentes sai completo numa rodada só.

    Lógica, do input ao output, em fases:
      Entrada: mapa, raw_dir, caminho_saida, log, dtb {codigo: (uf, municipio)}.
      Fase 1 — abre o .tmp (utf-8-sig, ';') e escreve o cabeçalho.
      Fase 2 — por contrato com bruto presente: extrai linhas; resolve o código no dtb;
               código SEM par vai ao acumulador de ausentes (linha não é escrita).
      Fase 3 — com ausentes: loga o relatório completo (código, linhas, contratos),
               descarta o .tmp e levanta ValueError.
      Fase 4 — sem ausentes: promove o .tmp ao definitivo (rename atômico).
      Saída: total de linhas escritas.
    """
    caminho_saida.parent.mkdir(parents=True, exist_ok=True)  # garante output/
    tmp = caminho_saida.with_name(caminho_saida.name + ".tmp")  # alvo provisório da escrita
    ausentes = {}                                  # codigo -> {"linhas": n, "contratos": set}
    total = 0                                      # contador de linhas escritas (saída)
    with open(tmp, "w", encoding=config.CSV_ENCODING, newline="") as fh:  # Fase 1: abre o .tmp
        escritor = csv.writer(fh, delimiter=config.CSV_DELIMITADOR)  # ';' (padrão pt-BR)
        escritor.writerow(COLS_BASE)               # cabeçalho (c/ uf/municipio/status)
        for contrato in mapa:                      # Fase 2: na ordem do mapa
            caminho = download.caminho_raw(contrato, raw_dir)  # bruto esperado
            if not caminho.exists():               # sem bruto => contrato não baixado
                log.info("sem bruto para %s — fora da consolidação", contrato)
                continue
            n_contrato = 0                         # linhas escritas deste contrato
            for odi, uc, codigo, status in extrair_linhas(caminho):  # linha enxuta do bruto
                par = dtb.get(codigo)              # código normalizado -> (uf, mun)?
                if par is None:                    # sem par => acumula e NÃO escreve
                    _registrar_ausente(ausentes, codigo, contrato)
                    continue
                escritor.writerow((contrato, odi, uc, par[0], par[1], status))  # linha final
                n_contrato += 1                    # soma do contrato
            total += n_contrato                    # soma geral
            log.info("%s: %d linhas consolidadas", contrato, n_contrato)
    if ausentes:                                   # Fase 3: falha com relatório COMPLETO
        tmp.unlink()                               # descarta o parcial (nada foi promovido)
        _falhar_se_ausentes(ausentes, log, caminho_saida.name)  # loga tudo e levanta
    tmp.replace(caminho_saida)                     # Fase 4: promove o .tmp ao definitivo
    log.info("%s: %d linhas no total", caminho_saida.name, total)
    return total                                   # saída: total de linhas
