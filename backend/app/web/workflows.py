"""Web routes for workflow management."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_optional_user
from app.db.database import get_db
from app.models.user import User
from app.models.workflow import (
    ActionType,
    StepType,
    TriggerType,
    Workflow,
    WorkflowStatus,
    WorkflowStep,
)
from app.services.workflow_service import WorkflowService

router = APIRouter(prefix="/workflows", tags=["web-workflows"])

TRIGGER_TYPES = [
    ("webhook", "Webhook - Disparado por requisição HTTP"),
    ("scheduled", "Agendado - Executa em horários definidos"),
    ("manual", "Manual - Disparado manualmente"),
    ("file_upload", "Upload de Arquivo - Disparado ao enviar arquivo"),
]

ACTION_TYPES = [
    ("http_request", "HTTP Request - Faz requisição para API externa"),
    ("send_email", "Enviar Email - Envia email"),
    ("write_database", "Escrever no Banco - Salva dados no banco"),
    ("transform_payload", "Transformar Dados - Modifica payload"),
    ("export_csv", "Exportar CSV - Gera arquivo CSV"),
    ("export_pdf", "Exportar PDF - Gera arquivo PDF"),
    ("notify", "Notificação - Envia notificação"),
]


@router.get("", response_class=HTMLResponse)
async def list_workflows(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
    search: Optional[str] = Query(None, description="Search by name or description"),
    status: Optional[str] = Query(None, description="Filter by status"),
    trigger_type: Optional[str] = Query(None, description="Filter by trigger type"),
):
    """List all workflows page with search and filters."""
    # Show login page if not authenticated
    if not user:
        return HTMLResponse(content="""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - Workflow Automation</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-50 min-h-screen flex items-center justify-center">
    <div class="bg-white shadow-lg rounded-lg p-8 max-w-md w-full">
        <h1 class="text-2xl font-bold text-indigo-600 mb-2 text-center">Workflow Automation</h1>
        <p class="text-gray-500 text-center mb-6">Faça login para acessar</p>
        
        <form id="login-form" class="space-y-4">
            <div>
                <label class="block text-sm font-medium text-gray-700">Email</label>
                <input type="email" id="email" required value="admin@example.com"
                    class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2">
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700">Senha</label>
                <input type="password" id="password" required value="admin123"
                    class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2">
            </div>
            <button type="submit" class="w-full bg-indigo-600 text-white py-2 px-4 rounded hover:bg-indigo-700">
                Entrar
            </button>
        </form>
        
        <div id="error" class="mt-4 text-red-600 text-sm hidden"></div>
        
        <div class="mt-4 text-center text-xs text-gray-500">
            <p>Credenciais de teste:</p>
            <p>admin@example.com / admin123</p>
        </div>
    </div>
    
    <script>
        document.getElementById('login-form').addEventListener('submit', async function(e) {
            e.preventDefault();
            const email = document.getElementById('email').value;
            const password = document.getElementById('password').value;
            
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
                    document.getElementById('error').textContent = 'Erro: ' + error;
                    document.getElementById('error').classList.remove('hidden');
                }
            } catch (err) {
                document.getElementById('error').textContent = 'Erro de conexão';
                document.getElementById('error').classList.remove('hidden');
            }
        });
    </script>
