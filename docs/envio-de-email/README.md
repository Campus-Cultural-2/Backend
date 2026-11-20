# Envio de e-mail pelo Gmail (Google Apps Script)

A API manda dois tipos de e-mail, os dois com um código de 8 caracteres:

- o código de **recuperação de senha** ("Esqueceu a senha?");
- o código de **confirmação de e-mail**, que toda conta nova precisa digitar
  antes do primeiro login.

## Por que assim

| Opção | Por que não serve |
|-------|-------------------|
| SMTP (Gmail, Outlook…) | o plano gratuito do Render bloqueia as portas de saída 25, 465 e 587: funcionaria na sua máquina e falharia em produção, sem erro visível |
| Resend, Mailgun, Amazon SES | sem domínio próprio, só enviam para o próprio dono da conta |
| Brevo | pede dados de empresa (endereço, CEP) no cadastro |

O caminho que sobra, de graça e sem domínio: um pequeno script no **Google Apps
Script** ligado a uma conta Gmail. A API chama o script por HTTPS (porta 443, que
o Render libera), e o script envia o e-mail pelo Gmail daquela conta.

```
app ──> API no Render ──HTTPS──> script no Google ──Gmail──> caixa do usuário
```

**Limite:** uma conta Gmail comum envia até **100 e-mails por dia** por script.
Para um projeto de faculdade, sobra. Se estourar, os pedidos daquele dia não
enviam (aparece `quota` no log) e voltam a funcionar no dia seguinte.

## Como montar (uma vez só)

### 1. A conta Gmail

Use uma conta Gmail **do projeto**, não a sua pessoal: os e-mails saem com o
endereço dela, e qualquer pessoa da equipe pode precisar mexer nela depois.
Guarde a senha onde a equipe guarda as outras (nunca no repositório).

### 2. Criar o script

1. Entrando com a conta do projeto, abra <https://script.google.com> e clique
   em **Novo projeto**.
2. Dê o nome `Campus Cultural - envio de e-mail` (clique em "Projeto sem título").
3. Apague o conteúdo do arquivo `Código.gs` e cole o conteúdo de
   [`Code.gs`](Code.gs), desta pasta. Salve (Ctrl+S).

### 3. Gerar e guardar o segredo

O segredo é a "senha" que a API manda para o script provar que é ela. Gere um
no seu computador:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

No editor do script: **Configurações do projeto** (ícone de engrenagem) >
**Propriedades do script** > **Adicionar propriedade do script**:

- Propriedade: `SEGREDO`
- Valor: o segredo gerado

Salve. O mesmo valor vai no Render no passo 6. Não cole o segredo em chat,
issue ou commit.

### 4. Dar a permissão de enviar e-mail

1. Volte ao **Editor** (ícone `< >`), escolha a função `testarPermissao` na
   lista ao lado de **Executar** e clique em **Executar**.
2. O Google pede autorização. Escolha a conta do projeto. Vai aparecer
   "O Google não verificou este app": é o seu próprio script, então clique em
   **Avançado** > **Acessar Campus Cultural - envio de e-mail (não seguro)** >
   **Permitir**.
3. O log embaixo deve mostrar `Envios restantes hoje: 100`.

### 5. Publicar

1. **Implantar** > **Nova implantação**.
2. Em "Selecione o tipo", clique na engrenagem > **App da Web**.
3. Preencha:
   - Executar como: **Eu** (a conta do projeto)
   - Quem pode acessar: **Qualquer pessoa**
4. **Implantar** e copie a **URL do app da Web** (termina em `/exec`).

"Qualquer pessoa" é necessário porque a API não tem conta Google. Quem protege
o script é o segredo: sem ele, o script responde `unauthorized` e não envia
nada. E mesmo com o segredo, ele só envia para e-mails da UTFPR.

### 6. Configurar no Render

No serviço da API, aba **Environment**:

| Variável | Valor |
|----------|-------|
| `EMAIL_RELAY_URL` | a URL que termina em `/exec` |
| `EMAIL_RELAY_SECRET` | o mesmo segredo do passo 3 |

Salve; o Render refaz o deploy. Em produção a API **não sobe** sem essas duas
variáveis, de propósito.

### 7. Testar

No app, faça um cadastro com um e-mail seu da UTFPR. O código deve chegar em
até um minuto (olhe o spam). Se não chegar, veja
a seção "O código de recuperação de senha não chega" do
[RUNBOOK](../RUNBOOK.md).

## Mudou o código do script?

Colar código novo no editor **não** muda o que está no ar. Depois de salvar:
**Implantar** > **Gerenciar implantações** > lápis (editar) > Versão:
**Nova versão** > **Implantar**. A URL continua a mesma.

## Trocar o segredo

Se o segredo vazou: gere outro (passo 3), troque a propriedade `SEGREDO` no
script e a `EMAIL_RELAY_SECRET` no Render. Entre a primeira troca e a segunda,
os envios falham com `unauthorized`, então faça as duas em seguida.
