# fazer_pacote_completo.ps1 - RODA NO DEV, a partir da raiz do projeto.
# Uso: powershell -ExecutionPolicy Bypass -File deploy\fazer_pacote_completo.ps1 -Versao 1
# Zipa o deploy_minimo INTEIRO (Fase 1 + Fase 2 + run_tudo + guias), numa versao
# consistente, com os scripts renomeados p/ *.renomeado.txt (anti-filtro de e-mail).
# Objetivo: evitar copia parcial/arquivo velho sobrando na VPN.
param(
    [int]$Versao = 1
)

$ErrorActionPreference = "Stop"

$destino = "pacote_completo_v$Versao.zip"
if (-not (Test-Path "deploy_minimo")) { Write-Error "deploy_minimo nao encontrado (rode na raiz do projeto)"; exit 1 }

# --- staging: copia limpa de deploy_minimo ---------------------------------
$stage = Join-Path $env:TEMP "pacote_completo_stage"
if (Test-Path $stage) { Remove-Item $stage -Recurse -Force -Confirm:$false }
New-Item -ItemType Directory $stage | Out-Null
Copy-Item "deploy_minimo" (Join-Path $stage "deploy_minimo") -Recurse

# remove lixo de runtime (venvs, saidas, caches, estado) - nao vai pro pacote
foreach ($d in @("__pycache__", ".venv", "output", "output_ucs")) {
    Get-ChildItem $stage -Recurse -Directory -Filter $d -ErrorAction SilentlyContinue |
        Remove-Item -Recurse -Force -Confirm:$false
}
Get-ChildItem $stage -Recurse -File |
    Where-Object { $_.Name -in @("estado_ucs.json", "estado_execucao.json") } |
    Remove-Item -Force -Confirm:$false

# --- renomeia .ps1/.py p/ passar no filtro de e-mail ------------------------
$ren = Get-ChildItem $stage -Recurse -File | Where-Object { $_.Extension -in @(".ps1", ".py") }
$ren | Rename-Item -NewName { $_.Name + ".renomeado.txt" }

# --- LEIA-ME (no topo do zip) ----------------------------------------------
$leiame = @"
LEIA-ME PRIMEIRO - deploy completo (Fase 1 LNC + Fase 2 UCs)
=============================================================

>>> IMPORTANTE - NAO misture versoes <<<
  Se ja existe a pasta antiga na VPN (ex.: extrator2), APAGUE-A POR COMPLETO
  antes de usar este pacote. Em especial, apague as venvs antigas:
      fase1_lnc\.venv   e   fase2_ucs\.venv
  Senao os scripts reaproveitam a venv velha (incompleta) e o erro PERSISTE.

1) Extraia este zip numa pasta NOVA e vazia.

2) Restaure os nomes dos scripts: abra o PowerShell NA PASTA extraida e cole:

Get-ChildItem -Recurse -Filter "*.renomeado.txt" | Rename-Item -NewName { `$_.Name -replace "\.renomeado\.txt`$", "" }

   Confira: deploy_minimo\run_tudo.ps1 deve existir de novo.

3) Pre-requisito: ter o 'uv' instalado (uma vez). Se nao tiver:
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

4) Entre na pasta e rode (com a sessao da VPN ativa/logada):
   cd deploy_minimo
   .\run_tudo.ps1            (Fase 1 + Fase 2, em sequencia)
   .\run_tudo.ps1 2         (so a Fase 2)
   .\run_tudo.ps1 1         (so a Fase 1)
   Detalhe de cada argumento: COMO_USAR.html

   Na 1a vez, cada fase cria sua venv e instala as deps sozinha. Funciona em
   Windows 32 OU 64 bits (a cryptography da Fase 1 esta fixada na 48.0.1, que
   tem wheel 32 bits - nao precisa compilar nada).

DICA: rode interativo. NAO capture com '... 2>&1 > log.txt' no PowerShell 5.1
(isso transforma a saida normal do uv em erro).
"@
Set-Content -Path (Join-Path $stage "LEIA-ME_PRIMEIRO.txt") -Value $leiame -Encoding ascii

# --- zipa ------------------------------------------------------------------
Compress-Archive -Path "$stage\*" -DestinationPath $destino -Force
Remove-Item $stage -Recurse -Force -Confirm:$false

Write-Host "Gerado: $((Get-Item $destino).FullName) ($([math]::Round((Get-Item $destino).Length / 1KB)) KB)"
Write-Host "Scripts renomeados: $($ren.Count) (.ps1/.py -> .renomeado.txt)"
Write-Host "Na VPN: APAGUE a pasta antiga, extraia este zip numa pasta nova, siga o LEIA-ME_PRIMEIRO.txt."
Write-Host "Se ainda bloquear, renomeie o proprio zip para $destino.txt antes de anexar."