</body>
</html>""")
    
    # Build query with filters
    query = select(Workflow).where(
        Workflow.organization_id == user.organization_id,
        Workflow.deleted_at.is_(None),
    )
    
    # Apply search filter
    if search:
        search_term = f"%{search}%"
        query = query.where(
            (Workflow.name.ilike(search_term)) | 
            (Workflow.description.ilike(search_term))
        )
    
    # Apply status filter
    if status:
        query = query.where(Workflow.status == status)
    
    # Apply trigger type filter
    if trigger_type:
        query = query.where(Workflow.trigger_type == trigger_type)
    
    # Execute query
    result = await db.execute(query.order_by(Workflow.created_at.desc()))
    workflows = result.scalars().all()
    
    # Get counts for filters
    status_counts = {}
    for s in ["active", "inactive", "draft", "archived"]:
        count_result = await db.execute(
            select(func.count(Workflow.id)).where(
                Workflow.organization_id == user.organization_id,
                Workflow.deleted_at.is_(None),
                Workflow.status == s,
            )
        )
        status_counts[s] = count_result.scalar() or 0
    
    trigger_counts = {}
    for t in ["webhook", "scheduled", "manual", "file_upload"]:
        count_result = await db.execute(
            select(func.count(Workflow.id)).where(
                Workflow.organization_id == user.organization_id,
                Workflow.deleted_at.is_(None),
                Workflow.trigger_type == t,
            )
        )
        trigger_counts[t] = count_result.scalar() or 0

    html = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Workflows - Workflow Automation</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/htmx.org@1.9.12"></script>
</head>
<body class="bg-gray-50 min-h-screen">
    <nav class="bg-white shadow-sm border-b border-gray-200">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="flex justify-between h-16">
                <div class="flex items-center">
                    <a href="/" class="text-xl font-bold text-indigo-600">Workflow Automation</a>
                    <span class="ml-4 text-gray-400">|</span>
                    <span class="ml-4 text-gray-900 font-medium">Workflows</span>
                </div>
                <div class="flex items-center space-x-4">
                    <button onclick="testEmail()" class="bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700" title="Testar configuração de email">
                        📧 Testar Email
                    </button>
                    <button onclick="reloadSchedule()" class="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700" title="Recarregar workflows agendados">
                        🔄 Agendados
                    </button>
                    <a href="/workflows/new" class="bg-indigo-600 text-white px-4 py-2 rounded hover:bg-indigo-700">
                        + Novo Workflow
                    </a>
                </div>
            </div>
        </div>
    </nav>

    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div class="mb-6">
            <h1 class="text-2xl font-bold text-gray-900">Meus Workflows</h1>
            <p class="text-gray-500 mt-1">Busque e gerencie seus workflows e automações</p>
        </div>

        <!-- Search and Filter Bar -->
        <div class="bg-white shadow rounded-lg p-4 mb-6">
            <form method="get" class="flex flex-wrap gap-4 items-end">
                <!-- Search -->
                <div class="flex-1 min-w-64">
                    <label class="block text-sm font-medium text-gray-700 mb-1">Buscar</label>
                    <input type="text" name="search" value="{search or ''}" placeholder="Buscar por nome ou descrição..."
                        class="w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 border p-2 text-sm">
                </div>

                <!-- Status Filter -->
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Status</label>
                    <select name="status" class="rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 border p-2 text-sm">
                        <option value="">Todos ({sum(status_counts.values())})</option>
                        <option value="active" {'selected' if status == 'active' else ''}>🟢 Ativo ({status_counts['active']})</option>
                        <option value="inactive" {'selected' if status == 'inactive' else ''}>⚪ Inativo ({status_counts['inactive']})</option>
                        <option value="draft" {'selected' if status == 'draft' else ''}>🟡 Rascunho ({status_counts['draft']})</option>
                        <option value="archived" {'selected' if status == 'archived' else ''}>🔴 Arquivado ({status_counts['archived']})</option>
                    </select>
                </div>

                <!-- Trigger Type Filter -->
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Trigger</label>
                    <select name="trigger_type" class="rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 border p-2 text-sm">
                        <option value="">Todos</option>
                        <option value="webhook" {'selected' if trigger_type == 'webhook' else ''}>🔔 Webhook ({trigger_counts['webhook']})</option>
                        <option value="scheduled" {'selected' if trigger_type == 'scheduled' else ''}>⏰ Agendado ({trigger_counts['scheduled']})</option>
                        <option value="manual" {'selected' if trigger_type == 'manual' else ''}>👆 Manual ({trigger_counts['manual']})</option>
                        <option value="file_upload" {'selected' if trigger_type == 'file_upload' else ''}>📁 Upload ({trigger_counts['file_upload']})</option>
                    </select>
                </div>

                <!-- Buttons -->
                <div class="flex gap-2">
                    <button type="submit" class="bg-indigo-600 text-white px-4 py-2 rounded-md hover:bg-indigo-700 text-sm font-medium">
                        🔍 Buscar
                    </button>
                    <a href="/workflows" class="bg-gray-200 text-gray-700 px-4 py-2 rounded-md hover:bg-gray-300 text-sm font-medium">
                        Limpar
                    </a>
                </div>
            </form>
        </div>

        <!-- Results count -->
        <div class="mb-4 text-sm text-gray-600">
            {len(workflows)} workflow(s) encontrado(s)
            {f'<span class="text-gray-400">| Filtros: ' + 
                (f'busca="{search}" ' if search else '') +
                (f'status={status} ' if status else '') +
                (f'trigger={trigger_type}' if trigger_type else '') +
                '</span>' if search or status or trigger_type else ''}
        </div>

        <div class="bg-white shadow rounded-lg overflow-hidden">
            <table class="min-w-full divide-y divide-gray-200">
                <thead class="bg-gray-50">
                    <tr>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Nome</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Trigger</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Versão</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Criado</th>
                        <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Ações</th>
                    </tr>
                </thead>
                <tbody class="bg-white divide-y divide-gray-200">
"""

    if not workflows:
        html += """
                    <tr>
                        <td colspan="6" class="px-6 py-12 text-center text-gray-500">
                            Nenhum workflow encontrado.
                            <a href="/workflows/new" class="text-indigo-600 hover:text-indigo-800 ml-1">Criar primeiro workflow</a>
                        </td>
                    </tr>
"""
    else:
        for workflow in workflows:
            # Handle both string and enum status
            status_val = workflow.status.value if hasattr(workflow.status, 'value') else workflow.status
            status_color = {
                "active": "bg-green-100 text-green-800",
                "inactive": "bg-gray-100 text-gray-800",
                "draft": "bg-yellow-100 text-yellow-800",
                "archived": "bg-red-100 text-red-800",
            }.get(status_val, "bg-gray-100 text-gray-800")

            # Get trigger type display
            trigger_val = workflow.trigger_type or "manual"
            trigger_display = {
                "webhook": "🔔 Webhook",
                "scheduled": "⏰ Agendado", 
                "manual": "👆 Manual",
                "file_upload": "📁 Upload",
            }.get(trigger_val, trigger_val)
            
            html += f"""
                    <tr>
                        <td class="px-6 py-4 whitespace-nowrap">
                            <div class="text-sm font-medium text-gray-900">{workflow.name}</div>
                            <div class="text-sm text-gray-500">{workflow.slug}</div>
                        </td>
                        <td class="px-6 py-4 whitespace-nowrap">
                            <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full {status_color}">
                                {status_val.upper()}
                            </span>
                        </td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                            {trigger_display}
                        </td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                            v{workflow.version}
                        </td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                            {workflow.created_at.strftime("%d/%m/%Y")}
                        </td>
                        <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                            <a href="/workflows/{workflow.id}/edit" class="text-indigo-600 hover:text-indigo-900 mr-3">Editar</a>
                            <a href="/workflows/{workflow.id}/run" class="text-green-600 hover:text-green-900">Executar</a>
                        </td>
                    </tr>
"""

    html += """
                </tbody>
            </table>
        </div>
    </main>
    
    <script>
        async function reloadSchedule() {
            const btn = document.querySelector('button[onclick="reloadSchedule()"]');
            btn.disabled = true;
            btn.textContent = '⏳ Recarregando...';
            
            try {
                const response = await fetch('/api/workflows/reload-schedule', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });
                
                if (response.ok) {
                    const data = await response.json();
                    alert(`✅ ${data.message}`);
                } else {
                    const error = await response.json();
                    alert(`❌ Erro: ${error.detail || 'Erro desconhecido'}`);
                }
            } catch (err) {
                alert(`❌ Erro de conexão: ${err.message}`);
            } finally {
                btn.disabled = false;
                btn.textContent = '🔄 Agendados';
            }
        }
        
        async function testEmail() {
            const btn = document.querySelector('button[onclick="testEmail()"]');
            btn.disabled = true;
            btn.textContent = '⏳ Enviando...';
            
            try {
                const response = await fetch('/api/workflows/test-email', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    if (data.configured) {
                        alert(`✅ ${data.message}\n\nSMTP: ${data.smtp_config.host}:${data.smtp_config.port}\nDe: ${data.smtp_config.from}`);
                    } else {
                        alert(`⚠️ ${data.message}\n\nConfigure no docker-compose.yml:\nSMTP_HOST, SMTP_USER, SMTP_PASSWORD`);
                    }
                } else {
                    alert(`❌ Erro: ${data.detail || 'Erro desconhecido'}`);
                }
            } catch (err) {
                alert(`❌ Erro de conexão: ${err.message}`);
            } finally {
                btn.disabled = false;
                btn.textContent = '📧 Testar Email';
            }
        }
    </script>
</body>
</html>
"""
    return html


