# Guia de Desenvolvimento - Workflow Automation

Guia completo para desenvolvedores contribuírem com o projeto.

## 📋 Índice

- [Configuração do Ambiente](#configuração-do-ambiente)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [Desenvolvendo Funcionalidades](#desenvolvendo-funcionalidades)
- [Padrões de Código](#padrões-de-código)
- [Testes](#testes)
- [Debug](#debug)
- [Contribuição](#contribuição)

---

## Configuração do Ambiente

### 1. Pré-requisitos

- Python 3.12+
- Docker e Docker Compose
- Git
- VS Code (recomendado)

### 2. Setup Inicial

```bash
# Clonar repositório
git clone <repository-url>
cd sistema-de-automacao

# Copiar configurações
cp .env.example .env

# Iniciar infraestrutura (DB, Redis)
docker-compose up -d db redis

# Configurar ambiente Python
cd backend
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt  # dependências de dev
```

### 3. Configurar VS Code

Extensões recomendadas:
- Python (Microsoft)
- Pylance
- Python Test Explorer
- Docker
- Thunder Client (API testing)

**Configuração `.vscode/settings.json`:**

```json
{
  "python.defaultInterpreterPath": "./backend/venv/bin/python",
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": false,
  "python.linting.flake8Enabled": true,
  "python.linting.mypyEnabled": true,
  "python.formatting.provider": "black",
  "editor.formatOnSave": true,
  "python.testing.pytestEnabled": true,
  "python.testing.pytestArgs": ["tests"]
}
```

---

## Estrutura do Projeto

```
sistema-de-automacao/
├── backend/
│   ├── app/
│   │   ├── api/              # Endpoints REST
│   │   ├── core/             # Configurações core
│   │   ├── db/               # Database connection
│   │   ├── models/           # SQLAlchemy models
│   │   ├── services/         # Business logic
│   │   ├── tasks/            # Celery tasks
│   │   ├── web/              # Web UI routes
│   │   └── main.py           # FastAPI application
│   ├── tests/
│   │   ├── unit/             # Unit tests
│   │   ├── integration/      # Integration tests
│   │   └── conftest.py       # Pytest fixtures
│   ├── alembic/              # Database migrations
│   └── pyproject.toml        # Project config
├── docker-compose.yml
├── Dockerfile
└── docs/                     # Documentation
```

---

## Desenvolvendo Funcionalidades

### Fluxo de Desenvolvimento

```
1. Criar branch
   git checkout -b feature/nome-da-feature

2. Desenvolver
   - Código
   - Testes
   - Documentação

3. Testar localmente
   pytest tests/

4. Commit
   git commit -m "feat: descrição da feature"

5. Push e PR
   git push origin feature/nome-da-feature
```

### Criando um Novo Endpoint

**Exemplo: Novo endpoint de relatórios**

```python
# app/api/reports.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.services.report_service import ReportService

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/workflow-executions")
async def get_workflow_execution_report(
    workflow_id: str,
    days: int = 30,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get workflow execution report."""
    report = await ReportService.generate_execution_report(
        db=db,
        workflow_id=workflow_id,
        days=days,
        organization_id=user.organization_id,
    )
    return report
```

**Registro no main.py:**

```python
# app/main.py
from app.api import reports

app.include_router(reports.router)
```

### Criando um Novo Service

```python
# app/services/report_service.py
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache


class ReportService:
    """Service for generating reports."""

    @staticmethod
    @cache.cached(ttl=300)  # Cache 5 minutos
    async def generate_execution_report(
        db: AsyncSession,
        workflow_id: str,
        days: int,
        organization_id: str,
    ) -> dict[str, Any]:
        """Generate execution report for workflow."""
        # Implementation
        return {
            "workflow_id": workflow_id,
            "period_days": days,
            "total_executions": 100,
            "success_rate": 95.5,
            # ...
        }
```

### Criando uma Nova Action

```python
# app/services/actions.py

async def execute_custom_action(
    config: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    """Execute custom action."""
    # Validar config
    required_fields = ["endpoint", "method"]
    for field in required_fields:
        if field not in config:
            raise ValueError(f"Missing required field: {field}")

    # Executar lógica
    result = await process_custom_logic(config, context)

    return result


async def process_custom_logic(config, context):
    """Process custom business logic."""
    # Implementation
    pass
```

---

## Padrões de Código

### 1. Estilo de Código

**Usamos:**
- **Black**: Formatação automática
- **isort**: Organização de imports
- **flake8**: Linting
- **mypy**: Type checking

**Comandos:**

```bash
# Formatar código
black app/ tests/

# Organizar imports
isort app/ tests/

# Verificar linting
flake8 app/ tests/

# Type checking
mypy app/

# Tudo de uma vez
./scripts/lint.sh
```

### 2. Convenções de Nomenclatura

```python
# Classes: PascalCase
class WorkflowService:
    pass

# Funções e variáveis: snake_case
def process_workflow(workflow_id: str) -> dict:
    result_data = {}
    return result_data

# Constantes: UPPER_CASE
MAX_RETRY_ATTEMPTS = 3
DEFAULT_TIMEOUT = 30

# Privados: _prefix
def _internal_helper():
    pass
```

### 3. Type Hints

```python
from typing import Any, Optional
from uuid import UUID

async def get_workflow(
    db: AsyncSession,
    workflow_id: UUID,
    organization_id: UUID,
) -> Optional[Workflow]:
    """Get workflow by ID."""
    result = await db.execute(
        select(Workflow).where(
            Workflow.id == workflow_id,
            Workflow.organization_id == organization_id,
        )
    )
    return result.scalar_one_or_none()
```

### 4. Documentação de Código

```python
async def execute_workflow(
    db: AsyncSession,
    workflow_id: UUID,
    payload: dict[str, Any],
    triggered_by: str = "manual",
) -> WorkflowExecution:
    """Execute a workflow with given payload.

    Args:
        db: Database session
        workflow_id: Workflow UUID
        payload: Input data for execution
        triggered_by: Who/what triggered the execution

    Returns:
        WorkflowExecution: Created execution record

    Raises:
        WorkflowNotFoundError: If workflow doesn't exist
        WorkflowInactiveError: If workflow is not active

    Example:
        >>> execution = await execute_workflow(
        ...     db=session,
        ...     workflow_id=uuid,
        ...     payload={"name": "Test"},
        ... )
    """
    # Implementation
    pass
```

### 5. Error Handling

```python
from fastapi import HTTPException

# Nunca faça isso:
try:
    result = risky_operation()
except Exception as e:
    print(e)  # Silencia o erro!

# Faça isso:
try:
    result = risky_operation()
except WorkflowNotFoundError as e:
    logger.warning(f"Workflow not found: {e}")
    raise HTTPException(status_code=404, detail="Workflow not found")
except ValidationError as e:
    logger.error(f"Validation failed: {e}")
    raise HTTPException(status_code=422, detail=str(e))
except Exception as e:
    logger.exception(f"Unexpected error: {e}")
    raise HTTPException(status_code=500, detail="Internal server error")
```

---

## Testes

### Estrutura de Testes

```
tests/
├── conftest.py           # Fixtures globais
├── unit/                 # Testes unitários
│   ├── test_workflow_service.py
│   ├── test_execution_service.py
│   └── ...
├── integration/          # Testes de integração
│   ├── test_workflows_api.py
│   └── ...
└── e2e/                  # Testes end-to-end
    └── test_full_flow.py
```

### Fixtures Comuns

```python
# tests/conftest.py
import pytest
from httpx import AsyncClient

from app.main import app
from app.db.database import get_db


@pytest.fixture
async def client():
    """Async HTTP client."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def authenticated_client(client, test_user):
    """Authenticated client."""
    response = await client.post(
        "/api/auth/login",
        json={"email": test_user.email, "password": "test123"},
    )
    token = response.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    yield client


@pytest.fixture
async def test_user(db):
    """Create test user."""
    user = User(
        email="test@example.com",
        hashed_password=get_password_hash("test123"),
    )
    db.add(user)
    await db.commit()
    yield user
```

### Escrevendo Testes

```python
# tests/unit/test_workflow_service.py
import pytest
from unittest.mock import AsyncMock, patch

from app.services.workflow_service import WorkflowService
from app.models.workflow import WorkflowStatus


class TestWorkflowService:
    """Test WorkflowService."""

    async def test_get_workflow_success(self, db, test_user):
        """Test getting existing workflow."""
        # Arrange
        workflow = await create_test_workflow(db, user=test_user)

        # Act
        result = await WorkflowService.get_workflow(
            db=db,
            workflow_id=workflow.id,
            organization_id=test_user.organization_id,
        )

        # Assert
        assert result is not None
        assert result.id == workflow.id
        assert result.name == workflow.name

    async def test_get_workflow_not_found(self, db, test_user):
        """Test getting non-existent workflow."""
        # Act
        result = await WorkflowService.get_workflow(
            db=db,
            workflow_id="non-existent-id",
            organization_id=test_user.organization_id,
        )

        # Assert
        assert result is None

    async def test_create_workflow(self, db, test_user):
        """Test creating new workflow."""
        # Arrange
        data = {
            "name": "Test Workflow",
            "slug": "test-workflow",
            "trigger_type": "manual",
        }

        # Act
        workflow = await WorkflowService.create_workflow(
            db=db,
            data=data,
            organization_id=test_user.organization_id,
        )

        # Assert
        assert workflow.name == "Test Workflow"
        assert workflow.status == WorkflowStatus.DRAFT
        assert workflow.organization_id == test_user.organization_id

    @patch("app.services.workflow_service.send_notification")
    async def test_execute_workflow_sends_notification(
        self,
        mock_send_notification,
        db,
        test_user,
    ):
        """Test that workflow execution sends notification."""
        # Arrange
        workflow = await create_test_workflow(db, user=test_user)
        mock_send_notification.return_value = AsyncMock()

        # Act
        await WorkflowService.execute_workflow(
            db=db,
            workflow_id=workflow.id,
            payload={},
        )

        # Assert
        mock_send_notification.assert_called_once()
```

### Executando Testes

```bash
# Todos os testes
pytest

# Com verbose
pytest -v

# Com cobertura
pytest --cov=app --cov-report=html

# Testes específicos
pytest tests/unit/test_workflow_service.py

# Apenas um teste
pytest tests/unit/test_workflow_service.py::TestWorkflowService::test_create_workflow

# Testes de integração
pytest tests/integration/ -v

# Paralelo (mais rápido)
pytest -n auto
```

---

## Debug

### 1. Debug com VS Code

**`.vscode/launch.json`:**

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: FastAPI",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": ["app.main:app", "--reload"],
      "jinja": true,
      "cwd": "${workspaceFolder}/backend"
    },
    {
      "name": "Python: Current File",
      "type": "python",
      "request": "launch",
      "program": "${file}",
      "console": "integratedTerminal",
      "cwd": "${workspaceFolder}/backend"
    }
  ]
}
```

### 2. Debug com PDB

```python
# Adicionar breakpoint
import pdb; pdb.set_trace()

# Ou no Python 3.7+
breakpoint()
```

Comandos PDB:
- `n` (next): Próxima linha
- `s` (step): Entrar na função
- `c` (continue): Continuar execução
- `p variable`: Printar variável
- `l` (list): Mostrar código
- `q` (quit): Sair

### 3. Logging

```python
import logging

logger = logging.getLogger(__name__)

# Níveis de log
logger.debug("Debug message")
logger.info("Info message")
logger.warning("Warning message")
logger.error("Error message")
logger.exception("Exception with traceback")
```

### 4. Debug de Tasks Celery

```python
# Executar task síncrono para debug
result = my_task.apply(args=[arg1, arg2])

# Ou com throw para ver exceções
result = my_task.apply(args=[arg1, arg2], throw=True)
```

---

## Contribuição

### 1. Criar Issue

Antes de começar, crie uma issue descrevendo:
- O problema ou feature
- Solução proposta
- Critérios de aceitação

### 2. Branch Naming

```
feature/descrição-da-feature
bugfix/descrição-do-bug
hotfix/descrição-do-hotfix
docs/descrição-da-doc
refactor/descrição-do-refactor
```

### 3. Commits

Seguimos [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: adicionar novo tipo de action
fix: corrigir bug no webhook handler
docs: atualizar README
style: formatar código com black
refactor: simplificar workflow service
test: adicionar testes para executions
chore: atualizar dependências
```

### 4. Pull Request

Template de PR:

```markdown
## Descrição
Breve descrição da mudança

## Tipo de Mudança
- [ ] Bug fix
- [ ] Nova feature
- [ ] Breaking change
- [ ] Documentação

## Checklist
- [ ] Código segue padrões do projeto
- [ ] Testes adicionados/atualizados
- [ ] Documentação atualizada
- [ ] Lint passa (black, flake8, mypy)
- [ ] Testes passam localmente

## Screenshots (se aplicável)

## Testes Realizados
Descreva os testes realizados
```

### 5. Code Review

Critérios de review:
- Código limpo e legível
- Testes adequados
- Documentação atualizada
- Sem bugs óbvios
- Performance aceitável

---

## Recursos Adicionais

### Documentação API

Acesse a documentação interativa:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Comandos Úteis

```bash
# Reset database
make reset-db

# Seed data
make seed

# Run all checks
make check  # lint + test + typecheck

# Generate migration
alembic revision --autogenerate -m "descrição"

# Shell interativo
python -m app.scripts.shell
```

---

Para mais informações, consulte:
- [Architecture](ARCHITECTURE.md)
- [Installation](INSTALLATION.md)
- [API Guide](API_GUIDE.md)
