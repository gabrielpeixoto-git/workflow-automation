# Workflow Automation Platform

Plataforma de automação de workflows e integrações internas, estilo "mini Zapier / mini Make".

## Stack Tecnológica

- **Backend:** Python 3.12+, FastAPI, SQLAlchemy 2.x (async), Pydantic v2
- **Database:** PostgreSQL 16
- **Queue:** Redis + Celery
- **Frontend:** HTMX + Alpine.js + Tailwind CSS (SSR leve)
- **Auth:** JWT (access + refresh tokens)
- **Testing:** pytest, pytest-asyncio
- **Deploy:** Docker + docker-compose

## Funcionalidades

### Triggers
- Webhook (endpoint dinâmico)
- Cron/Agendado
- Manual
- Upload de arquivo

### Actions
- HTTP Request
- Send Email
- Write to Database
- Transform Payload
- Export CSV
- Export PDF
- Notify

### Features
- Fila de execução com Celery
- Retry automático com backoff
- Dead letter queue
- Reprocessamento de falhas
- Logs estruturados
- Auditoria completa
- Dashboard de métricas
- Controle de acesso RBAC

## Setup Local

### 1. Entrar no diretório
```powershell
cd "sistema de automação"
```

### 2. Configurar variáveis de ambiente
```powershell
copy .env.example .env
# Edite .env conforme necessário
```

### 3. Iniciar com Docker
```powershell
docker-compose up -d
```

### 4. Criar migrations (primeira vez)
```powershell
docker-compose exec api alembic upgrade head
docker-compose exec api python -m app.db.seeds
```

### 5. Acessar
- API: http://localhost:8000
- Docs (Swagger): http://localhost:8000/docs
- Dashboard: http://localhost:8000

### Contas de Desenvolvimento
- `admin@example.com` / `admin123` (Admin)
- `editor@example.com` / `editor123` (Editor)
- `viewer@example.com` / `viewer123` (Viewer)

## Desenvolvimento

### Instalação local (sem Docker)
```powershell
cd backend
python -m venv venv
venv\Scripts\activate
pip install -e ".[dev]"
```

### Rodar migrations
```powershell
cd backend
alembic upgrade head
```

### Seeds de desenvolvimento
```powershell
cd backend
python -m app.db.seeds
```

### Testes
```powershell
cd backend
pytest
```

### Lint
```powershell
cd backend
ruff check .
ruff format .
```

## Estrutura do Projeto

```
.
├── backend/
│   ├── app/
│   │   ├── api/          # API routes
│   │   ├── core/         # Config, security, logging
│   │   ├── db/           # Database config
│   │   ├── models/       # SQLAlchemy models
│   │   ├── services/     # Business logic
│   │   ├── tasks/        # Celery tasks
│   │   ├── utils/        # Utilities
│   │   ├── web/          # Web routes (dashboard)
│   │   ├── celery_app.py # Celery configuration
│   │   └── main.py       # FastAPI app
│   ├── alembic/          # Migrations
│   ├── tests/            # Testes
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend/
│   ├── static/           # CSS, JS, images
│   └── templates/        # Jinja2 templates
├── docker-compose.yml
├── .env.example
└── README.md
```

## API Endpoints

### Auth
- `POST /api/auth/register` - Cadastro
- `POST /api/auth/login` - Login
- `POST /api/auth/logout` - Logout
- `POST /api/auth/refresh` - Refresh token

### Workflows
- `GET /api/workflows` - Listar
- `POST /api/workflows` - Criar
- `GET /api/workflows/{id}` - Detalhes
- `PUT /api/workflows/{id}` - Atualizar
- `DELETE /api/workflows/{id}` - Deletar
- `POST /api/workflows/{id}/duplicate` - Duplicar
- `POST /api/workflows/{id}/activate` - Ativar
- `POST /api/workflows/{id}/deactivate` - Desativar

### Execuções
- `GET /api/executions` - Listar
- `GET /api/executions/{id}` - Detalhes
- `POST /api/executions/{id}/retry` - Reprocessar
- `POST /api/executions/{id}/cancel` - Cancelar

### Webhooks
- `POST /webhooks/{token}` - Webhook dinâmico

### Files
- `POST /api/files/upload` - Upload de arquivo

## Decisões Técnicas

1. **Async vs Sync:** FastAPI async para endpoints I/O, Celery sync para workers de processamento
2. **Frontend:** HTMX + Alpine.js + Tailwind (SSR leve, sem framework pesado)
3. **Database:** PostgreSQL com SQLAlchemy 2.x async
4. **Queues:** Redis + Celery para tasks robustas
5. **Auth:** JWT access (15min) + refresh (7dias) tokens
6. **Multi-tenant:** workspace_id em todas as tabelas relevantes
7. **Idempotência:** execution_id único por trigger para evitar duplicatas
8. **Versionamento:** Snapshots JSON do workflow em tabela separada

## Licença

MIT
