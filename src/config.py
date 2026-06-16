"""Constantes do projeto: caminhos, timeouts e identificação de janelas do LNC.

Títulos/seletores CONFIRMADOS com os dumps reais da F1 (B1–B5, viagens de
12–16/06/2026, em vpn_resultados/). Exceções marcadas inline.
"""

from pathlib import Path

# --- Caminhos -----------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
BASE_CONTRATOS = BASE_DIR / "base_contratos.json"
CONFIG_DIR = BASE_DIR / "config"
PROGRAMAS_MAP = CONFIG_DIR / "programas_map.json"
PROGRAMAS_DROPDOWN = CONFIG_DIR / "programas_dropdown.json"
OUTPUT_DIR = BASE_DIR / "output"
PDF_DIR = OUTPUT_DIR / "pdf"
LOGS_DIR = OUTPUT_DIR / "logs"
INSPECAO_DIR = OUTPUT_DIR / "inspecao"
FIXTURES_DIR = BASE_DIR / "tests" / "fixtures"

# --- Sistema LPT --------------------------------------------------------
LNC_EXE = r"Z:\LNC\LNC.exe"
PRINTER_NAME = "Microsoft Print to PDF"

# Títulos de janela
TITULO_JANELA_PRINCIPAL_RE = "Sistema LPT.*"   # confirmado nos dumps da F1 (12/06/2026)
TITULO_PREVIEW = "Print Preview"               # confirmado no dump B4 (12/06/2026)
TITULO_DIALOGO_IMPRIMIR = "Imprimir"           # manuais/passo8.jpg; no fluxo real passa rápido (não capturado vivo)
TITULO_PROGRESSO = "Printing progress"         # confirmado no dump B5 (TQRProgressForm)
TITULO_SALVAR_COMO = "Salvar Saída de Impressão como"  # título REAL (não "Salvar como") — dump B5
TITULO_CONFIRMA_SOBRESCRITA = "Confirmar Salvar como"  # diálogo de sobrescrita padrão do Windows

# --- Diálogo "Salvar Saída de Impressão como" (Microsoft Print to PDF) — dump B5 ---
# Diálogo comum do Windows (#32770). Estratégia: digitar o caminho ABSOLUTO no
# campo Edit do nome e clicar "Sa&lvar" (ou Enter). É aqui que se define o PDF.
CLASSE_SALVAR_COMO = "#32770"
SALVAR_COMO_EDIT_NOME = "Edit"          # campo do nome do arquivo (class Edit, filho do ComboBox)
SALVAR_COMO_BOTAO = "Sa&lvar"           # & = acelerador (Alt+L); título literal do botão

# --- Janela de progresso da geração do PDF — dump B5 ---------------------
# TQRProgressForm 'Printing progress' com TProgressBar + botão "Cancel".
# Espera 4: esperar esta janela SUMIR + arquivo PDF com tamanho estável.
CLASSE_PROGRESSO = "TQRProgressForm"

# --- Preview (QuickReport) — dump B4, 12/06/2026 -------------------------
# Janela top-level TQRStandardPreview 'Print Preview' (maximizada; vai para
# TRÁS da principal ao perder o foco — set_focus antes de interagir; o app
# mantém formulários de preview antigos vivos -> limpeza deve fechá-los).
# "Pronto" = StatusBar com texto "Page N of M". Botões da toolbar não têm
# texto/HWND; identificação por posição (uia rects + manuais/passo7.jpg):
# zoom(3) | nav(4) | printer setup, IMPRIMIR | salvar, abrir | Close.
CLASSE_PREVIEW = "TQRStandardPreview"
# StatusBar do preview: 'Page N of M'. Enquanto renderiza mostra progresso
# ('0% Page 1 of 0', '50% Page 1 of 27'); pronto = SEM '%' e M>0 (grupo 1).
# A checagem do '%' fica em lnc_app._preview_pronto (VPN 16/06: clicávamos cedo).
PREVIEW_STATUS_PRONTO_RE = r"Page \d+ of (\d+)"

# --- Cliques por coordenada (controles sem HWND) — dumps B4/B5 -----------
# Botão "imprimir" da toolbar do preview: centro do Button9 uia (L212-235 ×
# T29-51); CONFIRMADO pelo tooltip THintWindow 'Print' em x~222. Preview é
# maximizado (L-8,T-8) => coords de cliente ~ coords de tela.
PREVIEW_BTN_IMPRIMIR_XY = (223, 40)
# Menu lateral TExchangeBar (L0..76 × T23..1021) é owner-drawn (sem filhos nos
# dois backends) => clique por coordenada. "Relatórios" é o 7º de 9 itens.
# ESTIMATIVA INICIAL a calibrar na 1ª viagem (PLAN_F1_F3 open question 1).
MENU_RELATORIOS_XY = (38, 760)

# --- Seletores do painel Relatórios (dumps da F1, viagem de 12/06/2026) ---
# O app é Delphi (VCL), não VB6. Radios/combos/datas são janelas win32 nativas;
# os botões da barra superior (Visualizar etc.) e os ITENS das listas só
# aparecem no backend uia. O menu lateral (TExchangeBar) é owner-drawn e
# invisível aos dois backends -> navegação por clique em coordenada.
CLASSE_JANELA_PRINCIPAL = "TfrmPrincipal"
ITEM_PROJETOS_EXECUTADOS = "7  - Projetos Executados"  # DOIS espaços após o 7 (literal do app)
TITULO_TAB_FILTROS = "Projetos Executados"     # TTabSheet/TabItem do painel de filtros
RADIO_PROGRAMA = "Programa"                    # TRadioButton (win32)
COMBO_PROGRAMA_BEST_MATCH = "ProgramaComboBox" # TComboBox; embrulhar com ComboBoxWrapper(handle)
RADIO_TIPO_PADRAO = "Eletrificação Rural"      # TGroupButton; conferir marcado, não alterar
BOTAO_VISUALIZAR = "Visualizar"                # uia, control_type=Button (sem HWND no win32)
BOTAO_PROIBIDO_REL_EXCEL = "Rel.Excel"         # NUNCA clicar (regra crítica)
DATA_INICIO_PADRAO = "01/01/2004"              # TMaskEdit; conferir, não alterar

# --- Timeouts (segundos) -------------------------------------------------
TIMEOUT_ABRIR_APP = 60        # LNC.exe iniciar e exibir a janela principal
TIMEOUT_PREVIEW = 180         # "Visualizar" -> janela Print Preview pronta (query SQL)
TIMEOUT_GERACAO = 300         # botão Imprimir desabilitado durante a geração (~1 min medido)
TIMEOUT_DIALOGO = 30          # diálogos comuns (Salvar como)
TIMEOUT_SOBRESCRITA = 3       # diálogo intermitente de sobrescrita
TIMEOUT_PROGRESSO = 120       # janela "Printing progress" sumir
ARQUIVO_ESTAVEL_INTERVALO = 1  # intervalo entre stats para considerar o PDF gravado

# --- Saída ---------------------------------------------------------------
CSV_CONSOLIDADO = OUTPUT_DIR / "consolidado.csv"
CSV_RELATORIO = OUTPUT_DIR / "relatorio_execucao.csv"
CSV_ENCODING = "utf-8-sig"
CSV_DELIMITADOR = ";"
