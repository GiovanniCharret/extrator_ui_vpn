# run.ps1 - executa o pipeline LPT (F5). Cria a venv na 1a vez e repassa os argumentos.
# Uso (na VPN, com a sessao RDP aberta, em foco e desbloqueada):
#   .\run.ps1                 (modo automatico: refresh ou retomar, lendo o estado)
#   .\run.ps1 --dry-run
#   .\run.ps1 --contratos "ECO 019/2020,ECO 021/2020"
#   .\run.ps1 --refresh       (forca re-exportar todos)
#   .\run.ps1 --somente-parse
# Pre-requisito unico: ter o 'uv' instalado (ver COMO_RODAR.html / README).
# F6 ainda vai fixar "Microsoft Print to PDF" como impressora padrao aqui.
$ErrorActionPreference = "Stop"

# Raiz do projeto = pasta deste script (independe do diretorio atual).
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $raiz
$py = Join-Path $raiz ".venv\Scripts\python.exe"

# Bootstrap: se a venv ainda nao existe, cria e instala as dependencias (uma unica vez).
if (-not (Test-Path $py)) {
    Write-Host "venv nao encontrada - criando .venv e instalando dependencias (so na 1a vez)..."
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        Write-Error 'uv nao instalado. Instale com: powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"'
        exit 1
    }
    uv venv
    if ($LASTEXITCODE -ne 0) { Write-Error "falha ao criar a venv (uv venv)"; exit 1 }
    # --python aponta uv para ESTA venv (sem depender de ativacao/VIRTUAL_ENV).
    uv pip install --python $py -r requirements.txt
    if ($LASTEXITCODE -ne 0) { Write-Error "falha ao instalar dependencias (uv pip install)"; exit 1 }
}

# Executa o pipeline repassando todos os argumentos recebidos.
& $py -m src.main @args
exit $LASTEXITCODE
