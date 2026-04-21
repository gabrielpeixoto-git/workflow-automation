# Guia de Instalação - Workflow Automation

Guia passo a passo para instalação e configuração do sistema.

## 📋 Requisitos

### Mínimos

- **CPU**: 2 cores
- **RAM**: 4 GB
- **Disco**: 20 GB SSD
- **OS**: Linux (Ubuntu 22.04+), macOS, Windows (WSL2)

### Recomendados (Produção)

- **CPU**: 4+ cores
- **RAM**: 8+ GB
- **Disco**: 50+ GB SSD
- **OS**: Linux (Ubuntu 22.04 LTS)

### Dependências

- Docker 24.0+
- Docker Compose 2.20+
- Git 2.40+

---

## 🚀 Instalação Rápida (Docker Compose)

### 1. Clonar Repositório

```bash
git clone <repository-url>
cd sistema-de-automacao
```

### 2. Configurar Variáveis de Ambiente

```bash
# Copiar arquivo de exemplo
cp .env.example .env

# Editar .env com suas configurações
nano .env
```

**Configurações essenciais:**

```env
# Database
DATABASE_URL=postgresql://postgres:postgres@db:5432/workflow_automation

# Redis
REDIS_URL=redis://redis:6379/0

# Security
SECRET_KEY=your-super-secret-key-change-in-production
JWT_SECRET_KEY=your-jwt-secret-key

# Email (opcional)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# Ambiente
DEBUG=false
ENVIRONMENT=production
```

### 3. Iniciar Serviços

```bash
# Construir e iniciar
docker-compose up -d

# Verificar status
docker-compose ps

# Ver logs
docker-compose logs -f api
```

### 4. Acessar Aplicação

- **Dashboard**: http://localhost:8000/
- **API Docs**: http://localhost:8000/docs
- **Web UI**: http://localhost:8000/workflows

### 5. Criar Usuário Admin

```bash
# Executar comando no container
docker-compose exec api python -c "
from app.scripts.create_admin import create_admin
create_admin()
"
```

Ou acesse `/setup` no navegador para criar o primeiro usuário.

---

## 🔧 Instalação Manual (Desenvolvimento)

### 1. Instalar Dependências do Sistema

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install -y python3.12 python3.12-venv python3.12-dev postgresql-16 redis-server git
```

**macOS:**
```bash
brew install python@3.12 postgresql@16 redis git
```

**Windows (WSL2):**
```bash
# Siga instruções Ubuntu acima
```

### 2. Configurar PostgreSQL

```bash
# Criar usuário e database
sudo -u postgres psql -c "CREATE USER workflow WITH PASSWORD 'workflow123';"
sudo -u postgres psql -c "CREATE DATABASE workflow_automation OWNER workflow;"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE workflow_automation TO workflow;"
```

### 3. Configurar Redis

```bash
# Iniciar Redis
sudo systemctl start redis
sudo systemctl enable redis

# Verificar
redis-cli ping  # Deve retornar PONG
```

### 4. Configurar Python Environment

```bash
cd backend

# Criar virtual environment
python3.12 -m venv venv

# Ativar
source venv/bin/activate  # Linux/Mac
# ou: venv\Scripts\activate  # Windows

# Instalar dependências
pip install --upgrade pip
pip install -r requirements.txt
```

### 5. Configurar Variáveis de Ambiente

```bash
cp .env.example .env
nano .env
```

Configuração local:
```env
DATABASE_URL=postgresql://workflow:workflow123@localhost:5432/workflow_automation
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=dev-secret-key
JWT_SECRET_KEY=dev-jwt-secret
DEBUG=true
ENVIRONMENT=development
```

### 6. Executar Migrations

```bash
alembic upgrade head
```

### 7. Criar Dados Iniciais

```bash
python -m app.scripts.seed_data
```

### 8. Iniciar Servidor

```bash
# Terminal 1: API
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Worker
celery -A app.tasks worker -l info

# Terminal 3: Scheduler
celery -A app.tasks beat -l info
```

---

## ☁️ Instalação em Produção

### AWS (ECS + RDS + ElastiCache)

#### 1. Infraestrutura (Terraform)

```hcl
# main.tf
provider "aws" {
  region = "us-east-1"
}

# VPC, Subnets, Security Groups
module "vpc" {
  source = "terraform-aws-modules/vpc/aws"
  
  name = "workflow-automation"
  cidr = "10.0.0.0/16"
  
  azs             = ["us-east-1a", "us-east-1b"]
  public_subnets  = ["10.0.1.0/24", "10.0.2.0/24"]
  private_subnets = ["10.0.3.0/24", "10.0.4.0/24"]
}

# RDS PostgreSQL
resource "aws_db_instance" "postgres" {
  identifier     = "workflow-db"
  engine         = "postgres"
  engine_version = "16.1"
  instance_class = "db.t3.medium"
  
  allocated_storage = 50
  storage_type      = "gp3"
  
  db_name  = "workflow_automation"
  username = "workflow_admin"
  password = var.db_password
  
  vpc_security_group_ids = [aws_security_group.db.id]
  db_subnet_group_name = aws_db_subnet_group.main.name
  
  backup_retention_period = 7
  multi_az               = true
}

# ElastiCache Redis
resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "workflow-cache"
  engine               = "redis"
  node_type            = "cache.t3.micro"
  num_cache_nodes      = 1
  parameter_group_name = "default.redis7"
  port                 = 6379
  
  security_group_ids = [aws_security_group.redis.id]
}

