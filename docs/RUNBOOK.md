# Runbook de operação

Guia para quando algo dá errado em produção, ou quando é preciso mexer no
ambiente publicado. Escrito para ser lido **durante** o problema, então cada
seção começa pelo sintoma.

Para o fluxo de desenvolvimento do dia a dia, veja
[`CONTRIBUTING.md`](../CONTRIBUTING.md). Para como o deploy funciona, a seção
**Deploy** do [`README.md`](../README.md).

---

## Onde cada coisa mora

| O quê | Onde | Para quê |
|-------|------|----------|
| API publicada | Render, serviço `campus-cultural-api` | roda a aplicação |
| Banco de produção | Neon (região Ohio) | guarda os dados |
| Imagens | Cloudinary | banners de evento e fotos de perfil |
| Configuração do deploy | [`render.yaml`](../render.yaml) | versionada no repositório |
| Segredos de produção | painel do Render, aba *Environment* | nunca no repositório |
| CI | GitHub Actions, workflow `CI`, job `quality` | roda a cada PR e push na `main` |
| Monitoramento | GitHub Actions, workflow `Monitorar aplicacao` | verifica `/health` a cada 2 horas |

URL de produção: <https://campus-cultural-api.onrender.com>
Documentação interativa: <https://campus-cultural-api.onrender.com/docs>

---

## A API não responde

**Primeiro, descubra se está fora do ar ou apenas dormindo.**

```bash
curl -i --max-time 120 https://campus-cultural-api.onrender.com/health
```

| Resposta | Significado | O que fazer |
|----------|-------------|-------------|
| `{"status":"ok"}` depois de ~1 min | estava dormindo | nada, é o plano gratuito |
| `{"status":"ok"}` imediato | está no ar | o problema é outro |
| `x-render-routing: no-server` | **o serviço não existe** | recriar pelo Blueprint |
| 502 / 503 | a aplicação não sobe | ver os logs, seção seguinte |

O plano gratuito do Render dorme depois de 15 minutos sem tráfego, e acordar
leva cerca de um minuto. **Isso não é bug.** Use `--max-time 120` no curl, ou
vai parecer queda.

---

## A aplicação não sobe depois de um deploy

Abra o serviço no Render e vá em **Logs**. A causa mais comum é configuração,
e nesse caso a aplicação diz exatamente o que falta:

```
Configuração de produção inválida:
  - JWT_SECRET_KEY ainda está no valor de desenvolvimento...
  - CORS_ORIGINS não pode ser '*' em produção.
```

Isso é proposital: a aplicação **se recusa a subir** com configuração insegura,
em vez de subir e funcionar errado. Corrija as variáveis na aba *Environment* e
o Render refaz o deploy sozinho.

Variáveis exigidas em produção:

| Variável | Valor |
|----------|-------|
| `ENVIRONMENT` | `production` |
| `DATABASE_URL` | string do Neon, colada como o Neon entrega |
| `JWT_SECRET_KEY` | 64 caracteres aleatórios, ver seção de rotação |
| `SEED_DEFAULT_ADMIN` | `false` |
| `CORS_ORIGINS` | origens do front, separadas por vírgula, nunca `*` |
| `CLOUDINARY_CLOUD_NAME` | painel do Cloudinary, *Settings > API Keys* |
| `CLOUDINARY_API_KEY` | idem |
| `CLOUDINARY_API_SECRET` | idem |

Se o erro **não** for de configuração, procure no log a falha do
`alembic upgrade head`: as migrations rodam antes da aplicação, e se falharem o
`&&` impede a aplicação de subir com o banco no formato errado. É o
comportamento desejado — conserte a migration, não contorne.

---

## Voltar para a versão anterior (rollback)

No Render, abra o serviço, vá em **Deploys**, ache um deploy anterior que
funcionava e use **Rollback to this deploy**.

> **Rollback volta o código, não o banco.** Se o deploy ruim rodou uma migration
> que alterou tabelas, a versão antiga do código vai encontrar um banco no
> formato novo. Para migration que só adiciona coluna isso costuma funcionar;
> para migration que apaga ou renomeia, não. Nesse caso veja a seção de
> restauração do banco.

---

## O deploy não dispara depois do merge

O `render.yaml` usa `autoDeployTrigger: checksPass`, e **o Render não publica um
commit que não tenha nenhuma checagem**.

Confira, nesta ordem:

1. O workflow `CI` rodou para aquele commit na `main`? Veja a aba *Actions*.
2. O gatilho `push` para `main` ainda existe em
   [`.github/workflows/main.yml`](../.github/workflows/main.yml)? Se alguém
   removeu achando que `pull_request` bastava, **os deploys param em silêncio**.
3. A checagem ficou vermelha? Então o Render não publica mesmo, por desenho.

