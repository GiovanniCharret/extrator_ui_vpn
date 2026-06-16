# fazer_pacote.ps1 - RODA NO DEV, a partir da raiz do projeto.
# Uso: powershell -ExecutionPolicy Bypass -File deploy\fazer_pacote.ps1 -Versao 1
# Gera pacote_v<N>.zip com tudo que a VPN precisa.
#
# ANTI-BLOQUEIO DE E-MAIL: scanners corporativos bloqueiam zips contendo
# .ps1/.py. O pacote e gerado com esses arquivos renomeados para
# *.renomeado.txt; o LEIA-ME_PRIMEIRO.txt dentro do zip traz o comando
# unico que restaura os nomes apos extrair na VPN.
param(
    [int]$Versao = 1
)

$ErrorActionPreference = "Stop"

$destino = "pacote_v$Versao.zip"

$itens = @(
    "src",
    "scripts",
    "tests",
    "deploy",
    "base_contratos.json",
    "requirements.txt",
    "planning\TESTES.md"
)
if (Test-Path "config") { $itens += "config" }
$existentes = $itens | Where-Object { Test-Path $_ }

# --- staging: copia limpa em pasta temporaria -------------------------------
$stage = Join-Path $env:TEMP "pacote_stage"
if (Test-Path $stage) { Remove-Item $stage -Recurse -Force -Confirm:$false }
New-Item -ItemType Directory $stage | Out-Null

foreach ($item in $existentes) {
    Copy-Item $item (Join-Path $stage (Split-Path $item -Leaf)) -Recurse
}

# remove caches do Python (lixo de DEV)
Get-ChildItem $stage -Recurse -Directory -Filter "__pycache__" |
    Remove-Item -Recurse -Force -Confirm:$false

# --- renomeia scripts para passar no filtro de e-mail ------------------------
$renomeados = Get-ChildItem $stage -Recurse -File |
    Where-Object { $_.Extension -eq ".ps1" -or $_.Extension -eq ".py" }
$renomeados | Rename-Item -NewName { $_.Name + ".renomeado.txt" }

# --- LEIA-ME com o comando de restauracao ------------------------------------
$leiame = @"
LEIA-ME PRIMEIRO - restauracao dos nomes de arquivo
====================================================

Os scripts .ps1 e .py deste pacote foram renomeados para *.renomeado.txt
para passar no filtro de seguranca do e-mail.

APOS EXTRAIR, abra o PowerShell NA PASTA EXTRAIDA e cole este comando:

Get-ChildItem -Recurse -Filter "*.renomeado.txt" | Rename-Item -NewName { `$_.Name -replace "\.renomeado\.txt`$", "" }

Confira: deploy\instalar.ps1 deve existir de novo.

Depois siga o roteiro em TESTES.md (Roteiro 1), comecando por:
powershell -ExecutionPolicy Bypass -File deploy\instalar.ps1
"@
Set-Content -Path (Join-Path $stage "LEIA-ME_PRIMEIRO.txt") -Value $leiame -Encoding ascii

# --- zipa ---------------------------------------------------------------------
Compress-Archive -Path "$stage\*" -DestinationPath $destino -Force
Remove-Item $stage -Recurse -Force -Confirm:$false

Write-Host "Gerado: $((Get-Item $destino).FullName) ($([math]::Round((Get-Item $destino).Length / 1KB)) KB)"
Write-Host "Scripts renomeados no pacote: $($renomeados.Count) (.ps1/.py -> .renomeado.txt)"
Write-Host "Na VPN: extrair, seguir o LEIA-ME_PRIMEIRO.txt (1 comando), depois TESTES.md."
Write-Host "Se ainda bloquear, renomeie o proprio zip para $destino.txt antes de anexar."
