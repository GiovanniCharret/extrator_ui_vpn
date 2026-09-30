"""Cliente SSRS — ponto ÚNICO do "como falar com o servidor de relatórios".

Concentra, num só módulo, (a) a montagem das URLs de URL-access (render em CSV),
(b) a montagem da requisição SOAP GetItemParameters e o parse da resposta, e
(c) a criação da sessão HTTP com autenticação Windows (SSPI/Negotiate). Isolar
aqui mantém `recon.py`/`download.py` agnósticos ao protocolo e deixa as partes
PURAS (montar URL, parsear XML) testáveis offline, sem rede.

Decisão (PLAN_part2, 18/06/2026): alvo = HTTP/SSPI (sem navegador); a recon (U0)
confirma se o servidor permite URL-access. A autenticação usa a sessão Windows da
VPN (requests-negotiate-sspi) — mesma premissa de "sessão ativa" da Fase 1.
"""

import urllib.parse                      # codificação de URL (path do relatório + params)
import xml.etree.ElementTree as ET       # parse da resposta SOAP (stdlib, sem dep nova)

from ucs import config                   # constantes centralizadas (URLs, NS, timeouts)


# =====================================================================
#  Partes PURAS (testáveis offline, sem rede)
# =====================================================================

def montar_url_render(item_path, params, *, fmt=config.RENDER_FORMAT_CSV,
                      server_url=config.REPORT_SERVER_URL):
    """Monta a URL de URL-access do SSRS que renderiza um relatório já filtrado.

    Por que existe: a forma de pedir o relatório (path + parâmetros + comando +
    formato) é detalhe do protocolo SSRS; centralizá-la num helper puro evita
    espalhar concatenação de URL pelo código e permite testar a montagem sem rede.

    Lógica, do input ao output, em fases:
      Entrada: item_path (caminho do relatório no catálogo), params (dict
               {nome_do_parâmetro: valor}), fmt (formato de render), server_url.
      Fase 1 — codifica o item_path como o 1º componente da query (SSRS espera o
               caminho logo após '?', com '/' escapado para %2f).
      Fase 2 — junta os parâmetros do relatório aos comandos do SSRS
               (rs:Command=Render e rs:Format=<fmt>) e os codifica como query.
      Saída: string da URL completa pronta para um GET autenticado.
    """
    caminho = urllib.parse.quote(item_path, safe="")   # Fase 1: path escapado (/, ç, espaços)
    consulta = dict(params)                             # Fase 2: cópia p/ não mutar o dict do chamador
    consulta["rs:Command"] = "Render"                  # comando SSRS: renderizar o relatório
    consulta["rs:Format"] = fmt                        # formato de saída (ex.: CSV)
    query = urllib.parse.urlencode(consulta)           # serializa params (com escape) em a=b&c=d
    return f"{server_url}?{caminho}&{query}"           # saída: URL completa de URL-access