Para publicar na mão enquanto investiga: Render → **Manual Deploy** →
*Deploy latest commit*.

---

## Perdemos dados no banco

**Aja rápido: a janela de recuperação do Neon no plano gratuito é de 6 horas.**
Passado esse tempo, não há como voltar.

### 1. Não restaure a `main` do banco

Restaurar o branch principal desfaz tudo que aconteceu desde o ponto escolhido,
inclusive dados legítimos criados depois, e pode devolver o schema para um
formato que a aplicação publicada não espera mais.

### 2. Crie um branch de restauração

No console do Neon: **Branches → Create branch → a partir de um ponto no tempo**.
Escolha um horário imediatamente anterior ao incidente. Isso cria uma cópia
independente, sem tocar em produção.

### 3. Veja o que havia lá

Use o SQL editor do Neon **apontando para o branch de restauração**:

```sql
SELECT count(*) FROM users;
SELECT count(*) FROM events;
```

Confirme que os dados estão nessa cópia antes de qualquer outra coisa.

### 4. Traga só o que precisa

Normalmente é mais seguro **recriar pela aplicação** do que copiar linhas entre
bancos, porque o schema pode ter mudado. Para volume pequeno, refazer pelo app é
mais rápido e não arrisca inconsistência.

### 5. Apague o branch de restauração

Ele consome a cota de 0,5 GB do plano gratuito.

> **Não existe backup automático.** A janela de 6 horas do Neon é a única rede.
> Se o projeto passar a ter dados que importam, isso precisa mudar.

---

## Trocar o segredo dos tokens (`JWT_SECRET_KEY`)

Necessário se o segredo vazar — commit acidental, print em grupo, qualquer
exposição.

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Coloque o valor na aba *Environment* do Render. O serviço reinicia sozinho.

> **Todo mundo é deslogado.** O segredo assina os tokens; trocando ele, os
> tokens existentes deixam de valer. É o efeito desejado quando houve vazamento.

Apagar a mensagem onde o segredo apareceu **não resolve**: se foi para o git,
está no histórico. Trocar é o único jeito.

---

## Criar o primeiro administrador

Em produção `SEED_DEFAULT_ADMIN=false`, então não existe admin no banco. A API
também bloqueia criação de admin de propósito.

1. Cadastre um usuário normal pelo app.
2. No SQL editor do Neon, promova:

```sql
UPDATE users SET role = 'admin' WHERE email = 'seu-email@utfpr.edu.br';
```

3. Faça logout e login de novo no app: o papel vai dentro do token, então o
   token antigo continua dizendo que você é estudante.

---

## As imagens não aparecem ou não sobem

As imagens ficam no **Cloudinary**; o banco guarda só o link e o `public_id`.

| Sintoma | Causa provável |
|---------|----------------|
| Upload falha com erro de configuração | alguma variável `CLOUDINARY_*` faltando no Render |
| Imagem some do app mas o evento existe | o registro aponta para um `public_id` apagado no Cloudinary |
| Imagens antigas sumiram de uma vez | a migration `9d706e24796a` descartou as imagens que estavam dentro do banco; precisam ser reenviadas pelo app |

O `CLOUDINARY_API_SECRET` fica **apenas no backend**. Nunca vai para o app nem
para o site: só o backend conversa com o Cloudinary.

---

## O monitoramento começou a falhar

O workflow `Monitorar aplicacao` roda `curl --fail` contra `/health` a cada 2
horas e manda e-mail quando falha.

- **Falhou uma vez e voltou:** provavelmente o serviço estava acordando e
  passou do tempo. Não é incidente.
- **Falha sempre:** a API está fora do ar de verdade, volte para a primeira
  seção.
- **Parou de rodar sozinho:** o GitHub desativa workflows agendados depois de
  60 dias sem atividade no repositório. Ele avisa por e-mail antes; basta
  reativar na aba *Actions*.

Para verificar na hora: *Actions* → **Monitorar aplicacao** → **Run workflow**.

---

## Limites dos planos gratuitos

Vale conhecer antes de bater neles, porque o efeito é o serviço parar.

| Serviço | Limite | O que acontece ao estourar |
|---------|--------|----------------------------|
| Render | 750 horas de execução por mês | **suspende** os serviços gratuitos até o mês seguinte |
| Neon | 0,5 GB de armazenamento, 100 horas de compute | suspende o compute até o mês seguinte |
| Neon | 6 horas de histórico | sem recuperação além disso |
| GitHub Actions | minutos de build do plano | builds bloqueados até o mês seguinte |

Um mês tem cerca de 730 horas, e o Render dá 750. Por isso o monitoramento roda
a cada 2 horas e não a cada 15 minutos: com intervalo curto a aplicação nunca
dorme e consome quase toda a cota — o monitoramento causaria a queda que existe
para detectar.