@router.get("/new", response_class=HTMLResponse)
async def new_workflow_page(
    request: Request,
    user: User = Depends(get_current_user),
):
    """Create new workflow page."""
    trigger_options = "".join([f'<option value="{v}">{l}</option>' for v, l in TRIGGER_TYPES])
    action_options = "".join([f'<option value="{v}">{l}</option>' for v, l in ACTION_TYPES])

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Novo Workflow - Workflow Automation</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/htmx.org@1.9.12"></script>
</head>
<body class="bg-gray-50 min-h-screen">
    <nav class="bg-white shadow-sm border-b border-gray-200">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="flex justify-between h-16">
                <div class="flex items-center">
                    <a href="/" class="text-xl font-bold text-indigo-600">Workflow Automation</a>
                    <span class="ml-4 text-gray-400">|</span>
                    <a href="/workflows" class="ml-4 text-gray-600 hover:text-gray-900">Workflows</a>
                    <a href="/executions" class="ml-4 text-gray-600 hover:text-gray-900">Execuções</a>
                    <span class="ml-2 text-gray-400">/</span>
                    <span class="ml-2 text-gray-900 font-medium">Novo</span>
                </div>
            </div>
        </div>
    </nav>

    <main class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div class="mb-6">
            <h1 class="text-2xl font-bold text-gray-900">Criar Novo Workflow</h1>
            <p class="text-gray-500 mt-1">Configure seu workflow com trigger e actions</p>
        </div>

        <form id="workflow-form" class="space-y-6">
            <!-- Workflow Info -->
            <div class="bg-white shadow rounded-lg p-6">
                <h2 class="text-lg font-medium text-gray-900 mb-4">Informações Básicas</h2>
                <div class="grid grid-cols-1 gap-6 sm:grid-cols-2">
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Nome</label>
                        <input type="text" name="name" required
                            class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
                            placeholder="Meu Workflow">
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Slug (identificador único)</label>
                        <input type="text" name="slug" required
                            class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
                            placeholder="meu-workflow">
                    </div>
                    <div class="sm:col-span-2">
                        <label class="block text-sm font-medium text-gray-700">Descrição</label>
                        <textarea name="description" rows="2"
                            class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
                            placeholder="Descreva o objetivo deste workflow..."></textarea>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Status</label>
                        <select name="status" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2">
                            <option value="draft">Rascunho</option>
                            <option value="active">Ativo</option>
                            <option value="inactive">Inativo</option>
                        </select>
                    </div>
                </div>
            </div>

            <!-- Trigger Step -->
            <div class="bg-white shadow rounded-lg p-6">
                <h2 class="text-lg font-medium text-gray-900 mb-4">Trigger (Disparador)</h2>
                <p class="text-sm text-gray-500 mb-4">Escolha como este workflow será iniciado</p>
                
                <div class="grid grid-cols-1 gap-6">
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Tipo de Trigger</label>
                        <select name="steps[0][trigger_type]" required
                            class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
                            onchange="updateTriggerConfig(this.value)">
                            <option value="">Selecione...</option>
                            {trigger_options}
                        </select>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Nome do Step</label>
                        <input type="text" name="steps[0][name]" required value="Trigger Principal"
                            class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2">
                    </div>
                    <div id="trigger-config" class="border rounded-md p-4 bg-gray-50">
                        <p class="text-sm text-gray-500">Selecione um tipo de trigger para ver as configurações</p>
                    </div>
                </div>
                
                <input type="hidden" name="steps[0][step_type]" value="trigger">
                <input type="hidden" name="steps[0][order]" value="0">
            </div>

            <!-- Action Steps -->
            <div class="bg-white shadow rounded-lg p-6">
                <div class="flex justify-between items-center mb-4">
                    <h2 class="text-lg font-medium text-gray-900">Actions (Ações)</h2>
                    <button type="button" onclick="addActionStep()" class="text-indigo-600 hover:text-indigo-800 text-sm font-medium">
                        + Adicionar Action
                    </button>
                </div>
                <p class="text-sm text-gray-500 mb-4">Ações que serão executadas quando o trigger for disparado</p>
                
                <div id="actions-container" class="space-y-4">
                    <!-- Actions will be added here -->
                </div>
            </div>

            <!-- Submit -->
            <div class="flex justify-end space-x-3">
                <a href="/workflows" class="bg-white py-2 px-4 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 hover:bg-gray-50">
                    Cancelar
                </a>
                <button type="submit" id="submit-btn" class="bg-indigo-600 py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white hover:bg-indigo-700">
                    Criar Workflow
                </button>
            </div>
        </form>
        <div id="error-message" class="hidden mt-4 p-4 bg-red-50 border border-red-200 rounded-md text-red-700"></div>
    </main>

    <script>
        let actionCount = 0;

        // Form submission handler
        document.getElementById('workflow-form').addEventListener('submit', async function(e) {{
            e.preventDefault();
            console.log('Form submit triggered');
            
            const btn = document.getElementById('submit-btn');
            const errorDiv = document.getElementById('error-message');
            
            // Show loading state
            btn.disabled = true;
            btn.innerHTML = 'Salvando...';
            errorDiv.classList.add('hidden');
            
            try {{
                // Collect form data
                const formData = new FormData(this);
                let slug = formData.get('slug');
                
                // Auto-generate slug from name if empty or add timestamp to ensure uniqueness
                if (!slug) {{
                    slug = formData.get('name').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
                }}
                // Always add timestamp to avoid "slug already exists" errors
                const timestamp = new Date().getTime().toString().slice(-4);
                slug = slug + '-' + timestamp;
                
                const data = {{
                    name: formData.get('name'),
                    slug: slug,
                    description: formData.get('description'),
                    status: formData.get('status'),
                    tags: [],
                    steps: []
                }};
                
                // Collect steps
                const steps = [];
                let stepIndex = 0;
                while (formData.has(`steps[${{stepIndex}}][step_type]`)) {{
                    const stepType = formData.get(`steps[${{stepIndex}}][step_type]`);
                    const step = {{
                        step_type: stepType,
                        order: parseInt(formData.get(`steps[${{stepIndex}}][order]`)),
                        name: formData.get(`steps[${{stepIndex}}][name]`),
                        description: formData.get(`steps[${{stepIndex}}][description]`) || null,
                        config: {{}},
                        is_active: true,
                        max_retries: 3,
                        retry_delay: 60
                    }};
                    
                    if (stepType === 'trigger') {{
                        step.trigger_type = formData.get(`steps[${{stepIndex}}][trigger_type]`);
                        step.action_type = null;
                    }} else {{
                        step.action_type = formData.get(`steps[${{stepIndex}}][action_type]`);
                        step.trigger_type = null;
                    }}
                    
                    // Collect config fields (simplified)
                    const configPrefix = `steps[${{stepIndex}}][config]`;
                    for (const [key, value] of formData.entries()) {{
                        if (key.startsWith(configPrefix)) {{
                            const configKey = key.replace(configPrefix, '').replace(/\[|\]/g, '');
                            if (configKey) {{
                                try {{
                                    // Try to parse as JSON if it looks like JSON
                                    if (value.trim().startsWith('{{') || value.trim().startsWith('[')) {{
                                        step.config[configKey] = JSON.parse(value);
                                    }} else {{
                                        step.config[configKey] = value;
                                    }}
                                }} catch (e) {{
                                    step.config[configKey] = value;
                                }}
                            }}
                        }}
                    }}
                    
                    steps.push(step);
                    stepIndex++;
                }}
                
                data.steps = steps;
                
                console.log('Sending data:', JSON.stringify(data, null, 2));
                
                // Send request
                const response = await fetch('/api/workflows', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json',
                    }},
                    body: JSON.stringify(data)
                }});
                
                if (response.ok) {{
                    const result = await response.json();
                    console.log('Success:', result);
                    window.location.href = '/workflows';
                }} else {{
                    const errorText = await response.text();
                    console.error('Error:', errorText);
                    
                    // Parse error message
                    let errorMsg = errorText;
                    try {{
                        const errorJson = JSON.parse(errorText);
                        errorMsg = errorJson.detail || errorText;
                    }} catch(e) {{}}
                    
                    // User-friendly messages
                    if (errorMsg.includes('slug already exists')) {{
                        errorMsg = 'Já existe um workflow com este identificador (slug). Por favor, use um nome diferente.';
                    }}
                    
                    errorDiv.textContent = errorMsg;
                    errorDiv.classList.remove('hidden');
                    btn.disabled = false;
                    btn.innerHTML = 'Criar Workflow';
                }}
            }} catch (err) {{
                console.error('Exception:', err);
                errorDiv.textContent = 'Erro de conexão: ' + err.message;
                errorDiv.classList.remove('hidden');
                btn.disabled = false;
                btn.innerHTML = 'Criar Workflow';
            }}
        }});
        const actionOptions = `{action_options}`;

        function updateTriggerConfig(triggerType) {{
            const configDiv = document.getElementById('trigger-config');
            let config = '';
            
            switch(triggerType) {{
                case 'webhook':
                    config = `
                        <div class="space-y-3">
                            <p class="text-sm font-medium text-gray-700">Webhook URL será gerado automaticamente</p>
                            <p class="text-xs text-gray-500">O endpoint será: /webhooks/trigger/&lt;workflow_id&gt;</p>
                        </div>`;
                    break;
                case 'scheduled':
                    config = `
                        <div class="space-y-3">
                            <label class="block text-sm font-medium text-gray-700">Expressão Cron</label>
                            <input type="text" name="steps[0][config][cron]" placeholder="0 9 * * * (todos os dias 9h)"
                                class="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2">
                            <p class="text-xs text-gray-500">Formato: minuto hora dia-mês mês dia-semana</p>
                        </div>`;
                    break;
                case 'manual':
                    config = '<p class="text-sm text-gray-600">Este workflow será executado apenas manualmente</p>';
                    break;
                case 'file_upload':
                    config = `
                        <div class="space-y-3">
                            <label class="block text-sm font-medium text-gray-700">Extensões permitidas</label>
                            <input type="text" name="steps[0][config][allowed_extensions]" value=".csv,.json,.xml"
                                class="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2">
                        </div>`;
                    break;
                default:
                    config = '<p class="text-sm text-gray-500">Selecione um tipo de trigger para ver as configurações</p>';
            }}
            
            configDiv.innerHTML = config;
        }}

        function addActionStep() {{
            actionCount++;
            const order = actionCount;
            const container = document.getElementById('actions-container');
            
            const actionDiv = document.createElement('div');
            actionDiv.className = 'border rounded-md p-4 bg-gray-50';
            actionDiv.id = `action-${{order}}`;
            actionDiv.innerHTML = `
                <div class="flex justify-between items-start mb-3">
                    <h3 class="font-medium text-gray-900">Action #${{order}}</h3>
                    <button type="button" onclick="removeActionStep(${{order}})" class="text-red-600 hover:text-red-800 text-sm">Remover</button>
                </div>
                <div class="grid grid-cols-1 gap-4">
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Tipo de Action</label>
                        <select name="steps[${{order}}][action_type]" required
                            class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
                            onchange="updateActionConfig(${{order}}, this.value)">
                            <option value="">Selecione...</option>
                            ${{actionOptions}}
                        </select>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Nome do Step</label>
                        <input type="text" name="steps[${{order}}][name]" required placeholder="Nome da ação"
                            class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2">
                    </div>
                    <div id="action-config-${{order}}" class="border rounded-md p-3 bg-white">
                        <p class="text-sm text-gray-500">Selecione um tipo de action para configurar</p>
                    </div>
                </div>
                <input type="hidden" name="steps[${{order}}][step_type]" value="action">
                <input type="hidden" name="steps[${{order}}][order]" value="${{order}}">
            `;
            
            container.appendChild(actionDiv);
        }}

        function removeActionStep(order) {{
            const actionDiv = document.getElementById(`action-${{order}}`);
            if (actionDiv) {{
                actionDiv.remove();
            }}
        }}

        function updateActionConfig(order, actionType) {{
            const configDiv = document.getElementById(`action-config-${{order}}`);
            let config = '';
            
            switch(actionType) {{
                case 'http_request':
                    config = `
                        <div class="space-y-3">
                            <div>
                                <label class="block text-sm font-medium text-gray-700">Método HTTP</label>
                                <select name="steps[${{order}}][config][method]" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2">
                                    <option value="GET">GET</option>
                                    <option value="POST">POST</option>
                                    <option value="PUT">PUT</option>
                                    <option value="PATCH">PATCH</option>
                                    <option value="DELETE">DELETE</option>
                                </select>
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-700">URL</label>
                                <input type="text" name="steps[${{order}}][config][url]" placeholder="https://api.exemplo.com/endpoint"
                                    class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2">
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-700">Headers (JSON)</label>
                                <textarea name="steps[${{order}}][config][headers]" rows="2" placeholder='{{"Authorization": "Bearer token"}}'
                                    class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2">{{}}</textarea>
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-700">Body (JSON ou template)</label>
                                <textarea name="steps[${{order}}][config][body]" rows="3" placeholder='{{"key": "{{{{value}}}}"}}'
                                    class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"></textarea>
                            </div>
                        </div>`;
                    break;
                case 'send_email':
                    config = `
                        <div class="space-y-3">
                            <div>
                                <label class="block text-sm font-medium text-gray-700">Para (email)</label>
                                <input type="email" name="steps[${{order}}][config][to]" placeholder="email@exemplo.com"
                                    class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2">
                                <p class="text-xs text-gray-500 mt-1">Aceita templates: {{{{email}}}}</p>
                            </div>
                            <div class="grid grid-cols-2 gap-4">
                                <div>
                                    <label class="block text-sm font-medium text-gray-700">CC (opcional)</label>
                                    <input type="text" name="steps[${{order}}][config][cc]" placeholder="cc@exemplo.com"
                                        class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2">
                                </div>
                                <div>
                                    <label class="block text-sm font-medium text-gray-700">BCC (opcional)</label>
                                    <input type="text" name="steps[${{order}}][config][bcc]" placeholder="bcc@exemplo.com"
                                        class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2">
                                </div>
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-700">Assunto</label>
                                <input type="text" name="steps[${{order}}][config][subject]" placeholder="Assunto do email"
                                    class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2">
                            </div>
                            <div>
                                <label class="flex items-center space-x-2">
                                    <input type="checkbox" name="steps[${{order}}][config][is_html]" value="true"
                                        class="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500">
                                    <span class="text-sm font-medium text-gray-700">Enviar como HTML</span>
                                </label>
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-700">Corpo (suporta templates)</label>
                                <textarea name="steps[${{order}}][config][body]" rows="4" placeholder="Olá {{{{nome}}}}, seu pedido {{{{pedido_id}}}} foi processado..."
                                    class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2 font-mono text-sm"></textarea>
                                <p class="text-xs text-gray-500 mt-1">Use {{{{campo}}}} para valores do payload. SMTP deve estar configurado.</p>
                            </div>
                        </div>`;
                    break;
                case 'transform_payload':
                    config = `
                        <div class="space-y-3">
                            <p class="text-sm text-gray-600 mb-2">Adicione transformações:</p>
                            <div class="grid grid-cols-3 gap-2">
                                <input type="text" name="steps[${{order}}][config][transformations][0][operation]" value="set" class="border rounded p-2 text-sm" placeholder="Operação">
                                <input type="text" name="steps[${{order}}][config][transformations][0][target_field]" class="border rounded p-2 text-sm" placeholder="Campo destino">
                                <input type="text" name="steps[${{order}}][config][transformations][0][value]" class="border rounded p-2 text-sm" placeholder="Valor">
                            </div>
                            <p class="text-xs text-gray-500">Operações: copy, set, delete, rename</p>
                        </div>`;
                    break;
                case 'write_database':
                    config = `
                        <div class="space-y-3">
                            <div>
                                <label class="block text-sm font-medium text-gray-700">Nome da Tabela</label>
                                <input type="text" name="steps[${{order}}][config][table]" placeholder="nome_da_tabela"
                                    class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2">
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-700">Operação</label>
                                <select name="steps[${{order}}][config][operation]" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2">
                                    <option value="insert">INSERT (Inserir)</option>
                                    <option value="upsert">UPSERT (Inserir ou Atualizar)</option>
                                </select>
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-700">Mapeamento de Campos (JSON)</label>
                                <textarea name="steps[${{order}}][config][field_mapping]" rows="4" placeholder='{{{{"nome": "{{{{nome}}}}", "email": "{{{{email}}}}", "created_at": "{{{{now}}}}"}}}}'
                                    class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2 font-mono">{{{{"nome": "{{{{nome}}}}", "email": "{{{{email}}}}", "data": "{{{{now}}}}"}}}}</textarea>
                                <p class="text-xs text-gray-500 mt-1">Use {{{{campo}}}} para valores do payload de entrada. Use {{{{now}}}} para data/hora atual.</p>
                            </div>
                        </div>`;
                    break;
                case 'notify':
                    config = `
                        <div class="space-y-3">
                            <div>
                                <label class="block text-sm font-medium text-gray-700">Nível</label>
                                <select name="steps[${{order}}][config][level]" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2">
                                    <option value="info">Info</option>
                                    <option value="success">Success</option>
                                    <option value="warning">Warning</option>
                                    <option value="error">Error</option>
                                </select>
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-700">Mensagem</label>
                                <textarea name="steps[${{order}}][config][message]" rows="2" placeholder="Mensagem de notificação"
                                    class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"></textarea>
                            </div>
                        </div>`;
                    break;
                default:
                    config = '<p class="text-sm text-gray-500">Selecione um tipo de action para configurar</p>';
            }}
            
            configDiv.innerHTML = config;
        }}

        // Add first action by default
        addActionStep();
    </script>
