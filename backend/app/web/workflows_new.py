"""Enhanced web routes for workflow management."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_optional_user
from app.db.database import get_db
from app.models.user import User
from app.models.workflow import Workflow, WorkflowStatus, TriggerType
from app.web.components import get_base_layout, get_empty_state, get_status_badge, get_trigger_icon

router = APIRouter(prefix="/workflows", tags=["web-workflows"])


@router.get("", response_class=HTMLResponse)
async def list_workflows(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
    search: Optional[str] = Query(None, description="Search by name or description"),
    status: Optional[str] = Query(None, description="Filter by status"),
    trigger_type: Optional[str] = Query(None, description="Filter by trigger type"),
    page: int = Query(1, ge=1),
    per_page: int = Query(12, ge=1, le=50),
):
    """List workflows with modern card layout and pagination."""
    if not user:
        return await _get_login_page()

    # Build query
    query = select(Workflow).where(
        Workflow.organization_id == user.organization_id,
        Workflow.deleted_at.is_(None),
    )

    # Apply filters
    if search:
        search_term = f"%{search}%"
        query = query.where(
            (Workflow.name.ilike(search_term)) |
            (Workflow.description.ilike(search_term))
        )

    if status:
        query = query.where(Workflow.status == status)

    if trigger_type:
        query = query.where(Workflow.trigger_type == trigger_type)

    # Get total count
    count_query = select(func.count(Workflow.id)).where(
        Workflow.organization_id == user.organization_id,
        Workflow.deleted_at.is_(None),
    )
    if status:
        count_query = count_query.where(Workflow.status == status)
    if trigger_type:
        count_query = count_query.where(Workflow.trigger_type == trigger_type)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    total_pages = (total + per_page - 1) // per_page

    # Get workflows with pagination
    offset = (page - 1) * per_page
    result = await db.execute(
        query.order_by(Workflow.created_at.desc()).offset(offset).limit(per_page)
    )
    workflows = result.scalars().all()

    # Get filter counts
    status_counts = await _get_status_counts(db, user.organization_id)
    trigger_counts = await _get_trigger_counts(db, user.organization_id)

    # Build content
    content = await _build_workflows_content(
        workflows, search, status, trigger_type,
        page, total_pages, total, per_page,
        status_counts, trigger_counts
    )

    return HTMLResponse(content=get_base_layout("Workflows", content, user, "workflows"))


async def _get_login_page() -> HTMLResponse:
    """Return login page HTML."""
    html = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - Workflow Automation</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
</head>
<body class="bg-gradient-to-br from-indigo-900 to-purple-800 min-h-screen flex items-center justify-center">
    <div class="bg-white shadow-2xl rounded-2xl p-8 max-w-md w-full mx-4">
        <div class="text-center mb-8">
            <div class="inline-flex items-center justify-center w-16 h-16 bg-indigo-100 rounded-full mb-4">
                <i class="fas fa-cogs text-2xl text-indigo-600"></i>
            </div>
            <h1 class="text-2xl font-bold text-gray-900">Workflow Automation</h1>
            <p class="text-gray-500 mt-2">Plataforma de automação de workflows</p>
        </div>

        <form id="login-form" class="space-y-5">
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Email</label>
                <div class="relative">
                    <span class="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400">
                        <i class="fas fa-envelope"></i>
                    </span>
                    <input type="email" id="email" required value="admin@example.com"
                        class="pl-10 block w-full rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 border p-3">
                </div>
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Senha</label>
                <div class="relative">
                    <span class="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400">
                        <i class="fas fa-lock"></i>
                    </span>
                    <input type="password" id="password" required value="admin123"
                        class="pl-10 block w-full rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 border p-3">
                </div>
            </div>
            <button type="submit" class="w-full bg-indigo-600 text-white py-3 px-4 rounded-lg hover:bg-indigo-700 transition flex items-center justify-center">
                <i class="fas fa-sign-in-alt mr-2"></i> Entrar
            </button>
        </form>

        <div id="error" class="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm hidden"></div>

        <div class="mt-6 text-center">
            <p class="text-xs text-gray-400">Credenciais de teste: admin@example.com / admin123</p>
        </div>
    </div>

    <script>
        document.getElementById('login-form').addEventListener('submit', async function(e) {
            e.preventDefault();
            const email = document.getElementById('email').value;
            const password = document.getElementById('password').value;
            const errorDiv = document.getElementById('error');

            try {
                const response = await fetch('/api/auth/login', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({email, password})
                });

                if (response.ok) {
                    window.location.href = '/workflows';
                } else {
                    const error = await response.text();
                    errorDiv.textContent = 'Credenciais inválidas';
                    errorDiv.classList.remove('hidden');
                }
            } catch (err) {
                errorDiv.textContent = 'Erro de conexão com o servidor';
                errorDiv.classList.remove('hidden');
            }
        });
    </script>
</body>
</html>"""
    return HTMLResponse(content=html)


