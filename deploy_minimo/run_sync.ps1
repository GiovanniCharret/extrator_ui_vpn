# run_sync.ps1 - envia os consolidados da rodada diaria para o site (VPS Hostinger).
# Vive em deploy_minimo\ (pasta de uso diario), ao lado do run_tudo.
#
# SO RODA NO DEV (nunca na VPN): precisa da chave SSH (~\.ssh\id_ed25519) e da
# pasta Downloads locais - na VPN ele nao tem funcao (se for junto no zip, ignore).
# Momento de uso: depois que voce baixou do Google Drive as pastas gemeas
# lpt\ e mla\ (cada uma com os 2 CSVs) para Downloads. Fluxo (decidido em
# 09/07/2026, ver planning/2026-07-08-atualizacao-diaria-entrada-site.md;
# mla incluido em 09/07/2026 - pastas gemeas em Downloads):
#
#   Downloads\lpt\consolidado.csv      -> /opt/anexov/entrada/lpt/consolidado.csv
#   Downloads\lpt\consolidado_ucs.csv  -> /opt/anexov/entrada/lpt/consolidado_ucs.csv
#   Downloads\mla\consolidado.csv      -> /opt/anexov/entrada/mla/consolidado.csv
#   Downloads\mla\consolidado_ucs.csv  -> /opt/anexov/entrada/mla/consolidado_ucs.csv
#
# Transporte: scp/ssh como usuario 'deploy' (chave ~\.ssh\id_ed25519), com envio
# para nome temporario (.new) + rename atomico no VPS - o backend recarrega por
# mtime e nunca pode ler um arquivo pela metade. So toca em /opt/anexov/entrada/.
# base_contratos.json fica FORA deste sync (decisao do usuario).
#
# Sanidade ANTES de enviar (aborta em vez de subir base quebrada):
#   - os 4 arquivos existem e nao estao vazios (faltar QUALQUER um aborta tudo);
#   - primeira linha e um cabecalho plausivel (contem ';');
#   - se o numero de linhas cair mais de 20% vs o ultimo envio, aborta e avisa
#     (rodada parcial e o modo de falha tipico);
#   - se o arquivo tem mais de 24h, AVISA (pode nao ser a base mais atual).
# "Atualizado?": o mtime de cada arquivo no ultimo envio fica gravado em
# deploy_minimo\estado_sync.json; arquivo com mtime IGUAL ao ja enviado e pulado
# (nada novo) - assim rodar 2x no dia nao re-envia nem da erro (idempotente).
#
# Uso:
#   .\run_sync.ps1              (envia o que mudou desde o ultimo envio)
#   .\run_sync.ps1 -DryRun      (so a sanidade; nao toca o VPS)
#   .\run_sync.ps1 -Forcar      (ignora as travas de 'sem mudanca' e 'queda de
#                                linhas' - use quando a mudanca for legitima)
#   .\run_sync.ps1 -Origem "C:\outra\pasta"   (fonte alternativa; default Downloads)
#
# Log completo em deploy_minimo\output\logs\sync_<ts>.log (execucao cega: tudo em arquivo).
param(
    [switch]$DryRun,                                        # so valida; nao envia
    [switch]$Forcar,                                        # re-envia mesmo sem mudanca / com queda
    [string]$Origem = (Join-Path $env:USERPROFILE "Downloads")  # raiz das pastas lpt\ e mla\
)
$ErrorActionPreference = "Stop"

# --- Configuracao (centralizada aqui; nada espalhado pelo corpo) -------------
$VpsHost  = "gerenciador-gclt.com"                 # IP fallback (se o DNS falhar): 82.25.68.143
$VpsUser  = "deploy"                               # dono de /opt/anexov (nunca root)
$Chave    = Join-Path $env:USERPROFILE ".ssh\id_ed25519"   # chave criada em 09/07/2026
$DestBase = "/opt/anexov/entrada"                  # UNICA arvore tocada no VPS
$QuedaMax = 0.20                                   # queda de linhas tolerada vs ultimo envio
$IdadeMaxHoras = 24                                # acima disso AVISA (arquivo talvez velho)
# Os 4 arquivos: pasta gemea (Downloads\<pasta>\ = entrada/<pasta>/ no VPS) + nome.
$Arquivos = @(
    @{ pasta = "lpt"; nome = "consolidado.csv" },      # Fase 1 (contratos LPT)
    @{ pasta = "lpt"; nome = "consolidado_ucs.csv" },  # Fase 2 (UCs dos contratos LPT)
    @{ pasta = "mla"; nome = "consolidado.csv" },      # contratos MLA (outra fonte)
    @{ pasta = "mla"; nome = "consolidado_ucs.csv" }   # UCs dos contratos MLA
)

