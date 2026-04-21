# Exemplos de Payloads - Workflow Automation Platform

## 1. Autenticação

### 1.1 Registro de Usuário
```http
POST /api/auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securepassword123",
  "full_name": "John Doe",
  "organization_name": "Acme Corp"
}
```

### 1.2 Login
```http
POST /api/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securepassword123"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 900
}
```

## 2. Workflows

### 2.1 Criar Workflow com Webhook Trigger
```http
POST /api/workflows
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "name": "Processar Pedido",
  "slug": "processar-pedido",
  "description": "Processa pedidos recebidos via webhook",
  "status": "active",
  "tags": ["pedidos", "ecommerce"],
  "steps": [
    {
      "name": "Webhook de Pedido",
      "step_type": "trigger",
      "trigger_type": "webhook",
      "order": 0,
      "config": {
        "webhook_url": "https://api.example.com/webhooks/processar-pedido"
      }
    },
    {
      "name": "Validar Dados",
      "step_type": "action",
      "action_type": "transform_payload",
      "order": 1,
      "config": {
        "transformations": [
          {
            "operation": "set",
            "target_field": "validated",
            "value": true
          }
        ]
      }
    },
    {
      "name": "Enviar Email de Confirmação",
      "step_type": "action",
      "action_type": "send_email",
      "order": 2,
      "config": {
        "to": "{{customer_email}}",
        "subject": "Pedido Recebido - #{{order_id}}",
        "body": "Obrigado pelo seu pedido! Número: {{order_id}}"
      }
    },
    {
      "name": "Salvar no Banco",
      "step_type": "action",
      "action_type": "write_database",
      "order": 3,
      "config": {
        "table": "orders",
        "data": {
          "order_id": "{{order_id}}",
          "customer_email": "{{customer_email}}",
          "total": "{{total}}",
          "status": "pending"
        }
      }
    }
  ]
}
```

### 2.2 Criar Workflow com Cron Trigger
```http
POST /api/workflows
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "name": "Relatório Diário",
  "slug": "relatorio-diario",
  "description": "Gera relatório diário às 9h",
  "status": "active",
  "tags": ["relatórios", "automático"],
  "steps": [
    {
      "name": "Agendamento Diário",
      "step_type": "trigger",
      "trigger_type": "scheduled",
      "order": 0,
      "config": {
        "cron": "0 9 * * *",
        "timezone": "America/Sao_Paulo"
      }
    },
    {
      "name": "Exportar CSV",
      "step_type": "action",
      "action_type": "export_csv",
      "order": 1,
      "config": {
        "data_path": "orders",
        "filename": "relatorio-{{date}}.csv",
        "fields": ["order_id", "customer_email", "total", "status"]
      }
    },
    {
      "name": "Enviar Email",
      "step_type": "action",
      "action_type": "send_email",
      "order": 2,
      "config": {
        "to": "admin@example.com",
        "subject": "Relatório Diário - {{date}}",
        "body": "Segue o relatório diário em anexo."
      }
    }
  ]
}
```

### 2.3 Atualizar Workflow
```http
PUT /api/workflows/{workflow_id}
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "name": "Novo Nome",
  "description": "Nova descrição",
  "tags": ["novo-tag"]
}
```

### 2.4 Duplicar Workflow
```http
POST /api/workflows/{workflow_id}/duplicate?new_name=Novo%20Workflow%20Copia
Authorization: Bearer {access_token}
```

## 3. Execuções

### 3.1 Trigger Manual
```http
POST /api/executions/trigger/{workflow_id}
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "order_id": "12345",
  "customer_email": "cliente@example.com",
  "total": 299.99,
  "items": [
    {"name": "Produto 1", "price": 199.99},
    {"name": "Produto 2", "price": 100.00}
  ]
}
```

### 3.2 Webhook Trigger
```http
POST /webhooks/{workflow_id}
Content-Type: application/json

{
  "event": "order.created",
  "data": {
    "order_id": "12345",
    "customer_email": "cliente@example.com",
    "total": 299.99
  }
}
```

### 3.3 Retry de Execução Falha
```http
POST /api/executions/{execution_id}/retry
Authorization: Bearer {access_token}
```

### 3.4 Cancelar Execução
```http
POST /api/executions/{execution_id}/cancel
Authorization: Bearer {access_token}
```

### 3.5 Listar Execuções
```http
GET /api/executions?status=failed&limit=50
Authorization: Bearer {access_token}
```

## 4. Actions - Configurações Detalhadas

### 4.1 HTTP Request Action
```json
{
  "name": "Chamar API Externa",
  "step_type": "action",
  "action_type": "http_request",
  "order": 1,
  "config": {
    "method": "POST",
    "url": "https://api.external.com/v1/orders",
    "headers": {
      "Authorization": "Bearer {{api_token}}",
      "Content-Type": "application/json"
    },
    "body": "{\"order_id\": \"{{order_id}}\", \"total\": {{total}}}",
    "timeout": 30
  },
  "max_retries": 3,
  "retry_delay": 60
}
```

### 4.2 Transform Payload Action
```json
{
  "name": "Transformar Dados",
  "step_type": "action",
  "action_type": "transform_payload",
  "order": 1,
  "config": {
    "transformations": [
      {
        "operation": "copy",
        "source_field": "customer_email",
        "target_field": "email"
      },
      {
        "operation": "set",
        "target_field": "processed_at",
        "value": "{{timestamp}}"
      },
      {
        "operation": "rename",
        "source_field": "order_id",
        "target_field": "id"
      },
      {
        "operation": "delete",
        "target_field": "temp_data"
      }
    ]
  }
}
```

