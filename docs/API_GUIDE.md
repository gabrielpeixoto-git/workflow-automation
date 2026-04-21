# API Guide - Workflow Automation

Guia completo para utilização da API REST do Workflow Automation.

## 📋 Índice

- [Autenticação](#autenticação)
- [Workflows](#workflows)
- [Execuções](#execuções)
- [Webhooks](#webhooks)
- [Integrações](#integrações)
- [Analytics](#analytics)
- [Exemplos](#exemplos)

---

## Autenticação

### Login (Obter Token JWT)

```http
POST /api/auth/login
Content-Type: application/json

{
  "email": "admin@example.com",
  "password": "admin123"
}
```

**Resposta:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### Usar Token

Incluir o token em todas as requisições:

```http
Authorization: Bearer <access_token>
```

### API Keys

Para integrações de serviço, use API Keys:

```http
X-API-Key: <api_key>
```

---

## Workflows

### Listar Workflows

```http
GET /api/workflows/?skip=0&limit=10
Authorization: Bearer <token>
```

**Resposta:**
```json
{
  "items": [
    {
      "id": "uuid",
      "name": "Meu Workflow",
      "slug": "meu-workflow",
      "status": "active",
      "trigger_type": "webhook",
      "version": 1,
      "created_at": "2024-01-15T10:30:00Z"
    }
  ],
  "total": 5,
  "skip": 0,
  "limit": 10
}
```

### Criar Workflow

```http
POST /api/workflows/
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "Processar Lead",
  "slug": "processar-lead",
  "description": "Workflow para processar leads do CRM",
  "trigger_type": "webhook",
  "status": "active",
  "steps": [
    {
      "name": "Validar Email",
      "action_type": "transform_payload",
      "order": 1,
      "config": {
        "transformations": [
          {"field": "email", "operation": "validate_email"}
        ]
      }
    },
    {
      "name": "Salvar no Banco",
      "action_type": "write_database",
      "order": 2,
      "config": {
        "table": "leads",
        "mapping": {
          "nome": "{{payload.name}}",
          "email": "{{payload.email}}"
        }
      }
    }
  ]
}
```

### Executar Workflow

```http
POST /api/workflows/{workflow_id}/execute
Authorization: Bearer <token>
Content-Type: application/json

{
  "payload": {
    "name": "João Silva",
    "email": "joao@exemplo.com"
  }
}
```

### Atualizar Workflow

```http
PUT /api/workflows/{workflow_id}
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "Processar Lead Atualizado",
  "steps": [...]
}
```

### Deletar Workflow

```http
DELETE /api/workflows/{workflow_id}
Authorization: Bearer <token>
```

---

## Execuções

### Listar Execuções

```http
GET /api/executions/?skip=0&limit=20&status=completed
Authorization: Bearer <token>
```

**Query Parameters:**
- `skip`: Offset para paginação
- `limit`: Limite de resultados
- `status`: Filtrar por status (completed, failed, running, pending)
- `workflow_id`: Filtrar por workflow

### Obter Detalhes da Execução

```http
GET /api/executions/{execution_id}
Authorization: Bearer <token>
```

**Resposta:**
```json
{
  "id": "uuid",
  "workflow_id": "uuid",
  "status": "completed",
  "trigger_type": "manual",
  "input_data": {"name": "João"},
  "output_data": {"success": true},
  "started_at": "2024-01-15T10:30:00Z",
  "completed_at": "2024-01-15T10:30:05Z",
  "error_message": null
}
```

### Obter Logs da Execução

```http
GET /api/executions/{execution_id}/logs
Authorization: Bearer <token>
```

---

## Webhooks

### Listar Webhooks Configurados

```http
GET /api/webhook-configs/
Authorization: Bearer <token>
```

### Criar Webhook

```http
POST /api/webhook-configs/
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "Webhook de Pagamento",
  "event": "payment.received",
  "url": "https://api.exemplo.com/webhooks/payment",
  "method": "POST",
  "headers": {
    "X-Custom-Header": "valor"
  },
  "retry_policy": {
    "max_retries": 3,
    "retry_interval": 60
  },
  "secret": "webhook_secret_key"
}
```

### Receber Webhook Externo

```http
POST /webhooks/{workflow_id}
X-Webhook-Secret: <secret>
Content-Type: application/json

{
  "event": "user.created",
  "data": {
    "user_id": "123",
    "email": "user@exemplo.com"
  }
}
```

---

## Integrações

### Configurar Slack

```http
POST /api/integrations/slack
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "Slack Notificações",
  "webhook_url": "https://hooks.slack.com/services/xxx/yyy/zzz",
  "channel": "#notificacoes",
  "username": "Workflow Bot"
}
```

### Configurar Email SMTP

```http
POST /api/integrations/email
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "Email Corporativo",
  "smtp_host": "smtp.gmail.com",
  "smtp_port": 587,
  "username": "noreply@empresa.com",
  "password": "senha_segura",
  "use_tls": true,
  "from_email": "noreply@empresa.com",
  "from_name": "Sistema de Workflows"
}
```

### Configurar Discord

```http
POST /api/integrations/discord
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "Discord Alerts",
  "webhook_url": "https://discord.com/api/webhooks/xxx/yyy"
}
```

### Enviar Mensagem Slack

```http
POST /api/integrations/{integration_id}/send-slack
Authorization: Bearer <token>
Content-Type: application/json

{
  "message": "Novo lead recebido: {{payload.name}}",
  "channel": "#vendas"
}
```

---

## Analytics

### Obter Estatísticas

```http
GET /api/analytics/dashboard?days=30
Authorization: Bearer <token>
```

**Resposta:**
```json
{
  "workflow_stats": {
    "total": 10,
    "active": 8,
    "inactive": 2
  },
  "execution_stats": {
    "total": 150,
    "completed": 140,
    "failed": 8,
    "running": 2
  },
  "recent_executions": [...],
  "top_workflows": [...]
}
```

### Health Score

```http
GET /api/analytics/health-score
Authorization: Bearer <token>
```

**Resposta:**
```json
{
  "health_score": 85,
  "status": "good",
  "workflows": {"total": 10, "active": 8, "health": 80},
  "executions": {"success_rate": 93, "health": 90}
}
```

---

## Exemplos

### Exemplo 1: Workflow de Onboarding

```python
import requests

# Criar workflow de onboarding
workflow = {
    "name": "Onboarding de Cliente",
    "slug": "onboarding-cliente",
    "trigger_type": "webhook",
    "status": "active",
    "steps": [
        {
            "name": "Validar Dados",
            "action_type": "transform_payload",
            "order": 1,
            "config": {
                "validations": [
                    {"field": "email", "required": True},
                    {"field": "nome", "required": True}
                ]
            }
        },
        {
            "name": "Criar no CRM",
            "action_type": "http_request",
            "order": 2,
            "config": {
                "url": "https://api.crm.com/contacts",
                "method": "POST",
                "headers": {"Authorization": "Bearer {{secrets.crm_token}}"},
                "body": {
                    "name": "{{payload.nome}}",
                    "email": "{{payload.email}}"
                }
            }
        },
        {
            "name": "Notificar Slack",
            "action_type": "send_slack",
            "order": 3,
            "config": {
                "integration_id": "slack-1",
                "message": "🎉 Novo cliente: {{payload.nome}} ({{payload.email}})"
            }
        }
    ]
}

response = requests.post(
    "http://localhost:8000/api/workflows/",
    json=workflow,
    headers={"Authorization": f"Bearer {token}"}
)
```

### Exemplo 2: Webhook Handler

```python
# Receber webhook externo
@app.post("/webhooks/lead-received")
async def handle_lead_webhook(payload: dict):
    # Forward to workflow automation
    response = requests.post(
        "http://localhost:8000/webhooks/onboarding-cliente",
        json=payload,
        headers={"X-Webhook-Secret": "secret_key"}
    )
    return {"status": "processed"}
```

### Exemplo 3: Execução Agendada

```python
# Criar workflow agendado
workflow = {
    "name": "Backup Diário",
    "slug": "backup-diario",
    "trigger_type": "scheduled",
    "schedule_config": {
        "cron": "0 2 * * *"  # 2 AM todos os dias
    },
    "steps": [
        {
            "name": "Executar Backup",
            "action_type": "http_request",
            "config": {
                "url": "https://api.servidor.com/backup",
                "method": "POST"
            }
        },
        {
            "name": "Notificar Sucesso",
            "action_type": "send_email",
            "config": {
                "to": "admin@empresa.com",
                "subject": "Backup Diário Concluído",
                "template": "backup_success"
            }
        }
    ]
}
```

---

## Códigos de Status HTTP

| Código | Significado |
|--------|-------------|
| 200 | OK - Sucesso |
| 201 | Created - Recurso criado |
| 400 | Bad Request - Dados inválidos |
| 401 | Unauthorized - Não autenticado |
| 403 | Forbidden - Sem permissão |
| 404 | Not Found - Recurso não encontrado |
| 422 | Unprocessable Entity - Validação falhou |
| 500 | Internal Server Error - Erro do servidor |

## Rate Limiting

A API possui rate limiting de 100 requisições por minuto por cliente. Headers incluídos nas respostas:

- `X-RateLimit-Limit`: Limite de requisições (100)
- `X-RateLimit-Remaining`: Requisições restantes
- `X-Process-Time`: Tempo de processamento

---

Para mais informações, consulte a documentação completa em:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
