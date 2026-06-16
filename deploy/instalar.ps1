# instalar.ps1 - RODA NA MAQUINA DA VPN, a partir da raiz do projeto extraido.
# Uso: powershell -ExecutionPolicy Bypass -File deploy\instalar.ps1
#
# Obtem um Python por uma ESCADA de tentativas, cria .venv, instala
# dependencias e roda o teste F0. TUDO em output\logs\instalar_<ts>.log
#   Ramo 1: py/python ja instalados      -> python -m venv
#   Ramo 2: uv ja instalado              -> uv venv (baixa CPython se preciso)
#   Ramo 3: instala uv sem admin (web)   -> uv venv
#   Falhou tudo -> avisar o Claude (plano C: Python embutido no pacote)

$ErrorActionPreference = "Continue"

New-Item -ItemType Directory -Force output\logs, output\inspecao, output\pdf | Out-Null

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
Start-Transcript -Path "output\logs\instalar_$ts.log"

Write-Host "=== INSTALAR.PS1 v2 - inicio $ts ==="
Write-Host "Pasta atual: $(Get-Location)"

function Encontrar-Python {
    foreach ($cand in @("py", "python")) {
        try {
            $v = & $cand --version 2>$null
            if ($LASTEXITCODE -eq 0 -and "$v" -match "Python 3") {
                Write-Host "Python encontrado via '$cand': $v"
                return $cand
            }
        } catch {}
    }
    return $null
}

function Encontrar-Uv {
    $cands = @("uv",
               "$env:USERPROFILE\.local\bin\uv.exe",
               "$env:USERPROFILE\.cargo\bin\uv.exe")
    foreach ($cand in $cands) {
        try {
            $v = & $cand --version 2>$null
            if ($LASTEXITCODE -eq 0) {
                Write-Host "uv encontrado via '$cand': $v"
                return $cand
            }
        } catch {}
    }
    return $null
}

$venvPy = ".venv\Scripts\python.exe"

# --- 1. Garantir um venv ------------------------------------------------------
if (Test-Path $venvPy) {
    Write-Host ".venv ja existe - reaproveitando."
} else {
    $python = Encontrar-Python
    if ($null -ne $python) {
        Write-Host "Ramo 1: criando .venv com '$python -m venv' ..."
        & $python -m venv .venv
    } else {
        Write-Host "Ramo 1 falhou: Python nao encontrado (tentei 'py' e 'python')."
        $uv = Encontrar-Uv
        if ($null -eq $uv) {
            Write-Host "Ramo 2 falhou: uv nao encontrado. Ramo 3: instalando uv (sem admin, requer internet) ..."
            try {
                [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
                Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
            } catch {
                Write-Host "ERRO ao baixar/instalar o uv: $_"
            }
            $uv = Encontrar-Uv
        }
        if ($null -ne $uv) {
            Write-Host "Criando .venv com uv (baixa o CPython 3.12 automaticamente se nao houver) ..."
            & $uv venv --python 3.12 .venv
        }
    }
}

if (-not (Test-Path $venvPy)) {
    Write-Host "ERRO: nao consegui obter um Python por nenhum caminho (python/py, uv, download do uv)."
    Write-Host "Causa provavel: proxy/firewall bloqueando downloads."
    Write-Host "ACAO: rode deploy\coletar.ps1, traga o zip e avise o Claude - plano C (Python embutido no pacote)."
    Stop-Transcript
    exit 1
}

# --- 2. Instalar dependencias (pip do venv; venv criado pelo uv nao tem pip) ---
& $venvPy -m pip --version 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host "Instalando dependencias com pip ..."
    & $venvPy -m pip install --disable-pip-version-check -r requirements.txt
} else {
    $uv = Encontrar-Uv
    if ($null -eq $uv) {
        Write-Host "ERRO: o venv nao tem pip e o uv nao esta disponivel."
        Stop-Transcript
        exit 1
    }
    Write-Host "Instalando dependencias com uv pip ..."
    & $uv pip install --python $venvPy -r requirements.txt
}
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERRO: instalacao de dependencias falhou (codigo $LASTEXITCODE). Veja o log acima."
    Stop-Transcript
    exit 1
}

# --- 3. Teste F0 ---------------------------------------------------------------
Write-Host "Rodando teste F0 ..."
& $venvPy -m pytest tests\test_f0_ambiente.py -v
$testes = $LASTEXITCODE

if ($testes -eq 0) {
    Write-Host "=== INSTALACAO OK - teste F0 verde ==="
} else {
    Write-Host "=== INSTALACAO COM FALHA - teste F0 retornou codigo $testes ==="
}

Stop-Transcript
exit $testes
