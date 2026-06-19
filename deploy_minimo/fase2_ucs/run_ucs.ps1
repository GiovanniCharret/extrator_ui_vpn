# run_ucs.ps1 - executa o pipeline da Fase 2 (UCs via SSRS). Cria a venv na 1a vez,
# sincroniza as deps e repassa os argumentos.
# Uso (na VPN, com a sessao Windows ativa/logada, acesso a http://sqlprdrs):
#   .\run_ucs.ps1                       (modo automatico: refresh ou retomar pelo estado)
#   .\run_ucs.ps1 --dry-run
#   .\run_ucs.ps1 --contratos "ECO 025/2021,ECO 021/2020"
#   .\run_ucs.ps1 --refresh             (forca re-baixar todos)
#   .\run_ucs.ps1 --somente-consolida   (so reprocessa os brutos)
#   .\run_ucs.ps1 --sqlite              (gera ucs.db + benchmark)
# Pre-requisito unico: ter o 'uv' instalado.
$ErrorActionPreference = "Stop"

# Raiz do projeto = pasta deste script (independe do diretorio atual).
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $raiz
$py = Join-Path $raiz ".venv\Scripts\python.exe"

# Bootstrap. Precisa do 'uv' (pre-requisito unico).
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Error 'uv nao instalado. Instale com: powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"'
    exit 1
}
# Cria a venv se ainda nao existe.
if (-not (Test-Path $py)) {
    Write-Host "venv nao encontrada - criando .venv..."
    # NAO forcar arquitetura: o PC da VPN pode ser Windows 32 bits (forcar 64 bits
    # quebra com 'os error 216'). uv escolhe o Python compativel com o SO. Bug 19/06.
    uv venv
    if ($LASTEXITCODE -ne 0) { Write-Error "falha ao criar a venv (uv venv)"; exit 1 }
}
# SEMPRE sincroniza as dependencias (idempotente; cobre venv pre-existente sem as deps novas).
uv pip install --python $py -r requirements.txt
if ($LASTEXITCODE -ne 0) { Write-Error "falha ao instalar dependencias (uv pip install)"; exit 1 }

# Executa o pipeline repassando todos os argumentos recebidos.
& $py -m ucs.main @args
exit $LASTEXITCODE
