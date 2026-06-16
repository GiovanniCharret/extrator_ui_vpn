# coletar.ps1 - RODA NA MAQUINA DA VPN, a partir da raiz do projeto.
# Uso: powershell -ExecutionPolicy Bypass -File deploy\coletar.ps1
# Zipa output\ (+ config\) em resultados_<timestamp>.zip para trazer de volta ao DEV.

$ErrorActionPreference = "Stop"

$ts = Get-Date -Format "yyyyMMdd_HHmm"
$destino = "resultados_$ts.zip"

$itens = @("output")
if (Test-Path "config") { $itens += "config" }

Compress-Archive -Path $itens -DestinationPath $destino -Force

Write-Host "Gerado: $((Get-Item $destino).FullName) ($([math]::Round((Get-Item $destino).Length / 1KB)) KB)"
Write-Host "Traga este arquivo de volta e coloque em vpn_resultados\ no DEV."
Write-Host "Se o e-mail bloquear .zip, renomeie para $destino.txt antes de enviar."