def montar_soap_parametros(item_path, valores=None, versao="2010", incluir_history=False):
    """Monta a requisição SOAP que lista os parâmetros (nomes, valores válidos, dependências).

    Por que existe: descobrir os NOMES INTERNOS dos parâmetros e enumerar os
    dropdowns (inclusive a cascata Concessionária→Programa) é o coração da recon. O
    servidor é SSRS 2008 R2 e aceita dois dialetos: ReportService2010
    (GetItemParameters/<ItemPath>) ou o legado ReportService2005
    (GetReportParameters/<Report>). Este helper monta QUALQUER um dos dois — puro,
    testável sem servidor — e get_parametros tenta as combinações.

    Nota (recon 18/06): o `<HistoryID xsi:nil="true"/>` faz o 2005 falhar com
    "snapshotID does not match the parameter type"; por isso o default é OMITIR o
    HistoryID (ele é opcional). `incluir_history=True` existe só p/ a recon comparar.

    Lógica, do input ao output, em fases:
      Entrada: item_path, valores (dict já fixado, p/ a cascata; None=nenhum),
               versao ("2010"|"2005"), incluir_history (manda <HistoryID> nil ou não).
      Fase 1 — escolhe método/elemento/namespace/ação conforme a versão.
      Fase 2 — monta o bloco <Values> com os parâmetros já fixados (cascata).
      Fase 3 — embrulha no envelope SOAP 1.1 com ForRendering=true (traz valores válidos).
      Saída: tupla (url, headers, body) pronta para um POST autenticado.
    """
    valores = valores or {}                            # sem valores fixados => cascata de 1º nível
    if versao == "2005":                               # Fase 1: dialeto legado (ReportService2005)
        url = config.SOAP_SERVICE_2005                 # endpoint .asmx do 2005
        ns = config.SOAP_NS_2005                       # namespace do 2005
        acao = config.SOAP_ACTION_GETREPORTPARAMETERS  # SOAPAction do GetReportParameters
        metodo = "GetReportParameters"                 # nome do método 2005
        elem_path = f"<Report>{_xml_escape(item_path)}</Report>"  # 2005 usa <Report>
    else:                                              # dialeto moderno (ReportService2010)
        url = config.SOAP_SERVICE_2010                 # endpoint .asmx do 2010
        ns = config.SOAP_NS_2010                       # namespace do 2010 (".../ReportServer")
        acao = config.SOAP_ACTION_GETITEMPARAMETERS    # SOAPAction do GetItemParameters
        metodo = "GetItemParameters"                   # nome do método 2010
        elem_path = f"<ItemPath>{_xml_escape(item_path)}</ItemPath>"  # 2010 usa <ItemPath>
    history = '<HistoryID xsi:nil="true"/>' if incluir_history else ""  # omitir por padrão (quirk do 2005)
    itens_valores = "".join(                            # Fase 2: cada par escolhido vira <ParameterValue>
        f"<ParameterValue><Name>{_xml_escape(n)}</Name>"
        f"<Value>{_xml_escape(v)}</Value></ParameterValue>"
        for n, v in valores.items()
    )
    body = (                                            # Fase 3: envelope SOAP 1.1
        '<?xml version="1.0" encoding="utf-8"?>'
        '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"'
        ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        '<soap:Body>'
        f'<{metodo} xmlns="{ns}">'                      # método no namespace certo
        f'{elem_path}'                                  # <ItemPath> (2010) ou <Report> (2005)
        f'{history}'                                    # <HistoryID> só se incluir_history
        '<ForRendering>true</ForRendering>'            # true => traz valores válidos/cascata
        f'<Values>{itens_valores}</Values>'            # parâmetros já fixados (cascata)
        '<Credentials/>'                               # sem credenciais de fonte de dados
        f'</{metodo}>'
        '</soap:Body></soap:Envelope>'
    )
    headers = {                                         # cabeçalhos exigidos pelo endpoint SOAP
        "Content-Type": "text/xml; charset=utf-8",     # SOAP 1.1 é XML
        "SOAPAction": f'"{acao}"',                      # ação (entre aspas, exigência SOAP 1.1)
    }
    return url, headers, body                           # saída: (url, headers, body)


def _local(tag):
    """Remove o namespace de um tag XML ('{ns}Nome' -> 'Nome').

    Por que existe: a resposta SOAP do SSRS é cheia de namespaces; comparar pelo
    nome local deixa o parse robusto a prefixos/namespaces que variam por versão.

    Lógica: Entrada tag com possível '{...}'. Fase 1 — corta tudo até '}'.
    Saída: nome local.
    """
    return tag.rsplit("}", 1)[-1]                      # Fase 1: pega o trecho após o '}' (ou o todo)


def _xml_escape(texto):
    """Escapa um texto para inserção segura no corpo XML do SOAP.

    Por que existe: nomes de programa têm '&', '<' etc.; sem escape o envelope
    SOAP quebraria. Helper pequeno e puro.

    Lógica: Entrada texto. Fase 1 — troca os 3 caracteres perigosos. Saída: texto seguro.
    """
    return (str(texto)                                 # garante string
            .replace("&", "&amp;")                     # & deve vir 1º (senão re-escaparia os outros)
            .replace("<", "&lt;")                      # abre tag
            .replace(">", "&gt;"))                     # fecha tag


