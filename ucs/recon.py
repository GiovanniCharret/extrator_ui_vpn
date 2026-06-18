"""U0 — Recon do SSRS (execução CEGA): descobre o que falta antes de escrever U1–U5.

Roda na VPN e grava TUDO em output_ucs/recon/. Princípio (PLAN_part2, 18/06/2026):
**persistir tudo em bruto, parsear best-effort, nunca perder dado por falha de parse**
— assim, mesmo que a suposição sobre o formato do SSRS esteja errada, o usuário volta
com as respostas cruas e o parser é consertado no DEV.

Responde, por escrito, aos 4 desconhecidos da U0:
  1. HTTP/SSPI alcança o servidor? (decide HTTP × navegador)
  2. Quais são os NOMES INTERNOS dos parâmetros? (via SOAP GetItemParameters)
  3. Enumeração dos 2 dropdowns (cascata Concessionária→Programa) -> dropdowns.json
  4. Layout do CSV (header + amostra) -> define as colunas enxutas da U4

Uso (na VPN, com a sessão Windows ativa):  python -m ucs.recon
Plano B se o HTTP falhar: o script grava um guia de captura manual (navegador).
"""

import json                                # serializa dropdowns/params em JSON legível
import logging                             # log p/ arquivo + console (execução cega)
import sys                                 # reconfigura stdout p/ utf-8 e exit code
import traceback                           # tracebacks completos no log (debug cego)
from datetime import datetime              # timestamp do log/RECON.md

from ucs import config, ssrs_client        # constantes + cliente SSRS (puro + rede)


