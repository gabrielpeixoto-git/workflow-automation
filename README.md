# 🚀 Workflow Automation Platform

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-00a393.svg)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791.svg)](https://postgresql.org)
[![Redis](https://img.shields.io/badge/Redis-7-dc382d.svg)](https://redis.io)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> **Plataforma enterprise de automação de workflows** - Uma alternativa open-source a Zapier, Make e n8n, com foco em performance, escalabilidade e facilidade de uso.

![Dashboard Preview](docs/assets/dashboard-preview.png)

## ✨ Funcionalidades

### 🎯 Core
- **Workflow Engine**: Motor de execução assíncrono com retry automático
- **Visual Builder**: Interface drag-and-drop para criação de workflows
- **Real-time Monitoring**: Dashboard com métricas em tempo real
- **Audit Logging**: Rastreamento completo de todas as ações

### 🔌 Integrações
- **Slack**: Notificações e interações em canais
- **Email SMTP**: Envio de emails com templates
- **Discord**: Webhooks e mensagens embed
- **HTTP/REST**: Integração com qualquer API
- **Database**: PostgreSQL nativo com queries dinâmicas

### 🛡️ Segurança
- **RBAC**: Controle de acesso baseado em roles (Admin, Manager, User, Viewer)
- **JWT Auth**: Tokens de acesso com refresh automático
- **API Keys**: Integração segura com scopes granulares
- **Webhook HMAC**: Validação de assinatura para webhooks externos

### ⚡ Performance
- **Redis Caching**: Cache em múltiplas camadas (TTL configurável)
- **Celery Workers**: Processamento assíncrono distribuído
- **Rate Limiting**: 100 req/min por cliente
- **Database Indexing**: Otimizado para queries complexas

## 🏗️ Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│                        Cliente                              │
│           (Web UI / API / Mobile)                           │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                     API Gateway                             │
│  - FastAPI (Async)                                          │
│  - Rate Limiting & Caching                                  │
│  - JWT & API Key Auth                                       │
└──────────────────────┬──────────────────────────────────────┘
                       │
           ┌───────────┼───────────┐
           │           │           │
           ▼           ▼           ▼
    ┌──────────┐ ┌──────────┐ ┌──────────┐
    │   Web    │ │   REST   │ │ Webhooks │
    │   UI     │ │   API    │ │          │
    │(HTMX)    │ │          │ │          │
    └──────────┘ └──────────┘ └──────────┘
           │           │           │
           └───────────┼───────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                   Business Layer                            │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐            │
│  │  Workflow   │ │  Execution  │ │  Analytics  │            │
│  │   Service   │ │   Service   │ │   Service   │            │
│  └─────────────┘ └─────────────┘ └─────────────┘            │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    Data Layer                               │
│  ┌──────────────────┐  ┌──────────────────┐                 │
│  │   PostgreSQL     │  │     Redis        │                 │
│  │   (Primary DB)   │  │  (Cache/Queue)   │                 │
│  └──────────────────┘  └──────────────────┘                 │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites
- Docker 24.0+
- Docker Compose 2.20+

### 1. Clone & Setup

```bash
git clone https://github.com/yourusername/workflow-automation.git
cd workflow-automation

# Configurar ambiente
cp .env.example .env
# Edite .env conforme necessário
```

### 2. Run with Docker

```bash
docker-compose up -d

# Verificar status
docker-compose ps
```

### 3. Access

| URL | Descrição |
|-----|-----------|
| http://localhost:8000 | Dashboard Web |
| http://localhost:8000/docs | API Swagger |
| http://localhost:8000/redoc | API ReDoc |

### 4. Login (Dev Accounts)

- **Admin**: `admin@example.com` / `admin123`
- **Manager**: `manager@example.com` / `manager123`
- **User**: `user@example.com` / `user123`

## 📚 Documentação

- **[API Guide](docs/API_GUIDE.md)** - Guia completo de APIs
- **[Architecture](docs/ARCHITECTURE.md)** - Documentação técnica
- **[Development](docs/DEVELOPMENT.md)** - Guia de desenvolvimento
- **[Installation](docs/INSTALLATION.md)** - Guia de instalação
- **[Examples](docs/EXAMPLES.md)** - Exemplos de workflows

## 🎯 Exemplos de Uso

### Workflow de Onboarding

```json
{
  "name": "Onboarding de Cliente",
  "trigger_type": "webhook",
  "steps": [
    {
      "name": "Validar Dados",
      "action_type": "transform_payload",
      "config": { "validations": [...] }
    },
    {
      "name": "Criar no CRM",
      "action_type": "http_request",
      "config": { "url": "https://api.crm.com/..." }
    },
    {
      "name": "Notificar Slack",
      "action_type": "send_slack",
      "config": { "message": "🎉 Novo cliente!" }
    }
  ]
}
```

### API Request

```bash
# Login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "admin123"}'

# Criar Workflow
curl -X POST http://localhost:8000/api/workflows/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d @workflow.json

# Executar
curl -X POST http://localhost:8000/api/workflows/{id}/execute \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"payload": {"name": "João"}}'
```

## 🛠️ Tech Stack

| Camada | Tecnologia |
|--------|-----------|
| **Backend** | Python 3.12, FastAPI, SQLAlchemy 2.x (async), Pydantic v2 |
| **Database** | PostgreSQL 16 |
| **Cache/Queue** | Redis 7 |
| **Worker** | Celery 5.3+ |
| **Frontend** | HTMX, Tailwind CSS, Alpine.js |
| **Testing** | pytest, pytest-asyncio (53+ testes) |
| **Deploy** | Docker, Docker Compose, Kubernetes |

## 📊 Features Avançadas

- ✅ **Workflow Versioning** - Histórico completo de versões
- ✅ **Schema Validation** - JSON Schema e JSON Logic
- ✅ **Template System** - 5 templates built-in + custom
- ✅ **Bulk Operations** - Ações em massa
- ✅ **Export** - CSV e PDF
- ✅ **Analytics** - Dashboard com Chart.js
- ✅ **Webhook Management** - Retries, HMAC, logs
- ✅ **RBAC** - 24 permissões granulares
- ✅ **Redis Caching** - TTL, decorators, middleware

## 🧪 Testing

```bash
# Todos os testes
docker-compose exec api pytest

# Com cobertura
docker-compose exec api pytest --cov=app

# Testes específicos
docker-compose exec api pytest tests/unit/test_workflow_service.py -v
```

## 📈 Screenshots

### Dashboard
![Dashboard](docs/assets/screenshot-dashboard.png)

### Workflow Editor
![Workflow Editor](docs/assets/screenshot-workflow.png)

### Execution Timeline
![Timeline](docs/assets/screenshot-timeline.png)

## 🤝 Contributing

Contribuições são bem-vindas! Leia o [CONTRIBUTING.md](CONTRIBUTING.md) para detalhes.

## 📝 License

Este projeto está licenciado sob a Licença MIT - veja o arquivo [LICENSE](LICENSE) para detalhes.

## 👨‍💻 Autor

**Gabriel Campos** - [@gabrielcampos](https://linkedin.com/in/gabrielcampos)

---

⭐ Star este repo se você achou útil!
