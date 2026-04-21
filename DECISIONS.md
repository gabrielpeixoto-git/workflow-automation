# Decisões Técnicas - Workflow Automation Platform

## 1. Arquitetura Geral

### 1.1 Stack Tecnológica
- **Backend:** FastAPI com Python 3.12+ (async first)
- **Database:** PostgreSQL 16 com SQLAlchemy 2.x (asyncpg driver)
- **Cache/Queue:** Redis 7
- **Worker:** Celery 5.x para tarefas assíncronas
- **Frontend:** HTMX + Alpine.js + Tailwind CSS (SSR leve)
- **Autenticação:** JWT (access + refresh tokens)

### 1.2 Decisão: Async vs Sync
- **Endpoints FastAPI:** Async (para I/O não-bloqueante)
- **Celery Workers:** Sync (Celery não suporta async nativamente)
- **Database:** SQLAlchemy 2.x com asyncpg para operações assíncronas

### 1.3 Estrutura de Pastas
```
backend/
├── app/
│   ├── api/          # Rotas REST
│   ├── core/         # Configurações, segurança, logging
│   ├── db/           # Database connection e session
│   ├── models/       # SQLAlchemy models
│   ├── services/     # Business logic
│   ├── tasks/        # Celery tasks
│   ├── utils/        # Helpers
│   └── web/          # Web routes (HTMX templates)
├── alembic/          # Migrations
└── tests/            # Testes

frontend/
├── static/           # CSS, JS, images
└── templates/        # Jinja2 templates
```

## 2. Database e Models

### 2.1 Multi-tenancy
- **Abordagem:** Shared Database, Shared Schema
- **Implementação:** `organization_id` em todas as tabelas relevantes
- **Filtragem:** Automática via dependências do FastAPI

### 2.2 Soft Delete
- **Campo:** `deleted_at` (timestamp ou null)
- **Query padrão:** Excluir registros onde `deleted_at IS NOT NULL`
- **Vantagens:** Auditoria e recuperação de dados

### 2.3 Índices
- Criados em campos de busca frequentes: `email`, `slug`, `status`, `organization_id`
- Índices compostos para constraints únicas: `(organization_id, slug)`
- Índices em foreign keys para join performance

### 2.4 Migrations
- **Ferramenta:** Alembic
- **Estratégia:** Autogenerate para desenvolvimento, manual review para produção
- **Async:** Suporte completo via `sqlalchemy.ext.asyncio`

## 3. Autenticação e Autorização

### 3.1 JWT Tokens
- **Access Token:** 15 minutos de expiração
- **Refresh Token:** 7 dias de expiração
- **Algoritmo:** HS256 (simétrico, mais simples para single-server)
- **Storage:** LocalStorage + Cookie HttpOnly (defesa contra XSS)

### 3.2 RBAC (Role-Based Access Control)
- **Roles:** admin, editor, viewer
- **Permissões:**
  - Admin: Full access
  - Editor: CRUD workflows, execute, retry
  - Viewer: Read-only

### 3.3 Multi-tenant Security
- Todas as queries filtram por `organization_id`
- User só acessa dados da própria organização
- Middleware verifica JWT e injeta usuário no contexto

## 4. Workflow Engine

### 4.1 Estrutura de Workflow
- **Workflow:** Definição (nome, status, tags, version)
- **Steps:** Lista ordenada de gatilhos e ações
- **Trigger:** Sempre o primeiro step (único)
- **Actions:** Steps subsequentes executados em sequência

### 4.2 Tipos de Triggers
- `webhook`: Endpoint HTTP dinâmico
- `scheduled`: Cron job via Celery Beat
- `manual`: Trigger via API/dashboard
- `file_upload`: Upload de arquivo processado async

### 4.3 Tipos de Actions
- `http_request`: Chamada HTTP com retries
- `send_email`: Envio de email (SMTP)
- `write_database`: Escrita em banco de dados
- `transform_payload`: Transformação de dados
- `export_csv`: Geração de CSV
- `export_pdf`: Geração de PDF
- `notify`: Notificação in-app

### 4.4 Execução
- **Status:** pending → running → completed/failed/cancelled
- **Retry:** Máximo 3 tentativas com backoff exponencial
- **Context:** Passagem de dados entre steps via dict compartilhado
- **Idempotência:** `correlation_id` único por execução

## 5. Celery e Processamento Assíncrono

### 5.1 Configuração
- **Broker:** Redis (db 1)
- **Backend:** Redis (db 2) para resultados
- **Prefetch:** 1 (um job por worker por vez)
- **Acks Late:** Sim (ack apenas após conclusão)

### 5.2 Retry Strategy
- **Default:** 3 retries com delay progressivo
- **Backoff:** Exponencial (60s, 120s, 240s)
- **Max Time:** 1 hora por task