# --- Log (console + arquivo; execucao cega) ----------------------------------
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path     # raiz = deploy_minimo\
$logDir = Join-Path $raiz "output\logs"                     # mesmo lugar dos logs das rodadas
New-Item -ItemType Directory -Force $logDir | Out-Null      # garante a pasta
$ts = Get-Date -Format "yyyyMMdd_HHmmss"                    # carimbo desta execucao
$logFile = Join-Path $logDir "sync_$ts.log"                 # 1 log por execucao
function Log([string]$msg) {                                # toda mensagem vai p/ console E arquivo
    $linha = "{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg
    Write-Host $linha
    Add-Content -Path $logFile -Value $linha -Encoding UTF8
}
function Falhar([string]$msg) {                             # falha SEMPRE explicita e logada
    Log ("ERRO: " + $msg)
    Log "=== SYNC ABORTADO (nada foi enviado ao VPS alem do ja concluido acima) ==="
    exit 1
}

Log "=== run_sync (DryRun=$DryRun Forcar=$Forcar) origem=$Origem destino=${VpsUser}@${VpsHost}:$DestBase ==="

# --- Fase 1: pre-requisitos locais (falha cedo, antes de tocar a rede) -------
if (-not (Test-Path $Chave)) { Falhar "chave SSH nao encontrada: $Chave (gerar com ssh-keygen; ver planning/2026-07-08-...md)" }
$estadoPath = Join-Path $raiz "estado_sync.json"            # mtime+linhas do ultimo envio
$estadoAnt = @{}                                            # default: primeiro envio
if (Test-Path $estadoPath) {                                # carrega o estado anterior, se houver
    try {
        $json = Get-Content $estadoPath -Raw | ConvertFrom-Json
        foreach ($p in $json.PSObject.Properties) { $estadoAnt[$p.Name] = $p.Value }
    } catch { Log "AVISO: estado_sync.json ilegivel (seguindo como primeiro envio): $($_.Exception.Message)" }
}

# --- Fase 2: sanidade dos 4 arquivos (tudo validado ANTES de enviar qualquer um)
$aEnviar = @()                                              # quem passou e TEM mudanca
$pulados = @()                                              # quem passou mas nao mudou (mantem estado)
foreach ($a in $Arquivos) {
    $chaveArq = "$($a.pasta)/$($a.nome)"                    # chave do estado (ex.: lpt/consolidado.csv)
    $caminho = Join-Path (Join-Path $Origem $a.pasta) $a.nome
    # 2a. existe? (faltar um dos 4 aborta o envio inteiro - "no minimo, nao faltando")
    if (-not (Test-Path $caminho)) { Falhar "arquivo nao encontrado: $caminho (baixou a pasta $($a.pasta)\ do Drive?)" }
    $item = Get-Item $caminho
    # 2b. nao-vazio?
    if ($item.Length -eq 0) { Falhar "arquivo vazio: $caminho" }
    # 2c. atualizado? arquivo com mais de 24h merece um aviso (nao aborta)
    $idade = ((Get-Date) - $item.LastWriteTime).TotalHours
    if ($idade -gt $IdadeMaxHoras) {
        Log ("AVISO: {0} foi gerado ha {1:N0}h ({2}) - e a base mais atual?" -f $chaveArq, $idade, $item.LastWriteTime.ToString("yyyy-MM-dd HH:mm"))
    }
    # 2d. cabecalho plausivel? (primeira linha precisa conter ';' - separador do projeto)
    $reader = New-Object System.IO.StreamReader($caminho)
    $cabecalho = $reader.ReadLine()
    $reader.Close()
    if ($null -eq $cabecalho -or -not $cabecalho.Contains(";")) { Falhar "cabecalho invalido em ${chaveArq}: primeira linha sem ';' -> '$cabecalho'" }
    # 2e. contagem de linhas (rapida via ReadLines; inclui o cabecalho)
    $linhas = 0
    foreach ($l in [System.IO.File]::ReadLines($caminho)) { $linhas++ }
    # 2f. baseline do ultimo envio (migracao: estado antigo usava chave sem pasta, era o lpt)
    $ant = $null
    if ($estadoAnt.ContainsKey($chaveArq)) { $ant = $estadoAnt[$chaveArq] }
    elseif ($a.pasta -eq "lpt" -and $estadoAnt.ContainsKey($a.nome)) { $ant = $estadoAnt[$a.nome] }
    # 2g. queda >20% vs ultimo envio? (rodada parcial = modo de falha tipico)
    if (-not $Forcar -and $null -ne $ant -and [int]$ant.linhas -gt 0 -and $linhas -lt ([int]$ant.linhas * (1 - $QuedaMax))) {
        Falhar ("queda de linhas suspeita em ${chaveArq}: {0} -> {1} (mais de {2:P0}); rodada parcial? Se for legitima, rode com -Forcar." -f [int]$ant.linhas, $linhas, $QuedaMax)
    }
    # 2h. mudou desde o ultimo envio? mtime igual = mesmo arquivo ja enviado => pula
    $mtime = $item.LastWriteTime.ToString("o")              # ISO com precisao total
    $jaEnviado = ($null -ne $ant) -and ($null -ne $ant.PSObject.Properties["mtime_origem"]) -and ($ant.mtime_origem -eq $mtime)
    $info = @{ chave = $chaveArq; caminho = $caminho; destino = "$DestBase/$($a.pasta)/$($a.nome)"; linhas = $linhas; mtime = $mtime }
    if ($jaEnviado -and -not $Forcar) {
        Log ("PULANDO {0}: sem mudanca desde o envio de {1} (use -Forcar p/ re-enviar)" -f $chaveArq, $ant.enviado_em)
        $pulados += $info
    } else {
        Log ("OK sanidade: {0} ({1} bytes, {2} linhas; ultimo envio: {3})" -f $chaveArq, $item.Length, $linhas, $(if ($null -ne $ant) { [string]$ant.linhas + " linhas" } else { "n/a" }))
        $aEnviar += $info
    }
}

