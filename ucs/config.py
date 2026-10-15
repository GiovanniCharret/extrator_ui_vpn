"""Constantes da Fase 2 (extração das UCs via SSRS) — pacote `ucs/`.

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
# Raiz das saídas da Fase 2 (NÃO versionar — ver .gitignore).
OUTPUT_UCS_DIR = BASE_DIR / "output_ucs"
# CSV bruto por contrato = fonte da verdade (1 arquivo por contrato).
RAW_DIR = OUTPUT_UCS_DIR / "raw"
# Logs das rodadas/recon.
LOGS_DIR = OUTPUT_UCS_DIR / "logs"
# Dumps crus da recon (respostas HTTP/SOAP, amostra de CSV, RECON.md).
RECON_DIR = OUTPUT_UCS_DIR / "recon"
# Fixtures de teste (compartilhada com a Fase 1).
FIXTURES_DIR = BASE_DIR / "tests" / "fixtures"

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
# Chutes (plano B só p/ a recon, caso o SOAP falhe num servidor diferente).
PARAM_CONCESSIONARIA_GUESSES = ("codese", "Concessionaria", "Concessionária")
PARAM_PROGRAMA_GUESSES = ("programa", "Programa")

# Par de amostra p/ o teste de render da recon. Valores = CÓDIGOS (não rótulos):
# COELBA = codese 20; "COELBA 11ª TRANCHE REVISÃO 2" = programa 1520 (recon U0).
AMOSTRA_CONCESSIONARIA = "20"
AMOSTRA_PROGRAMA = "1520"

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
# Colunas de projeto — opcionais na saída (via --dados-projetos); usadas só como rastreio.
COL_COD_PROJETO = "PPC_Cod_Projeto"   # código do projeto
COL_NOME_PROJETO = "PPC_Nome_Projeto"  # nome/descrição do projeto
# Data de envio do projeto (16ª das 30 colunas do relatório). Entra na base desde
# 08/10/2026 a pedido do usuário; vai VERBATIM, como o SSRS registra (mesma regra de
# uf/município) — se um dia for preciso ordenar/comparar por ela, aí sim normalizar.
COL_DATA_ENVIO = "PPC_Data_Envio"
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
# Base consolidada (enxuta) e banco opcional (derivado dos brutos, regenerável).
# Sufixo "_modelo" no nome pedido pelo usuário em 18/09/2026 (o consumidor identifica o
# arquivo por esse nome) — trocar aqui muda a saída de toda a Fase 2.
CSV_CONSOLIDADO_UCS = OUTPUT_UCS_DIR / "consolidado_ucs_modelo.csv"
UCS_DB = OUTPUT_UCS_DIR / "ucs.db"