def parse_parametros(xml_text):
    """Extrai os parâmetros (nome, valores válidos, dependências) da resposta SOAP.

    Por que existe: a recon precisa, da resposta crua, dos NOMES dos parâmetros e
    da lista de valores de cada dropdown (Label/Value) — inclusive saber quem
    depende de quem (cascata). Funciona p/ os DOIS dialetos: <ItemParameter> (2010)
    e <ReportParameter> (2005), e p/ as duas formas de listar dependências
    (<string> dentro de <Dependencies>, ou <Dependency>). Parse puro → testável.

    Lógica, do input ao output, em fases:
      Entrada: xml_text (corpo da resposta SOAP).
      Fase 1 — parseia o XML e varre os elementos de parâmetro (Item/Report).
      Fase 2 — por parâmetro: 1º <Name> = nome próprio; <ValidValue> -> (Label,Value).
      Fase 3 — dependências: qualquer texto dentro de um contêiner <Dependencies>.
      Saída: lista de dicts {name, valid_values:[(label,value)], dependencies:[nome]}.
    """
    raiz = ET.fromstring(xml_text)                     # Fase 1: árvore XML da resposta
    parametros = []                                    # acumulador (saída)
    for elem in raiz.iter():                           # varre toda a árvore
        if _local(elem.tag) not in ("ItemParameter", "ReportParameter"):  # 2010 ou 2005
            continue                                   # ignora os demais nós
        nome = None                                    # nome interno do parâmetro
        valores = []                                   # pares (label, value) dos valores válidos
        dependencias = []                              # nomes de parâmetros dos quais este depende
        for filho in elem.iter():                      # Fase 2: percorre o conteúdo do parâmetro
            local = _local(filho.tag)                  # nome local do sub-elemento
            if local == "Name" and nome is None:       # 1º <Name> = nome do próprio parâmetro
                nome = (filho.text or "").strip()      # guarda o nome (sem espaços nas bordas)
            elif local == "ValidValue":                # cada <ValidValue> = uma opção do dropdown
                label = ""                              # rótulo exibido
                value = ""                              # valor enviado ao SSRS
                for vv in filho:                        # lê Label e Value do ValidValue
                    if _local(vv.tag) == "Label":
                        label = (vv.text or "").strip()
                    elif _local(vv.tag) == "Value":
                        value = (vv.text or "").strip()
                valores.append((label, value))         # registra a opção
        for cont in elem.iter():                       # Fase 3: dependências (forma robusta)
            if _local(cont.tag) != "Dependencies":     # acha os contêineres <Dependencies>
                continue
            for child in cont:                         # cada filho (<string> ou <Dependency>) é um nome
                dep = (child.text or "").strip()       # nome do parâmetro do qual depende
                if dep:                                 # ignora vazios
                    dependencias.append(dep)
        if nome:                                       # só registra parâmetros nomeados
            parametros.append({                        # monta o registro do parâmetro
                "name": nome,                          # nome interno (o que vai na URL de render)
                "valid_values": valores,               # opções do dropdown (vazio se depende de outro)
                "dependencies": dependencias,          # de quem depende (vazio = parâmetro raiz)
            })
    return parametros                                  # saída: lista de parâmetros


def classificar_concessionaria_programa(parametros):
    """Adivinha qual parâmetro é a Concessionária (raiz) e qual é o Programa (dependente).

    Por que existe: a cascata exige saber QUEM fixar primeiro. O parâmetro raiz não
    tem dependências e já traz valores válidos; o dependente lista o raiz em
    Dependencies. Heurística isolada e pura → testável.

    Lógica, do input ao output, em fases:
      Entrada: parametros (saída de parse_getitemparameters).
      Fase 1 — raiz = primeiro sem dependências e com valores válidos.
      Fase 2 — dependente = primeiro que tem dependências (idealmente aponta p/ a raiz).
      Saída: tupla (nome_concessionaria | None, nome_programa | None).
    """
    raiz = next(                                       # Fase 1: parâmetro raiz (sem dependência, com valores)
        (p["name"] for p in parametros
         if not p["dependencies"] and p["valid_values"]),
        None,
    )
    dependente = next(                                 # Fase 2: parâmetro dependente (tem dependências)
        (p["name"] for p in parametros if p["dependencies"]),
        None,
    )
    return raiz, dependente                            # saída: (concessionaria, programa)


