# Como contribuir — Campus Cultural (Backend)

Guia do fluxo de trabalho do time: setup, branch, código, checagens e Pull Request.

O ciclo do dia a dia é sempre o mesmo:

```
main atualizada → branch → código → checagens locais → commit → push → PR → review + CI → merge
```

> **O projeto usa uma branch só: `main`.** Não existe branch `develop`. Todo trabalho sai de
> `main` em uma branch curta e volta para `main` por Pull Request. O que protege a `main` não é
> uma branch intermediária: é a **branch protection** do GitHub exigindo Pull Request e CI verde
> antes do merge.

---

## Antes de tudo: são dois repositórios

| Repositório | O que tem lá |
|-------------|--------------|
| [Backend](https://github.com/Campus-Cultural-2/Backend) | A API. Python, FastAPI, banco de dados e todas as regras de negócio. |
| [Frontend](https://github.com/Campus-Cultural-2/Frontend) | O app. Expo, React Native e todas as telas. |

São repositórios separados, com históricos, branches e Pull Requests separados. A maioria das
tarefas mexe em só um. Uma tarefa que mexe nos dois precisa de **dois Pull Requests**, e eles
devem ser mergeados próximos um do outro para as duas metades não ficarem incompatíveis.

> **Atenção:** todo comando `git` vale para a pasta em que você está. Rodar `git status` na
> pasta errada é a maior fonte de confusão quando se trabalha nos dois repositórios. Na dúvida,
> confirme com `git branch --show-current`.

---

## Parte 1 — Setup inicial

Feito uma vez por máquina.

Pré-requisito: [uv](https://docs.astral.sh/uv/) instalado. Ele cuida do Python, do ambiente
virtual e de todas as dependências.

```bash
git clone https://github.com/Campus-Cultural-2/Backend.git
cd Backend
uv sync
uv run task dev
```

Abra <http://127.0.0.1:8000/docs>. Se a documentação da API aparecer, o setup está pronto.

O `task dev` roda `alembic upgrade head` antes de subir a API, então o banco local é
criado sozinho no primeiro uso. É exatamente o que o Render faz em produção: a
aplicação **não** cria tabelas ao subir, quem cria é o Alembic.

### Sobre o `.env`

- `.env.example` **é versionado** e tem valores de exemplo. Ele documenta quais configurações existem.
- `.env` **nunca é versionado** (está no `.gitignore`) e tem os seus valores reais.

**No backend o `.env` é opcional.** Toda configuração tem um valor padrão seguro de
desenvolvimento, então `uv run task dev` funciona em um clone limpo, sem nenhum setup. Copie o
exemplo se quiser ver quais opções existem:

```bash
cp .env.example .env
```

> No frontend é o contrário: lá o `.env` é **obrigatório**, porque não existe padrão razoável
> para "onde está o servidor". Sem ele o app quebra ao iniciar.

> **Nunca commite um segredo de verdade.** Nem no `.env`, nem em comentário no código, nem em
> print no grupo. Se acontecer sem querer, avise na hora: um segredo que foi enviado precisa ser
> **trocado**, não apenas apagado, porque ele fica no histórico do git para sempre.

---

## Parte 2 — O ciclo do dia a dia

### 1. Comece de uma `main` atualizada

Sempre. Criar branch a partir de uma `main` desatualizada é o que gera conflito chato depois.

```bash
git checkout main
git pull
```

### 2. Crie uma branch para a sua tarefa

Uma branch por tarefa. Mantenha pequena — uma branch que mexe em trinta arquivos é impossível de
revisar, e o revisor vai ou aprovar sem ler ou deixar parada por uma semana.

```bash
git checkout -b feat/inscricao-em-evento
```

### 3. Escreva o código

Siga o que já está documentado no repositório:

- [`README.md`](README.md) — arquitetura em camadas e comandos disponíveis.
- [`AGENTS.md`](AGENTS.md) — regras de código: controller fino, regra de negócio no service,
  acesso a banco no repository.

Adicione ou atualize testes quando o comportamento mudar.

### 4. Rode as checagens localmente — antes do push

São **as mesmas** checagens que o CI vai rodar. Rodar agora evita um PR vermelho e dez minutos
de espera.

```bash
uv run task format    # reescreve seu código no padrão do projeto
uv run task check     # lint + os 46 testes
```

### 5. Faça o commit no padrão do time

Veja a Parte 3 para os prefixos. Escreva no imperativo e diga **o que mudou**.

```bash
git add .
git commit -m "feat: adiciona inscricao em evento"
```

### 6. Envie a branch

O primeiro push de uma branch nova precisa do `-u` para ligá-la ao remoto. Depois disso, só
`git push`.

```bash
git push -u origin feat/inscricao-em-evento
```

### 7. Abra o Pull Request com destino a `main`

O GitHub mostra um botão "Compare & pull request" depois do push.

Na descrição, diga o que mudou, por quê, e como o revisor pode testar. Duas frases bastam.

### 8. Espere o CI e peça review

O robô roda as checagens em uma máquina limpa. Se ficar vermelho, corrija e faça push de novo —
o mesmo Pull Request se atualiza sozinho, não precisa abrir outro.

Depois um colega revisa. Comentários são sobre o código, não sobre você.

### 9. Faça o merge e limpe

Com o CI verde e o review aprovado, faça o merge em `main`. Depois apague a branch (o GitHub
oferece um botão) e limpe a sua máquina:

```bash
git checkout main
git pull
git branch -d feat/inscricao-em-evento
```

---

## Parte 3 — Convenções de nome

O time já usa isso na maior parte dos commits. O valor está em usar **de forma consistente**,
para o histórico continuar legível daqui a um ano.

### Mensagens de commit — Conventional Commits

Formato: `tipo: descrição curta em minúsculas`

| Prefixo | Use para | Exemplo |
|---------|----------|---------|
| `feat:` | funcionalidade nova que o usuário percebe | `feat: adiciona tela de perfil` |
| `fix:` | correção de bug | `fix: corrige data invalida no calendario` |
| `refactor:` | reorganização sem mudar comportamento | `refactor: organiza camada de api` |
| `test:` | só testes | `test: cobre login com usuario inativo` |
| `docs:` | só documentação | `docs: atualiza README de setup` |
| `chore:` | ferramentas, configuração, dependências | `chore: atualiza dependencias` |

### Nomes de branch

Formato: `tipo/descricao-curta-com-hifens`, com os mesmos prefixos acima.

| Bom | Evite |
|-----|-------|
| `feat/inscricao-em-evento` | `dev_calendario` — underline, sem tipo |
| `fix/refatora-arquitetura` | `tela-Login` — maiúscula, sem tipo |
| `chore/atualiza-dependencias` | `teste` — não diz nada |

### Idioma

A convenção do projeto, registrada no `AGENTS.md`: **código e identificadores em inglês, texto
para o usuário final e descrição de commit em pt-BR.**

---

## Parte 4 — O que o CI verifica

O CI é uma máquina Ubuntu nova que clona a sua branch, instala tudo do zero e roda as checagens.
Ele prova que o seu código funciona em outro lugar além da sua máquina.

| Verifica | Reproduza localmente com |
|----------|--------------------------|
| Formatação, lint e os 46 testes | `uv run task format-check && uv run task check` |

### Quando o CI ficar vermelho

**Reproduza localmente com o mesmo comando.** Leia o log: abra o passo que falhou na aba
*Actions* do GitHub e procure o **primeiro** erro, não o último. Erros se acumulam em cascata; o
primeiro costuma ser o de verdade.

Causas mais comuns:

- **Formatação** — você esqueceu de rodar `uv run task format`.
- **Um teste que você não rodou** — rodou um arquivo só, em vez da suíte inteira.
- **"Na minha máquina funciona"** — normalmente um arquivo que você esqueceu de commitar, ou uma
  dependência instalada localmente e não adicionada ao `pyproject.toml`.

> **Nunca faça merge de um Pull Request vermelho.** Se uma checagem parece errada, conserte a
> checagem — não passe por cima dela. Um CI que todo mundo ignora é pior que não ter CI, porque
> parece proteção sem proteger nada.

---

## Parte 5 — Revisão de código

**Como autor:**

- Mantenha o PR pequeno e focado em uma coisa só.
- Explique o **porquê**; o diff já mostra o quê.
- Responda todos os comentários, mesmo que seja só "feito".
- Envie correções como commits novos. Não faça force-push no meio da revisão — isso apaga o
  ponto onde o revisor estava.

**Como revisor:**

- Revise no mesmo dia. PR parado apodrece e acumula conflito.
- Separe "isso está quebrado" de "eu teria feito diferente".
- Baixe a branch e rode de verdade quando a mudança não for trivial.
- Aprove quando estiver bom o suficiente, não quando estiver perfeito.

---

## Parte 6 — Chegando em produção

**`main` é a única branch de longa duração, e ela deve estar sempre funcionando.** Todo Pull
Request mergeado entra nela.

Quando o deploy automático estiver configurado, **todo merge em `main` vai publicar para os
usuários reais**. Isso é intencional, e é por isso que a branch protection não é opcional: ela
é o que garante que só entra em `main` código revisado e com CI verde.

> **Não faça merge de algo grande numa sexta à tarde.** Não é superstição: se quebrar, quem sabe
> consertar já foi embora. Publique quando o time estiver por perto.

---

## Parte 7 — Problemas comuns

### Conflito de merge

Acontece quando a sua branch e a `main` mudaram as mesmas linhas. Não é desastre:

```bash
git checkout main
git pull
git checkout sua-branch
git merge main
# resolva os conflitos marcados no editor, depois:
git add .
git commit
```

Trazer a `main` para a sua branch com frequência mantém os conflitos pequenos.

### Um diff gigante de arquivos que você não tocou

É quebra de linha — diferença entre Windows e Mac. O repositório tem um `.gitattributes` para
evitar isso. Se acontecer mesmo assim, avise quem cuida do DevOps em vez de commitar.

### Cuidado com o terminal na mensagem de commit

O histórico deste repositório tem um commit chamado
`Mource /Users/.../activate rge branch 'main' into develop` — alguém colou um comando no meio da
mensagem de merge. Se a mensagem sair estranha, corrija **antes** do push com
`git commit --amend`. Depois do push, ela é permanente.

---

## Onde está o resto da documentação

| Arquivo | Cobre |
|---------|-------|
| [`README.md`](README.md) | Arquitetura (controller → service → repository), comandos `task`, estrutura de pastas |
| [`AGENTS.md`](AGENTS.md) | Regras de código do backend — o que fazer e o que não fazer |
| [`e2e/README.md`](e2e/README.md) | Suíte end-to-end em Bruno rodando contra um servidor de verdade |
| [`.env.example`](.env.example) | Todas as configurações que existem, com explicação |

> **Documentação envelhece.** Quando você mudar o comportamento, atualize a documentação no
> mesmo Pull Request. Documentação que mente é pior que documentação que não existe.
