"""U3 — carregamento/validação do mapa e download do CSV de UCs por contrato.

Puro (testável no DEV): carregar_map, validar_mapeamento, sanitizar_nome, caminho_raw.
Rede (só na VPN): baixar (renderiza o relatório de um contrato em CSV e grava o bruto).

O bruto `output_ucs/raw/<contrato>.csv` é a FONTE DA VERDADE (a consolidação/banco
derivam dele). Espelha o papel do exportar_pdf da Fase 1, mas via HTTP/SSPI (sem UI).
"""

import json                                  # leitura do ucs_map.json
import re                                    # sanitização do nome de arquivo

from ucs import config, ssrs_client          # constantes + cliente SSRS


def carregar_map(caminho=config.UCS_MAP):
    """Carrega o mapa contrato -> {codese, programa, ...} do JSON.

    Por que existe: ponto único de leitura do mapa (gerado na U2 a partir da recon),
    para o laço e a consolidação compartilharem a mesma fonte.

    Lógica, do input ao output:
      Entrada: caminho do ucs_map.json.
      Fase 1 — lê o arquivo como utf-8 e desserializa.
      Saída: dict {contrato: {codese, programa, concessionaria, programa_label}}.
    """
    with open(caminho, encoding="utf-8") as fh:   # Fase 1: abre o JSON em utf-8
        return json.load(fh)                       # saída: dict do mapa


def validar_mapeamento(mapa):
    """Falha cedo se o mapa estiver vazio ou com entrada sem codese/programa.

    Por que existe: melhor abortar antes de tocar a rede do que descobrir no meio da
    rodada que um contrato não tem como ser baixado (espelha contratos.validar_mapeamento
    da Fase 1).

    Lógica, do input ao output, em fases:
      Entrada: mapa (dict carregado).
      Fase 1 — exige pelo menos 1 contrato.
      Fase 2 — cada entrada precisa de 'codese' e 'programa' não-vazios.
      Saída: True se válido; senão levanta ValueError descrevendo o problema.
    """
    if not mapa:                                   # Fase 1: mapa vazio é erro
        raise ValueError("ucs_map.json vazio ou ausente")
    for contrato, info in mapa.items():            # Fase 2: confere cada contrato
        if not info.get("codese"):                 # codese é obrigatório (param 'codese')
            raise ValueError(f"{contrato}: 'codese' ausente no ucs_map.json")
        if not info.get("programa"):               # programa é obrigatório (param 'programa')
            raise ValueError(f"{contrato}: 'programa' ausente no ucs_map.json")
    return True                                    # saída: tudo certo


def sanitizar_nome(contrato):
    """Converte o código do contrato num nome de arquivo seguro.

    Por que existe: 'ECO 011/2018' tem '/' e espaço, inválidos em nome de arquivo;
    o CSV bruto é nomeado pelo contrato (chave primária), igual à Fase 1.

    Lógica: Entrada contrato. Fase 1 — troca não-alfanumérico por '_' e apara as bordas.
    Saída: nome seguro ('ECO_011_2018').
    """
    return re.sub(r"[^A-Za-z0-9]+", "_", contrato).strip("_")   # Fase 1/saída


def caminho_raw(contrato, raw_dir=config.RAW_DIR):
    """Caminho do CSV bruto de um contrato (output_ucs/raw/<contrato>.csv).

    Por que existe: baixar (grava) e consolidar (lê) precisam derivar o mesmo caminho
    a partir do contrato — um único ponto evita divergência.

    Lógica: Entrada contrato, raw_dir. Fase 1 — sanitiza e compõe o Path. Saída: Path.
    """
    return raw_dir / f"{sanitizar_nome(contrato)}.csv"          # Fase 1/saída


def baixar(sessao, contrato, info, log, *, destino=None):
    """Renderiza o relatório de UCs de UM contrato em CSV e grava o bruto.

    Por que existe: é o passo de rede que materializa a fonte da verdade por contrato;
    a recon já provou o render — aqui ele vira operação com validação e gravação.

    Lógica, do input ao output, em fases:
      Entrada: sessao autenticada, contrato, info (entrada do mapa com codese/programa),
               log, destino (Path; default = caminho_raw).
      Fase 1 — monta os nomes internos dos parâmetros e renderiza (codese, programa).
      Fase 2 — valida: HTTP 200 e conteúdo parecendo CSV (content-type csv OU header
               esperado com a coluna-âncora). Caso contrário, levanta erro (vira falha).
      Fase 3 — grava o bruto e conta as linhas de dados (linhas - 1 do header).
      Saída: dict {contrato, status:'baixado', n_linhas, n_bytes, destino}.
    """
    destino = destino or caminho_raw(contrato)     # Fase 1: caminho de saída
    nomes_params = {                               # nomes INTERNOS reais (recon U0)
        "concessionaria": config.PARAM_CONCESSIONARIA,   # 'codese'
        "programa": config.PARAM_PROGRAMA,               # 'programa'
    }
    status, ctype, conteudo = ssrs_client.render_csv(   # render CSV (codese/programa = códigos)
        sessao, info["codese"], info["programa"], nomes_params)

    ancora = config.COL_UC.encode("utf-8")         # Fase 2: coluna-âncora esperada no header
    parece_csv = "csv" in ctype.lower() or ancora in conteudo[:200]  # csv por tipo OU header
    if status != 200 or not parece_csv:            # qualquer desvio => falha explícita
        raise RuntimeError(                        # mensagem com o começo do corpo (debug cego)
            f"{contrato}: render inválido (HTTP {status}, {ctype}). "
            f"Início: {conteudo[:300]!r}")

    destino.parent.mkdir(parents=True, exist_ok=True)   # Fase 3: garante output_ucs/raw/
    destino.write_bytes(conteudo)                  # grava o CSV bruto (fonte da verdade)
    n_linhas = max(0, conteudo.count(b"\n") - 1)   # linhas de dados (desconta o header)
    log.info("%s: baixado %d linhas (%d bytes) -> %s",
             contrato, n_linhas, len(conteudo), destino.name)
    return {"contrato": contrato, "status": "baixado",   # saída: resultado do contrato
            "n_linhas": n_linhas, "n_bytes": len(conteudo), "destino": str(destino)}