### 4.3 Export CSV Action
```json
{
  "name": "Exportar para CSV",
  "step_type": "action",
  "action_type": "export_csv",
  "order": 1,
  "config": {
    "data_path": "orders",
    "filename": "orders-{{date}}-{{time}}.csv",
    "fields": ["order_id", "customer_email", "total", "status", "created_at"]
  }
}
```

### 4.4 Export PDF Action
```json
{
  "name": "Gerar PDF",
  "step_type": "action",
  "action_type": "export_pdf",
  "order": 1,
  "config": {
    "filename": "report-{{order_id}}.pdf",
    "template": "<html><body><h1>Pedido {{order_id}}</h1><p>Cliente: {{customer_email}}</p><p>Total: R$ {{total}}</p></body></html>"
  }
}
```

## 5. Respostas de API

### 5.1 Workflow Response
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Processar Pedido",
  "slug": "processar-pedido",
  "description": "Processa pedidos recebidos via webhook",
  "status": "active",
  "tags": ["pedidos", "ecommerce"],
  "version": 1,
  "organization_id": "550e8400-e29b-41d4-a716-446655440001",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z",
  "steps": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440010",
      "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "Webhook de Pedido",
      "step_type": "trigger",
      "trigger_type": "webhook",
      "order": 0,
      "config": {},
      "is_active": true,
      "max_retries": 3,
      "retry_delay": 60,
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-15T10:30:00Z"
    }
  ]
}
```

### 5.2 Execution Response
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440100",
  "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
  "correlation_id": "exec_a1b2c3d4e5f6_1705319400",
  "status": "completed",
  "trigger_type": "webhook",
  "started_at": "2024-01-15T10:30:00Z",
  "completed_at": "2024-01-15T10:30:05Z",
  "error_message": null,
  "retry_count": 0,
  "created_at": "2024-01-15T10:30:00Z",
  "step_logs": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440110",
      "step_id": "550e8400-e29b-41d4-a716-446655440010",
      "step_order": 0,
      "step_name": "Webhook de Pedido",
      "step_type": "trigger",
      "status": "completed",
      "started_at": "2024-01-15T10:30:00Z",
      "completed_at": "2024-01-15T10:30:00Z",
      "duration_ms": 0,
      "error_message": null,
      "retry_count": 0
    },
    {
      "id": "550e8400-e29b-41d4-a716-446655440111",
      "step_id": "550e8400-e29b-41d4-a716-446655440011",
      "step_order": 1,
      "step_name": "Validar Dados",
      "step_type": "action",
      "status": "completed",
      "started_at": "2024-01-15T10:30:01Z",
      "completed_at": "2024-01-15T10:30:02Z",
      "duration_ms": 1000,
      "error_message": null,
      "retry_count": 0
    }
  ]
}
```

### 5.3 Error Response
```json
{
  "detail": "Workflow not found"
}
```

## 6. Dashboard Metrics

### 6.1 Get Metrics
```http
GET /api/metrics
Authorization: Bearer {access_token}
```

**Response:**
```json
{
  "total_workflows": 10,
  "active_workflows": 5,
  "total_executions_today": 150,
  "successful_executions_today": 145,
  "failed_executions_today": 5,
  "pending_executions": 2,
  "avg_execution_time_ms": 2500
}
```

## 7. Templates de Variáveis

### 7.1 Variáveis Disponíveis
- `{{order_id}}` - ID do pedido
- `{{customer_email}}` - Email do cliente
- `{{total}}` - Valor total
- `{{date}}` - Data atual (YYYY-MM-DD)
- `{{time}}` - Hora atual (HH:MM:SS)
- `{{timestamp}}` - Timestamp Unix
- `{{execution_id}}` - ID da execução
- `{{correlation_id}}` - ID de correlação

### 7.2 Exemplo de Uso
```json
{
  "config": {
    "to": "{{customer_email}}",
    "subject": "Pedido {{order_id}} - {{date}}",
    "filename": "order-{{order_id}}-{{date}}.pdf"
  }
}
```

## 8. Webhook Payloads

### 8.1 Estrutura Padrão
```json
{
  "event": "tipo.do.evento",
  "data": {
    // Dados específicos do evento
  },
  "_webhook": {
    "headers": {
      "user-agent": "...",
      "content-type": "application/json"
    },
    "query_params": {
      "key": "value"
    },
    "ip_address": "192.168.1.1"
  }
}
```

### 8.2 Exemplo: Order Created
```http
POST /webhooks/550e8400-e29b-41d4-a716-446655440000
Content-Type: application/json
X-Webhook-Signature: sha256=...

{
  "event": "order.created",
  "data": {
    "order_id": "ORD-12345",
    "customer_email": "cliente@example.com",
    "total": 299.99,
    "currency": "BRL",
    "items": [
      {
        "sku": "PROD-001",
        "name": "Produto Exemplo",
        "quantity": 2,
        "price": 149.99
      }
    ],
    "shipping_address": {
      "street": "Rua Exemplo, 123",
      "city": "São Paulo",
      "state": "SP",
      "zip": "01000-000"
    }
  }
}
```

## 9. Filtros e Paginação

### 9.1 Listar Workflows
```http
GET /api/workflows?status=active&skip=0&limit=20
Authorization: Bearer {access_token}
```

### 9.2 Listar Execuções
```http
GET /api/executions?workflow_id=xxx&status=failed&skip=0&limit=50
Authorization: Bearer {access_token}
```

### 9.3 Parâmetros Suportados
- `skip`: Offset (padrão: 0)
- `limit`: Limite de resultados (padrão: 100, máx: 1000)
- `status`: Filtrar por status
- `workflow_id`: Filtrar por workflow específico
