"""Constantes da extração ÚNICA 2023-2025 (cópia de sqlprdrs-reports/, uso de uma vez só).

Diferenças p/ a Fase 2 diária: saídas em output/ (consolidado_ucs_2023-2025.csv), coluna
extra "PPC Status Web Descricao" e resolução, em tempo de execução, do código de programa
dos contratos que ainda não o têm no ucs_map (ver main.resolver_programas).

Constantes da Fase 2 (extração das UCs via SSRS) — pacote `ucs/`.

Confirmado nas telas manuais/export1.jpg / export2.jpg (Report Manager do SSRS,
18/06/2026): relatório 22.3-UCs_paraAprovacao, 2 parâmetros em cascata
(Concessionária → Programa), exportação CSV nativa. Os NOMES INTERNOS dos
parâmetros e o layout exato do CSV serão preenchidos APÓS a recon (U0) — por
enquanto a recon DESCOBRE os nomes (via SOAP GetItemParameters) e só usa os
"guesses" abaixo como plano B. Marcados com `TODO-U0` o que depende do retorno.

Espelha o papel de `src/config.py` (Fase 1): nada de URL/timeout/caminho espalhado
pelo código — tudo centralizado aqui.
"""

from pathlib import Path

# --- Caminhos -----------------------------------------------------------
# Raiz do projeto = duas pastas acima deste arquivo (ucs/config.py -> raiz).
BASE_DIR = Path(__file__).resolve().parent.parent
# Pasta de configs versionadas (compartilhada com a Fase 1).
CONFIG_DIR = BASE_DIR / "config"
# Mapa contrato -> {concessionaria, programa} (NOVO; montado na U2 a partir da recon).
UCS_MAP = CONFIG_DIR / "ucs_map.json"
# Raiz das saídas da extração 2023-2025 (pedido do usuário: output/, não output_ucs/).
OUTPUT_UCS_DIR = BASE_DIR / "output"
# CSV bruto por contrato = fonte da verdade (1 arquivo por contrato).
RAW_DIR = OUTPUT_UCS_DIR / "raw"
# Logs das rodadas.
LOGS_DIR = OUTPUT_UCS_DIR / "logs"
# Auditoria da resolução de programas: dropdowns consultados + par escolhido por contrato.
AUDITORIA_PROGRAMAS = OUTPUT_UCS_DIR / "programas_resolvidos.json"

# --- SSRS ---------------------------------------------------------------
# Host do SSRS na VPN (visto na barra de endereço das telas export1/2.jpg).
SSRS_HOST = "http://sqlprdrs"
# Report Manager (UI) — onde o usuário navega/exporta à mão (telas export1/2.jpg).
REPORT_MANAGER_URL = f"{SSRS_HOST}/Reports"
# Report Server (URL access + web service SOAP) — fica no MESMO host, em /ReportServer.
REPORT_SERVER_URL = f"{SSRS_HOST}/ReportServer"
# Endpoints SOAP de gerenciamento. O servidor é SSRS 2008 R2 (10.50, confirmado na
# recon 18/06): tem o ReportService2010.asmx (moderno) E o ReportService2005.asmx
# (legado). Tentamos o 2010 e caímos no 2005 — qual o servidor aceitar (ver get_parametros).
SOAP_SERVICE_2010 = f"{REPORT_SERVER_URL}/ReportService2010.asmx"
SOAP_SERVICE_2005 = f"{REPORT_SERVER_URL}/ReportService2005.asmx"
# Caminho do relatório no catálogo (barra de navegação em export1.jpg).
ITEM_PATH = "/LPT/Privados/Desenvolvidos/Projetos/22.3-UCs_paraAprovacao"

# Namespace/SOAPAction do ReportService2010. ATENÇÃO: é ".../ReportServer" (NÃO
# ".../ReportService") — confirmado pelo targetNamespace do WSDL real na recon 18/06
# (o erro da 1ª recon foi exatamente esse: "Server did not recognize ... SOAPAction").
# Método: GetItemParameters, com elemento <ItemPath>.
SOAP_NS_2010 = "http://schemas.microsoft.com/sqlserver/reporting/2010/03/01/ReportServer"
SOAP_ACTION_GETITEMPARAMETERS = f"{SOAP_NS_2010}/GetItemParameters"
# Namespace/SOAPAction do ReportService2005 (fallback). Método: GetReportParameters,
# com elemento <Report> (em vez de <ItemPath>).
SOAP_NS_2005 = "http://schemas.microsoft.com/sqlserver/2005/06/30/reporting/reportingservices"
SOAP_ACTION_GETREPORTPARAMETERS = f"{SOAP_NS_2005}/GetReportParameters"

