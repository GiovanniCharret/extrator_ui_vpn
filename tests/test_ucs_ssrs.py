"""U0/U3 [AUTO] — partes PURAS do ssrs_client (montagem de URL/SOAP e parse de XML).

Offline no DEV, sem rede. A corretude contra o servidor real (status, render, nomes
reais) é validação [VPN] (recon U0). Aqui garantimos que a montagem da URL de render,
o envelope SOAP e o parse do GetItemParameters fazem o que prometem — usando um XML
sintético no MESMO formato documentado da API ReportService2010.
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from ucs import config, ssrs_client


# --- montar_url_render ------------------------------------------------------

def test_url_render_tem_comando_formato_e_path_escapado():
    url = ssrs_client.montar_url_render("/LPT/X/22.3", {"Concessionaria": "COELBA"})
    # path escapado (/, vira %2f) logo após o '?'
    assert "?%2FLPT%2FX%2F22.3" in url or "?%2flpt".lower() in url.lower()
    # comandos do SSRS presentes
    assert "rs%3ACommand=Render" in url
    assert "rs%3AFormat=CSV" in url
    # o parâmetro do relatório foi incluído
    assert "Concessionaria=COELBA" in url


def test_url_render_escapa_valor_com_espaco_e_acento():
    url = ssrs_client.montar_url_render(
        config.ITEM_PATH, {"Programa": "COELBA 11ª TRANCHE REVISÃO 2"})
    # espaço vira '+' ou '%20'; o 'ª'/acento é percent-encoded (não vaza cru)
    assert "Programa=" in url
    assert " " not in url.split("Programa=", 1)[1]


# --- montar_soap_parametros (2010 e 2005) ----------------------------------

def test_soap_2010_tem_acao_itempath_e_forrendering():
    url, headers, body = ssrs_client.montar_soap_parametros("/LPT/X/22.3")
    assert url == config.SOAP_SERVICE_2010
    assert headers["SOAPAction"].strip('"') == config.SOAP_ACTION_GETITEMPARAMETERS
    # 2010 usa GetItemParameters/<ItemPath> no namespace ".../ReportServer"
    assert "<GetItemParameters" in body
    assert "<ItemPath>/LPT/X/22.3</ItemPath>" in body
    # namespace correto é ".../2010/03/01/ReportServer" (não "ReportService")
    assert '2010/03/01/ReportServer"' in body
    assert "<ForRendering>true</ForRendering>" in body
    assert "<Values></Values>" in body  # sem valores fixados => bloco vazio


def test_soap_2005_usa_getreportparameters_e_report():
    url, headers, body = ssrs_client.montar_soap_parametros("/LPT/X/22.3", versao="2005")
    assert url == config.SOAP_SERVICE_2005
    assert headers["SOAPAction"].strip('"') == config.SOAP_ACTION_GETREPORTPARAMETERS
    # 2005 usa GetReportParameters/<Report>
    assert "<GetReportParameters" in body
    assert "<Report>/LPT/X/22.3</Report>" in body


def test_soap_envelope_inclui_valores_da_cascata_escapados():
    _u, _h, body = ssrs_client.montar_soap_parametros(
        "/LPT/X/22.3", valores={"Concessionaria": "LIGHT & CIA"})
    assert "<Name>Concessionaria</Name>" in body
    # '&' do valor foi escapado p/ não quebrar o XML
    assert "LIGHT &amp; CIA" in body


# --- parse_parametros + classificação --------------------------------------

# XML sintético no formato real: ItemParameter (2010), Dependencies via <string>
# (ArrayOfString). Concessionaria = raiz (com ValidValues); Programa = dependente.
XML_PARAMS = """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
 <soap:Body>
  <GetItemParametersResponse xmlns="http://schemas.microsoft.com/sqlserver/reporting/2010/03/01/ReportServer">
   <Parameters>
    <ItemParameter>
      <Name>Concessionaria</Name>
      <ValidValues>
        <ValidValue><Label>COELBA</Label><Value>COELBA</Value></ValidValue>
        <ValidValue><Label>CELPA</Label><Value>CELPA</Value></ValidValue>
      </ValidValues>
    </ItemParameter>
    <ItemParameter>
      <Name>Programa</Name>
      <Dependencies><string>Concessionaria</string></Dependencies>
      <ValidValues/>
    </ItemParameter>
   </Parameters>
  </GetItemParametersResponse>
 </soap:Body>
</soap:Envelope>"""

# XML sintético do dialeto 2005: ReportParameter (em vez de ItemParameter).
XML_PARAMS_2005 = XML_PARAMS.replace("ItemParameter", "ReportParameter")


def test_parse_extrai_nomes_valores_e_dependencias():
    params = ssrs_client.parse_parametros(XML_PARAMS)
    por_nome = {p["name"]: p for p in params}
    assert set(por_nome) == {"Concessionaria", "Programa"}
    # a raiz traz os valores válidos (os dois Values)
    assert [v for (_l, v) in por_nome["Concessionaria"]["valid_values"]] == ["COELBA", "CELPA"]
    assert por_nome["Concessionaria"]["dependencies"] == []
    # o dependente lista a raiz (via <string>) e ainda não tem valores (cascata)
    assert por_nome["Programa"]["dependencies"] == ["Concessionaria"]
    assert por_nome["Programa"]["valid_values"] == []


def test_parse_tambem_entende_reportparameter_2005():
    params = ssrs_client.parse_parametros(XML_PARAMS_2005)
    assert {p["name"] for p in params} == {"Concessionaria", "Programa"}


def test_classificar_acha_raiz_e_dependente():
    params = ssrs_client.parse_parametros(XML_PARAMS)
    conc, prog = ssrs_client.classificar_concessionaria_programa(params)
    assert conc == "Concessionaria"
    assert prog == "Programa"


# --- _param_faltante (descoberta de nome por render) ------------------------

def test_param_faltante_extrai_nome_da_pagina_de_erro():
    # texto real da recon 18/06 (rsReportParameterValueNotSet)
    html = ("<li>This report requires a default or user-defined value for the "
            "report parameter 'codese'. (rsReportParameterValueNotSet)</li>")
    assert ssrs_client._param_faltante(html) == "codese"


def test_param_faltante_none_quando_nao_ha_erro_de_parametro():
    assert ssrs_client._param_faltante("<html>relatório ok</html>") is None
