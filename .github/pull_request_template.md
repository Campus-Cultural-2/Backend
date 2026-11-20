<!--
Este texto aparece sozinho ao abrir uma Pull Request. Preencha e apague o
que nao se aplicar. O objetivo e que quem revisa entenda a mudanca sem
precisar perguntar.
-->

## O que muda

<!-- Uma ou duas frases. O diff mostra o que mudou; aqui diga o porque. -->

## Como testar

<!-- Passos para o revisor conferir. Ex.: rode `uv run task dev`, chame
     POST /events com ..., espere 201. -->

## Checklist

- [ ] Rodei `uv run task format` e `uv run task check` localmente
- [ ] Adicionei ou atualizei testes, se o comportamento mudou
- [ ] Atualizei a documentação afetada (README, CONTRIBUTING, RUNBOOK, `.env.example`)

## Esta PR tem migration?

- [ ] Não tem migration
- [ ] Tem migration, e ela **só adiciona** coisas (coluna, tabela, índice)
- [ ] ⚠️ Tem migration **destrutiva**: apaga ou renomeia coluna ou tabela

> Se marcou a terceira opção, descreva aqui **quais dados são perdidos** e o
> que precisa ser feito depois do deploy. Em produção não existe backup
> automático: a janela de recuperação do Neon é de 6 horas. Veja
> [`docs/RUNBOOK.md`](../docs/RUNBOOK.md).

## Esta PR precisa de variável de ambiente nova?

- [ ] Não
- [ ] Sim — e já declarei em `.env.example` e em `render.yaml` (com `sync: false`
      se for segredo), e vou preencher o valor no painel do Render **antes** do merge

> Se a variável for obrigatória em produção e não estiver configurada, a
> aplicação se recusa a subir e o deploy falha.
