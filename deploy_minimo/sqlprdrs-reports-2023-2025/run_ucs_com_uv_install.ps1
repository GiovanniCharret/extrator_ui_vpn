# run_ucs_com_uv_install.ps1 - ponto de entrada da extracao 2023-2025 (chamado pelo executar.bat).
# Existe para uma maquina SEM o 'uv' instalado: garante o 'uv' (instalando-o na 1a vez) e
# entao delega ao run_ucs.ps1, que exige o 'uv' como pre-requisito.
# Uso: identico ao run_ucs.ps1 (os argumentos sao repassados).
$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path

# 1) Garante o 'uv'. Se ausente, instala pelo instalador oficial (a VPN tem internet).
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "uv nao encontrado - instalando (astral.sh)..."
    # Fixa o diretorio de destino num caminho conhecido, para adiciona-lo ao PATH abaixo.
    $env:UV_INSTALL_DIR = Join-Path $env:USERPROFILE ".local\bin"
    try {
        Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
    } catch {
        Write-Error "falha ao instalar o uv: $($_.Exception.Message)"
        exit 1
    }
    # SUTILEZA: o instalador so ajusta o PATH do usuario no registro - o processo atual
    # nao ve. Injeta-se o destino no PATH desta sessao para o 'uv' valer JA nesta rodada
    # (o run_ucs.ps1 roda no mesmo processo e herda este PATH).
    $env:PATH = "$env:UV_INSTALL_DIR;$env:PATH"
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        Write-Error "uv instalado mas ausente no PATH ($env:UV_INSTALL_DIR). Reabra o terminal e rode de novo."
        exit 1
    }
    Write-Host "uv instalado com sucesso."
}

# 2) Delega ao run_ucs.ps1, repassando todos os argumentos (roda neste mesmo processo).
& (Join-Path $raiz "run_ucs.ps1") @args
exit $LASTEXITCODE