</body>
</html>
"""


@router.get("/{workflow_id}/edit", response_class=HTMLResponse)
async def edit_workflow_page(
    workflow_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Edit workflow page."""
    result = await db.execute(
        select(Workflow).where(
            Workflow.id == workflow_id,
            Workflow.organization_id == user.organization_id,
            Workflow.deleted_at.is_(None),
        )
    )
    workflow = result.scalar_one_or_none()

    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Load steps
    result = await db.execute(
        select(WorkflowStep).where(
            WorkflowStep.workflow_id == workflow_id,
        ).order_by(WorkflowStep.order)
    )
    steps = result.scalars().all()

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Editar {workflow.name} - Workflow Automation</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/htmx.org@1.9.12"></script>
</head>
<body class="bg-gray-50 min-h-screen">
    <nav class="bg-white shadow-sm border-b border-gray-200">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="flex justify-between h-16">
                <div class="flex items-center">
                    <a href="/" class="text-xl font-bold text-indigo-600">Workflow Automation</a>
                    <span class="ml-4 text-gray-400">|</span>
                    <a href="/workflows" class="ml-4 text-gray-600 hover:text-gray-900">Workflows</a>
                    <a href="/executions" class="ml-4 text-gray-600 hover:text-gray-900">Execuções</a>
                    <span class="ml-2 text-gray-400">/</span>
                    <span class="ml-2 text-gray-900 font-medium">{workflow.name}</span>
                </div>
            </div>
        </div>
    </nav>

    <main class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div class="mb-6">
            <h1 class="text-2xl font-bold text-gray-900">Editar Workflow</h1>
            <p class="text-gray-500 mt-1">ID: {workflow.id} | Versão: v{workflow.version}</p>
        </div>

        <div class="bg-white shadow rounded-lg p-6">
            <h2 class="text-lg font-medium text-gray-900 mb-4">Steps do Workflow</h2>
            <div class="space-y-4">
