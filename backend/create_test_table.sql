-- Criar tabela de teste para workflow automation
CREATE TABLE IF NOT EXISTS workflow_data (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(255),
    email VARCHAR(255),
    telefone VARCHAR(50),
    mensagem TEXT,
    origem VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Criar tabela de logs genérica
CREATE TABLE IF NOT EXISTS workflow_logs (
    id SERIAL PRIMARY KEY,
    workflow_id VARCHAR(100),
    execution_id VARCHAR(100),
    event_type VARCHAR(50),
    event_data JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Criar tabela de leads (exemplo de CRM)
CREATE TABLE IF NOT EXISTS leads (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE,
    telefone VARCHAR(50),
    empresa VARCHAR(255),
    status VARCHAR(50) DEFAULT 'novo',
    fonte VARCHAR(100),
    dados_adicionais JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índices úteis
CREATE INDEX IF NOT EXISTS idx_workflow_data_created_at ON workflow_data(created_at);
CREATE INDEX IF NOT EXISTS idx_workflow_logs_workflow_id ON workflow_logs(workflow_id);
CREATE INDEX IF NOT EXISTS idx_leads_email ON leads(email);
CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);

-- Comentários
COMMENT ON TABLE workflow_data IS 'Tabela para testes de workflows de automação';
COMMENT ON TABLE workflow_logs IS 'Logs de eventos de workflows';
COMMENT ON TABLE leads IS 'Tabela de leads para exemplo de CRM';
