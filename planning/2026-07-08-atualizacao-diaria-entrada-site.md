# Atualização diária de `entrada/` do site (gerenciador-gclt.com) — orientações

> **Para o agente deste projeto (`atualizacao_clientes`).** Este documento foi escrito
> pelo agente do projeto do site (`site_classificacao_beneficiarios_programa`) em
> 2026-07-08 e **atualizado em 2026-07-09** com as respostas de infraestrutura SSH.
> Descreve o que precisa ser desenvolvido AQUI para manter as bases do site
> atualizadas diariamente.

## Contexto

O site **https://gerenciador-gclt.com** (repo `site_classificacao_beneficiarios_programa`,
GitHub privado `GiovanniCharret/sistema_gclt`, produção num VPS Hostinger em
`/opt/anexov`, serviço systemd `anexov-api`) valida planilhas "Anexo V" contra uma
base de referência que vive em `entrada/` daquele repo. Essa base é gerada **aqui**,
pela rodada diária deste projeto (fase1_lnc / fase2_ucs).

**Decisão ATUALIZADA em 2026-07-09 (com o usuário): a sincronização será via
SSH/scp direto ao VPS — solução PROVISÓRIA** (substitui a decisão de 2026-07-08,
que era via git), válida até uma estrutura mais robusta (ex.: endpoint de upload
autenticado) entrar nas próximas versões do site. Fluxo:

```
rodada diária aqui ──▶ scp dos 4 CSVs ──▶ /opt/anexov/entrada/ no VPS
                                                  │
                       backend recarrega sozinho (mtime) — sem restart
```

## Respostas às 3 perguntas de infraestrutura (verificadas em 2026-07-09)

1. **Host/porta:** o SSH atende no próprio domínio — `gerenciador-gclt.com`
   resolve para o IP dedicado do VPS **`82.25.68.143`**, e a **porta 22 está
   aberta** (verificado por teste TCP em 2026-07-09). Pode usar o domínio ou o
   IP; o domínio é preferível (sobrevive a troca de IP), com o IP como fallback
   documentado no script.
2. **Usuário de login SSH:** hoje o acesso usado pelo usuário é **`root`**;
   login direto como `deploy` **ainda não está configurado** (não há
   `authorized_keys` para ele). Recomendação: fazer o **setup único** abaixo para
   logar direto como `deploy` — os CSVs já caem `deploy:deploy` com mtime novo,
   sem `chown`. Enquanto o setup não for feito, o script pode operar como `root`,
   MAS deve terminar com `chown deploy:deploy` nos 4 arquivos (arquivos
   root-owned no working tree de `/opt/anexov` atrapalham operações git futuras
   do usuário `deploy`).