"""

    for step in steps:
        step_type_val = step.step_type.value if hasattr(step.step_type, 'value') else step.step_type
        trigger_type_val = step.trigger_type.value if hasattr(step.trigger_type, 'value') else step.trigger_type if step.trigger_type else None
        action_type_val = step.action_type.value if hasattr(step.action_type, 'value') else step.action_type if step.action_type else None
        
        step_type_label = "🚀 Trigger" if step_type_val == "trigger" else "⚡ Action"
        trigger_or_action = trigger_type_val or action_type_val or "-"

        html += f"""
                <div class="border rounded-lg p-4 {{('bg-indigo-50' if step_type_val == 'trigger' else 'bg-gray-50')}}">
                    <div class="flex items-center justify-between">
                        <div>
                            <span class="text-sm font-medium text-gray-500">{step_type_label}</span>
                            <h3 class="font-medium text-gray-900">{step.name}</h3>
                            <p class="text-sm text-gray-600">{trigger_or_action}</p>
                        </div>
                        <span class="text-xs text-gray-400">Order: {step.order}</span>
                    </div>
                    <div class="mt-2 text-sm text-gray-500">
                        Config: <pre class="inline bg-white px-2 py-1 rounded">{step.config}</pre>
                    </div>
                </div>
"""

    # Check if workflow has webhook trigger
    webhook_url = None
    for step in steps:
        if hasattr(step.step_type, 'value') and step.step_type.value == 'trigger':
            trigger_type_val = step.trigger_type.value if hasattr(step.trigger_type, 'value') else step.trigger_type
            if trigger_type_val == 'webhook':
                webhook_url = f"/webhooks/trigger/{workflow.id}"
                break
    
    html += f"""
            </div>
        </div>
