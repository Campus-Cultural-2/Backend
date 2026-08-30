# Campus Cultural Backend

API backend do projeto usando Python.

## Fluxo de desenvolvimento

Para contribuir no projeto, siga este fluxo:

1. Clone o repositório e entre na branch `develop`.
2. Crie uma nova branch a partir de `develop` para implementar sua alteração.
3. Faça o desenvolvimento, rode os testes e valide o lint localmente.
4. Envie sua branch para o repositório remoto.
5. Abra uma Pull Request com destino para a branch `develop`.
6. Após a revisão e aprovação, faça o merge da Pull Request.

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

Depois disso, a API ficará disponível em:

- `http://127.0.0.1:8000`
- Documentação automática: `http://127.0.0.1:8000/docs`

## Deploy

O deploy roda no Render e a configuracao esta versionada em
[`render.yaml`](render.yaml). O banco de producao e um Postgres no Neon.

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
