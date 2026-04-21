"""Audit log web routes."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.core.deps import get_optional_user
from app.db.database import get_db
from app.models.audit_log import AuditLog, AuditAction
from app.models.user import User

router = APIRouter(prefix="/audit", tags=["audit-web"])


@router.get("/logs", response_class=HTMLResponse)
async def audit_logs_page(
    request: Request,
    action: str | None = Query(None),
    resource_type: str | None = Query(None),
    user_email: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    """Audit logs list page."""
    if not user:
        return RedirectResponse(url="/auth/login?redirect=/audit/logs")
    
    # Build query
    query = (
        select(AuditLog)
        .where(AuditLog.organization_id == user.organization_id)
        .order_by(desc(AuditLog.created_at))
    )
    
    if action:
        query = query.where(AuditLog.action == action)
    if resource_type:
        query = query.where(AuditLog.resource_type == resource_type)
    if user_email:
        query = query.where(AuditLog.user_email.ilike(f"%{user_email}%"))
    
    result = await db.execute(query.limit(100))
    logs = result.scalars().all()
    
    # Build HTML
    action_types = [(a.value, format_action(a.value)) for a in AuditAction]
    resource_types = [("workflow", "Workflow"), ("execution", "Execução"), 
                      ("user", "Usuário"), ("organization", "Organização")]
    
    html = generate_audit_logs_html(logs, action_types, resource_types, action, resource_type, user_email)
    return HTMLResponse(content=html)


@router.get("/logs/{log_id}", response_class=HTMLResponse)
async def audit_log_detail(
    request: Request,
    log_id: str,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    """Audit log detail page."""
    if not user:
        return RedirectResponse(url=f"/auth/login?redirect=/audit/logs/{log_id}")
    
    try:
        log_uuid = UUID(log_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid log ID")
    
    result = await db.execute(
        select(AuditLog)
        .where(
            AuditLog.id == log_uuid,
            AuditLog.organization_id == user.organization_id,
        )
    )
    log = result.scalar_one_or_none()
    
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")
    
    html = generate_audit_detail_html(log)
    return HTMLResponse(content=html)


def format_action(action: str | None) -> str:
    """Format action name for display."""
    if not action:
        return "Ação Desconhecida"
    
    translations = {
        "login": "Login",
        "logout": "Logout",
        "password_change": "Alteração de Senha",
        "token_refresh": "Refresh Token",
        "user_create": "Criação de Usuário",
        "user_update": "Atualização de Usuário",
        "user_delete": "Exclusão de Usuário",
        "org_create": "Criação de Organização",
        "org_update": "Atualização de Organização",
        "org_delete": "Exclusão de Organização",
        "workflow_create": "Criação de Workflow",
        "workflow_update": "Atualização de Workflow",
        "workflow_delete": "Exclusão de Workflow",
        "workflow_activate": "Ativação de Workflow",
        "workflow_deactivate": "Desativação de Workflow",
        "workflow_duplicate": "Duplicação de Workflow",
        "execution_start": "Início de Execução",
        "execution_complete": "Execução Completa",
        "execution_fail": "Falha de Execução",
        "execution_retry": "Retry de Execução",
        "execution_cancel": "Cancelamento de Execução",
        "file_upload": "Upload de Arquivo",
        "file_delete": "Exclusão de Arquivo",
        "webhook_trigger": "Webhook Trigger",
    }
    return translations.get(action, action.replace("_", " ").title())


def get_action_class(action: str | None) -> str:
    """Get CSS class for action badge."""
    if not action:
        return "secondary"
    
    if "create" in action:
        return "success"
    elif "update" in action or "activate" in action:
        return "primary"
    elif "delete" in action or "deactivate" in action or "fail" in action:
        return "danger"
    elif "login" in action or "logout" in action:
        return "info"
    elif "execution" in action:
        return "warning"
    return "secondary"


def generate_audit_logs_html(logs, action_types, resource_types, current_action, current_resource_type, current_user_email):
    """Generate HTML for audit logs list page."""
    
    # Build filter form
    action_options = '<option value="">Todas as Ações</option>' + ''.join([
        f'<option value="{value}" {"selected" if current_action == value else ""}>{label}</option>'
        for value, label in action_types
    ])
    
    resource_options = '<option value="">Todos os Tipos</option>' + ''.join([
        f'<option value="{value}" {"selected" if current_resource_type == value else ""}>{label}</option>'
        for value, label in resource_types
    ])
    
    # Build table rows
    rows = ""
    for log in logs:
        action_class = get_action_class(log.action.value if log.action else None)
        action_label = format_action(log.action.value if log.action else None)
        created_at = log.created_at.strftime("%d/%m/%Y %H:%M") if log.created_at else "-"
        user_email = log.user_email or "Sistema"
        resource_type = log.resource_type or "-"
        description = log.description or "-"
        
        rows += f"""
        <tr>
            <td>{created_at}</td>
            <td><span class="badge bg-{action_class}">{action_label}</span></td>
            <td>{user_email}</td>
            <td>{resource_type}</td>
            <td>{description}</td>
            <td>
                <a href="/audit/logs/{log.id}" class="btn btn-sm btn-outline-primary">Ver</a>
            </td>
        </tr>
        """
    
    if not rows:
        rows = '<tr><td colspan="6" class="text-center">Nenhum log encontrado</td></tr>'
    
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Logs de Auditoria - Workflow Automation</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.css">
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container">
            <a class="navbar-brand" href="/workflows">
                <i class="bi bi-diagram-3"></i> Workflow Automation
            </a>
            <div class="navbar-nav ms-auto">
                <a class="nav-link" href="/workflows">Workflows</a>
                <a class="nav-link" href="/executions">Execuções</a>
                <a class="nav-link active" href="/audit/logs">Audit Logs</a>
            </div>
        </div>
    </nav>

    <div class="container mt-4">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <h1><i class="bi bi-journal-text"></i> Logs de Auditoria</h1>
            <a href="/api/audit-logs" class="btn btn-outline-secondary" target="_blank">
                <i class="bi bi-download"></i> API
            </a>
        </div>

        <!-- Filters -->
        <div class="card mb-4">
            <div class="card-body">
                <form method="get" class="row g-3">
                    <div class="col-md-3">
                        <label class="form-label">Ação</label>
                        <select name="action" class="form-select">{action_options}</select>
                    </div>
                    <div class="col-md-3">
                        <label class="form-label">Tipo de Recurso</label>
                        <select name="resource_type" class="form-select">{resource_options}</select>
                    </div>
                    <div class="col-md-3">
                        <label class="form-label">Usuário (Email)</label>
                        <input type="text" name="user_email" class="form-control" value="{current_user_email or ''}" placeholder="Buscar por email...">
                    </div>
                    <div class="col-md-3 d-flex align-items-end">
                        <button type="submit" class="btn btn-primary w-100">
                            <i class="bi bi-search"></i> Filtrar
                        </button>
                    </div>
                </form>
            </div>
        </div>

        <!-- Logs Table -->
        <div class="card">
            <div class="card-body">
                <div class="table-responsive">
                    <table class="table table-hover">
                        <thead class="table-dark">
                            <tr>
                                <th>Data/Hora</th>
                                <th>Ação</th>
                                <th>Usuário</th>
                                <th>Recurso</th>
                                <th>Descrição</th>
                                <th>Ações</th>
                            </tr>
                        </thead>
                        <tbody>
                            {rows}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <div class="mt-3 text-muted">
            <small>Mostrando últimos 100 registros. Use a API para mais resultados.</small>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>"""


