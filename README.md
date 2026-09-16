# Campus Cultural Backend

API backend do projeto usando Python.

## Fluxo de desenvolvimento

O projeto usa **uma única branch de longa duração: `main`**. Não existe branch
`develop`. Para contribuir:

1. Clone o repositório e atualize a `main` (`git checkout main && git pull`).
2. Crie uma branch curta a partir da `main`, no formato `tipo/descricao-curta`.
3. Faça o desenvolvimento, rode os testes e valide o lint localmente
   (`uv run task format && uv run task check`).
4. Envie sua branch para o repositório remoto.
5. Abra uma Pull Request com destino para a branch `main`.
6. Após o CI verde e a aprovação na revisão, faça o merge da Pull Request.

A `main` é protegida por *branch protection*: só aceita commit via Pull Request com
a checagem `quality` do CI passando. O merge na `main` dispara o deploy automático.

O fluxo completo, com convenções de nome e o que fazer quando o CI falha, está em
[`CONTRIBUTING.md`](CONTRIBUTING.md).

## O que este projeto usa

- `FastAPI`: camada HTTP. Recebe requisições, valida entrada e devolve respostas da API.
- `Pydantic`: validação dos dados de entrada e saída da API.
- `SQLAlchemy`: camada de acesso a dados. Faz a comunicação com o banco SQLite.
- `Alembic`: controle de versões do banco de dados (migrations).
- `Pytest`: testes automatizados.
- `Ruff`: lint e formatação de código.
- `Taskipy`: atalhos para comandos frequentes.
- `SQLite`: banco de dados local em arquivo.

## Arquitetura usada

O projeto segue uma separação simples por camadas:

- `Controller`: recebe a requisição HTTP pelo FastAPI, valida os dados com Pydantic e chama a próxima camada.
- `Service`: concentra a regra de negócio.
- `Repository`: faz o acesso ao banco com SQLAlchemy.

Fluxo geral:

`Request HTTP -> Controller -> Service -> Repository -> Banco de Dados`

## Estrutura de pastas

- `api/features/`: código onde ficarão os recursos.
- `api/shared`: código reutilizável da aplicação.
- `database/config`: configuração do banco e da sessão.
- `tests`: testes automatizados.
- `alembic`: arquivos de migration.

## Como instalar as dependências

Se ainda não instalou as dependências do projeto:

```bash
uv sync
```

## Como iniciar o projeto

Comando para subir a API em modo de desenvolvimento:

```bash
uv run task dev
```

Este comando roda `alembic upgrade head` antes do servidor, então o banco local
(SQLite) é criado e atualizado sozinho. A aplicação **não** cria tabelas ao subir:
tanto aqui quanto em produção, quem define o formato do banco é o Alembic.

Depois disso, a API ficará disponível em:

- `http://127.0.0.1:8000`
- Documentação automática: `http://127.0.0.1:8000/docs`

## Deploy

O deploy roda no Render e a configuracao esta versionada em
[`render.yaml`](render.yaml). O banco de producao e um Postgres no Neon.

### Nao existe deploy.yml, e isso e proposital

O deploy **nao** e feito por GitHub Actions. Quem publica e o proprio Render, que
observa a branch `main` — comportamento declarado em [`render.yaml`](render.yaml)
no campo `autoDeployTrigger: checksPass`. Ja e entrega continua: um `deploy.yml`
nao acrescentaria um passo que falta, substituiria por uma versao feita a mao um
passo que a plataforma ja executa.

Sao cinco motivos.

**1. Exigiria uma credencial de producao dentro do GitHub.** Para um workflow mandar
o Render publicar, ele precisaria de uma chave de API do Render guardada nos
*secrets* do repositorio. Hoje **nenhum workflow deste projeto usa `secrets`**: o CI
so le codigo e roda teste.

Isso importa por causa de uma classe de ataque conhecida como **Poisoned Pipeline
Execution** (CICD-SEC-4 do OWASP Top 10 CI/CD). O CI executa codigo de terceiros —
qualquer pessoa pode abrir um Pull Request — com as credenciais que o pipeline
tiver. Como o pipeline nao tem credencial nenhuma, nao ha o que roubar. Colocar uma
chave de deploy ali faria com que executar codigo dentro de uma execucao passasse a
significar publicar em producao. As credenciais ficam so no painel do Render, que e
quem precisa delas; o GitHub nao precisa saber publicar.

**2. Criaria duas descricoes do mesmo processo.** O `render.yaml` ja descreve build,
start, migrations, health check e variaveis. Um `deploy.yml` seria uma segunda
descricao da mesma coisa, e duas fontes de verdade so concordam enquanto alguem
lembra de atualizar as duas. E o mesmo problema que ja tivemos entre o `create_all`
e o Alembic disputando o formato do banco: resolver aquilo foi escolher uma fonte
de verdade so.

