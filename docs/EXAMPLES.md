# Exemplos de Workflows - Workflow Automation

Coleção de exemplos práticos de workflows para diferentes cenários de automação.

## 📋 Índice

- [Onboarding de Clientes](#1-onboarding-de-clientes)
- [Processamento de Pagamentos](#2-processamento-de-pagamentos)
- [Notificações em Cadeia](#3-notificações-em-cadeia)
- [Integração CRM](#4-integração-crm)
- [Backup Automático](#5-backup-automático)
- [Processamento de Arquivos](#6-processamento-de-arquivos)
- [Webhook de E-commerce](#7-webhook-de-e-commerce)

---

## 1. Onboarding de Clientes

**Cenário**: Automatizar o processo de onboarding quando um novo cliente se cadastra.

**Trigger**: Webhook do formulário de cadastro

**Steps**:
1. Validar dados do cliente
2. Criar registro no CRM
3. Enviar email de boas-vindas
4. Notificar equipe no Slack
5. Adicionar à lista de emails

```json
{
  "name": "Onboarding de Cliente",
  "slug": "onboarding-cliente",
  "description": "Processo completo de onboarding para novos clientes",
  "trigger_type": "webhook",
  "status": "active",
  "steps": [
    {
      "name": "Validar Dados",
      "action_type": "transform_payload",
      "order": 1,
      "config": {
        "validations": [
          {
            "field": "email",
            "required": true,
            "type": "email"
          },
          {
            "field": "nome",
            "required": true,
            "min_length": 3
          },
          {
            "field": "telefone",
            "required": true,
            "type": "phone"
          }
        ]
      }
    },
    {
      "name": "Criar no CRM",
      "action_type": "http_request",
      "order": 2,
      "config": {
        "url": "https://api.crm.com/v1/contacts",
        "method": "POST",
        "headers": {
          "Authorization": "Bearer {{secrets.crm_token}}",
          "Content-Type": "application/json"
        },
        "body": {
          "name": "{{payload.nome}}",
          "email": "{{payload.email}}",
          "phone": "{{payload.telefone}}",
          "source": "website",
          "tags": ["novo_cliente", "web"]
        }
      }
    },
    {
      "name": "Email de Boas-vindas",
      "action_type": "send_email",
      "order": 3,
      "config": {
        "to": "{{payload.email}}",
        "subject": "Bem-vindo à nossa plataforma, {{payload.nome}}!",
        "template": "welcome_email",
        "variables": {
          "nome": "{{payload.nome}}",
          "email": "{{payload.email}}",
          "login_url": "https://app.exemplo.com/login"
        }
      }
    },
    {
      "name": "Notificar Equipe",
      "action_type": "send_slack",
      "order": 4,
      "config": {
        "integration_id": "slack-vendas",
        "channel": "#novos-clientes",
        "message": "🎉 Novo cliente cadastrado!\n\n*Nome:* {{payload.nome}}\n*Email:* {{payload.email}}\n*Telefone:* {{payload.telefone}}\n\nAção: Criado no CRM e email enviado."
      }
    }
  ]
}
```

**Payload de Teste**:

```json
{
  "nome": "João Silva",
  "email": "joao.silva@empresa.com",
  "telefone": "+55 11 98765-4321",
  "empresa": "Empresa XYZ"
}
```

---

## 2. Processamento de Pagamentos

**Cenário**: Processar pagamentos e atualizar status do pedido.

**Trigger**: Webhook do gateway de pagamento

```json
{
  "name": "Processar Pagamento",
  "slug": "processar-pagamento",
  "trigger_type": "webhook",
  "status": "active",
  "steps": [
    {
      "name": "Validar Webhook",
      "action_type": "transform_payload",
      "order": 1,
      "config": {
        "validations": [
          {
            "field": "payment_id",
            "required": true
          },
          {
            "field": "status",
            "required": true,
            "allowed_values": ["approved", "rejected", "pending"]
          }
        ]
      }
    },
    {
      "name": "Atualizar Pedido",
      "action_type": "write_database",
      "order": 2,
      "config": {
        "table": "orders",
        "operation": "update",
        "where": {
          "id": "{{payload.order_id}}"
        },
        "data": {
          "payment_status": "{{payload.status}}",
          "payment_id": "{{payload.payment_id}}",
          "paid_at": "{{timestamp}}"
        }
      }
    },
    {
      "name": "Email de Confirmação",
      "action_type": "send_email",
      "order": 3,
      "condition": "{{payload.status}} == 'approved'",
      "config": {
        "to": "{{payload.customer_email}}",
        "subject": "Pagamento Confirmado - Pedido #{{payload.order_id}}",
        "template": "payment_confirmed"
      }
    },
    {
      "name": "Notificar Discord",
      "action_type": "send_discord",
      "order": 4,
      "config": {
        "integration_id": "discord-financeiro",
        "message": "💰 Pagamento recebido: R$ {{payload.amount}} - Pedido #{{payload.order_id}}"
      }
    }
  ]
}
```

---

## 3. Notificações em Cadeia

**Cenário**: Enviar notificações em múltiplos canais quando um evento crítico ocorre.

**Trigger**: Webhook de monitoramento

```json
{
  "name": "Alerta Crítico - Multi Canal",
  "slug": "alerta-critico",
  "trigger_type": "webhook",
  "status": "active",
  "steps": [
    {
      "name": "Enviar Email",
      "action_type": "send_email",
      "order": 1,
      "config": {
        "to": "devops@empresa.com",
        "cc": ["manager@empresa.com"],
        "subject": "🚨 ALERTA CRÍTICO: {{payload.service}}",
        "template": "critical_alert",
        "priority": "high"
      }
    },
    {
      "name": "Notificar Slack",
      "action_type": "send_slack",
      "order": 2,
      "config": {
        "integration_id": "slack-devops",
        "channel": "#alertas-criticos",
        "message": "🚨 *ALERTA CRÍTICO*\n\n*Serviço:* {{payload.service}}\n*Status:* {{payload.status}}\n*Erro:* {{payload.error}}\n*Hora:* {{timestamp}}\n\n<!channel> Ação imediata necessária!"
      }
    },
    {
      "name": "Notificar Discord",
      "action_type": "send_discord",
      "order": 3,
      "config": {
        "integration_id": "discord-ops",
        "embed": {
          "title": "Alerta Crítico",
          "description": "{{payload.error}}",
          "color": 16711680,
          "fields": [
            {
              "name": "Serviço",
              "value": "{{payload.service}}",
              "inline": true
            },
            {
              "name": "Status",
              "value": "{{payload.status}}",
              "inline": true
            },
            {
              "name": "Timestamp",
              "value": "{{timestamp}}"
            }
          ]
        }
      }
    },
    {
      "name": "Criar Ticket",
      "action_type": "http_request",
      "order": 4,
      "config": {
        "url": "https://api.jira.com/issue",
        "method": "POST",
        "headers": {
          "Authorization": "Basic {{secrets.jira_token}}"
        },
        "body": {
          "fields": {
            "project": { "key": "OPS" },
            "summary": "[ALERTA] {{payload.service}} - {{payload.status}}",
            "description": "Erro detectado em {{payload.service}}:\n{{payload.error}}",
            "issuetype": { "name": "Bug" },
            "priority": { "name": "Highest" }
          }
        }
      }
    }
  ]
}
```

---

## 4. Integração CRM

**Cenário**: Sincronizar leads entre website e CRM.

**Trigger**: Webhook do formulário de contato

```json
{
  "name": "Sincronizar Lead CRM",
  "slug": "sync-lead-crm",
  "trigger_type": "webhook",
  "status": "active",
  "steps": [
    {
      "name": "Validar Lead",
      "action_type": "transform_payload",
      "order": 1,
      "config": {
        "transformations": [
          {
            "field": "email",
            "operation": "normalize_email"
          },
          {
            "field": "telefone",
            "operation": "normalize_phone"
          },
          {
            "field": "nome",
            "operation": "title_case"
          }
        ]
      }
    },
    {
      "name": "Verificar Duplicado",
      "action_type": "http_request",
      "order": 2,
      "config": {
        "url": "https://api.crm.com/v1/contacts/search",
        "method": "GET",
        "headers": {
          "Authorization": "Bearer {{secrets.crm_token}}"
        },
        "query_params": {
          "email": "{{payload.email}}"
        },
        "save_response": "existing_contact"
      }
    },
    {
      "name": "Criar Lead",
      "action_type": "http_request",
      "order": 3,
      "condition": "{{existing_contact.total}} == 0",
      "config": {
        "url": "https://api.crm.com/v1/leads",
        "method": "POST",
        "headers": {
          "Authorization": "Bearer {{secrets.crm_token}}"
        },
        "body": {
          "first_name": "{{payload.nome | split(' ') | first}}",
          "last_name": "{{payload.nome | split(' ') | slice(1) | join(' ')}}",
          "email": "{{payload.email}}",
          "phone": "{{payload.telefone}}",
          "company": "{{payload.empresa}}",
          "source": "Website - Formulário Contato",
          "status": "new",
          "priority": "medium",
          "custom_fields": {
            "interesse": "{{payload.interesse}}",
            "mensagem": "{{payload.mensagem}}"
          }
        }
      }
    },
    {
      "name": "Atualizar Lead Existente",
      "action_type": "http_request",
      "order": 4,
      "condition": "{{existing_contact.total}} > 0",
      "config": {
        "url": "https://api.crm.com/v1/leads/{{existing_contact.results[0].id}}",
        "method": "PUT",
        "headers": {
          "Authorization": "Bearer {{secrets.crm_token}}"
        },
        "body": {
          "last_contact": "{{timestamp}}",
          "notes": "Novo contato via website: {{payload.mensagem}}"
        }
      }
    },
    {
      "name": "Notificar Vendas",
      "action_type": "send_slack",
      "order": 5,
      "config": {
        "integration_id": "slack-vendas",
        "channel": "#leads",
        "message": "📥 *Novo Lead*\n\n*Nome:* {{payload.nome}}\n*Email:* {{payload.email}}\n*Telefone:* {{payload.telefone}}\n*Empresa:* {{payload.empresa}}\n*Interesse:* {{payload.interesse}}\n\n➡️ Lead {{existing_contact.total > 0 ? 'atualizado' : 'criado'}} no CRM"
      }
    }
  ]
}
```

---

## 5. Backup Automático

**Cenário**: Executar backup diário e notificar resultado.

**Trigger**: Agendado (Cron)

```json
{
  "name": "Backup Diário",
  "slug": "backup-diario",
  "trigger_type": "scheduled",
  "schedule_config": {
    "cron": "0 2 * * *",
    "timezone": "America/Sao_Paulo"
  },
  "status": "active",
  "steps": [
    {
      "name": "Backup Database",
      "action_type": "http_request",
      "order": 1,
      "config": {
        "url": "https://api.servidor.com/backup/database",
        "method": "POST",
        "headers": {
          "Authorization": "Bearer {{secrets.server_token}}"
        },
        "timeout": 300,
        "save_response": "backup_result"
      }
    },
    {
      "name": "Upload para S3",
      "action_type": "http_request",
      "order": 2,
      "config": {
        "url": "https://api.servidor.com/backup/upload",
        "method": "POST",
        "headers": {
          "Authorization": "Bearer {{secrets.server_token}}"
        },
        "body": {
          "backup_id": "{{backup_result.id}}",
          "destination": "s3://backups/workflow-automation/"
        }
      }
    },
    {
      "name": "Limpar Backups Antigos",
      "action_type": "http_request",
      "order": 3,
      "config": {
        "url": "https://api.servidor.com/backup/cleanup",
        "method": "POST",
        "headers": {
          "Authorization": "Bearer {{secrets.server_token}}"
        },
        "body": {
          "retention_days": 30
        }
      }
    },
    {
      "name": "Email de Sucesso",
      "action_type": "send_email",
      "order": 4,
      "condition": "{{backup_result.status}} == 'success'",
      "config": {
        "to": "admin@empresa.com",
        "subject": "✅ Backup Diário Concluído",
        "template": "backup_success",
        "variables": {
          "date": "{{timestamp | date}}",
          "size": "{{backup_result.size}}",
          "duration": "{{backup_result.duration}}"
        }
      }
    },
    {
      "name": "Email de Falha",
      "action_type": "send_email",
      "order": 5,
      "condition": "{{backup_result.status}} != 'success'",
      "config": {
        "to": "admin@empresa.com",
        "subject": "❌ Falha no Backup Diário",
        "template": "backup_failed",
        "variables": {
          "date": "{{timestamp | date}}",
          "error": "{{backup_result.error}}"
        }
      }
    }
  ]
}
```

---

## 6. Processamento de Arquivos

**Cenário**: Processar CSV de produtos enviado via upload.

**Trigger**: File upload

```json
{
  "name": "Importar Produtos CSV",
  "slug": "importar-produtos",
  "trigger_type": "file_upload",
  "status": "active",
  "steps": [
    {
      "name": "Validar Arquivo",
      "action_type": "transform_payload",
      "order": 1,
      "config": {
        "validations": [
          {
            "field": "file.type",
            "equals": "text/csv"
          },
          {
            "field": "file.size",
            "max": 10485760
          }
        ]
      }
    },
    {
      "name": "Processar CSV",
      "action_type": "http_request",
      "order": 2,
      "config": {
        "url": "https://api.erp.com/v1/products/import",
        "method": "POST",
        "headers": {
          "Authorization": "Bearer {{secrets.erp_token}}",
          "Content-Type": "multipart/form-data"
        },
        "files": {
          "csv": "{{payload.file}}"
        },
        "save_response": "import_result"
      }
    },
    {
      "name": "Gerar Relatório",
      "action_type": "export_csv",
      "order": 3,
      "config": {
        "filename": "importacao_produtos_{{timestamp | date}}.csv",
        "data": "{{import_result.details}}",
        "columns": [
          "sku",
          "nome",
          "status",
          "erro"
        ]
      }
    },
    {
      "name": "Email de Resultado",
      "action_type": "send_email",
      "order": 4,
      "config": {
        "to": "{{payload.uploaded_by_email}}",
        "subject": "Importação de Produtos - Resultado",
        "template": "import_result",
        "attachments": [
          "{{import_result.report_file}}"
        ]
      }
    }
  ]
}
```

---

## 7. Webhook de E-commerce

**Cenário**: Processar pedidos de um e-commerce.

**Trigger**: Webhook de novo pedido

```json
{
  "name": "Processar Pedido E-commerce",
  "slug": "processar-pedido",
  "trigger_type": "webhook",
  "status": "active",
  "steps": [
    {
      "name": "Validar Pedido",
      "action_type": "transform_payload",
      "order": 1,
      "config": {
        "validations": [
          {
            "field": "order_id",
            "required": true
          },
          {
            "field": "customer.email",
            "required": true,
            "type": "email"
          },
          {
            "field": "total_amount",
            "required": true,
            "type": "number",
            "min": 0
          }
        ]
      }
    },
    {
      "name": "Salvar no ERP",
      "action_type": "http_request",
      "order": 2,
      "config": {
        "url": "https://api.erp.com/v1/orders",
        "method": "POST",
        "headers": {
          "Authorization": "Bearer {{secrets.erp_token}}"
        },
        "body": {
          "external_id": "{{payload.order_id}}",
          "customer": {
            "name": "{{payload.customer.name}}",
            "email": "{{payload.customer.email}}",
            "phone": "{{payload.customer.phone}}"
          },
          "items": "{{payload.items}}",
          "total": "{{payload.total_amount}}",
          "shipping_address": "{{payload.shipping_address}}",
          "status": "pending"
        },
        "save_response": "erp_order"
      }
    },
    {
      "name": "Separar Estoque",
      "action_type": "http_request",
      "order": 3,
      "config": {
        "url": "https://api.erp.com/v1/inventory/reserve",
        "method": "POST",
        "headers": {
          "Authorization": "Bearer {{secrets.erp_token}}"
        },
        "body": {
          "order_id": "{{erp_order.id}}",
          "items": "{{payload.items}}"
        }
      }
    },
    {
      "name": "Email de Confirmação",
      "action_type": "send_email",
      "order": 4,
      "config": {
        "to": "{{payload.customer.email}}",
        "subject": "Pedido #{{payload.order_id}} Recebido",
        "template": "order_confirmation",
        "variables": {
          "customer_name": "{{payload.customer.name}}",
          "order_id": "{{payload.order_id}}",
          "total": "{{payload.total_amount}}",
          "items": "{{payload.items}}",
          "tracking_url": "https://loja.exemplo.com/pedido/{{payload.order_id}}"
        }
      }
    },
    {
      "name": "Notificar Logística",
      "action_type": "send_slack",
      "order": 5,
      "config": {
        "integration_id": "slack-logistica",
        "channel": "#novos-pedidos",
        "message": "📦 *Novo Pedido*\n\n*Pedido:* #{{payload.order_id}}\n*Cliente:* {{payload.customer.name}}\n*Valor:* R$ {{payload.total_amount}}\n*Itens:* {{payload.items.length}}\n\n➡️ ERP: {{erp_order.id}}"
      }
    }
  ]
}
```

---

## 🧪 Testando Workflows

### Via API

```bash
# 1. Obter token
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "admin123"}'

# 2. Criar workflow
curl -X POST http://localhost:8000/api/workflows/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d @workflow.json

# 3. Executar workflow
curl -X POST http://localhost:8000/api/workflows/{id}/execute \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "payload": {
      "nome": "Teste",
      "email": "teste@exemplo.com"
    }
  }'

# 4. Verificar execução
curl http://localhost:8000/api/executions/{execution_id} \
  -H "Authorization: Bearer $TOKEN"
```

### Via Web UI

1. Acesse http://localhost:8000/workflows
2. Clique em "Novo Workflow"
3. Cole o JSON do exemplo
4. Salve e execute com payload de teste

---

## 📝 Templates Disponíveis

O sistema já inclui templates pré-configurados:

| Template | Descrição | Trigger |
|----------|-----------|---------|
| `welcome_email` | Email de boas-vindas | Webhook |
| `order_confirmation` | Confirmação de pedido | Webhook |
| `payment_received` | Confirmação de pagamento | Webhook |
| `lead_notification` | Notificação de lead | Webhook |
| `daily_backup` | Backup automatizado | Scheduled |
| `weekly_report` | Relatório semanal | Scheduled |

---

## 🔄 Variáveis e Templating

### Variáveis Disponíveis

| Variável | Descrição | Exemplo |
|----------|-----------|---------|
| `{{payload}}` | Dados do payload | `{"nome": "João"}` |
| `{{timestamp}}` | Timestamp atual | `2024-01-15T10:30:00Z` |
| `{{workflow.id}}` | ID do workflow | `uuid-string` |
| `{{execution.id}}` | ID da execução | `uuid-string` |
| `{{secrets.xxx}}` | Secrets | Valor do secret |

### Filtros

| Filtro | Descrição | Exemplo |
|--------|-----------|---------|
| `upper` | Maiúsculas | `{{nome \| upper}}` |
| `lower` | Minúsculas | `{{nome \| lower}}` |
| `date` | Formatar data | `{{timestamp \| date}}` |
| `split` | Dividir string | `{{nome \| split(' ')}}` |

---

Para mais exemplos, consulte a [API Guide](API_GUIDE.md).
