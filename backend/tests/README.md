# Testes Automatizados - Workflow Automation

## Estrutura de Testes

```
tests/
├── conftest.py                 # Configurações e fixtures compartilhadas
├── unit/                       # Testes unitários
│   ├── test_auth.py           # Testes de autenticação
│   └── test_actions.py        # Testes das actions (HTTP, Email, Transform)
└── integration/               # Testes de integração
    ├── test_workflows_api.py  # Testes da API de workflows
    └── test_executions_api.py # Testes da API de execuções
```

## Como Executar

### Executar todos os testes:
```bash
cd backend
pytest
```

### Executar com coverage:
```bash
pytest --cov=app --cov-report=html
```

### Executar testes específicos:
```bash
# Testes unitários apenas
pytest tests/unit/

# Testes de integração apenas
pytest tests/integration/

# Um arquivo específico
pytest tests/unit/test_actions.py

# Um teste específico
pytest tests/unit/test_actions.py::TestHTTPAction::test_http_get_request
```

### Executar com verbose:
```bash
pytest -v
```

### Executar testes que falharam na última execução:
```bash
pytest --lf
```

## Fixtures Disponíveis

### Usuários e Organizações
- `test_org` - Organização de teste
- `test_user` - Usuário Admin
- `test_editor` - Usuário Editor
- `test_viewer` - Usuário Viewer

### Workflows
- `test_workflow` - Workflow básico
- `test_workflow_with_steps` - Workflow com steps (trigger + action)

### Execuções
- `test_execution` - Execução completada
- `test_execution_with_logs` - Execução com logs de steps

### Banco de Dados
- `db` - Sessão async do SQLAlchemy
- `setup_database` - Setup do banco de testes

### Cliente HTTP
- `client` - Cliente TestClient do FastAPI
- `auth_headers` - Headers com token JWT do test_user

## Banco de Dados de Teste

Os testes usam um banco PostgreSQL separado:
```
postgresql+asyncpg://workflow:workflow123@localhost:5432/workflow_automation_test
```

**Importante:** O banco é limpo e recriado a cada sessão de teste.

## Categorias de Testes

### Testes Unitários
Testam componentes isolados sem dependências externas:
- `test_actions.py` - Actions (HTTP, Email, Transform, Database)
- `test_auth.py` - Hash de senha, tokens JWT

### Testes de Integração
Testam a API completa com banco de dados:
- `test_workflows_api.py` - CRUD de workflows, execução
- `test_executions_api.py` - Listagem, detalhes, retry

## Adicionar Novos Testes

### Teste Unitário Simples:
```python
import pytest

class TestMinhaFuncionalidade:
    def test_exemplo_simples(self):
        """Teste simples."""
        resultado = minha_funcao(2, 3)
        assert resultado == 5
    
    @pytest.mark.asyncio
    async def test_exemplo_async(self):
        """Teste async."""
        resultado = await minha_funcao_async()
        assert resultado is not None
```

### Teste de Integração com Banco:
```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

class TestMinhaAPI:
    @pytest.mark.asyncio
    async def test_endpoint(
        self, 
        client: TestClient, 
        auth_headers: dict,
        db: AsyncSession,
        test_workflow: Workflow
    ):
        """Teste de endpoint."""
        response = client.get(
            f"/api/workflows/{test_workflow.id}",
            headers=auth_headers
        )
        assert response.status_code == 200
```

## Boas Práticas

1. **Nomenclatura**: Use nomes descritivos que expliquem o comportamento testado
2. **Isolamento**: Cada teste deve ser independente
3. **Fixtures**: Use fixtures para setup/teardown reutilizável
4. **Asserts claros**: Use mensagens explicativas quando necessário
5. **Mock externo**: Use mocks para serviços externos (HTTP, Email, etc)

## CI/CD

Para integração contínua, adicione ao pipeline:
```bash
pytest --cov=app --cov-fail-under=80
```

Isso garante que o código tenha pelo menos 80% de cobertura de testes.