def _configurar_log():
    """Configura logging para arquivo (output_ucs/recon) e console, em utf-8.

    Por que existe: na execução cega o log É o resultado; precisa sair completo,
    com acentos, tanto em arquivo (p/ trazer da VPN) quanto no console (p/ o usuário ver).
    Espelha src/lnc_app._configurar_log.

    Lógica, do input ao output, em fases:
      Entrada: nenhuma.
      Fase 1 — força utf-8 no stdout (console Windows quebra acento por padrão).
      Fase 2 — garante a pasta de logs e monta o nome com timestamp.
      Fase 3 — instala handlers de arquivo + console.
      Saída: logger 'ucs.recon'.
    """
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # Fase 1: console aceita acento
    config.RECON_DIR.mkdir(parents=True, exist_ok=True)          # Fase 2: pasta da recon existe
    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)           # e a de logs também
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")               # carimbo de tempo do arquivo
    logging.basicConfig(                                         # Fase 3: arquivo + console
        level=logging.INFO,
        handlers=[
            logging.FileHandler(config.LOGS_DIR / f"recon_{ts}.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
        format="%(asctime)s %(levelname)s %(message)s",
    )
    return logging.getLogger("ucs.recon")                       # saída: logger nomeado


def _salvar(nome, conteudo, log):
    """Grava um artefato cru da recon em output_ucs/recon/<nome> (bytes ou texto).

    Por que existe: o valor da recon está nos arquivos crus trazidos da VPN; este
    helper padroniza a gravação (texto vira utf-8) e loga o caminho/tamanho.

    Lógica, do input ao output, em fases:
      Entrada: nome do arquivo, conteudo (str ou bytes), log.
      Fase 1 — normaliza para bytes (str -> utf-8).
      Fase 2 — escreve em RECON_DIR e loga tamanho.
      Saída: Path do arquivo gravado.
    """
    caminho = config.RECON_DIR / nome                  # destino dentro da pasta da recon
    dados = conteudo if isinstance(conteudo, bytes) else conteudo.encode("utf-8")  # Fase 1
    caminho.write_bytes(dados)                          # Fase 2: grava cru
    log.info("salvo %s (%d bytes)", caminho.name, len(dados))  # rastro p/ execução cega
    return caminho                                      # saída: caminho gravado


def etapa_reachability(sessao, log):
    """Etapa 1 — testa se o HTTP/SSPI alcança o Report Server (decide HTTP × navegador).

    Por que existe: antes de qualquer coisa, precisamos saber se o URL-access/SOAP é
    sequer acessível com a auth Windows; um 401/404 aqui já direciona p/ o fallback.

    Lógica, do input ao output, em fases:
      Entrada: sessao autenticada, log.
      Fase 1 — faz GET em alvos-chave (Report Server, Report Manager, .asmx do SOAP).
      Fase 2 — para cada alvo, registra status e salva um trecho do corpo cru.
      Saída: dict {url: status_ou_erro} (e arquivos crus em recon/).
    """
    alvos = {                                          # Fase 1: alvos de sondagem
        "report_server": config.REPORT_SERVER_URL,     # raiz do URL-access
        "report_manager": config.REPORT_MANAGER_URL,   # UI (deve responder também)
        "soap_asmx": config.SOAP_SERVICE_2010 + "?wsdl",  # WSDL do serviço SOAP
    }
    resultado = {}                                     # acumulador (status por alvo)
    for chave, url in alvos.items():                   # sonda cada alvo
        try:                                           # Fase 2: nunca deixa um alvo derrubar a etapa
            resp = sessao.get(url, timeout=config.TIMEOUT_HTTP)  # GET autenticado
            resultado[chave] = resp.status_code        # registra o status HTTP
            log.info("reachability %s -> HTTP %s (%s)", chave, resp.status_code,
                     resp.headers.get("Content-Type", ""))
            _salvar(f"reach_{chave}.txt",              # salva um trecho do corpo (debug)
                    f"GET {url}\nHTTP {resp.status_code}\n\n{resp.text[:4000]}", log)
        except Exception as exc:                        # falha de rede/auth/DNS
            resultado[chave] = f"ERRO: {exc!r}"        # registra o erro
            log.error("reachability %s FALHOU: %s", chave, exc)
    return resultado                                   # saída: status por alvo


def etapa_parametros(sessao, log):
    """Etapa 2 — descobre nomes dos parâmetros e enumera os 2 dropdowns (cascata).

    Por que existe: é o coração da recon — sem os nomes internos e a enumeração não
    dá p/ montar o ucs_map.json (U2) nem a URL de render (U3).

    Lógica, do input ao output, em fases:
      Entrada: sessao autenticada, log.
      Fase 1 — GetItemParameters de 1º nível (sem valores) -> nomes + valores da raiz.
      Fase 2 — classifica raiz (Concessionária) e dependente (Programa).
      Fase 3 — p/ cada valor da Concessionária, refaz o GetItemParameters fixando-o
               -> obtém os Programas daquela concessionária (cascata).
      Fase 4 — salva params.json (estrutura) e dropdowns.json (mapa enumerado).
      Saída: dict {nomes:{concessionaria,programa}, dropdowns:{conc: [programas]}}.
    """
    # Probe por render: descobre os NOMES internos um a um (independe do SOAP). Já
    # revelou 'codese' na recon anterior; aqui pega todos em ordem.
    try:
        nomes_probe, paginas = ssrs_client.descobrir_nomes_por_render(sessao, config.ITEM_PATH)
        for i, (_vals, html) in enumerate(paginas):    # salva cada página de erro crua
            _salvar(f"probe_{i}.html", html, log)
        log.info("nomes via probe (em ordem): %s", nomes_probe)
    except Exception as exc:                            # nunca derruba a etapa
        nomes_probe = []
        log.error("probe por render falhou: %s", exc)

    # SOAP: tenta a matriz (2010/2005 x history omit/nil) e SALVA TODAS as tentativas.
    cru, parametros, combo, tentativas = ssrs_client.get_parametros(sessao, config.ITEM_PATH)  # Fase 1
    for (v, hist, raw) in tentativas:                  # salva cada tentativa crua (diagnóstico)
        _salvar(f"getparams_{v}_{'nil' if hist else 'omit'}.xml", raw, log)
    _salvar("getitemparameters_nivel1.xml", cru, log)  # a que venceu (ou a última)
    log.info("combo SOAP que funcionou: %s | parâmetros: %s",
             combo, [p["name"] for p in parametros])

    nome_conc, nome_prog = ssrs_client.classificar_concessionaria_programa(parametros)  # Fase 2
    # Se o SOAP não classificou mas o probe achou nomes, usa os do probe (raiz=1º, prog=2º).
    if not nome_conc and nomes_probe:
        nome_conc = nomes_probe[0]
    if not nome_prog and len(nomes_probe) > 1:
        nome_prog = nomes_probe[1]
    log.info("classificação -> concessionaria=%r programa=%r", nome_conc, nome_prog)

    # valores válidos da Concessionária (raiz) já vieram no 1º nível
    conc_param = next((p for p in parametros if p["name"] == nome_conc), None)  # acha a raiz
    conc_values = [v for (_label, v) in conc_param["valid_values"]] if conc_param else []  # só os Values

    dropdowns = {}                                     # Fase 3: mapa concessionaria -> [(label,value)]
    amostra_par = None                                 # 1º par (conc,prog) VÁLIDO p/ render de amostra
    for valor_conc in conc_values:                     # itera cada concessionária (valor=código)
        try:                                           # nunca deixa uma concessionária derrubar a etapa
            xml_dep, params_dep, _c, _t = ssrs_client.get_parametros(  # fixa a concessionária (cascata)
                sessao, config.ITEM_PATH, valores={nome_conc: valor_conc}, combo=combo)
            prog_param = next((p for p in params_dep if p["name"] == nome_prog), None)  # acha o Programa
            programas = [list(par) for par in prog_param["valid_values"]] if prog_param else []  # (label,value)
            dropdowns[valor_conc] = programas          # registra os programas (label+value) dessa conc.
            log.info("  %s -> %d programas", valor_conc, len(programas))
            _salvar(f"params_{_slug(valor_conc)}.xml", xml_dep, log)  # XML cru da cascata
            if amostra_par is None and programas:      # guarda o 1º par válido (códigos) p/ a amostra
                amostra_par = {"conc_value": valor_conc,
                               "prog_label": programas[0][0], "prog_value": programas[0][1]}
        except Exception as exc:                        # erro nessa concessionária específica
            dropdowns[valor_conc] = f"ERRO: {exc!r}"   # registra mas segue
            log.error("  %s FALHOU: %s", valor_conc, exc)

    nomes = {"concessionaria": nome_conc, "programa": nome_prog,  # Fase 4: nomes descobertos
             "combo_soap": list(combo) if combo else None,  # qual combinação funcionou (p/ fixar na U1)
             "nomes_via_probe": nomes_probe}           # cross-check independente do SOAP
    _salvar("params.json", json.dumps(                 # estrutura completa dos parâmetros
        {"nomes": nomes, "parametros": parametros}, ensure_ascii=False, indent=2), log)
    _salvar("dropdowns.json", json.dumps(              # enumeração dos dropdowns (insumo da U2)
        dropdowns, ensure_ascii=False, indent=2), log)
    return {"nomes": nomes, "dropdowns": dropdowns, "amostra": amostra_par}  # saída


def etapa_amostra_csv(sessao, params, log):
    """Etapa 3 — renderiza 1 contrato em CSV (amostra) p/ revelar o layout das colunas.

    Por que existe: a U4 (consolidação) só sabe quais colunas são UC/ODI/município
    depois de ver um CSV real; esta etapa baixa um e salva header + amostra.

    Lógica, do input ao output, em fases:
      Entrada: sessao, params (saída da etapa 2: nomes internos + 'amostra' com um par
               conc/prog VÁLIDO em código), log.
      Fase 1 — resolve nomes internos (descobertos ou guesses) e o par de VALORES
               (códigos) a renderizar — preferindo o par válido achado na cascata.
      Fase 2 — renderiza esse par em CSV.
      Fase 3 — salva o conteúdo cru e loga status, content-type, tamanho e header.
      Saída: dict {status, content_type, n_bytes, primeira_linha}.
    """
    nomes = params.get("nomes", {}) if params else {}  # nomes internos descobertos
    amostra = params.get("amostra") if params else None  # par válido (códigos) da cascata
    nome_conc = nomes.get("concessionaria") or config.PARAM_CONCESSIONARIA_GUESSES[0]  # Fase 1
    nome_prog = nomes.get("programa") or config.PARAM_PROGRAMA_GUESSES[0]              # plano B
    nomes_params = {"concessionaria": nome_conc, "programa": nome_prog}                # dict p/ o cliente
    if amostra:                                        # usa os CÓDIGOS válidos (o render espera código)
        conc_val, prog_val = amostra["conc_value"], amostra["prog_value"]
        log.info("amostra usando códigos: %s=%s, %s=%s (programa=%r)",
                 nome_conc, conc_val, nome_prog, prog_val, amostra.get("prog_label"))
    else:                                              # plano B: rótulos do config (provável 500)
        conc_val, prog_val = config.AMOSTRA_CONCESSIONARIA, config.AMOSTRA_PROGRAMA

    status, ctype, conteudo = ssrs_client.render_csv(  # Fase 2: render CSV da amostra
        sessao, conc_val, prog_val, nomes_params)
    log.info("render amostra -> HTTP %s (%s, %d bytes)", status, ctype, len(conteudo))

    # Fase 3: salva cru com extensão pelo content-type — assim um erro HTML não se
    # disfarça de CSV e o usuário/DEV vê na hora o que o servidor devolveu.
    ct = ctype.lower()                                 # content-type normalizado
    ext = ("csv" if "csv" in ct else                   # CSV de verdade
           "html" if "html" in ct else                 # página de erro do SSRS
           "xml" if "xml" in ct else "bin")            # XML ou binário desconhecido
    _salvar(f"amostra_COELBA_11.{ext}", conteudo, log)
    primeira = conteudo.split(b"\n", 1)[0].decode("utf-8", "replace") if conteudo else ""  # header
    log.info("amostra header: %s", primeira[:500])     # mostra o cabeçalho no log
    return {"status": status, "content_type": ctype,   # saída: resumo da amostra
            "n_bytes": len(conteudo), "primeira_linha": primeira}


def escrever_recon_md(reach, params, amostra, log, erro_sessao=None):
    """Escreve o RECON.md — resumo legível que o usuário traz de volta da VPN.

    Por que existe: o usuário e o DEV precisam de um veredito rápido (HTTP funcionou?
    nomes? quantos programas? header do CSV?) sem ler logs longos. E, se a sessão HTTP
    nem pôde ser criada (ex.: deps faltando numa venv pré-existente), o RECON.md tem
    de DIZER isso — senão o run cego volta vazio e sem pista (foi o que ocorreu na 1ª recon).

    Lógica, do input ao output, em fases:
      Entrada: dicts das 3 etapas (reach, params, amostra), log, erro_sessao (str|None).
      Fase 1 — se houve erro de sessão, abre o md com um bloco de diagnóstico explícito.
      Fase 2 — monta o corpo com os 4 desconhecidos respondidos.
      Fase 3 — salva como recon/RECON.md.
      Saída: Path do RECON.md.
    """
    nomes = params.get("nomes", {})                    # nomes descobertos
    dropdowns = params.get("dropdowns", {})            # enumeração
    bloco_erro = []                                    # Fase 1: diagnóstico se a sessão falhou
    if erro_sessao:                                    # sem sessão => nada de rede rodou
        bloco_erro = [
            "## [!] FALHA AO CRIAR A SESSÃO HTTP — nenhuma etapa de rede rodou",
            f"- erro: `{erro_sessao}`",
            "- causa provável: as dependências da Fase 2 (`requests` / "
            "`requests-negotiate-sspi`) não estão na venv (venv pré-existente da Fase 1). "
            "O `run_recon.ps1` agora sincroniza as deps sempre — basta rodar de novo.",
            "",
        ]
    linhas = [                                         # Fase 2: corpo do markdown
        "# RECON U0 — relatório 22.3-UCs_paraAprovacao",
        f"_gerado em {datetime.now():%Y-%m-%d %H:%M:%S}_",
        "",
        *bloco_erro,
        "## 1. HTTP/SSPI alcança o servidor?",
        *([f"- `{k}` -> **{v}**" for k, v in reach.items()] or ["- (não testado)"]),
        "",
        "## 2. Nomes internos dos parâmetros",
        f"- Concessionária: **{nomes.get('concessionaria')!r}**",
        f"- Programa: **{nomes.get('programa')!r}**",
        "",
        "## 3. Dropdowns (cascata) — resumo",
        f"- concessionárias enumeradas: **{len(dropdowns)}**",
        *[f"  - {c}: {len(p) if isinstance(p, list) else p} programas" for c, p in dropdowns.items()],
        "- detalhe completo em `dropdowns.json`",
        "",
        "## 4. Amostra CSV (COELBA 11ª)",
        f"- HTTP **{amostra.get('status')}**, content-type `{amostra.get('content_type')}`, "
        f"{amostra.get('n_bytes')} bytes",
        f"- 1ª linha (header?): `{amostra.get('primeira_linha', '')[:300]}`",
        "",
        "> Se algo acima falhou, ver `fallback_manual.txt` e os arquivos crus desta pasta.",
    ]
    return _salvar("RECON.md", "\n".join(linhas), log)  # Fase 2/saída


def escrever_fallback_manual(log):
    """Grava o guia de captura MANUAL (navegador) — plano B se o HTTP falhar.

    Por que existe: uma viagem à VPN não pode ser desperdiçada; se o URL-access/SOAP
    falhar, o usuário ainda consegue trazer os dados à mão seguindo este guia.

    Lógica: Entrada log. Fase 1 — texto com os passos manuais. Fase 2 — salva. Saída: Path.
    """
    texto = (                                          # Fase 1: passos manuais (do fluxo das telas)
        "FALLBACK MANUAL — captura via navegador (só se o HTTP da recon falhou)\n"
        "====================================================================\n\n"
        "1. Abrir no navegador:\n"
        f"   {config.REPORT_MANAGER_URL}/Pages/Report.aspx?ItemPath="
        "%2fLPT%2fPrivados%2fDesenvolvidos%2fProjetos%2f22.3-UCs_paraAprovacao\n\n"
        "2. PARÂMETROS (anotar os nomes/opções):\n"
        "   - Concessionária: tirar print da lista COMPLETA de opções.\n"
        "   - Programa: para CADA concessionária, tirar print da lista de Programas.\n"
        "     (é a enumeração que vira o config/ucs_map.json)\n\n"
        "3. AMOSTRA: selecionar Concessionária=COELBA, Programa='COELBA 11ª TRANCHE "
        "REVISÃO 2', clicar 'Exibir Relatório', depois Exportar -> 'CSV (delimitado "
        "por vírgula)'. Trazer esse CSV.\n\n"
        "4. Trazer também: o print da barra de endereço ao exportar (às vezes mostra os "
        "nomes internos dos parâmetros na URL).\n\n"
        "Colocar tudo em vpn_resultados/ ao voltar.\n"
    )
    return _salvar("fallback_manual.txt", texto, log)  # Fase 2/saída


def main():
    """Orquestra a recon: roda as 3 etapas, sempre grava o que conseguiu, nunca aborta cega.

    Por que existe: ponto de entrada único (`python -m ucs.recon`) que amarra logging,
    sessão autenticada e as etapas, garantindo que mesmo com falha parcial o usuário
    volte com o máximo de informação.

    Lógica, do input ao output, em fases:
      Entrada: nenhuma (lê tudo do config).
      Fase 1 — configura log e escreve o fallback manual (sempre, mesmo se tudo falhar).
      Fase 2 — cria a sessão autenticada; roda reachability, parâmetros e amostra,
               cada etapa isolada em try/except.
      Fase 3 — consolida tudo no RECON.md.
      Saída: código de saída do processo (0 sempre que conseguiu gravar o resumo).
    """
    log = _configurar_log()                            # Fase 1: logging
    log.info("=== RECON U0 — 22.3-UCs_paraAprovacao ===")
    escrever_fallback_manual(log)                      # grava o plano B logo de cara

    reach, params, amostra = {}, {}, {}                # acumuladores (saída parcial garantida)
    erro_sessao = None                                 # texto do erro de sessão (vai p/ o RECON.md)
    try:                                               # Fase 2: a sessão exige as deps de rede
        sessao = ssrs_client.criar_sessao()            # sessão autenticada (SSPI)
    except Exception as exc:                            # sem deps/auth => registra e segue p/ o resumo
        erro_sessao = repr(exc)                         # guarda p/ surgir no RECON.md (run cego)
        log.error("não foi possível criar a sessão HTTP:\n%s", traceback.format_exc())
        sessao = None

    if sessao is not None:                             # só sonda a rede se há sessão
        try:
            reach = etapa_reachability(sessao, log)    # etapa 1
        except Exception:
            log.error("etapa_reachability falhou:\n%s", traceback.format_exc())
        try:
            params = etapa_parametros(sessao, log)     # etapa 2
        except Exception:
            log.error("etapa_parametros falhou:\n%s", traceback.format_exc())
        try:
            amostra = etapa_amostra_csv(sessao, params, log)  # etapa 3 (usa nomes + par válido)
        except Exception:
            log.error("etapa_amostra_csv falhou:\n%s", traceback.format_exc())

    escrever_recon_md(reach, params, amostra, log, erro_sessao)  # Fase 3: resumo legível (+ diagnóstico)
    log.info("=== RECON U0 concluída — ver output_ucs/recon/ ===")
    return 0                                            # saída: sucesso de gravação (mesmo com falha parcial)


def _slug(texto):
    """Transforma um valor em nome de arquivo seguro (p/ os XML crus por concessionária).

    Por que existe: nomes de concessionária podem ter espaço/acento; vira sufixo de arquivo.
    Lógica: Entrada texto. Fase 1 — mantém alfanumérico, troca o resto por '_'. Saída: slug.
    """
    return "".join(c if c.isalnum() else "_" for c in str(texto))[:40]  # Fase 1/saída


if __name__ == "__main__":                             # permite `python -m ucs.recon`
    sys.exit(main())                                   # propaga o código de saída