# NOMES INTERNOS reais dos parâmetros — CONFIRMADOS na recon U0 (18/06/2026): o
# rótulo "Concessionária" é o parâmetro 'codese' (um código) e "Programa" é 'programa'
# (também código). É isso que vai na URL de render (não os textos da tela).
PARAM_CONCESSIONARIA = "codese"
PARAM_PROGRAMA = "programa"
# Combinação SOAP que funcionou: ReportService2010 (namespace ".../ReportServer") com
# o HistoryID OMITIDO. Ver ssrs_client.PARAM_COMBOS / montar_soap_parametros.
SOAP_COMBO = ("2010", False)
# Similaridade mínima (difflib, 0-1) p/ aceitar um programa por APROXIMAÇÃO quando o
# nome exato (normalizado) não existe no dropdown — só aceito se houver UM candidato.
SIMILARIDADE_MIN_PROGRAMA = 0.85

# Formato de render alvo (exportação nativa do SSRS; "CSV" = delimitado por vírgula).
RENDER_FORMAT_CSV = "CSV"

# Layout do CSV de ENTRADA (vindo do SSRS) — confirmado na amostra da recon U0:
# vírgula como separador, decimais "12,34" entre aspas, e BOM (utf-8-sig). 30 colunas.
CSV_IN_DELIMITADOR = ","
CSV_IN_ENCODING = "utf-8-sig"
# Colunas que interessam à base enxuta (U4). NÃO há município/UF neste relatório —
# ele é a base UC↔ODI; o município vem da Fase 1 (ODI→município), unido por ODI.
COL_UC = "UCP_Num_UC"                 # número da Unidade Consumidora
COL_ODI = "PPC_Odi"                   # Ordem de Imobilização (chave de junção c/ a Fase 1)
# Status do projeto no Web (texto, ex.: "Fechado em Lote") — coluna extra da extração 2023-2025.
COL_STATUS_WEB_DESCRICAO = "PPC_Status_Web_Descricao"
# Código IBGE de 7 dígitos do município da UC. O relatório 22.3 NÃO traz UF/município em
# texto (30 colunas conferidas) — só este código; UF e município saem do cruzamento com a
# tabela DTB do IBGE abaixo (regra do projeto, reconfirmada pelo usuário em 18/09/2026).
COL_LOCALIZACAO = "PPC_COD_LOCALIZACAO"

# --- Tabela de municípios (DTB/IBGE) ------------------------------------
# Entrada do pipeline (viaja no pacote, em entrada/). É o RELATORIO_DTB_BRASIL_<ano>_
# MUNICIPIOS do IBGE exportado em CSV ';': linhas 1-6 são título/cabeçalho do relatório,
# a linha de nomes de coluna vem depois — por isso a leitura PROCURA o cabeçalho pelo nome
# em vez de fixar a linha (sobrevive à troca do ano-base).
DTB_CSV = BASE_DIR / "entrada" / "RELATORIO_DTB_BRASIL_2024_MUNICIPIOS.csv"
DTB_ENCODING = "utf-8-sig"             # exportado com BOM
DTB_DELIMITADOR = ";"                  # padrão pt-BR
# Coluna H, com o código de 7 dígitos (inclui o dígito verificador). ATENÇÃO: o SSRS
# entrega o código com 6 dígitos (SEM o DV) — confirmado no bruto real em 21/07/2026 —,
# por isso municipios.carregar_dtb indexa cada município pelas DUAS chaves (7 e 6).
DTB_COL_CODIGO = "Código Município Completo"
DTB_COL_UF = "Nome_UF"                 # coluna B — UF por extenso ("Amapá"), como registrado
DTB_COL_MUNICIPIO = "Nome_Município"   # coluna I — nome do município, como registrado

# --- Timeouts (segundos) ------------------------------------------------
# GET simples (reachability) e POST SOAP (metadados de parâmetros).
TIMEOUT_HTTP = 60
# Render do relatório em CSV: é uma consulta pesada (o grid tem milhares de linhas).
TIMEOUT_RENDER = 300

# --- Estado / saída -----------------------------------------------------
# Estado da rodada (retomada), espelhando src/estado_execucao.json: fica em ucs/
# (NÃO em output_ucs/) por ser estado operacional, não resultado. Usado a partir da U5.
ESTADO_UCS_JSON = BASE_DIR / "ucs" / "estado_ucs.json"
# Quantas rodadas seguidas um contrato pode falhar antes de virar "desistido" (U5).
MAX_TENTATIVAS_CONTRATO = 3
# CSV de saída: utf-8-sig (Excel abre com acento) e ';' (padrão pt-BR), iguais à Fase 1.
CSV_ENCODING = "utf-8-sig"
CSV_DELIMITADOR = ";"
# Base consolidada da extração 2023-2025 (nome pedido pelo usuário em 30/09/2026).
CSV_CONSOLIDADO_UCS = OUTPUT_UCS_DIR / "consolidado_ucs_2023-2025.csv"