### 5.3 Monitoring
- Eventos: `task_prerun`, `task_success`, `task_failure`
- Logging estruturado com structlog
- Audit trail automático de todas as execuções

## 6. Observabilidade

### 6.1 Logging
- **Formato:** JSON em produção, pretty print em desenvolvimento
- **Biblioteca:** structlog
- **Campos:** timestamp, level, event, correlation_id, user_id

### 6.2 Audit Logs
- **Ações Trackeadas:**
  - Auth: login, logout, password_change
  - User: create, update, delete
  - Workflow: create, update, delete, activate, duplicate
  - Execution: start, complete, fail, retry, cancel

### 6.3 Request Context
- IP address e User-Agent capturados
- Correlation ID para tracing entre serviços
- Organization ID em todas as ações

## 7. Frontend

### 7.1 Decisão: HTMX vs React/Vue
- **Escolha:** HTMX + Alpine.js
- **Motivo:** Simplicidade, SSR nativo, menos complexidade
- **Performance:** Menos JavaScript no cliente, atualizações parciais

### 7.2 Componentes
- **Templates:** Jinja2 com macros
- **CSS:** Tailwind CSS via CDN (dev) / build (prod)
- **Ícones:** Lucide
- **Interatividade:** Alpine.js para estados locais

### 7.3 Páginas Implementadas
- Dashboard com métricas em tempo real
- Lista de workflows com filtros
- Modal de criação de workflow
- Login page com JWT handling

## 8. Testes

### 8.1 Estratégia
- **Unitários:** Testes de serviços e utilities isolados
- **Integração:** Testes de API com database real
- **Fixtures:** Factory pattern para dados de teste

### 8.2 Configuração
- **pytest-asyncio:** Suporte a async tests
- **Async DB:** Sessão dedicada para testes
- **Rollback:** Cada teste roda em transação que é revertida

## 9. Docker e Deploy

### 9.1 Serviços
- `db`: PostgreSQL 16
- `redis`: Redis 7
- `api`: FastAPI app
- `worker`: Celery workers
- `beat`: Celery beat (scheduler)

### 9.2 Volumes
- `postgres_data`: Persistência de dados
- `uploads`: Arquivos enviados
- `logs`: Logs da aplicação

### 9.3 Health Checks
- PostgreSQL: `pg_isready`
- Redis: `redis-cli ping`
- API: Endpoint `/health`

## 10. Segurança

### 10.1 OWASP Top 10 Considerações
- **Injection:** SQLAlchemy ORM (parameterized queries)
- **Broken Auth:** JWT com expiração, bcrypt para senhas
- **Sensitive Data:** HTTPS em produção, variáveis em .env
- **XXE:** Não processamos XML externo
- **Broken Access Control:** RBAC + multi-tenant filters
- **Security Misconfig:** Settings via env vars
- **XSS:** HTMX auto-escapa HTML, CSP headers
- **Insecure Deserialization:** Pydantic validation
- **Vulnerable Components:** Dependabot/renovate
- **Insufficient Logging:** Audit logs completos

### 10.2 Headers de Segurança
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- (HTTPS em produção)

## 11. Performance

### 11.1 Database
- Connection pooling: 10 conexões base + 20 overflow
- Pre-ping para detectar conexões mortas
- Lazy loading para relationships

### 11.2 Caching
- Redis para resultados Celery
- Potencial para cache de queries frequentes

### 11.3 Async I/O
- Todas as operações de I/O são async
- HTTP requests via httpx (async)
- Email via aiosmtplib (async)

## 12. Escalabilidade

### 12.1 Horizontal Scaling
- Workers Celery podem escalar horizontalmente
- Stateless API (session no JWT)
- Shared database e Redis

### 12.2 Limites
- Max upload: 10MB
- Max execution time: 1 hora
- Max retries: 3 por step

## 13. Manutenibilidade

### 13.1 Código
- Type hints em todo o código
- Docstrings em todas as funções públicas
- PEP8 compliance via ruff
- Single Responsibility Principle

### 13.2 Dependencies
- pyproject.toml para gestão de dependências
- Versões pinadas para reprodutibilidade
- Dev dependencies separadas

## 14. Tratamento de Erros

### 14.1 Estratégia
- Exceptions customizadas para casos de negócio
- HTTPException do FastAPI para API errors
- Try/catch em tasks Celery para não perder jobs

### 14.2 Logging de Erros
- Stack traces em logs estruturados
- Contexto completo (user_id, workflow_id, execution_id)
- Audit logs para ações falhas

## 15. Idempotência

### 15.1 Implementação
- `correlation_id` único por execução
- Verificação antes de criar nova execução
- Retry logic preserva contexto original

### 15.2 Benefícios
- Safe retries sem duplicatas
- Webhooks podem ser chamados múltiplas vezes
- Recovery de falhas confiável