if ($DryRun) {                                              # dry-run para aqui: nada de rede
    Log "=== DRY-RUN OK: $($aEnviar.Count) enviaria(m), $($pulados.Count) sem mudanca; nada foi enviado ==="
    exit 0
}
if ($aEnviar.Count -eq 0) {                                 # nada novo: sai limpo (idempotente)
    Log "=== NADA NOVO: os $($pulados.Count) arquivos ja estao no VPS (mtime igual ao ultimo envio) ==="
    exit 0
}

# --- Fase 3: envio (scp para .new; nada substituido ainda) --------------------
# BatchMode: falha em vez de pedir senha (uso nao interativo); -q sem barra de progresso.
$sshOpts = @("-i", $Chave, "-o", "BatchMode=yes", "-o", "ConnectTimeout=15")
foreach ($e in $aEnviar) {
    Log "enviando $($e.chave) -> ${VpsHost}:$($e.destino).new ..."
    scp -q @sshOpts $e.caminho "${VpsUser}@${VpsHost}:$($e.destino).new"
    if ($LASTEXITCODE -ne 0) { Falhar "scp falhou para $($e.chave) (codigo $LASTEXITCODE)" }
}

# --- Fase 4: rename atomico de TODOS num unico ssh (janela minima de inconsistencia)
$mvs = @()
foreach ($e in $aEnviar) { $mvs += "mv $($e.destino).new $($e.destino)" }
$cmd = $mvs -join " && "                                    # cada mv so roda se o anterior funcionou
Log "aplicando no VPS: $cmd"
ssh @sshOpts "${VpsUser}@${VpsHost}" $cmd
if ($LASTEXITCODE -ne 0) { Falhar "rename no VPS falhou (codigo $LASTEXITCODE) - pode ter sobrado .new em $DestBase" }
Log "arquivos substituidos no VPS (backend recarrega sozinho pelo mtime)"

# --- Fase 5: grava o estado do envio (base das travas do proximo) -------------
# Reconstroi do zero com as 4 chaves novas (pasta/nome): enviados ganham dados
# frescos; pulados carregam o registro anterior. Chaves antigas (sem pasta) somem.
$estadoNovo = @{}
foreach ($e in $aEnviar) {
    $estadoNovo[$e.chave] = @{ linhas = $e.linhas; enviado_em = (Get-Date -Format "s"); mtime_origem = $e.mtime }
}
foreach ($p in $pulados) {
    $chaveP = $p.chave
    if ($estadoAnt.ContainsKey($chaveP)) { $estadoNovo[$chaveP] = $estadoAnt[$chaveP] }
}
$estadoNovo | ConvertTo-Json | Out-File -FilePath $estadoPath -Encoding utf8
Log "estado gravado: $estadoPath"

# --- Fase 6: verificacao fim a fim (best-effort; nao derruba um envio ja feito)
try {
    $health = Invoke-RestMethod "https://gerenciador-gclt.com/api/health" -TimeoutSec 30
    Log ("api/health: " + ($health | ConvertTo-Json -Compress -Depth 5))
} catch {
    Log "AVISO: api/health inacessivel (o envio em si foi concluido): $($_.Exception.Message)"
}

Log "=== SYNC OK: $($aEnviar.Count) enviado(s), $($pulados.Count) sem mudanca ==="
exit 0
