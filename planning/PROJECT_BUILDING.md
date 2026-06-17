# OBJECTIVE

Estruturar o desenvolvimento via arquitetura de projetos com IA para tornar eficazes os outputs.

## Glossário

a - anulado
f - Revisão Futura
x - concluído
n - Não se aplica
r - Rollback - falhou

## Fases

[x] - Escreva em CLAUDE: Não faça alterações em PROJECT_BULDING.md. As fases e controles de progresso deve ser feitos e registrados em PLAN.md.
[x] - Construir pasta planning E criar arquivo PLAN.md
[ ] - Escrever no CLAUDE.md que toda a documentação estará em `planning` directory e o key document is PLAN.md
[a] - Criar o hook de revisão por outra IA (Kimi, Codex) e escrever em REVIEW.md
[a] - Criar uma pesquisa do plano equivalente ao texto abaixo:
    - "Realize uma pesquisa abrangente(...) e escreva documentos no diretório de planejamento em XXX_API.md"
    - "Pesquise API. Escreva a documentação com exemplos de código"
    - "Use isso para projetar a API em Python que deve ser usada para XXXX. Documente isso em XXX.md"
    - Por fim, documente a estrutura de código para [OBJETIVO]
[ ] - Criar novo arquivo com a estrutura do backend em detalhes, com code snippets mais exemplo, de todas funcionalidades, escreva tudo em XXX_BACKEND.md
[ ] - Subplanos dentro do plano para cada grande marco de implementação com certificação de bons testes em cada subplano
[ ] - Prepara o Github
[ ] - Preparar o gitignore
[ ] - Crie a pasta bug_fix
[ ] - Usar Skill SDD para planejas as fases e subfases. GSD, feature-dev e superpowers são bons exemplos
[a] - Definir se o projeto usará single ou mult agents
[x] - Adicionar BEHVIORAL_GUIDELINES à pasta do projeto e no claude.
[ ] - Após o /init - Leia todo o conteúdo de planning/. Depois, escreva o planning/ADVERSARIAL_REVIEW.md, que testa as falhas e ambiguidades do script: "Aja como um adversário maximamente competente. Sua tarefa é encontrar todas as ambiguidades, lacunas semânticas e formulações suaves neste documento que permiritiram a você seguir tecnicamente a refra enquanto viala seu espírito. Liste cada brecha com o caminho de exploração específico".
[ ] - Solicitar que desenvolvimento do site seja feito em pequenas partes para facilitar o teste humano.
[ ] - Mapa de testes (o que teste e como testar) escrito em um arquivo TESTES.md. Explica o teste de cada fase caso queira repetir. 
[ ] - Comparar arquitetura atual e clean Architecture
[ ] - Avaliar usar sandbox e WSL2/VSCODE Ubuntu para execução
[ ] - Criar e instalar dependências
[ ] - Governança de desenvolvimento - Explica critérios de sucesso de cada fase em `definition of done.md` para humanos poderem acompanhar.
[ ] - sinalizar quais arquivos da NÃO SÃO entradas (raiz, scripts antigos, minhas_notas.ignore)
[a] - Criar a pasta script_antigos e informar ao claude para ignorar a pasta
[x] - Clonar o repositório do thariq https://github.com/ThariqS/html-effectiveness. Crie um html de [tarefa] inspirados nos modelos disponíveis em html-effectveness/ para aumentar minha compreensão das suas atividades e a eficiência das minhas decisões.
[n] - AI Operational assistant prompt - Atue como a personalidade  do documento com o qual estou interagindo. Seu nome é "Assistente de IA". Usando o contexto fornecido, responda à pergunta do usuário da melhor forma possível utilizando os recursos disponibilizados.
[x] - Convenção de documentação do código - "Toda função com docstring explicando, nesta ordem: por que a função existe (o problema que ela resolve / o motivo de ser função separada); a lógica do input ao output, em fases numeradas (Entrada → Fase 1 → Fase 2 → … → Saída), descrevendo o que cada bloco transforma. Além disso, toda linha de código comentada — inclusive as que parecem óbvias."

Se não houver nada no contexto relevante para a pergunta em questão, apenas diga "Hmm, não tenho certeza" e pare por aí. Recuse-se a responder qualquer pergunta que não seja sobre essas informações. Nunca saia do personagem.

### Python emv
1 - powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
2 - .venv\Scripts\activate

### Requirements
4 - uv pip install ....
5 - uv pip freeze > requirements.txt