3. **Autenticação/chave:** **não existe chave SSH no DEV ainda** — a pasta
   `C:\Users\GiovanniAzevedoCharr\.ssh\` não existe (verificado em 2026-07-09).
   O Windows tem OpenSSH nativo (`ssh.exe`, `scp.exe`, `ssh-keygen.exe` em
   `C:\Windows\System32\OpenSSH\`). Gerar a chave é parte do setup único abaixo;
   o caminho resultante será **`C:\Users\GiovanniAzevedoCharr\.ssh\id_ed25519`**.
   Concordo: chave, nunca senha em script.

### Setup único (fazer com o usuário, uma vez)

No **DEV** (PowerShell):

```powershell
ssh-keygen -t ed25519 -C "sync-entrada-dev" -f $env:USERPROFILE\.ssh\id_ed25519
# (Enter na passphrase se quiser uso não interativo pelo script/agendador)
type $env:USERPROFILE\.ssh\id_ed25519.pub   # copiar a linha inteira
```

No **VPS** (o usuário loga como root, como faz hoje) — instalar a chave pública
para o usuário `deploy`:

```bash
mkdir -p /home/deploy/.ssh
echo 'ssh-ed25519 AAAA... sync-entrada-dev' >> /home/deploy/.ssh/authorized_keys
chown -R deploy:deploy /home/deploy/.ssh
chmod 700 /home/deploy/.ssh && chmod 600 /home/deploy/.ssh/authorized_keys
```

Teste no DEV: `ssh deploy@gerenciador-gclt.com "ls -la /opt/anexov/entrada/lpt"`
(a primeira conexão pede confirmação do fingerprint do host — aceitar uma vez
interativamente antes de agendar o script).

## O contrato de destino (o que o site espera)

Destino no VPS: `/opt/anexov/entrada/`

| Arquivo de destino (no VPS) | Conteúdo | Formato |
|---|---|---|
| `/opt/anexov/entrada/lpt/consolidado.csv` | consolidado de contratos LPT | CSV, **UTF-8 com BOM** (`utf-8-sig`), separador `;` |
| `/opt/anexov/entrada/lpt/consolidado_ucs.csv` | UCs dos contratos LPT | idem |
| `/opt/anexov/entrada/mla/consolidado.csv` | consolidado de contratos MLA | idem |
| `/opt/anexov/entrada/mla/consolidado_ucs.csv` | UCs dos contratos MLA | idem |

- O backend do site varre `entrada/**/*.csv` e **recarrega sozinho quando o mtime
  muda** — atualizar esses 4 arquivos no VPS **não exige restart nem build**.
- ⚠️ Como o reload é por mtime, **evitar que o backend leia um arquivo pela
  metade** durante a cópia: enviar para um nome temporário e renomear (rename no
  mesmo filesystem é atômico):
  ```
  scp arquivo.csv deploy@HOST:/opt/anexov/entrada/lpt/consolidado.csv.new
  ssh deploy@HOST "mv /opt/anexov/entrada/lpt/consolidado.csv.new /opt/anexov/entrada/lpt/consolidado.csv"
  ```
- ⚠️ `base_contratos.json` (raiz do repo do site) é outra história: o backend o lê
  **uma única vez por processo** (cache sem recarga). Se ele também entrar no sync
  diário, a cópia precisa ser seguida de `systemctl restart anexov-api` — e a
  cópia do front (`modelo/src/base_contratos.json`) exigiria ainda `npm run build`.
  **Por padrão, deixe `base_contratos.json` FORA do sync automático** (confirmar com
  o usuário se/quando incluir).

## O que desenvolver aqui

Um script de sincronização (PowerShell ou Python, seguindo o padrão deste projeto)
que rode **ao final da rodada diária** (ou agendado logo depois dela) e faça:

1. **Mapear** as saídas da rodada (fase1_lnc → `consolidado.csv`,
   fase2_ucs → `consolidado_ucs.csv`; a separação lpt × mla deve ser confirmada com
   o usuário — ele sabe qual saída alimenta qual pasta) para os 4 destinos acima.
2. **Sanidade mínima antes de enviar** (barato, mas evita subir base quebrada):
   - arquivo existe e não está vazio;
   - primeira linha é um cabeçalho plausível (contém `;`);
   - se o nº de linhas cair mais de ~20% em relação ao envio anterior, **abortar
     e avisar** em vez de enviar (rodada parcial é o modo de falha típico).
3. **Envio via scp + rename atômico** (OpenSSH nativo do Windows), por arquivo:
   ```powershell
   $HOST_VPS = "gerenciador-gclt.com"   # IP fallback: 82.25.68.143
   $CHAVE    = "$env:USERPROFILE\.ssh\id_ed25519"
   scp -i $CHAVE saida_lpt.csv deploy@${HOST_VPS}:/opt/anexov/entrada/lpt/consolidado.csv.new
   ssh -i $CHAVE deploy@$HOST_VPS "mv /opt/anexov/entrada/lpt/consolidado.csv.new /opt/anexov/entrada/lpt/consolidado.csv"
   # (repetir para os outros 3 arquivos)
   ```
   - Se o setup do login `deploy` ainda não tiver sido feito e o script rodar como
     `root`: acrescentar ao final
     `ssh root@$HOST_VPS "chown deploy:deploy /opt/anexov/entrada/lpt/*.csv /opt/anexov/entrada/mla/*.csv"`.
4. **Idempotência e log:** rodar duas vezes no mesmo dia não pode causar erro; deixar
   um log simples (data, arquivos enviados, nº de linhas, sucesso/falha por arquivo).
5. **Verificação fim a fim** no final do script (opcional, recomendado):
   `Invoke-RestMethod https://gerenciador-gclt.com/api/health` e logar as
   contagens retornadas.