"""
    
    # Add webhook test section if applicable
    if webhook_url:
        html += f"""
        <div class="mt-6 bg-white shadow rounded-lg p-6">
            <h2 class="text-lg font-medium text-gray-900 mb-4">🌐 Testar Webhook</h2>
            <div class="bg-gray-50 p-4 rounded-md mb-4">
                <p class="text-sm text-gray-600 mb-2">URL do Webhook:</p>
                <code class="block bg-gray-800 text-green-400 p-3 rounded text-sm font-mono break-all">
                    POST http://localhost:8000{webhook_url}
                </code>
            </div>
            
            <div class="space-y-4">
                <div>
                    <label class="block text-sm font-medium text-gray-700">Payload JSON para teste</label>
                    <textarea id="webhook-payload" rows="4" 
                        class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2 font-mono"
                        placeholder='{{"event": "test", "data": "valor"}}'>
{{"event": "webhook_test", "timestamp": "{__import__('datetime').datetime.now().isoformat()}", "source": "manual_test"}}</textarea>
                </div>
                
                <button onclick="testWebhook()" class="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700">
                    📤 Enviar Teste de Webhook
                </button>
                
                <div id="webhook-result" class="hidden mt-4 p-4 rounded-md"></div>
            </div>
            
            <script>
                async function testWebhook() {{
                    const payloadText = document.getElementById('webhook-payload').value;
                    const resultDiv = document.getElementById('webhook-result');
                    
                    let payload = {{}};
                    if (payloadText.trim()) {{
                        try {{
                            payload = JSON.parse(payloadText);
                        }} catch (err) {{
                            resultDiv.innerHTML = '<p class="text-red-600">❌ JSON inválido: ' + err.message + '</p>';
                            resultDiv.className = 'mt-4 p-4 bg-red-50 border border-red-200 rounded-md';
                            resultDiv.classList.remove('hidden');
                            return;
                        }}
                    }}
                    
                    resultDiv.innerHTML = '<p class="text-blue-600">⏳ Enviando...</p>';
                    resultDiv.className = 'mt-4 p-4 bg-blue-50 border border-blue-200 rounded-md';
                    resultDiv.classList.remove('hidden');
                    
                    try {{
                        const response = await fetch('{webhook_url}', {{
                            method: 'POST',
                            headers: {{
                                'Content-Type': 'application/json',
                            }},
                            body: JSON.stringify(payload)
                        }});
                        
                        const result = await response.json();
                        
                        if (response.ok) {{
                            resultDiv.innerHTML = `
                                <p class="text-green-600 font-medium">✅ Webhook disparado com sucesso!</p>
                                <p class="text-sm text-gray-600 mt-2">Execution ID: ${{result.execution_id}}</p>
                                <p class="text-sm text-gray-600">Correlation ID: ${{result.correlation_id}}</p>
                                <p class="text-sm text-gray-600">Status: ${{result.status}}</p>
                            `;
                            resultDiv.className = 'mt-4 p-4 bg-green-50 border border-green-200 rounded-md';
                        }} else {{
                            resultDiv.innerHTML = `<p class="text-red-600">❌ Erro: ${{result.detail || 'Erro desconhecido'}}</p>`;
                            resultDiv.className = 'mt-4 p-4 bg-red-50 border border-red-200 rounded-md';
                        }}
                    }} catch (err) {{
                        resultDiv.innerHTML = `<p class="text-red-600">❌ Erro de conexão: ${{err.message}}</p>`;
                        resultDiv.className = 'mt-4 p-4 bg-red-50 border border-red-200 rounded-md';
                    }}
                }}
            </script>
        </div>