# =====================================================================
#  Partes de REDE (só rodam na VPN; não unit-testadas)
# =====================================================================

def criar_sessao():
    """Cria uma sessão HTTP autenticada com a sessão Windows (SSPI/Negotiate).

    Por que existe: o SSRS corporativo usa autenticação integrada do Windows; a
    sessão da VPN já está logada, então reaproveitamos essas credenciais sem pedir
    senha. Centralizar a criação evita repetir a configuração de auth.

    Lógica, do input ao output, em fases:
      Entrada: nenhuma (usa a sessão do usuário Windows corrente).
      Fase 1 — importa as libs de rede aqui dentro (são deps só desta fase; o
               import tardio mantém os helpers PUROS importáveis no DEV sem elas).
      Fase 2 — cria a Session e anexa o handler de autenticação Negotiate (SSPI).
      Saída: requests.Session pronta para GET/POST autenticados.
    """
    import requests                                    # Fase 1: dep de rede (import tardio)
    from requests_negotiate_sspi import HttpNegotiateAuth  # auth Windows via SSPI

    sessao = requests.Session()                        # Fase 2: sessão reutilizável (keep-alive)
    sessao.auth = HttpNegotiateAuth()                  # usa credenciais Windows da sessão atual
    return sessao                                      # saída: sessão autenticada


# Combinações (dialeto, incluir_history) tentadas na descoberta de parâmetros. Ordem
# escolhida pós-recon 18/06: omitir HistoryID primeiro (o nil quebrou o 2005).
PARAM_COMBOS = (("2010", False), ("2005", False), ("2010", True), ("2005", True))


def get_parametros(sessao, item_path, valores=None, *, combo=None, timeout=config.TIMEOUT_HTTP):
    """Lista os parâmetros do relatório, tentando combinações de dialeto/HistoryID.

    Por que existe: junta a montagem (pura) com o POST (rede) e resolve a
    incompatibilidade do servidor automaticamente — a recon descobre na 1ª chamada
    QUAL combinação (dialeto + forma do HistoryID) funciona e reusa na cascata. Devolve
    TODAS as tentativas cruas p/ a recon salvar (diagnóstico cego, sem perder nada).

    Lógica, do input ao output, em fases:
      Entrada: sessao, item_path, valores já fixados (cascata), combo (tupla
               (versao, incluir_history) p/ forçar; None = tentar a matriz), timeout.
      Fase 1 — define as combinações a tentar (a forçada, ou a matriz PARAM_COMBOS).
      Fase 2 — para cada uma: monta o SOAP, faz o POST, guarda o cru, parseia; se veio
               parâmetro, retorna já indicando a combinação vencedora.
      Fase 3 — se nenhuma rendeu parâmetros, devolve o último cru (p/ diagnóstico).
      Saída: tupla (xml_cru, parametros, combo_usado, tentativas) onde tentativas é
             lista de (versao, incluir_history, xml_cru).
    """
    combos = [combo] if combo else list(PARAM_COMBOS)  # Fase 1: forçada ou matriz
    tentativas = []                                    # (versao, hist, cru) de cada tentativa
    for (v, hist) in combos:                           # Fase 2: tenta cada combinação
        url, headers, body = montar_soap_parametros(item_path, valores, v, incluir_history=hist)
        resp = sessao.post(url, data=body.encode("utf-8"), headers=headers, timeout=timeout)  # POST
        tentativas.append((v, hist, resp.text))         # registra a tentativa (crua)
        parametros = parse_parametros(resp.text)        # XML -> parâmetros
        if parametros:                                  # achou => essa combinação serve
            return resp.text, parametros, (v, hist), tentativas  # saída antecipada
    ultimo = tentativas[-1][2] if tentativas else ""   # Fase 3: nada funcionou
    return ultimo, [], (combos[-1] if combos else None), tentativas  # cru p/ diagnóstico


