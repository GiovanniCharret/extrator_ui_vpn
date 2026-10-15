"""U6 — lookup UF/município a partir do DTB/IBGE (módulo PURO: sem rede, testável no DEV).

O relatório SSRS traz só o código IBGE do município (PPC_COD_LOCALIZACAO); os nomes
vivem no DTB 2024, exportado como CSV em entrada/. Este módulo carrega o DTB uma vez
num dict {codigo: (uf, municipio)} para a consolidação (U4) resolver linha a linha.
Decisões no design 2026-07-20: código sem par => rodada falha com relatório completo.
"""

import csv                                     # leitura do CSV do DTB (stdlib)

from ucs import config                         # caminhos/nomes centralizados


def normalizar_codigo(valor):
    """Normaliza o código de município vindo de CSV para comparação exata no dict.

    Por que existe: o mesmo código pode chegar como '1100015', ' 1100015 ' ou
    '1100015.0' (Excel/SSRS); sem normalizar, o join falharia por diferença de formato,
    não de conteúdo. Centralizar aqui garante que DTB e bruto usam a MESMA regra.

    Lógica, do input ao output, em fases:
      Entrada: valor (string do CSV; tolera None).
      Fase 1 — vira string e tira espaços das pontas.
      Fase 2 — remove sufixo decimal se a parte fracionária for só zeros ('.0', '.000').
      Fase 3 — valida: só dígitos passa; qualquer outra coisa vira '' (nunca inventa código).
      Saída: string de dígitos ('' se vazio/não-numérico).
    """
    texto = str(valor or "").strip()           # Fase 1: string sem espaços (None vira "")
    if "." in texto:                           # Fase 2: possível sufixo decimal
        inteiro, _, fracao = texto.partition(".")   # separa parte inteira e fracionária
        if fracao.strip("0") == "":            # fração só de zeros => é inteiro disfarçado
            texto = inteiro                    # fica só a parte inteira
    return texto if texto.isdigit() else ""    # Fase 3/saída: dígitos ou ""


def carregar_dtb(caminho=config.DTB_CSV):
    """Carrega o DTB do IBGE num dict {codigo: (uf, municipio)} para o join da U4.

    Por que existe: a consolidação resolve ~1M linhas; um dict em memória dá lookup
    O(1) sem dependência nova. Ponto único de leitura do DTB — valida forma e conteúdo
    ANTES de qualquer bruto ser processado (falha cedo). Cada município entra com DUAS
    chaves: o código completo (7 dígitos) E o prefixo sem o dígito verificador (6) —
    o SSRS entrega 6 dígitos (confirmado no bruto real de 21/07/2026) e o prefixo é
    único no DTB 2024 (0 colisões, validado na mesma data).

    Lógica, do input ao output, em fases:
      Entrada: caminho do CSV do DTB (default: config.DTB_CSV em entrada/).
      Fase 1 — arquivo precisa existir (FileNotFoundError com o caminho).
      Fase 2 — varre linhas até achar o CABEÇALHO PELO CONTEÚDO (linha que contém as
               3 colunas esperadas) — robusto a mudanças no preâmbulo do IBGE.
      Fase 3 — linhas seguintes: normaliza o código e guarda (uf, municipio) nas duas
               chaves (7 e 6 dígitos); prefixo repetido => ValueError (lookup viraria
               loteria); linhas curtas/sem código são ignoradas.
      Fase 4 — valida o resultado: sem cabeçalho ou dict vazio => ValueError.
      Saída: dict {codigo7 e codigo6: (uf, municipio)}.
    """
    if not caminho.exists():                   # Fase 1: falha cedo com caminho claro
        raise FileNotFoundError(  # falha cedo com o caminho e a instrução de re-export
            f"DTB não encontrado: {caminho} — exporte o .ods do IBGE como CSV "
            f"(utf-8-sig, ';') para entrada/")
    esperadas = {config.DTB_COL_CODIGO, config.DTB_COL_UF, config.DTB_COL_MUNICIPIO}  # 3 colunas obrigatórias do cabeçalho
    idx = None                                 # índices das colunas (preenchido na Fase 2)
    mapa = {}                                  # acumulador {codigo: (uf, municipio)}
    with open(caminho, encoding=config.DTB_ENCODING, newline="") as fh:  # abre c/ BOM
        for linha in csv.reader(fh, delimiter=config.DTB_DELIMITADOR):   # linha a linha
            nomes = [c.strip() for c in linha]                # células sem espaços nas pontas
            if idx is None:                    # Fase 2: ainda procurando o cabeçalho
                if esperadas <= set(nomes):    # linha contém as 3 colunas => é o cabeçalho
                    idx = {nome: i for i, nome in enumerate(nomes)}  # nome -> índice
                continue                       # preâmbulo (ou o próprio cabeçalho): segue p/ a próxima linha
            i_cod = idx[config.DTB_COL_CODIGO]                # Fase 3: índices das 3 colunas
            i_uf, i_mun = idx[config.DTB_COL_UF], idx[config.DTB_COL_MUNICIPIO]  # índices de uf e município
            if len(linha) <= max(i_cod, i_uf, i_mun):         # linha curta => não é dado
                continue                       # ignora a linha curta (não é linha de dados)
            codigo = normalizar_codigo(linha[i_cod])          # código na regra única do join
            if not codigo:                     # sem código utilizável => ignora a linha
                continue                       # ignora a linha sem código utilizável
            par = (linha[i_uf].strip(), linha[i_mun].strip())  # (uf, municipio) da linha
            mapa[codigo] = par                 # chave completa (7 dígitos, com DV)
            prefixo = codigo[:6]               # chave do formato SSRS (6 dígitos, sem DV)
            if prefixo in mapa and mapa[prefixo] != par:      # prefixo já usado por OUTRO município
                raise ValueError(              # colisão de prefixo => lookup ambíguo; aborta
                    f"{caminho}: prefixo de 6 dígitos colidente no DTB: {prefixo!r} "
                    f"({mapa[prefixo]} vs {par})")
            mapa[prefixo] = par                # registra também o prefixo sem DV
    if idx is None:                            # Fase 4: nunca achou o cabeçalho
        raise ValueError(  # sem cabeçalho => ValueError
            f"{caminho}: cabeçalho não encontrado — esperava colunas {sorted(esperadas)}")
    if not mapa:                               # cabeçalho ok mas zero municípios
        raise ValueError(f"{caminho}: nenhum município carregado (arquivo truncado?)")  # dict vazio => ValueError
    return mapa                                # saída: dict do join
