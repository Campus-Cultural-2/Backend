# E2E — Campus Cultural

Suite de testes end-to-end em Bruno (formato YAML / OpenCollection 1.0.0) que cobre
exaustivamente todas as rotas expostas em `api/features/` mais o `/health` global.

Diferente da pasta `tests/` (pytest + `TestClient` em processo), esta suite roda
contra a aplicação real, com servidor ASGI, banco SQLite no disco, lifespan
executado (incluindo o seed do admin padrão) e JWT real circulando entre
requests.

## Pré-requisitos

- Bruno CLI 3.x instalado (`bru --version`).
- API rodando localmente em `http://localhost:8000`:
  ```
  uv run task dev
  ```
- Variáveis `CLOUDINARY_*` preenchidas no `.env` da API. Sem elas o upload
  de profile picture responde 503 e a pasta `Users/Profile Picture` falha.

## Como executar

A partir da raiz do repositório:

```
cd e2e
bru run -r . --env Local
```

Saída esperada (estado verde): **50 requests / 114 tests** passando.

### Subconjuntos úteis

```
bru run "Health"                       --env Local
bru run "Users/Auth"                   --env Local
bru run "Users/Auth" "Users/CRUD"      --env Local
bru run "Users/Profile Picture"        --env Local   # depende de auth prévia
bru run "Events"                       --env Local   # depende de auth prévia
```

> Os subconjuntos que dependem de autenticação precisam que `Users/Auth/Login Student`
> tenha rodado antes — caso contrário `{{authToken}}` fica vazio e tudo cai em 401.

## Estrutura

```
e2e/
├── opencollection.yml            # raiz da collection (OpenCollection 1.0.0)
├── environments/
│   └── Local.yml                 # baseUrl + credenciais do admin padrão
├── fixtures/
│   └── pixel.png                 # PNG 1x1 usado no upload de profile picture
├── Health/
│   └── Health Check.yml
├── Users/
│   ├── Auth/                     # register, login, refresh-token (happy + erros)
│   ├── CRUD/                     # list, get, update, delete (happy + erros)
│   └── Profile Picture/          # upload/download/remoção (happy + erros)
├── Events/                       # create, list, get, update, delete (happy + erros)
└── Cleanup/
    └── Delete Student.yml        # remove o student criado, deixa o DB só com admin
```

Cada arquivo `.yml` é um request. Cada pasta tem um `folder.yml` que define o
`seq` (ordem de execução dentro do pai).

## Ambiente

`environments/Local.yml` aponta para `http://localhost:8000` e contém o
e-mail/senha do admin padrão (`admin@example.com` / `admin123`) que é seedado
pelo lifespan da aplicação na primeira inicialização.

Para um run "limpo" (sem dados de execuções anteriores), apague o SQLite antes:

```
rm database/app.db
```

A aplicação recria as tabelas e o admin padrão no próximo start.

## Convenções

- **Auth chain.** `Users/Auth/Login Student` salva o `access_token` em
  `{{authToken}}` via `bru.setVar`. Todos os requests autenticados usam
  `auth: { type: bearer, token: "{{authToken}}" }`. `Login Admin` também
  decodifica o JWT para armazenar `{{adminId}}` e `{{adminToken}}`, usados
  por testes que precisam do admin (ex.: `Get Profile Picture Not Found`).
- **Negativos (401).** Cada request negativo sobrescreve `auth: { type: none }`
  no nível do request, garantindo que o token inherido seja ignorado.
- **Idempotência.** Os registros `Register Student` e `Register Professor`
  geram e-mail e RA únicos a cada run via `Date.now()` num script
  `before-request`. Rodar `bru run` várias vezes contra o mesmo SQLite
  funciona sem conflito.
- **Asserções por request.** No mínimo: status code, shape do response
  (chaves esperadas, valores de identidade) e, em erros, o `body.code` igual
  ao `ErrorCode` definido em `api/shared/exceptions.py`.
- **Binary upload.** O upload de profile picture usa `body.type: file`
  apontando para `./fixtures/pixel.png` — o path é resolvido em relação à
  raiz da collection (`e2e/`), não ao arquivo do request.
- **Ordem de execução.** `seq` define a ordem dentro de cada pasta. A ordem
  natural — `Health` (1) → `Users/Auth` (1) → `Users/CRUD` (2) →
  `Users/Profile Picture` (3) → `Events` (3 — depende de `authToken` já
  populado) → `Cleanup` (4) — satisfaz as dependências de dados.

## Matriz de cobertura

| Rota                                       | Métodos cobertos     | Cenários                                                |
| ------------------------------------------ | -------------------- | ------------------------------------------------------- |
| `GET /health`                              | 200                  | happy path                                              |
| `POST /users/register`                     | 201 / 400 / 409 / 422 | student, professor, admin proibido, dup email, dup RA, RA em professor, campo faltando |
| `POST /users/login`                        | 200 / 401            | admin, student, senha errada, e-mail desconhecido       |
| `POST /users/refresh-token`                | 200 / 401            | happy, sem token, token malformado                      |
| `GET /users`                               | 200 / 401            | happy, sem token                                        |
| `GET /users/{id}`                          | 200 / 401 / 404      | happy, sem token, id inexistente                        |
| `PUT /users/{id}`                          | 200 / 401 / 404 / 409 | happy, sem token, id inexistente, e-mail conflitante    |
| `POST /users/{id}/profile-picture`         | 200 / 401 / 404      | happy (octet-stream), sem token, id inexistente         |
| `GET /users/{id}/profile-picture`          | 307→200 / 401 / 404  | happy (redirect para o Cloudinary), sem token, admin sem foto |
| `DELETE /users/{id}/profile-picture`       | 204 / 401 / 403 / 404 | happy (apaga do Cloudinary), sem token, foto de outro usuário, já removida |
| `DELETE /users/{id}`                       | 204 / 401 / 404      | professor (em CRUD), sem token, id inexistente, student (cleanup) |
| `POST /events`                             | 201 / 401 / 422      | happy, sem token, campo faltando                        |
| `GET /events`                              | 200                  | happy (público)                                         |
| `GET /events/{id}`                         | 200 / 404            | happy (público), id inexistente                         |
| `PUT /events/{id}`                         | 200 / 401 / 404      | happy (partial update), sem token, id inexistente       |
| `DELETE /events/{id}`                      | 204 / 401 / 404      | happy, sem token, id inexistente                        |

## Quando algum teste falhar

1. Confirme que a API está rodando (`curl http://localhost:8000/health`).
2. Para falhas de conflito (409 inesperado em algum register), apague o
   SQLite e tente novamente — algum estado de run anterior pode ter
   colidido.
3. O warning `toBrunoAuth failed: Unsupported auth type` na stderr é
   inofensivo: o Bruno CLI 3.3 imprime esse log mesmo quando o header
   `Authorization` é enviado corretamente. Ignore.
4. Se o upload de profile picture falhar com `File ... is not a file`,
   verifique se o `filePath` está relativo à raiz da collection
   (`e2e/fixtures/pixel.png`).
