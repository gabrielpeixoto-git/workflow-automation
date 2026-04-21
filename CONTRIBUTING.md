# Contributing to Workflow Automation

Obrigado pelo seu interesse em contribuir com o Workflow Automation! 🎉

## 📋 Como Contribuir

### 1. Reportando Bugs

Se você encontrou um bug:

1. Verifique se o bug já foi reportado nas [Issues](https://github.com/yourusername/workflow-automation/issues)
2. Se não, crie uma nova issue com:
   - Título descritivo
   - Passos para reproduzir
   - Comportamento esperado vs atual
   - Screenshots (se aplicável)
   - Ambiente (OS, versões, etc)

### 2. Sugerindo Features

Para sugerir novas funcionalidades:

1. Abra uma issue com o label `enhancement`
2. Descreva a feature e seu caso de uso
3. Explique por que seria útil

### 3. Pull Requests

#### Processo

1. **Fork** o repositório
2. **Clone** seu fork: `git clone https://github.com/seu-usuario/workflow-automation.git`
3. **Crie uma branch**: `git checkout -b feature/sua-feature`
4. **Faça as alterações**
5. **Commit** com mensagens claras (veja [Conventional Commits](#conventional-commits))
6. **Push** para seu fork: `git push origin feature/sua-feature`
7. **Abra um PR** para a branch `main`

#### Padrões de Código

- Siga [PEP 8](https://pep8.org/)
- Use type hints
- Documente funções e classes
- Mantenha cobertura de testes > 80%

#### Antes de Submeter

```bash
# Rodar testes
pytest

# Verificar linting
ruff check .

# Formatar código
black app/ tests/
isort app/ tests/

# Type checking
mypy app/
```

## 📝 Conventional Commits

Use o formato:

```
<type>(<scope>): <descrição>

[corpo opcional]

[rodapé opcional]
```

### Tipos

- `feat`: Nova funcionalidade
- `fix`: Correção de bug
- `docs`: Documentação
- `style`: Formatação (sem alteração de código)
- `refactor`: Refatoração
- `test`: Testes
- `chore`: Tarefas de build/CI

### Exemplos

```
feat(workflow): add retry logic to webhook actions

fix(auth): resolve JWT token expiration issue

docs(api): update swagger documentation for webhooks

test(execution): add unit tests for execution service
```

## 🧪 Desenvolvimento Local

### Setup

```bash
# Clone
git clone https://github.com/yourusername/workflow-automation.git
cd workflow-automation

# Docker
docker-compose up -d db redis

# Python
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Migrations
alembic upgrade head

# Seeds
python -m app.db.seeds
```

### Rodar

```bash
# API
uvicorn app.main:app --reload

# Worker
celery -A app.tasks worker -l info

# Scheduler
celery -A app.tasks beat -l info
```

### Testar

```bash
# Todos os testes
pytest

# Com verbose
pytest -v

# Com cobertura
pytest --cov=app --cov-report=html
```

## 🎯 Áreas de Contribuição

### Alta Prioridade

- [ ] Testes E2E com Playwright
- [ ] Documentação de API (OpenAPI/Swagger)
- [ ] Otimização de queries do database
- [ ] Internacionalização (i18n)

### Média Prioridade

- [ ] Novos conectores de integração
- [ ] Templates de workflows
- [ ] Dashboard de métricas
- [ ] Dark mode na UI

### Baixa Prioridade

- [ ] Mobile app
- [ ] PWA
- [ ] Plugins/extensions
- [ ] Tema customizável

## 🏆 Reconhecimento

Contribuidores serão reconhecidos no README do projeto!

## ❓ Dúvidas?

- Abra uma [Discussion](https://github.com/yourusername/workflow-automation/discussions)
- Ou entre em contato: gabrielcampos@gmail.com

---

Obrigado por contribuir! 🚀
