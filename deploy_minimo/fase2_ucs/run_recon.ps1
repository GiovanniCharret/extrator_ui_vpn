# run_recon.ps1 - U0 (Fase 2): recon do SSRS (relatorio 22.3-UCs_paraAprovacao).
# Cria a venv na 1a vez e roda a recon. Grava TUDO em output_ucs/recon/.
# Uso (na VPN, com a sessao Windows ativa/logada):
#   .\run_recon.ps1
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
# SEMPRE sincroniza as dependencias (idempotente; rapido se ja satisfeitas). Necessario
# porque a venv pode pre-existir da Fase 1 SEM as deps novas da Fase 2 (requests,
# requests-negotiate-sspi) - foi o que fez a 1a recon falhar em criar_sessao.
Write-Host "sincronizando dependencias (uv pip install)..."
uv pip install --python $py -r requirements.txt
if ($LASTEXITCODE -ne 0) { Write-Error "falha ao instalar dependencias (uv pip install)"; exit 1 }

# Executa a recon. Resultados em output_ucs/recon/ (RECON.md + arquivos crus).
& $py -m ucs.recon
$rc = $LASTEXITCODE
Write-Host ""
Write-Host "Recon concluida. Veja output_ucs\recon\RECON.md e traga a pasta output_ucs\ INTEIRA de volta (recon\ + logs\)."
exit $rc
