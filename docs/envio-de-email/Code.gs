// Envia os e-mails do Campus Cultural (codigo de recuperacao de senha e
// codigo de confirmacao de e-mail) pela conta Gmail que publicou o script.
//
// Por que existe: o plano gratuito do Render bloqueia as portas do SMTP, e os
// servicos de e-mail transacional pedem dominio proprio ou dados de empresa.
// O backend chama este script por HTTPS, que o Render libera, e ele envia
// pelo Gmail. Como montar: docs/envio-de-email/README.md.
//
// O segredo NAO fica neste arquivo. Ele fica em Configuracoes do projeto >
// Propriedades do script, com o nome SEGREDO, e o mesmo valor vai na
// variavel EMAIL_RELAY_SECRET do Render. Assim este codigo pode ficar no
// repositorio sem expor nada.

// So envia para estes dominios. O backend ja so cadastra e-mails da UTFPR;
// isto e uma segunda trava: mesmo quem descobrisse o segredo nao conseguiria
// usar a conta para mandar e-mail para fora da universidade.
var DOMINIOS_PERMITIDOS = ['utfpr.edu.br', 'alunos.utfpr.edu.br'];

var TAMANHO_MAXIMO_ASSUNTO = 200;
var TAMANHO_MAXIMO_HTML = 20000;

function doPost(e) {
  try {
    var dados = JSON.parse(e.postData.contents);

    var segredo = PropertiesService.getScriptProperties().getProperty('SEGREDO');
    if (!segredo || segredo.length < 32 || !iguais(String(dados.secret || ''), segredo)) {
      return resposta(false, 'unauthorized');
    }

    // Um destinatario so: sem virgula, ponto e virgula ou espaco, que o Gmail
    // trataria como varios enderecos.
    var para = String(dados.to || '').trim().toLowerCase();
    var partes = /^[^@\s,;]+@([^@\s,;]+)$/.exec(para);
    if (!partes || DOMINIOS_PERMITIDOS.indexOf(partes[1]) === -1) {
      return resposta(false, 'recipient_not_allowed');
    }

    var assunto = String(dados.subject || '');
    var html = String(dados.html || '');
    if (!assunto || !html || assunto.length > TAMANHO_MAXIMO_ASSUNTO || html.length > TAMANHO_MAXIMO_HTML) {
      return resposta(false, 'invalid_message');
    }

    if (MailApp.getRemainingDailyQuota() < 1) {
      return resposta(false, 'quota');
    }

    MailApp.sendEmail({
      to: para,
      subject: assunto,
      htmlBody: html,
      name: String(dados.senderName || 'Campus Cultural UTFPR'),
    });
    return resposta(true, null);
  } catch (erro) {
    // O detalhe fica so em Execucoes, no editor do Apps Script. O endereco
    // de quem recebe nao entra no log.
    console.error('Falha ao enviar: ' + (erro && erro.name));
    return resposta(false, 'error');
  }
}

// Rode esta funcao uma vez pelo editor (botao Executar) antes de publicar:
// o Google pede a permissao de enviar e-mail, e o log mostra quantos envios
// ainda restam hoje.
function testarPermissao() {
  console.log('Envios restantes hoje: ' + MailApp.getRemainingDailyQuota());
}

// Compara sem parar no primeiro caractere diferente, para o tempo de resposta
// nao dar pistas sobre o segredo.
function iguais(a, b) {
  if (a.length !== b.length) {
    return false;
  }
  var diferenca = 0;
  for (var i = 0; i < a.length; i++) {
    diferenca |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return diferenca === 0;
}

function resposta(ok, erro) {
  return ContentService.createTextOutput(JSON.stringify({ ok: ok, error: erro })).setMimeType(
    ContentService.MimeType.JSON
  );
}
