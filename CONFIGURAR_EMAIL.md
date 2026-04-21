# Como Configurar Email SMTP

## Passo 1: Criar arquivo .env

Copie o arquivo `.env.example` para `.env`:

```powershell
copy .env.example .env
```

## Passo 2: Editar o arquivo .env

Abra o arquivo `.env` e configure as variáveis de email:

### Para Gmail:
```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=seuemail@gmail.com
SMTP_PASSWORD=xxxx xxxx xxxx xxxx  # App Password (16 caracteres)
SMTP_FROM=seuemail@gmail.com
```

**IMPORTANTE:** Você precisa criar uma "App Password" (Senha de App) no Gmail:
1. Acesse: https://myaccount.google.com/apppasswords
2. Faça login na sua conta Google
3. Em "Selecionar app", escolha "Outro (Nome personalizado)"
4. Digite "Workflow Automation" e clique "GERAR"
5. Copie a senha de 16 caracteres (ex: `abcd efgh ijkl mnop`)

### Para Outlook/Hotmail:
```env
SMTP_HOST=smtp.office365.com
SMTP_PORT=587
SMTP_USER=seuemail@outlook.com
SMTP_PASSWORD=sua-senha-aqui
SMTP_FROM=seuemail@outlook.com
```

## Passo 3: Reiniciar o servidor

```powershell
docker-compose restart api
```

## Passo 4: Testar

1. Acesse: http://localhost:8000/workflows
2. Clique no botão **"📧 Testar Email"**
3. Verifique se o email chegou na sua caixa de entrada!

## Solução de Problemas

### "SMTP not configured"
- Verifique se o arquivo `.env` existe na pasta raiz
- Confirme se as variáveis estão preenchidas corretamente

### "Authentication failed"
- Gmail: Use App Password, não a senha normal
- Outlook: Ative "Acesso a apps menos seguros" ou use autenticação moderna

### "Connection refused"
- Verifique se a porta 587 não está bloqueada pelo firewall
- Tente usar porta 465 com SSL (mudar no código se necessário)

## Criar Workflow de Email

1. Vá em http://localhost:8000/workflows/new
2. Trigger: Manual ou Webhook
3. Action: Send Email
4. Configure:
   - **Para**: `{{email}}` (ou email fixo)
   - **Assunto**: Bem-vindo!
   - **Corpo**: Olá {{nome}}, obrigado por se cadastrar!
5. Salve e execute!
