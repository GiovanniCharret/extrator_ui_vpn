"""F4 — parsing do PDF 'Projetos Executados' em (ODI, UF, Município).

Estratégia (do PLAN.md): pdfplumber dá coordenadas (x) de cada palavra; as faixas
das colunas ODI e Município são calculadas a partir dos CABEÇALHOS da 1ª página
(o cabeçalho seguinte, "Data Início", delimita o fim de Município) — nunca
hardcoded. Linha válida = token de 6+ dígitos na faixa do ODI (descarta cabeçalhos
repetidos, "Page N of M", títulos e totais). Município vem como "UF - NOME":
separa no primeiro " - ".
"""

import logging
import re

import pdfplumber

log = logging.getLogger("parse_pdf")

UFS = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
    "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
    "SP", "SE", "TO",
}

TOLERANCIA_LINHA = 3  # px de diferença em 'top' para considerar a mesma linha
# ODI = código do projeto, sempre na coluna mais à esquerda. É ALFANUMÉRICO: além
# de numérico (10010263) aparece com letras (ODR136PROJ019A, B0174334,
# PA2000112LPT130024PA) — VPN 17/06/2026. O regex antigo (^\d{6,}$) descartava
# silenciosamente esses; agora aceita qualquer token alfanumérico (sem espaço/
# pontuação). Linhas não-dado seguem barradas pela validação de UF do município.
RE_ODI = re.compile(r"^[A-Za-z0-9]+$")


def _x0_cabecalho(words, texto):
    """Menor x0 entre as ocorrências de `texto` no topo da página (área de cabeçalho)."""
    xs = [w["x0"] for w in words if w["text"] == texto and w["top"] < 200]
    return min(xs) if xs else None


def _faixas(words_pag1):
    """(proj_x0, muni_x0, data_x0) dos cabeçalhos da 1ª página."""
    proj_x0 = _x0_cabecalho(words_pag1, "Projeto")
    muni_x0 = _x0_cabecalho(words_pag1, "Município")
    data_x0 = _x0_cabecalho(words_pag1, "Data")  # 1ª "Data" = Data Início (menor x0)
    if None in (proj_x0, muni_x0, data_x0):
        raise ValueError("cabeçalhos ODI/Projeto/Município/Data não encontrados no PDF")
    return proj_x0, muni_x0, data_x0


def _agrupar_linhas(words):
    """Agrupa palavras por linha (mesmo 'top' dentro da tolerância). Ordena por x0."""
    linhas = []
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if linhas and abs(w["top"] - linhas[-1][0]) <= TOLERANCIA_LINHA:
            linhas[-1][1].append(w)
        else:
            linhas.append((w["top"], [w]))
    return [sorted(ws, key=lambda w: w["x0"]) for _, ws in linhas]


def _centro(w):
    return (w["x0"] + w["x1"]) / 2


def _split_municipio(texto):
    """'UF - NOME' -> (uf, nome) no primeiro ' - '. UF inválida vira warning (não exceção)."""
    partes = texto.split(" - ", 1)
    if len(partes) != 2:
        return None
    uf, municipio = partes[0].strip(), partes[1].strip()
    if uf not in UFS:
        log.warning("UF inválida em %r — linha ignorada", texto)
        return None
    return uf, municipio


def extrair_linhas(pdf_path):
    """-> list[tuple[odi, uf, municipio]] de todas as páginas do PDF."""
    resultado = []
    with pdfplumber.open(pdf_path) as doc:
        proj_x0, muni_x0, data_x0 = _faixas(doc.pages[0].extract_words())
        for page in doc.pages:
            for linha in _agrupar_linhas(page.extract_words()):
                # ODI: token alfanumérico à esquerda da coluna Projeto
                odi = next(
                    (w["text"] for w in linha
                     if _centro(w) < proj_x0 and RE_ODI.match(w["text"])),
                    None,
                )
                if not odi:
                    continue  # cabeçalho repetido, título, "Page N of M", totais
                muni_txt = " ".join(
                    w["text"] for w in linha if muni_x0 <= _centro(w) < data_x0
                )
                sep = _split_municipio(muni_txt)
                if sep is None:
                    continue
                resultado.append((odi, sep[0], sep[1]))
    return resultado