# ECS Cluster
resource "aws_ecs_cluster" "main" {
  name = "workflow-automation"
  
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}
```

#### 2. Deploy da Aplicação

```bash
# Build e push da imagem
aws ecr get-login-password | docker login --username AWS --password-stdin <account>.dkr.ecr.us-east-1.amazonaws.com

docker build -t workflow-automation:latest ./backend
docker tag workflow-automation:latest <account>.dkr.ecr.us-east-1.amazonaws.com/workflow-automation:latest
docker push <account>.dkr.ecr.us-east-1.amazonaws.com/workflow-automation:latest

# Deploy ECS
terraform apply
```

### Kubernetes (EKS/GKE/AKS)

#### 1. Namespace e Configurações

```yaml
# namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: workflow-automation
---
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: workflow-config
  namespace: workflow-automation
data:
  DATABASE_URL: "postgresql://..."
  REDIS_URL: "redis://..."
  ENVIRONMENT: "production"
```

#### 2. Secrets

```yaml
# secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: workflow-secrets
  namespace: workflow-automation
type: Opaque
stringData:
  SECRET_KEY: "super-secret-key"
  JWT_SECRET_KEY: "jwt-secret-key"
  DB_PASSWORD: "db-password"
```

#### 3. Deployment API

```yaml
# api-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: workflow-api
  namespace: workflow-automation
spec:
  replicas: 3
  selector:
    matchLabels:
      app: workflow-api
  template:
    metadata:
      labels:
        app: workflow-api
    spec:
      containers:
      - name: api
        image: workflow-automation:latest
        ports:
        - containerPort: 8000
        envFrom:
        - configMapRef:
            name: workflow-config
        - secretRef:
            name: workflow-secrets
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
```

#### 4. Service e Ingress

```yaml
# service.yaml
apiVersion: v1
kind: Service
metadata:
  name: workflow-api-service
  namespace: workflow-automation
spec:
  selector:
    app: workflow-api
  ports:
  - port: 80
    targetPort: 8000
  type: ClusterIP
---
# ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: workflow-ingress
  namespace: workflow-automation
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
  - hosts:
    - workflow.exemplo.com
    secretName: workflow-tls
  rules:
  - host: workflow.exemplo.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: workflow-api-service
            port:
              number: 80
```

#### 5. Deploy Workers

```yaml
# worker-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: workflow-worker
  namespace: workflow-automation
spec:
  replicas: 2
  selector:
    matchLabels:
      app: workflow-worker
  template:
    metadata:
      labels:
        app: workflow-worker
    spec:
      containers:
      - name: worker
        image: workflow-automation:latest
        command: ["celery", "-A", "app.tasks", "worker", "-l", "info"]
        envFrom:
        - configMapRef:
            name: workflow-config
        - secretRef:
            name: workflow-secrets
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
```

#### 6. Apply

```bash
kubectl apply -f k8s/
```

---

## 🔐 Configurações de Segurança

### 1. SSL/TLS

**Com Certbot (Let's Encrypt):**

```bash
# Instalar certbot
sudo apt install certbot

# Gerar certificado
sudo certbot certonly --standalone -d workflow.exemplo.com

# Configurar auto-renewal
sudo certbot renew --dry-run
```

**No Docker Compose:**

```yaml
services:
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - /etc/letsencrypt:/etc/letsencrypt
```

### 2. Firewall

```bash
# UFW (Ubuntu)
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

### 3. Backup

**Script de Backup:**

```bash
#!/bin/bash
# backup.sh

BACKUP_DIR="/backups/$(date +%Y%m%d)"
mkdir -p $BACKUP_DIR

# Backup PostgreSQL
docker exec workflow-db pg_dump -U postgres workflow_automation > $BACKUP_DIR/database.sql

# Backup Redis
docker exec workflow-redis redis-cli BGSAVE
docker cp workflow-redis:/data/dump.rdb $BACKUP_DIR/redis.rdb

# Compressão
tar -czf $BACKUP_DIR.tar.gz $BACKUP_DIR
rm -rf $BACKUP_DIR

# Upload para S3 (opcional)
aws s3 cp $BACKUP_DIR.tar.gz s3://workflow-backups/
```

---

## 📊 Monitoramento

### 1. Health Checks

```bash
# Verificar saúde do sistema
curl http://localhost:8000/health

# Verificar database
curl http://localhost:8000/health/db

# Verificar Redis
curl http://localhost:8000/health/redis
```

### 2. Logs

```bash
# Ver logs em tempo real
docker-compose logs -f api

# Ver logs dos workers
docker-compose logs -f worker
```

---

## 🔄 Atualização

### Atualização Sem Downtime

```bash
# 1. Pull novas imagens
docker-compose pull

# 2. Executar migrations
docker-compose run --rm api alembic upgrade head

# 3. Reiniciar serviços
docker-compose up -d

# 4. Verificar saúde
curl http://localhost:8000/health
```

---

## ❌ Troubleshooting

### Problemas Comuns

**1. Erro de conexão com database:**
```bash
# Verificar se PostgreSQL está rodando
docker-compose ps db

# Verificar logs
docker-compose logs db

# Testar conexão
docker-compose exec db psql -U postgres -d workflow_automation -c "SELECT 1"
```

**2. Redis não conecta:**
```bash
# Verificar Redis
docker-compose exec redis redis-cli ping

# Verificar variável REDIS_URL no .env
```

**3. Worker não processa tarefas:**
```bash
# Verificar logs do worker
docker-compose logs worker

# Verificar fila no Redis
docker-compose exec redis redis-cli LLEN celery
```

---

Para mais informações, consulte:
- [Architecture](ARCHITECTURE.md)
- [Development Guide](DEVELOPMENT.md)
- [API Guide](API_GUIDE.md)