def descobrir_nomes_por_render(sessao, item_path, *, max_params=6, timeout=config.TIMEOUT_HTTP):
    """Descobre os NOMES internos dos parâmetros forçando o render a reclamar, um a um.

    Por que existe: independe do SOAP. O render sem um parâmetro obrigatório responde
    "report parameter 'X'" (rsReportParameterValueNotSet) nomeando o 1º faltante; ao
    fixar um valor-dummy nele, o próximo faltante é revelado. É o backup robusto p/ os
    nomes quando o GetParameters falha (foi assim que descobrimos 'codese').

    Lógica, do input ao output, em fases:
      Entrada: sessao, item_path, max_params (trava de segurança), timeout.
      Fase 1 — começa sem valores; a cada volta, renderiza e lê o nome faltante.
      Fase 2 — fixa um dummy nesse nome e repete, acumulando os nomes em ordem.
      Fase 3 — para quando não há mais nome faltante (ou repetiu / atingiu o limite).
      Saída: tupla (nomes_em_ordem, paginas) — paginas = lista de (valores, html cru).
    """
    nomes = []                                         # nomes descobertos, em ordem
    paginas = []                                       # (valores_usados, html) p/ a recon salvar
    valores = {}                                       # acumulador de dummies
    for _ in range(max_params):                        # Fase 1/2: itera até o limite
        url = montar_url_render(item_path, valores)     # render com o que já temos
        resp = sessao.get(url, timeout=timeout)         # GET autenticado
        paginas.append((dict(valores), resp.text))      # guarda a página crua
        nome = _param_faltante(resp.text)               # extrai o nome faltante do erro
        if not nome or nome in valores:                # Fase 3: sem novidade => para
            break
        nomes.append(nome)                              # registra o nome
        valores[nome] = "0"                             # dummy p/ destravar o próximo
    return nomes, paginas                              # saída: nomes + páginas cruas


def _param_faltante(html):
    """Extrai o nome do parâmetro faltante de uma página de erro do SSRS.

    Por que existe: o nome interno vem entre aspas na mensagem rsReportParameterValueNotSet
    ("...report parameter 'codese'..."). Helper puro p/ descobrir_nomes_por_render.

    Lógica: Entrada html. Fase 1 — regex do 1º "parameter 'X'". Saída: X ou None.
    """
    import re                                           # regex local (uso pontual)
    m = re.search(r"parameter '([^']+)'", html or "")  # Fase 1: 1ª ocorrência "parameter 'X'"
    return m.group(1) if m else None                   # saída: nome ou None


def render_csv(sessao, concessionaria, programa, nomes_params, *,
               item_path=config.ITEM_PATH, timeout=config.TIMEOUT_RENDER):
    """Renderiza o relatório de UCs de um programa em CSV (bytes) via URL-access.

    Por que existe: é o passo que efetivamente baixa os dados; isolado aqui, a recon
    o usa p/ a amostra e a Fase 2 (U3) o reusa p/ baixar todos os contratos.

    Lógica, do input ao output, em fases:
      Entrada: sessao autenticada, valores de concessionária e programa, nomes_params
               (dict {'concessionaria': nome_interno, 'programa': nome_interno}),
               item_path, timeout.
      Fase 1 — monta o dict de parâmetros do relatório com os nomes internos reais.
      Fase 2 — monta a URL de render (CSV) e faz o GET autenticado.
      Saída: tupla (status_http, content_type, conteudo_bytes).
    """
    params = {                                          # Fase 1: parâmetros do relatório
        nomes_params["concessionaria"]: concessionaria,
        nomes_params["programa"]: programa,
    }
    url = montar_url_render(item_path, params)          # Fase 2: URL de URL-access (CSV)
    resp = sessao.get(url, timeout=timeout)            # GET autenticado (download)
    return resp.status_code, resp.headers.get("Content-Type", ""), resp.content  # saída