"""
    
    html += f"""
        <div class="mt-6 flex justify-between">
            <a href="/workflows" class="text-gray-600 hover:text-gray-900">← Voltar</a>
            <a href="/workflows/{workflow.id}/run" class="bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700">
                ▶ Executar Workflow
            </a>
        </div>
    </main>
</body>
</html>
"""
    return html


@router.get("/{workflow_id}/run", response_class=HTMLResponse)
async def run_workflow_page(
    workflow_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Run workflow page."""
    result = await db.execute(
        select(Workflow).where(
            Workflow.id == workflow_id,
            Workflow.organization_id == user.organization_id,
            Workflow.deleted_at.is_(None),
        )
    )
    workflow = result.scalar_one_or_none()

    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Executar {workflow.name} - Workflow Automation</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/htmx.org@1.9.12"></script>
</head>
<body class="bg-gray-50 min-h-screen">
    <nav class="bg-white shadow-sm border-b border-gray-200">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="flex justify-between h-16">
                <div class="flex items-center">
                    <a href="/" class="text-xl font-bold text-indigo-600">Workflow Automation</a>
                    <span class="ml-4 text-gray-400">|</span>
                    <a href="/workflows" class="ml-4 text-gray-600 hover:text-gray-900">Workflows</a>
                    <a href="/executions" class="ml-4 text-gray-600 hover:text-gray-900">Execuções</a>
                    <span class="ml-2 text-gray-400">/</span>
                    <span class="ml-2 text-gray-900 font-medium">Executar</span>
                </div>
            </div>
        </div>
    </nav>

    <main class="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div class="mb-6">
            <h1 class="text-2xl font-bold text-gray-900">Executar Workflow</h1>
            <p class="text-gray-500 mt-1">{workflow.name} (v{workflow.version})</p>
        </div>

        <div class="bg-white shadow rounded-lg p-6">
            <form id="execute-form">
                
                <div class="mb-4">
                    <label class="block text-sm font-medium text-gray-700">Payload JSON (opcional)</label>
                    <textarea id="payload" name="payload" rows="6" 
                        class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2 font-mono"
                        placeholder='{{"key": "value", "data": "..."}}'>{{}}</textarea>
                    <p class="mt-1 text-xs text-gray-500">Dados que serão passados para o workflow</p>
                </div>

                <div class="flex justify-end space-x-3">
                    <a href="/workflows/{workflow_id}/edit" class="bg-white py-2 px-4 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 hover:bg-gray-50">
                        Cancelar
                    </a>
                    <button type="submit" id="execute-btn" class="bg-green-600 py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white hover:bg-green-700 flex items-center">
                        <span class="mr-2">▶</span> Executar Agora
                    </button>
                </div>
            </form>

            <div id="result" class="mt-6 hidden">
                <!-- Result will appear here -->
            </div>
        </div>

        <div class="mt-6">
            <a href="/workflows/{workflow_id}/edit" class="text-indigo-600 hover:text-indigo-800">← Voltar ao workflow</a>
        </div>
    </main>

    <script>
        document.getElementById('execute-form').addEventListener('submit', async function(e) {{
            e.preventDefault();
            
            const btn = document.getElementById('execute-btn');
            const resultDiv = document.getElementById('result');
            const payloadText = document.getElementById('payload').value;
            
            // Show loading
            btn.disabled = true;
            btn.innerHTML = '<span class="mr-2">⏳</span> Executando...';
            resultDiv.classList.add('hidden');
            
            try {{
                // Parse payload
                let payload = {{}};
                if (payloadText.trim()) {{
                    try {{
                        payload = JSON.parse(payloadText);
                    }} catch (err) {{
                        resultDiv.innerHTML = `
                            <div class="bg-red-50 border border-red-200 rounded-md p-4">
                                <h3 class="text-red-800 font-medium mb-2">✗ JSON inválido</h3>
                                <p class="text-sm text-red-700">Verifique o formato do payload: ${{err.message}}</p>
                            </div>
                        `;
                        resultDiv.classList.remove('hidden');
                        btn.disabled = false;
                        btn.innerHTML = '<span class="mr-2">▶</span> Executar Agora';
                        return;
                    }}
                }}
                
                console.log('Executing workflow with payload:', payload);
                
                // Build URL - use window.location to get current workflow ID from URL
                const currentPath = window.location.pathname;
                const workflowIdFromPath = currentPath.split('/')[2]; // /workflows/{id}/run
                const apiUrl = '/api/executions/trigger/' + workflowIdFromPath;
                console.log('Calling API URL:', apiUrl);
                
                // Call API (correct endpoint for manual trigger)
                const response = await fetch(apiUrl, {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json',
                    }},
                    body: JSON.stringify(payload)
                }});
                
                const result = await response.json();
                
                if (response.ok) {{
                    resultDiv.innerHTML = `
                        <div class="bg-green-50 border border-green-200 rounded-md p-4">
                            <h3 class="text-green-800 font-medium mb-2">✓ Workflow iniciado com sucesso!</h3>
                            <p class="text-sm text-green-700">Execution ID: ${{result.execution_id}}</p>
                            <p class="text-sm text-green-700">Status: ${{result.status}}</p>
                            <p class="text-sm text-green-700 mt-2">Correlation ID: ${{result.correlation_id || '-'}}</p>
                            <a href="/workflows" class="mt-3 inline-block text-indigo-600 hover:text-indigo-800 text-sm">
                                ← Voltar à lista de workflows
                            </a>
                        </div>
                    `;
                }} else {{
                    resultDiv.innerHTML = `
                        <div class="bg-red-50 border border-red-200 rounded-md p-4">
                            <h3 class="text-red-800 font-medium mb-2">✗ Erro ao executar</h3>
                            <p class="text-sm text-red-700">${{result.detail || 'Erro desconhecido'}}</p>
                        </div>
                    `;
                }}
            }} catch (err) {{
                console.error('Error:', err);
                resultDiv.innerHTML = `
                    <div class="bg-red-50 border border-red-200 rounded-md p-4">
                        <h3 class="text-red-800 font-medium mb-2">✗ Erro de conexão</h3>
                        <p class="text-sm text-red-700">${{err.message}}</p>
                    </div>
                `;
            }}
            
            resultDiv.classList.remove('hidden');
            btn.disabled = false;
            btn.innerHTML = '<span class="mr-2">▶</span> Executar Agora';
        }});
    </script>
</body>
</html>
"""
