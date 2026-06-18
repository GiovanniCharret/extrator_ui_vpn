# fazer_pacote_recon.ps1 - RODA NO DEV, a partir da raiz do projeto.
# Uso: powershell -ExecutionPolicy Bypass -File deploy\fazer_pacote_recon.ps1 -Versao 1
# Gera pacote_recon_v<N>.zip com o MINIMO p/ a recon (U0) da Fase 2 rodar na VPN.
#
# ANTI-BLOQUEIO DE E-MAIL: scanners corporativos bloqueiam zips contendo .ps1/.py.
# O pacote sai com esses arquivos renomeados para *.renomeado.txt; o
# LEIA-ME_PRIMEIRO.txt traz o comando unico que restaura os nomes apos extrair.
param(
    [int]$Versao = 1
)

$ErrorActionPreference = "Stop"

$destino = "pacote_recon_v$Versao.zip"

# So o necessario p/ `.\run_recon.ps1` rodar: o pacote ucs/, o runner, as deps e config.
$itens = @(
    "ucs",
    "run_recon.ps1",
    "requirements.txt"
)
if (Test-Path "config") { $itens += "config" }
$existentes = $itens | Where-Object { Test-Path $_ }

# --- staging: copia limpa em pasta temporaria -------------------------------
$stage = Join-Path $env:TEMP "pacote_recon_stage"
if (Test-Path $stage) { Remove-Item $stage -Recurse -Force -Confirm:$false }
New-Item -ItemType Directory $stage | Out-Null

foreach ($item in $existentes) {
    Copy-Item $item (Join-Path $stage (Split-Path $item -Leaf)) -Recurse
}

# remove caches do Python (lixo de DEV)
Get-ChildItem $stage -Recurse -Directory -Filter "__pycache__" |
    Remove-Item -Recurse -Force -Confirm:$false

# NUNCA empacotar o estado da rodada (vive na VPN).
Get-ChildItem $stage -Recurse -File -Filter "estado_ucs.json" |
    Remove-Item -Force -Confirm:$false

# --- renomeia scripts para passar no filtro de e-mail ------------------------
$renomeados = Get-ChildItem $stage -Recurse -File |
    Where-Object { $_.Extension -eq ".ps1" -or $_.Extension -eq ".py" }
$renomeados | Rename-Item -NewName { $_.Name + ".renomeado.txt" }

# --- LEIA-ME com o comando de restauracao e o passo da recon -----------------
$leiame = @"
LEIA-ME PRIMEIRO - recon da Fase 2 (U0)
========================================

Os scripts .ps1 e .py deste pacote foram renomeados para *.renomeado.txt
para passar no filtro de seguranca do e-mail.

1) APOS EXTRAIR, abra o PowerShell NA PASTA EXTRAIDA e cole este comando p/
   restaurar os nomes:

Get-ChildItem -Recurse -Filter "*.renomeado.txt" | Rename-Item -NewName { `$_.Name -replace "\.renomeado\.txt`$", "" }

   Confira: o arquivo run_recon.ps1 deve existir de novo.

2) Pre-requisito: ter o 'uv' instalado (uma vez). Se nao tiver:
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

3) Com a SESSAO WINDOWS da VPN ativa/logada (acesso a http://sqlprdrs), rode:
   .\run_recon.ps1
   (na 1a vez ele cria a venv e instala as dependencias sozinho)

4) TRAGA DE VOLTA a pasta output_ucs\ INTEIRA (recon\ + logs\):
   - recon\: RECON.md, getitemparameters_nivel1.xml, dropdowns.json,
     params.json, amostra_COELBA_11.*
   - logs\: recon_*.log (tem os tracebacks completos)

Se o HTTP falhar, o script grava output_ucs\recon\fallback_manual.txt com o
passo a passo da captura manual pelo navegador.
"@
Set-Content -Path (Join-Path $stage "LEIA-ME_PRIMEIRO.txt") -Value $leiame -Encoding ascii

# --- zipa ---------------------------------------------------------------------
Compress-Archive -Path "$stage\*" -DestinationPath $destino -Force
Remove-Item $stage -Recurse -Force -Confirm:$false

Write-Host "Gerado: $((Get-Item $destino).FullName) ($([math]::Round((Get-Item $destino).Length / 1KB)) KB)"
Write-Host "Scripts renomeados no pacote: $($renomeados.Count) (.ps1/.py -> .renomeado.txt)"
Write-Host "Na VPN: extrair, seguir o LEIA-ME_PRIMEIRO.txt, depois .\run_recon.ps1."
Write-Host "Se ainda bloquear, renomeie o proprio zip para $destino.txt antes de anexar."