def generate_audit_detail_html(log):
    """Generate HTML for audit log detail page."""
    
    action_class = get_action_class(log.action.value if log.action else None)
    action_label = format_action(log.action.value if log.action else None)
    created_at = log.created_at.strftime("%d/%m/%Y %H:%M:%S") if log.created_at else "-"
    user_email = log.user_email or "Sistema"
    resource_type = log.resource_type or "-"
    resource_id = log.resource_id or "-"
    description = log.description or "-"
    ip_address = log.ip_address or "-"
    user_agent = log.user_agent or "-"
    
    # Format details as JSON
    import json
    details_html = '<p class="text-muted">Nenhum detalhe disponível</p>'
    if log.details:
        details_json = json.dumps(log.details, indent=2, ensure_ascii=False)
        details_html = f'<pre class="bg-light p-3 rounded"><code>{details_json}</code></pre>'
    
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Detalhes do Log - Workflow Automation</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.css">
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container">
            <a class="navbar-brand" href="/workflows">
                <i class="bi bi-diagram-3"></i> Workflow Automation
            </a>
            <div class="navbar-nav ms-auto">
                <a class="nav-link" href="/workflows">Workflows</a>
                <a class="nav-link" href="/executions">Execuções</a>
                <a class="nav-link active" href="/audit/logs">Audit Logs</a>
            </div>
        </div>
    </nav>

    <div class="container mt-4">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <h1><i class="bi bi-journal-text"></i> Detalhes do Log</h1>
            <a href="/audit/logs" class="btn btn-outline-secondary">
                <i class="bi bi-arrow-left"></i> Voltar
            </a>
        </div>

        <div class="row">
            <div class="col-md-8">
                <div class="card mb-4">
                    <div class="card-header">
                        <h5 class="mb-0">Informações Gerais</h5>
                    </div>
                    <div class="card-body">
                        <table class="table table-borderless">
                            <tr>
                                <td width="150"><strong>ID:</strong></td>
                                <td><code>{log.id}</code></td>
                            </tr>
                            <tr>
                                <td><strong>Data/Hora:</strong></td>
                                <td>{created_at}</td>
                            </tr>
                            <tr>
                                <td><strong>Ação:</strong></td>
                                <td><span class="badge bg-{action_class}">{action_label}</span></td>
                            </tr>
                            <tr>
                                <td><strong>Usuário:</strong></td>
                                <td>{user_email}</td>
                            </tr>
                            <tr>
                                <td><strong>Recurso:</strong></td>
                                <td>{resource_type} <code>{resource_id}</code></td>
                            </tr>
                            <tr>
                                <td><strong>Descrição:</strong></td>
                                <td>{description}</td>
                            </tr>
                        </table>
                    </div>
                </div>

                <div class="card">
                    <div class="card-header">
                        <h5 class="mb-0">Detalhes</h5>
                    </div>
                    <div class="card-body">
                        {details_html}
                    </div>
                </div>
            </div>

            <div class="col-md-4">
                <div class="card">
                    <div class="card-header">
                        <h5 class="mb-0">Informações Técnicas</h5>
                    </div>
                    <div class="card-body">
                        <table class="table table-sm table-borderless">
                            <tr>
                                <td><strong>IP:</strong></td>
                                <td><code>{ip_address}</code></td>
                            </tr>
                            <tr>
                                <td><strong>User Agent:</strong></td>
                                <td><small class="text-muted">{user_agent}</small></td>
                            </tr>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>"""