**3. Perderiamos o que a plataforma ja faz.** O Render so considera o deploy
concluido quando a rota `/health` responde, guarda as versoes anteriores com
rollback em um clique, mantem o historico de qual commit esta no ar e so encaminha
trafego para a versao nova depois que ela sobe. Um `deploy.yml` que apenas chamasse
a API e encerrasse nao teria nada disso.

**4. O que garante que so codigo testado vai para producao nao e o deploy.** E a
*branch protection*: a `main` so aceita commit via Pull Request com a checagem
`quality` verde. Quando um commit chega na `main`, ele ja passou pelo CI — nao
existe caminho que pule essa etapa. Alem disso, o `autoDeployTrigger: checksPass`
faz o Render esperar as checagens daquele commit antes de publicar. Um workflow
conferindo o CI de novo seria redundante.

**5. Complexidade sem beneficio e custo puro.** Mais um arquivo para manter, mais um
ponto de falha e mais uma coisa para entender ao entrar no time, para produzir o
mesmo resultado que uma linha de configuracao ja produz.

#### Quando um deploy.yml faria sentido

A recomendacao nao e errada em geral — ela e a resposta certa quando a hospedagem
**nao** observa o repositorio (um VPS, Kubernetes, publicar um APK numa loja),
quando existem passos entre build e publicacao (construir imagem Docker, enviar
para um registry, rodar testes de fumaca, avisar o time), quando ha varios
ambientes com aprovacao manual entre eles, ou quando o deploy precisa coordenar
mais de um repositorio. Nenhum e o caso aqui: um servico, um ambiente, uma
hospedagem que ja observa a `main`.

### Monitoramento

O [`.github/workflows/monitoring.yml`](.github/workflows/monitoring.yml) verifica a
rota `/health` a cada 30 minutos e tambem pode ser disparado a mao. Se a aplicacao
nao responder, a execucao falha e o GitHub notifica por e-mail.

### Como o deploy funciona

1. Merge na `main` dispara o build no Render.
2. `pip install uv && uv sync --frozen --no-dev` instala as dependencias
   exatas do `uv.lock`.
3. `uv run alembic upgrade head` aplica as migrations pendentes. Se falhar,
   a aplicacao nao sobe.
4. `uv run uvicorn main:app` sobe a API.
5. O Render confere a rota `/health` para dar o deploy como concluido.

A aplicacao **nao cria tabelas ao subir**. Quem cria e altera o formato do
banco e o Alembic, no passo 3. Isso evita ter duas fontes de verdade sobre
o schema.

### Variaveis de ambiente em producao

Os valores ficam no painel do Render, nunca no repositorio. O `render.yaml`
declara apenas quais variaveis existem.

| Variavel | Valor |
|----------|-------|
| `ENVIRONMENT` | `production` |
| `DATABASE_URL` | string do Neon, colada como o Neon entrega |
| `JWT_SECRET_KEY` | `python -c "import secrets; print(secrets.token_hex(32))"` |
| `SEED_DEFAULT_ADMIN` | `false` |
| `CORS_ORIGINS` | origens do front, separadas por virgula. Nao pode ser `*` |

Se alguma estiver errada, a aplicacao **se recusa a subir** e os logs do
Render listam exatamente o que esta faltando. Isso e proposital: e melhor
quebrar alto do que subir com um segredo publico ou com o SQLite.

### Primeiro admin em producao

Com `SEED_DEFAULT_ADMIN=false` nao existe nenhum admin no banco, e a API
bloqueia a criacao de admin de proposito. Para criar o primeiro, cadastre
um usuario normal pelo app e promova pelo SQL editor do Neon:

```sql
UPDATE users SET role = 'admin' WHERE email = 'seu-email@utfpr.edu.br';
```

### Plano free do Render

O servico dorme depois de ~15 min sem uso. A primeira requisicao depois
disso leva de 30 a 60 segundos. E esperado; nao e bug.


## Comandos úteis

Executar os testes:

```bash
uv run task test
```

Verificar problemas no código:

```bash
uv run task lint
```

Formatar o código:

```bash
uv run task format
```

Executar lint + testes:

```bash
uv run task check
```

Aplicar migrations:

```bash
uv run task db-upgrade
```

Criar uma nova migration:

```bash
uv run task db-revision -- "nome_da_migration"
```

## Banco de dados

O projeto usa SQLite. O banco local fica no arquivo:

`/backend/database/app.db`

Esse arquivo fica dentro da pasta do projeto e será criado localmente durante o uso da aplicação.

Se quiser limpar o banco local, use:

```bash
uv run task db-clean
```

Na próxima execução da aplicação, o arquivo será criado novamente.

## Testes

Os testes atuais cobrem o CRUD básico de `Usuario`:

- criar
- listar
- buscar por id
- atualizar
- remover

## Observação

Este projeto foi organizado para ficar simples de entender e fácil de evoluir. A ideia é manter cada responsabilidade em sua própria camada, para o código ficar mais limpo e mais fácil de manter.
