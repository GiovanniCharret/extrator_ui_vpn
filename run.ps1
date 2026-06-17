# run.ps1 - executa o pipeline LPT (F5). Repassa os argumentos para src.main.
# Uso (na VPN, com a sessao RDP aberta, em foco e desbloqueada):
#   .\run.ps1                 (modo automatico: refresh ou retomar, lendo o estado)
#   .\run.ps1 --dry-run
#   .\run.ps1 --contratos "ECO 019/2020,ECO 021/2020"
#   .\run.ps1 --refresh       (forca re-exportar todos)
#   .\run.ps1 --somente-parse
# F6 ainda vai fixar "Microsoft Print to PDF" como impressora padrao aqui.
$ErrorActionPreference = "Stop"

# Raiz do projeto = pasta deste script (independe do diretorio atual).
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
$py = Join-Path $raiz ".venv\Scripts\python.exe"

# Sem venv nao da para rodar: falha cedo com instrucao clara.
if (-not (Test-Path $py)) {
    Write-Error "venv nao encontrado em $py - rode deploy\instalar.ps1 primeiro."
    exit 1
}

# Executa o pipeline repassando todos os argumentos recebidos.
Set-Location $raiz
& $py -m src.main @args
exit $LASTEXITCODE
