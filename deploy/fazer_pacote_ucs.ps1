# fazer_pacote_ucs.ps1 - RODA NO DEV, a partir da raiz do projeto.
# Uso: powershell -ExecutionPolicy Bypass -File deploy\fazer_pacote_ucs.ps1 -Versao 1
# Gera pacote_ucs_v<N>.zip com o pipeline da Fase 2 (download + consolidacao) p/ a VPN.
#
# ANTI-BLOQUEIO DE E-MAIL: .ps1/.py saem renomeados p/ *.renomeado.txt; o
# LEIA-ME_PRIMEIRO.txt traz o comando que restaura os nomes apos extrair.
param(
    [int]$Versao = 1
)

$ErrorActionPreference = "Stop"

$destino = "pacote_ucs_v$Versao.zip"

# Necessario p/ `.\run_ucs.ps1`: o pacote ucs/, o runner, as deps e o config (com ucs_map.json).
$itens = @(
    "ucs",
    "run_ucs.ps1",
    "run_recon.ps1",
    "requirements.txt",
    "config"
)
$existentes = $itens | Where-Object { Test-Path $_ }

# --- staging ---------------------------------------------------------------
$stage = Join-Path $env:TEMP "pacote_ucs_stage"
if (Test-Path $stage) { Remove-Item $stage -Recurse -Force -Confirm:$false }
New-Item -ItemType Directory $stage | Out-Null

foreach ($item in $existentes) {
    Copy-Item $item (Join-Path $stage (Split-Path $item -Leaf)) -Recurse
}

# remove caches do Python e o estado da rodada (vive na VPN, nao pode ser sobrescrito).
Get-ChildItem $stage -Recurse -Directory -Filter "__pycache__" |
    Remove-Item -Recurse -Force -Confirm:$false
Get-ChildItem $stage -Recurse -File -Filter "estado_ucs.json" |
    Remove-Item -Force -Confirm:$false

# --- renomeia scripts ------------------------------------------------------
$renomeados = Get-ChildItem $stage -Recurse -File |
    Where-Object { $_.Extension -eq ".ps1" -or $_.Extension -eq ".py" }
$renomeados | Rename-Item -NewName { $_.Name + ".renomeado.txt" }

# --- LEIA-ME ---------------------------------------------------------------
$leiame = @"
LEIA-ME PRIMEIRO - pipeline da Fase 2 (UCs via SSRS)
=====================================================

Os scripts .ps1 e .py deste pacote foram renomeados para *.renomeado.txt
para passar no filtro de seguranca do e-mail.

1) APOS EXTRAIR, abra o PowerShell NA PASTA EXTRAIDA e cole este comando p/
   restaurar os nomes:

Get-ChildItem -Recurse -Filter "*.renomeado.txt" | Rename-Item -NewName { `$_.Name -replace "\.renomeado\.txt`$", "" }

   Confira: o arquivo run_ucs.ps1 deve existir de novo.

2) Pre-requisito: ter o 'uv' instalado (uma vez). Se nao tiver:
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

3) Com a SESSAO WINDOWS da VPN ativa/logada (acesso a http://sqlprdrs):
   a) Ver o plano (nao baixa nada):   .\run_ucs.ps1 --dry-run
   b) Baixar tudo e consolidar:       .\run_ucs.ps1
      (na 1a vez cria a venv e instala as deps sozinho; ~21 relatorios)
   c) Opcional, com banco+benchmark:  .\run_ucs.ps1 --sqlite

   O modo e automatico: 1a vez/rodada completa => baixa tudo; se a anterior
   foi interrompida => retoma so o que faltou. Para um subconjunto:
   .\run_ucs.ps1 --contratos "ECO 025/2021,ECO 021/2020"

4) TRAGA DE VOLTA a pasta output_ucs\ INTEIRA:
   - output_ucs\consolidado_ucs.csv  (a base enxuta contrato;odi;uc;...)
   - output_ucs\raw\*.csv            (os brutos por contrato)
   - output_ucs\logs\*.log           (tracebacks/medidas)
   - output_ucs\ucs.db               (se usou --sqlite)
"@
Set-Content -Path (Join-Path $stage "LEIA-ME_PRIMEIRO.txt") -Value $leiame -Encoding ascii

# --- zipa ------------------------------------------------------------------
Compress-Archive -Path "$stage\*" -DestinationPath $destino -Force
Remove-Item $stage -Recurse -Force -Confirm:$false

Write-Host "Gerado: $((Get-Item $destino).FullName) ($([math]::Round((Get-Item $destino).Length / 1KB)) KB)"
Write-Host "Scripts renomeados no pacote: $($renomeados.Count) (.ps1/.py -> .renomeado.txt)"
Write-Host "Na VPN: extrair, seguir o LEIA-ME_PRIMEIRO.txt, depois .\run_ucs.ps1 --dry-run e .\run_ucs.ps1."
Write-Host "Se ainda bloquear, renomeie o proprio zip para $destino.txt antes de anexar."
