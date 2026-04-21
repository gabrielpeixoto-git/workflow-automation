# Workflow Automation - Documentação

Sistema completo de automação de workflows com FastAPI, PostgreSQL, Redis e Celery.

## 📚 Documentação Disponível

| Documento | Descrição |
|-----------|-----------|
| [API Guide](API_GUIDE.md) | Guia completo de uso da API |
| [Architecture](ARCHITECTURE.md) | Documentação da arquitetura do sistema |
| [Development](DEVELOPMENT.md) | Guia de desenvolvimento |
| [Installation](INSTALLATION.md) | Guia de instalação e configuração |
| [Examples](EXAMPLES.md) | Exemplos de workflows |

## 🚀 Quick Start

```bash
# 1. Clonar o repositório
git clone <repository-url>
cd sistema-de-automacao

# 2. Iniciar com Docker Compose
docker-compose up -d

# 3. Acessar a aplicação
# Dashboard: http://localhost:8000/
# API Docs: http://localhost:8000/docs
```

## 📋 Funcionalidades Principais

- **Workflows**: Criação e gerenciamento de workflows
- **Execuções**: Monitoramento em tempo real
- **Webhooks**: Integração com sistemas externos
- **Integrações**: Slack, Email, Discord
- **RBAC**: Controle de acesso baseado em roles
- **Analytics**: Métricas e dashboards
- **Templates**: Workflows pré-configurados

## 🛠️ Stack Tecnológico

| Componente | Tecnologia |
|------------|------------|
| Backend | FastAPI + Python 3.12 |
| Database | PostgreSQL 16 |
| Cache/Queue | Redis 7 |
| Worker | Celery + AsyncIO |
| Frontend | HTMX + Tailwind CSS |
| Auth | JWT + API Keys |

## 📞 Suporte

Para dúvidas ou suporte, consulte a documentação específica ou entre em contato com a equipe de desenvolvimento.