async def _get_status_counts(db: AsyncSession, org_id: str) -> dict:
    """Get workflow counts by status."""
    counts = {}
    for status in ["active", "inactive", "draft", "archived"]:
        result = await db.execute(
            select(func.count(Workflow.id)).where(
                Workflow.organization_id == org_id,
                Workflow.deleted_at.is_(None),
                Workflow.status == status,
            )
        )
        counts[status] = result.scalar() or 0
    return counts


async def _get_trigger_counts(db: AsyncSession, org_id: str) -> dict:
    """Get workflow counts by trigger type."""
    counts = {}
    for trigger in ["webhook", "scheduled", "manual", "file_upload"]:
        result = await db.execute(
            select(func.count(Workflow.id)).where(
                Workflow.organization_id == org_id,
                Workflow.deleted_at.is_(None),
                Workflow.trigger_type == trigger,
            )
        )
        counts[trigger] = result.scalar() or 0
    return counts


async def _build_workflows_content(
    workflows, search, status, trigger_type,
    page, total_pages, total, per_page,
    status_counts, trigger_counts
) -> str:
    """Build the main workflows content HTML."""

    # Build filter pills
    filter_pills = ""
    if search:
        filter_pills += f'<span class="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-indigo-100 text-indigo-800 mr-2"><i class="fas fa-search mr-1"></i>Busca: {search} <a href="?{build_query_string(status=status, trigger_type=trigger_type)}" class="ml-2 text-indigo-600 hover:text-indigo-800"><i class="fas fa-times"></i></a></span>'
    if status:
        filter_pills += f'<span class="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-green-100 text-green-800 mr-2"><i class="fas fa-filter mr-1"></i>Status: {status} <a href="?{build_query_string(search=search, trigger_type=trigger_type)}" class="ml-2 text-green-600 hover:text-green-800"><i class="fas fa-times"></i></a></span>'
    if trigger_type:
        filter_pills += f'<span class="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-blue-100 text-blue-800 mr-2"><i class="fas fa-bolt mr-1"></i>Trigger: {trigger_type} <a href="?{build_query_string(search=search, status=status)}" class="ml-2 text-blue-600 hover:text-blue-800"><i class="fas fa-times"></i></a></span>'

    # Build workflow cards
    if not workflows:
        workflows_grid = get_empty_state(
            "fa-folder-open",
            "Nenhum workflow encontrado",
            "Crie seu primeiro workflow para começar a automatizar processos.",
            '<button onclick="openModal(\'create-modal\')" class="inline-flex items-center px-4 py-2 border border-transparent rounded-lg shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700"><i class="fas fa-plus mr-2"></i>Novo Workflow</button>'
        )
    else:
        workflows_grid = '<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">'
        for workflow in workflows:
            status_val = workflow.status.value if hasattr(workflow.status, 'value') else workflow.status
            status_badge = get_status_badge(status_val)
            trigger_icon = get_trigger_icon(workflow.trigger_type or "")

            workflows_grid += f"""
            <div class="workflow-card bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
                <div class="p-5">
                    <div class="flex items-start justify-between mb-3">
                        <div class="flex items-center space-x-2">
                            <span class="text-gray-400"><i class="fas {trigger_icon}"></i></span>
                            <span class="text-xs text-gray-500 uppercase font-semibold tracking-wider">{workflow.trigger_type or 'manual'}</span>
                        </div>
                        {status_badge}
                    </div>
                    <h3 class="text-lg font-semibold text-gray-900 mb-2">{workflow.name}</h3>
                    <p class="text-sm text-gray-500 mb-4 line-clamp-2">{workflow.description or 'Sem descrição'}</p>
                    <div class="flex items-center justify-between text-xs text-gray-400">
                        <span><i class="fas fa-code-branch mr-1"></i>v{workflow.version}</span>
                        <span><i class="fas fa-calendar mr-1"></i>{workflow.created_at.strftime('%d/%m/%Y')}</span>
                    </div>
                </div>
                <div class="px-5 py-3 bg-gray-50 border-t border-gray-200 flex items-center justify-between">
                    <div class="flex space-x-2">
                        <a href="/workflows/{workflow.id}" class="text-indigo-600 hover:text-indigo-800 text-sm font-medium">
                            <i class="fas fa-edit mr-1"></i>Editar
                        </a>
                        <a href="/executions?workflow_id={workflow.id}" class="text-gray-500 hover:text-gray-700 text-sm">
                            <i class="fas fa-history mr-1"></i>Logs
                        </a>
                    </div>
                    <button onclick="executeWorkflow('{workflow.id}')" class="text-green-600 hover:text-green-800 text-sm font-medium" title="Executar workflow">
                        <i class="fas fa-play"></i>
                    </button>
                </div>
            </div>
            """
        workflows_grid += '</div>'

    # Build pagination
    pagination = ""
    if total_pages > 1:
        pagination = '<div class="flex items-center justify-between mt-8">'
        pagination += '<div class="text-sm text-gray-500">'
        pagination += f'Mostrando <span class="font-medium">{(page-1)*per_page + 1}</span> a <span class="font-medium">{min(page*per_page, total)}</span> de <span class="font-medium">{total}</span> workflows'
        pagination += '</div>'
        pagination += '<div class="flex items-center space-x-2">'

        # Previous button
        if page > 1:
            pagination += f'<a href="?{build_query_string(search=search, status=status, trigger_type=trigger_type, page=page-1)}" class="px-3 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50"><i class="fas fa-chevron-left"></i></a>'

        # Page numbers
        start_page = max(1, page - 2)
        end_page = min(total_pages, page + 2)
        for p in range(start_page, end_page + 1):
            if p == page:
                pagination += f'<span class="px-3 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium">{p}</span>'
            else:
                pagination += f'<a href="?{build_query_string(search=search, status=status, trigger_type=trigger_type, page=p)}" class="px-3 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50">{p}</a>'

        # Next button
        if page < total_pages:
            pagination += f'<a href="?{build_query_string(search=search, status=status, trigger_type=trigger_type, page=page+1)}" class="px-3 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50"><i class="fas fa-chevron-right"></i></a>'

        pagination += '</div></div>'

    return f"""
    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <!-- Header -->
        <div class="flex items-center justify-between mb-8">
            <div>
                <h1 class="text-3xl font-bold text-gray-900">Workflows</h1>
                <p class="text-gray-500 mt-1">Gerencie e monitore seus workflows de automação</p>
            </div>
            <button onclick="openModal('create-modal')" class="inline-flex items-center px-4 py-2 border border-transparent rounded-lg shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500">
                <i class="fas fa-plus mr-2"></i>Novo Workflow
            </button>
        </div>

        <!-- Filter Bar -->
        <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-4 mb-6">
            <form method="get" class="flex flex-wrap gap-3 items-end">
                <div class="flex-1 min-w-64">
                    <label class="block text-sm font-medium text-gray-700 mb-1">
                        <i class="fas fa-search mr-1"></i>Buscar
                    </label>
                    <input type="text" name="search" value="{search or ''}" placeholder="Nome ou descrição..."
                        class="w-full rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 border p-2.5 text-sm">
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Status</label>
                    <select name="status" class="rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 border p-2.5 text-sm">
                        <option value="">Todos ({sum(status_counts.values())})</option>
                        <option value="active" {'selected' if status == 'active' else ''}>Ativos ({status_counts['active']})</option>
                        <option value="inactive" {'selected' if status == 'inactive' else ''}>Inativos ({status_counts['inactive']})</option>
                        <option value="draft" {'selected' if status == 'draft' else ''}>Rascunhos ({status_counts['draft']})</option>
                        <option value="archived" {'selected' if status == 'archived' else ''}>Arquivados ({status_counts['archived']})</option>
                    </select>
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Trigger</label>
                    <select name="trigger_type" class="rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 border p-2.5 text-sm">
                        <option value="">Todos</option>
                        <option value="webhook" {'selected' if trigger_type == 'webhook' else ''}>Webhook ({trigger_counts['webhook']})</option>
                        <option value="scheduled" {'selected' if trigger_type == 'scheduled' else ''}>Agendado ({trigger_counts['scheduled']})</option>
                        <option value="manual" {'selected' if trigger_type == 'manual' else ''}>Manual ({trigger_counts['manual']})</option>
                        <option value="file_upload" {'selected' if trigger_type == 'file_upload' else ''}>Upload ({trigger_counts['file_upload']})</option>
                    </select>
                </div>
                <div class="flex gap-2">
                    <button type="submit" class="bg-indigo-600 text-white px-4 py-2.5 rounded-lg hover:bg-indigo-700 text-sm font-medium">
                        <i class="fas fa-filter mr-1"></i>Filtrar
                    </button>
                    <a href="/workflows" class="bg-gray-100 text-gray-700 px-4 py-2.5 rounded-lg hover:bg-gray-200 text-sm font-medium">
                        <i class="fas fa-times mr-1"></i>Limpar
                    </a>
                </div>
            </form>

            <!-- Active Filters -->
            {f'<div class="mt-3 flex items-center flex-wrap">{filter_pills}</div>' if filter_pills else ''}
        </div>

        <!-- Workflows Grid -->
        {workflows_grid}

        <!-- Pagination -->
        {pagination}
    </main>

    <!-- Create Workflow Modal -->
    <div id="create-modal" class="modal-overlay">
        <div class="modal-content">
            <div class="p-6 border-b border-gray-200">
                <div class="flex items-center justify-between">
                    <h2 class="text-xl font-semibold text-gray-900">
                        <i class="fas fa-plus-circle text-indigo-600 mr-2"></i>Criar Novo Workflow
                    </h2>
                    <button onclick="closeModal('create-modal')" class="text-gray-400 hover:text-gray-600">
                        <i class="fas fa-times text-xl"></i>
                    </button>
                </div>
            </div>
            <form id="create-workflow-form" class="p-6 space-y-5">
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Nome *</label>
                    <input type="text" name="name" required
                        class="block w-full rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 border p-3">
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Slug (identificador único) *</label>
                    <input type="text" name="slug" required
                        class="block w-full rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 border p-3">
                    <p class="text-xs text-gray-500 mt-1">Usado na URL, ex: meu-workflow</p>
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Descrição</label>
                    <textarea name="description" rows="3"
                        class="block w-full rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 border p-3"></textarea>
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Tipo de Trigger *</label>
                    <select name="trigger_type" required
                        class="block w-full rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 border p-3">
                        <option value="manual">Manual - Executado manualmente</option>
                        <option value="webhook">Webhook - Disparado por HTTP</option>
                        <option value="scheduled">Agendado - Executa periodicamente</option>
                        <option value="file_upload">Upload - Disparado por arquivo</option>
                    </select>
                </div>
                <div class="flex items-center justify-end space-x-3 pt-4 border-t border-gray-200">
                    <button type="button" onclick="closeModal('create-modal')" class="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50">
                        Cancelar
                    </button>
                    <button type="submit" class="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700">
                        <i class="fas fa-check mr-2"></i>Criar Workflow
                    </button>
                </div>
            </form>
        </div>
    </div>

    <script>
        // Execute workflow
        async function executeWorkflow(workflowId) {{
            try {{
                const response = await fetch(`/api/workflows/${{workflowId}}/execute`, {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}}
                }});

                if (response.ok) {{
                    showToast('Workflow executado com sucesso!', 'success');
                }} else {{
                    const error = await response.text();
                    showToast('Erro ao executar workflow: ' + error, 'error');
                }}
            }} catch (err) {{
                showToast('Erro de conexão', 'error');
            }}
        }}

        // Create workflow form
        document.getElementById('create-workflow-form').addEventListener('submit', async function(e) {{
            e.preventDefault();
            const formData = new FormData(e.target);
            const data = Object.fromEntries(formData);

            try {{
                const response = await fetch('/api/workflows/', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify(data)
                }});

                if (response.ok) {{
                    showToast('Workflow criado com sucesso!', 'success');
                    closeModal('create-modal');
                    setTimeout(() => window.location.reload(), 1000);
                }} else {{
                    const error = await response.text();
                    showToast('Erro: ' + error, 'error');
                }}
            }} catch (err) {{
                showToast('Erro de conexão', 'error');
            }}
        }});
    </script>
    """


def build_query_string(**kwargs) -> str:
    """Build query string from kwargs."""
    params = []
    for key, value in kwargs.items():
        if value:
            params.append(f"{key}={value}")
    return "&".join(params)
