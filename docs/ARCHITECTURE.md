# Arquitetura do Sistema - Workflow Automation

Documentação técnica da arquitetura do sistema de automação de workflows.

## 📋 Índice

- [Visão Geral](#visão-geral)
- [Stack Tecnológico](#stack-tecnológico)
- [Arquitetura de Componentes](#arquitetura-de-componentes)
- [Fluxo de Dados](#fluxo-de-dados)
- [Modelo de Dados](#modelo-de-dados)
- [Segurança](#segurança)
- [Escalabilidade](#escalabilidade)

---

## Visão Geral

O Workflow Automation é um sistema distribuído composto por múltiplos serviços que trabalham em conjunto para processar workflows de automação.

### Diagrama de Arquitetura de Alto Nível

```
┌─────────────────────────────────────────────────────────────┐
│                        Cliente                              │
│  (Browser / Mobile / API Client)                              │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ HTTP/HTTPS
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                     API Gateway                             │
│  - FastAPI Application                                      │
│  - Rate Limiting (100 req/min)                             │
│  - Cache Middleware (Redis)                                 │
│  - Auth Middleware (JWT/API Keys)                          │
└──────────────────────┬──────────────────────────────────────┘
                       │
           ┌───────────┼───────────┐
           │           │           │
           ▼           ▼           ▼
    ┌──────────┐ ┌──────────┐ ┌──────────┐
    │   Web    │ │   API    │ │ Webhooks │
    │   UI     │ │  REST    │ │          │
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
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐            │
│  │ Integration│ │  Webhook    │ │    RBAC     │            │
│  │   Service   │ │   Service   │ │   Service   │            │
│  └─────────────┘ └─────────────┘ └─────────────┘            │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    Data Layer                               │
│                                                             │
│  ┌──────────────────┐  ┌──────────────────┐                 │
│  │   PostgreSQL     │  │     Redis        │                 │
│  │   (Primary DB)   │  │  (Cache/Queue)   │                 │
│  └──────────────────┘  └──────────────────┘                 │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                   Task Workers                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Celery Workers                         │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐    │   │
│  │  │  Default    │ │   High      │ │   Low       │    │   │
│  │  │   Queue     │ │  Priority   │ │  Priority   │    │   │
│  │  └─────────────┘ └─────────────┘ └─────────────┘    │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Celery Beat (Scheduler)                │   │
│  │  - Periodic task scheduling                         │   │
│  │  - Cron expressions support                         │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## Stack Tecnológico

### Backend

| Componente | Tecnologia | Versão | Propósito |
|------------|-----------|---------|-----------|
| Framework | FastAPI | 0.109+ | API REST async |
| Linguagem | Python | 3.12 | Backend logic |
| ORM | SQLAlchemy | 2.0+ | Database access |
| Migrations | Alembic | 1.13+ | Schema versioning |
| Validation | Pydantic | 2.5+ | Data validation |

### Database & Cache

| Componente | Tecnologia | Versão | Propósito |
|------------|-----------|---------|-----------|
| Database | PostgreSQL | 16 | Primary data store |
| Cache | Redis | 7 | Caching & sessions |
| Queue | Redis | 7 | Task queue (Celery) |

### Task Processing

| Componente | Tecnologia | Versão | Propósito |
|------------|-----------|---------|-----------|
| Worker | Celery | 5.3+ | Async task processing |
| Scheduler | Celery Beat | 5.3+ | Periodic tasks |
| Broker | Redis | 7 | Message broker |
| Result Backend | Redis | 7 | Task results |

### Frontend

| Componente | Tecnologia | Versão | Propósito |
|------------|-----------|---------|-----------|
| Templating | Jinja2 | 3.1+ | HTML rendering |
| Styling | Tailwind CSS | 3.4+ | CSS framework |
| Interactivity | HTMX | 1.9+ | Dynamic content |
| Icons | Font Awesome | 6.4+ | Icon library |

---

## Arquitetura de Componentes

### 1. API Layer (`app/api/`)

Responsável por expor endpoints REST.

```
app/api/
├── __init__.py
├── auth.py          # Autenticação (JWT, API Keys)
├── workflows.py     # Workflow CRUD
├── executions.py    # Execution management
├── webhooks.py      # Webhook handling
├── analytics.py     # Analytics endpoints
├── dashboard.py     # Dashboard data
├── rbac.py          # Role-based access control
├── audit.py         # Audit logging
└── ...
```

### 2. Service Layer (`app/services/`)

Lógica de negócio encapsulada em serviços.

```
app/services/
├── __init__.py
├── workflow_service.py         # Workflow operations
├── execution_service.py        # Execution management
├── analytics_service.py        # Analytics & metrics
├── webhook_service.py          # Webhook processing
├── webhook_enhanced_service.py # Enhanced webhooks
├── integration_service.py      # External integrations
├── integration_action_handlers.py # Integration actions
├── cache_service.py            # Redis caching
├── email_service.py            # Email notifications
├── audit_service.py            # Audit logging
├── rbac_service.py             # Permission management
├── export_service.py           # Export (CSV, PDF)
└── ...
```

### 3. Model Layer (`app/models/`)

Definição de entidades SQLAlchemy.

```
app/models/
├── __init__.py
├── user.py              # User & Organization
├── workflow.py          # Workflow & Steps
├── execution.py         # Execution & Logs
├── webhook.py           # Webhook configs
├── integration.py       # Integration configs
├── audit.py             # Audit logs
├── template.py          # Workflow templates
└── ...
```

### 4. Task Layer (`app/tasks/`)

Tarefas assíncronas Celery.

```
app/tasks/
├── __init__.py
├── workflow_tasks.py    # Workflow execution
├── notification_tasks.py # Email notifications
├── audit_tasks.py      # Audit logging
└── ...
```

### 5. Web Layer (`app/web/`)

Interface web HTMX + Tailwind.

```
app/web/
├── __init__.py
├── components.py        # Shared UI components
├── workflows_new.py     # Workflow pages
├── executions_new.py    # Execution pages
├── dashboard.py         # Dashboard
└── ...
```

---

## Fluxo de Dados

### 1. Execução de Workflow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Client    │────▶│  API Layer  │────▶│   Service   │
│             │     │             │     │   Layer     │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
                                               ▼
                                        ┌─────────────┐
                                        │   Celery    │
                                        │   Broker    │
                                        │   (Redis)   │
                                        └──────┬──────┘
                                               │
                                               ▼
                                        ┌─────────────┐
                                        │   Worker    │
                                        │   (Task)    │
                                        └──────┬──────┘
                                               │
                          ┌────────────────────┼────────────────────┐
                          │                    │                    │
                          ▼                    ▼                    ▼
                   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
                   │  Database   │    │    Cache    │    │  External   │
                   │(PostgreSQL) │    │   (Redis)   │    │    APIs     │
                   └─────────────┘    └─────────────┘    └─────────────┘
```

**Fluxo detalhado:**

1. Client envia requisição para `/api/workflows/{id}/execute`
2. API layer valida autenticação e permissões
3. Service layer cria registro de execução no database
4. Tarefa é enfileirada no Celery (Redis)
5. Worker processa a tarefa assíncrona
6. Cada step do workflow é executado sequencialmente
7. Logs são gravados durante a execução
8. Resultado é atualizado no database
9. Notificações são enviadas (se configurado)

### 2. Recebimento de Webhook

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   External  │────▶│  Webhook    │────▶│   Service   │
│   System    │     │   Endpoint  │     │   Layer     │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
                                               ▼
                                        ┌─────────────┐
                                        │  Validate   │
                                        │   HMAC/     │
                                        │   Secret    │
                                        └──────┬──────┘
                                               │
                                               ▼
                                        ┌─────────────┐
                                        │   Trigger   │
                                        │   Workflow  │
                                        └─────────────┘
```

---

## Modelo de Dados

### Diagrama ER Simplificado

```
┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐
│   Organization   │───────│      User        │       │    APIKey        │
├──────────────────┤       ├──────────────────┤       ├──────────────────┤
│ id (PK)          │1     M│ id (PK)          │1     M│ id (PK)          │
│ name             │       │ email            │       │ key_hash         │
│ slug             │       │ hashed_password  │       │ scopes           │
│ settings         │       │ organization_id  │       │ user_id          │
└──────────────────┘       │ role             │       └──────────────────┘
                             └──────────────────┘
                                      │
                                      │1
                                      │
                                      ▼M
                             ┌──────────────────┐
                             │    Workflow      │
                             ├──────────────────┤
                             │ id (PK)          │
                             │ name             │
                             │ slug             │
                             │ status           │
                             │ trigger_type     │
                             │ organization_id  │
                             └──────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    │1                │1                │1
                    │                 │                 │
                    ▼M                ▼M                ▼M
           ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
           │   WorkflowStep   │ │ WorkflowExecution│ │  WebhookConfig   │
           ├──────────────────┤ ├──────────────────┤ ├──────────────────┤
           │ id (PK)          │ │ id (PK)          │ │ id (PK)          │
           │ workflow_id      │ │ workflow_id      │ │ workflow_id      │
           │ name             │ │ status           │ │ url              │
           │ action_type      │ │ trigger_type     │ │ method           │
           │ config           │ │ input_data       │ │ headers          │
           │ order            │ │ output_data      │ │ retry_policy     │
           └──────────────────┘ │ error_message    │ └──────────────────┘
                                │ started_at       │
                                │ completed_at   │◄─────────────┐
                                └──────────────────┘              │
                                                                  │1
                                                                  │
                                                                  ▼M
                                                        ┌──────────────────┐
                                                        │   ExecutionLog   │
                                                        ├──────────────────┤
                                                        │ id (PK)          │
                                                        │ execution_id     │
                                                        │ step_name        │
                                                        │ level            │
                                                        │ message          │
                                                        │ details          │
                                                        └──────────────────┘

┌──────────────────┐       ┌──────────────────┐
│   Integration    │       │   AuditLog       │
├──────────────────┤       ├──────────────────┤
│ id (PK)          │       │ id (PK)          │
│ name             │       │ user_id          │
│ type             │       │ action           │
│ config           │       │ entity_type      │
│ organization_id  │       │ entity_id        │
└──────────────────┘       │ details          │
                           │ created_at       │
                           └──────────────────┘
```

---

## Segurança

### Autenticação

1. **JWT Tokens**
   - Access token: 30 minutos
   - Refresh token: 7 dias
   - Algoritmo: HS256

2. **API Keys**
   - Prefixo identificador
   - Hash armazenado (bcrypt)
   - Scopes granulares

### Autorização

1. **RBAC (Role-Based Access Control)**
   - Roles: admin, manager, user, viewer
   - 24 permissões granulares
   - Middleware de verificação

2. **Permissões por Workflow**
   - owner, editor, viewer por recurso

### Proteção de Dados

1. **Senhas**: bcrypt com salt
2. **API Keys**: hash único, não recuperável
3. **Webhook Secrets**: HMAC-SHA256
4. **Dados Sensíveis**: criptografia em repouso

---

## Escalabilidade

### Horizontal Scaling

```
                    ┌──────────────────┐
                    │   Load Balancer  │
                    │    (Nginx/ALB)   │
                    └────────┬─────────┘
                             │
            ┌────────────────┼────────────────┐
            │                │                │
     ┌──────▼──────┐  ┌─────▼──────┐  ┌─────▼──────┐
     │   API       │  │   API      │  │   API      │
     │  Instance 1 │  │ Instance 2 │  │ Instance N │
     └──────┬──────┘  └─────┬──────┘  └─────┬──────┘
            │               │               │
            └───────────────┼───────────────┘
                            │
                    ┌───────▼────────┐
                    │     Redis      │
                    │   (Cluster)    │
                    └───────┬────────┘
                            │
                    ┌───────▼────────┐
                    │  PostgreSQL    │
                    │  (Primary-     │
                    │   Replica)     │
                    └────────────────┘
```

### Cache Strategy

| Dados | TTL | Estratégia |
|-------|-----|------------|
| Workflow | 5 min | Cache com invalidação |
| Analytics | 10 min | Cache com stale-while-revalidate |
| User Session | 30 min | Redis sessions |
| API Response | 5 min | Middleware cache |

### Queue Strategy

- **High Priority**: Webhook processing
- **Default**: Workflow execution
- **Low Priority**: Analytics, audit logs

---

## Monitoramento

### Métricas Principais

1. **Performance**
   - Response time (p50, p95, p99)
   - Throughput (req/s)
   - Database query time

2. **Saúde do Sistema**
   - Worker queue size
   - Error rate
   - CPU/Memory usage

3. **Negócio**
   - Workflow execution rate
   - Success/failure ratio
   - Active workflows

### Health Checks

- `/health` - API health
- `/health/db` - Database connectivity
- `/health/redis` - Redis connectivity
- `/health/worker` - Worker status

---

## Deployment

### Docker Compose (Desenvolvimento)

```yaml
services:
  api:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://...
      - REDIS_URL=redis://redis:6379/0
  
  worker:
    build: ./backend
    command: celery -A app.tasks worker
  
  scheduler:
    build: ./backend
    command: celery -A app.tasks beat
  
  db:
    image: postgres:16
  
  redis:
    image: redis:7-alpine
```

### Kubernetes (Produção)

- Deployments: API, Worker, Scheduler
- Services: LoadBalancer para API
- PersistentVolumes: PostgreSQL
- ConfigMaps/Secrets: Configurações
- HPA: Auto-scaling baseado em CPU/memory

---

Para mais detalhes, consulte:
- [Installation Guide](INSTALLATION.md)
- [Development Guide](DEVELOPMENT.md)
- [API Guide](API_GUIDE.md)