## ⚠️ Consequência git do transporte via scp (importante)

Os 4 CSVs de `entrada/` **continuam rastreados no git** do repo do site. O scp
diário vai deixá-los **divergentes do HEAD** no working tree do VPS — exatamente o
cenário que aborta `git pull` ("local changes would be overwritten", já vivido com
`usuarios.json` em 2026-07-08). Regras operacionais:

- **Antes de qualquer `git pull` de deploy em `/opt/anexov`** (atualização de
  código do site), descartar as cópias locais primeiro:
  ```bash
  sudo -u deploy git -C /opt/anexov checkout -- entrada/
  sudo -u deploy git -C /opt/anexov pull --ff-only
  ```
  (o scp do dia seguinte — ou uma rodada manual do script — restaura a base atual).
- O cron de `git pull` no VPS (plano antigo de 2026-07-08) **não deve ser criado**
  neste modelo — pull automático + working tree divergente = aborto silencioso.
- Alternativa estrutural (decidir com o usuário, ver pontos em aberto): **parar de
  versionar** os CSVs de `entrada/` no repo do site (gitignore + `git rm --cached`),
  eliminando a divergência de vez.

## Notas do VPS (aprendidas a caminho do V0)

- Git/npm no `/opt/anexov` **sempre como `deploy`** (`sudo -u deploy …`); git rodado
  como root planta arquivos root-owned em `.git/` e quebra pulls futuros
  (`FETCH_HEAD: Permission denied` → corrige com `chown -R deploy:deploy /opt/anexov`).
- O remoto git do VPS usa um **token fine-grained read-only** (repo é privado) —
  irrelevante para o scp, mas continua valendo para deploys de código.

## Regras de segurança (invioláveis)

- A **chave privada** (`id_ed25519`) fica só no DEV — **jamais commitá-la** (nem
  aqui nem no repo do site); só a `.pub` vai para o VPS.
- O repo `GiovanniCharret/sistema_gclt` **deve permanecer privado** (o histórico do
  git contém hashes pbkdf2 de `backend/usuarios.json`, que foi versionado por um dia
  e removido em 2026-07-08).
- **Jamais commitar**: `.env`, `backend/.env`, `backend/usuarios.json` (os usuários
  reais de produção vivem só no VPS) e o arquivo `senha e-mail hostinger` (raiz do
  repo do site).
- O script **nunca** toca em nada fora de `/opt/anexov/entrada/` no VPS.
- Sem senha hardcoded em script — autenticação exclusivamente por chave.

## Verificação de sucesso (fim a fim)

Depois de um envio completo:

```bash
curl -s https://gerenciador-gclt.com/api/health
```

A resposta expõe as contagens da referência (`chaves_uc`, `odi_ref`) e a integridade
(contratos com/sem referência) — os números devem refletir a base nova.

## Pontos em aberto (perguntar ao usuário antes de codar)

1. Qual saída da rodada alimenta `lpt/` e qual alimenta `mla/` (mapeamento exato
   origem → destino)?
2. Disparo: acoplado ao fim do `run*.ps1` da rodada, ou Tarefa Agendada do Windows
   em horário fixo?
3. `base_contratos.json` entra no sync diário ou continua manual? (Se entrar,
   lembrar do restart no VPS + rebuild do front.)
4. **(novo, 2026-07-09)** Os CSVs de `entrada/` continuam versionados no repo do
   site (exigindo o `git checkout -- entrada/` antes de cada deploy) ou saem do
   git (gitignore + `git rm --cached`)? Recomendação do agente do site: sair do
   git, já que o transporte não é mais por commit.
