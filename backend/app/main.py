"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CacheMiddleware, RateLimitMiddleware, TimingMiddleware
from app.core.config import get_settings
from app.core.deps import get_db, get_current_user, get_optional_user
from app.core.logging_config import configure_logging, get_logger
from app.db.database import init_db
from app.models.user import User

settings = get_settings()

# Create frontend directories before app starts
settings.static_dir.mkdir(parents=True, exist_ok=True)
settings.templates_dir.mkdir(parents=True, exist_ok=True)

# Configure logging
configure_logging(settings.log_level)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Application starting - environment: %s, version: 1.0.0", settings.environment)
    await init_db()
    yield
    # Shutdown
    logger.info("Application stopping")


app = FastAPI(
    title="Workflow Automation Platform",
    description="Plataforma de automação de workflows e integrações internas",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Timing middleware - adds X-Process-Time header
app.add_middleware(TimingMiddleware)

# Rate limiting middleware
app.add_middleware(RateLimitMiddleware, requests_per_minute=100)

# Cache middleware for GET requests
app.add_middleware(CacheMiddleware, ttl=300)

# Static files
app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "1.0.0"}


@app.get("/", response_class=HTMLResponse)
async def root_dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
):
    """Root endpoint - Dashboard with statistics or login page."""
    # If not authenticated, show login page
    if not user:
        return """<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Workflow Automation - Login</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-50 min-h-screen flex items-center justify-center">
    <div class="max-w-md w-full mx-4">
        <div class="bg-white shadow-lg rounded-lg p-8">
            <div class="text-center mb-8">
                <h1 class="text-3xl font-bold text-indigo-600 mb-2">Workflow Automation</h1>
                <p class="text-gray-600">Faça login para continuar</p>
            </div>
            
            <form id="login-form" class="space-y-6">
                <div>
                    <label class="block text-sm font-medium text-gray-700">Email</label>
                    <input type="email" id="email" required
                        class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 border p-2">
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700">Senha</label>
                    <input type="password" id="password" required
                        class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 border p-2">
                </div>
                <div id="error-message" class="hidden text-red-600 text-sm"></div>
                <button type="submit" class="w-full bg-indigo-600 text-white py-2 px-4 rounded-md hover:bg-indigo-700">
                    Entrar
                </button>
            </form>
            
            <div class="mt-6 p-4 bg-gray-50 rounded-md text-sm text-gray-600">
                <p class="font-medium mb-2">Credenciais de teste:</p>
                <p>admin@example.com / admin123</p>
                <p>editor@example.com / editor123</p>
            </div>
            
            <p class="mt-4 text-center text-sm text-gray-500">
                Ou acesse a <a href="/docs" class="text-indigo-600 hover:text-indigo-800">API Docs</a>
            </p>
        </div>
    </div>
    
    <script>
        document.getElementById('login-form').addEventListener('submit', async function(e) {
            e.preventDefault();
            const email = document.getElementById('email').value;
            const password = document.getElementById('password').value;
            const errorDiv = document.getElementById('error-message');
            
            try {
                const response = await fetch('/api/auth/login', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({email, password})
                });
                
                if (response.ok) {
                    window.location.reload();
                } else {
                    const error = await response.json();
                    errorDiv.textContent = error.detail || 'Erro ao fazer login';
                    errorDiv.classList.remove('hidden');
                }
            } catch (err) {
                errorDiv.textContent = 'Erro de conexão';
                errorDiv.classList.remove('hidden');
            }
        });
    </script>
</body>
</html>"""
    
    from app.models.workflow import Workflow
    from app.models.execution import WorkflowExecution
    from sqlalchemy import func
    
    # Get statistics
    # Total workflows
    workflows_result = await db.execute(
        select(func.count(Workflow.id))
        .where(
            Workflow.organization_id == user.organization_id,
            Workflow.deleted_at.is_(None)
        )
    )
    total_workflows = workflows_result.scalar() or 0
    
    # Active workflows
    active_result = await db.execute(
        select(func.count(Workflow.id))
        .where(
            Workflow.organization_id == user.organization_id,
            Workflow.status == "active",
            Workflow.deleted_at.is_(None)
        )
    )
    active_workflows = active_result.scalar() or 0
    
    # Total executions
    executions_result = await db.execute(
        select(func.count(WorkflowExecution.id))
        .join(Workflow)
        .where(Workflow.organization_id == user.organization_id)
    )
    total_executions = executions_result.scalar() or 0
    
    # Executions today
    today = datetime.utcnow().date()
    today_start = datetime.combine(today, datetime.min.time())
    today_result = await db.execute(
        select(func.count(WorkflowExecution.id))
        .join(Workflow)
        .where(
            Workflow.organization_id == user.organization_id,
            WorkflowExecution.created_at >= today_start
        )
    )
    executions_today = today_result.scalar() or 0
    
    # Executions by status
    status_result = await db.execute(
        select(WorkflowExecution.status, func.count(WorkflowExecution.id))
        .join(Workflow)
        .where(Workflow.organization_id == user.organization_id)
        .group_by(WorkflowExecution.status)
    )
    status_counts = dict(status_result.all())
    
    completed = status_counts.get("completed", 0)
    failed = status_counts.get("failed", 0)
    running = status_counts.get("running", 0) + status_counts.get("pending", 0)
    
    # Recent executions (last 5)
    recent_result = await db.execute(
        select(WorkflowExecution, Workflow)
        .join(Workflow)
        .where(Workflow.organization_id == user.organization_id)
        .order_by(WorkflowExecution.created_at.desc())
        .limit(5)
    )
    recent_executions = recent_result.all()
    
    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard - Workflow Automation</title>
    <script src="https://cdn.tailwindcss.com"></script>
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
                </div>
                <div class="flex items-center">
                    <span class="text-sm text-gray-500 mr-4">{user.email}</span>
                    <a href="/docs" class="text-sm text-indigo-600 hover:text-indigo-800">API Docs</a>
                </div>
            </div>
        </div>
    </nav>

    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <!-- Header -->
        <div class="mb-8">
            <h1 class="text-3xl font-bold text-gray-900">Dashboard</h1>
            <p class="text-gray-500 mt-1">Visão geral do sistema</p>
        </div>

        <!-- Stats Cards -->
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            <!-- Workflows -->
            <a href="/workflows" class="bg-white p-6 rounded-lg shadow hover:shadow-lg transition-shadow">
                <div class="flex items-center justify-between">
                    <div>
                        <p class="text-sm font-medium text-gray-600">Total Workflows</p>
                        <p class="text-3xl font-bold text-indigo-600">{total_workflows}</p>
                    </div>
                    <div class="text-3xl">🔄</div>
                </div>
                <p class="text-sm text-green-600 mt-2">{active_workflows} ativos</p>
            </a>

            <!-- Total Executions -->
            <a href="/executions" class="bg-white p-6 rounded-lg shadow hover:shadow-lg transition-shadow">
                <div class="flex items-center justify-between">
                    <div>
                        <p class="text-sm font-medium text-gray-600">Total Execuções</p>
                        <p class="text-3xl font-bold text-blue-600">{total_executions}</p>
                    </div>
                    <div class="text-3xl">⚡</div>
                </div>
                <p class="text-sm text-gray-500 mt-2">{executions_today} hoje</p>
            </a>

            <!-- Completed -->
            <div class="bg-white p-6 rounded-lg shadow">
                <div class="flex items-center justify-between">
                    <div>
                        <p class="text-sm font-medium text-gray-600">Completadas</p>
                        <p class="text-3xl font-bold text-green-600">{completed}</p>
                    </div>
                    <div class="text-3xl">✅</div>
                </div>
                <p class="text-sm text-green-600 mt-2">Sucesso</p>
            </div>

            <!-- Failed -->
            <div class="bg-white p-6 rounded-lg shadow">
                <div class="flex items-center justify-between">
                    <div>
                        <p class="text-sm font-medium text-gray-600">Falhas</p>
                        <p class="text-3xl font-bold text-red-600">{failed}</p>
                    </div>
                    <div class="text-3xl">❌</div>
                </div>
                <p class="text-sm text-gray-500 mt-2">Requer atenção</p>
            </div>
        </div>

        <!-- Charts Section -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
            <!-- Executions Timeline Chart -->
            <div class="bg-white p-6 rounded-lg shadow">
                <div class="flex justify-between items-center mb-4">
                    <h2 class="text-lg font-medium text-gray-900">Tendência de Execuções (7 dias)</h2>
                    <div class="text-sm text-gray-500" id="chart-summary"></div>
                </div>
                <div class="relative h-64">
                    <canvas id="executionsChart"></canvas>
                </div>
                <div class="mt-4 flex justify-center gap-4 text-sm">
                    <span class="flex items-center"><span class="w-3 h-3 bg-green-500 rounded-full mr-2"></span>Completadas</span>
                    <span class="flex items-center"><span class="w-3 h-3 bg-red-500 rounded-full mr-2"></span>Falhas</span>
                    <span class="flex items-center"><span class="w-3 h-3 bg-blue-500 rounded-full mr-2"></span>Em andamento</span>
                </div>
            </div>

            <!-- Success Rate Chart -->
            <div class="bg-white p-6 rounded-lg shadow">
                <h2 class="text-lg font-medium text-gray-900 mb-4">Taxa de Sucesso</h2>
                <div class="relative h-48 flex items-center justify-center">
                    <canvas id="successRateChart"></canvas>
                    <div class="absolute text-center">
                        <div class="text-3xl font-bold text-gray-800" id="success-rate-value">--%</div>
                        <div class="text-sm text-gray-500">Taxa de sucesso</div>
                    </div>
                </div>
                <div class="mt-4 grid grid-cols-3 gap-4 text-center">
                    <div>
                        <div class="text-2xl font-bold text-green-600" id="stat-completed">--</div>
                        <div class="text-xs text-gray-500">Completadas</div>
                    </div>
                    <div>
                        <div class="text-2xl font-bold text-red-600" id="stat-failed">--</div>
                        <div class="text-xs text-gray-500">Falhas</div>
                    </div>
                    <div>
                        <div class="text-2xl font-bold text-blue-600" id="stat-total">--</div>
                        <div class="text-xs text-gray-500">Total</div>
                    </div>
                </div>
            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
        <script>
            // Load chart data from API
            async function loadChartData() {{
                try {{
                    const response = await fetch('/api/executions/stats/timeseries?days=7');
                    const data = await response.json();
                    
                    // Update summary stats
                    document.getElementById('success-rate-value').textContent = data.summary.success_rate + '%';
                    document.getElementById('stat-completed').textContent = data.summary.completed;
                    document.getElementById('stat-failed').textContent = data.summary.failed;
                    document.getElementById('stat-total').textContent = data.summary.total;
                    document.getElementById('chart-summary').textContent = 
                        'Total: ' + data.summary.total + ' | Sucesso: ' + data.summary.success_rate + '%';
                    
                    // Executions Timeline Chart
                    const ctx1 = document.getElementById('executionsChart').getContext('2d');
                    new Chart(ctx1, {{
                        type: 'bar',
                        data: {{
                            labels: data.labels,
                            datasets: [
                                {{
                                    label: 'Completadas',
                                    data: data.datasets.completed,
                                    backgroundColor: 'rgba(34, 197, 94, 0.8)',
                                    borderColor: 'rgb(34, 197, 94)',
                                    borderWidth: 1,
                                }},
                                {{
                                    label: 'Falhas',
                                    data: data.datasets.failed,
                                    backgroundColor: 'rgba(239, 68, 68, 0.8)',
                                    borderColor: 'rgb(239, 68, 68)',
                                    borderWidth: 1,
                                }},
                                {{
                                    label: 'Em andamento',
                                    data: data.datasets.running,
                                    backgroundColor: 'rgba(59, 130, 246, 0.8)',
                                    borderColor: 'rgb(59, 130, 246)',
                                    borderWidth: 1,
                                }}
                            ]
                        }},
                        options: {{
                            responsive: true,
                            maintainAspectRatio: false,
                            scales: {{
                                x: {{
                                    stacked: true,
                                    grid: {{ display: false }}
                                }},
                                y: {{
                                    stacked: true,
                                    beginAtZero: true,
                                    ticks: {{ stepSize: 1 }}
                                }}
                            }},
                            plugins: {{
                                legend: {{ display: false }},
                                tooltip: {{
                                    mode: 'index',
                                    intersect: false,
                                    callbacks: {{
                                        title: function(context) {{
                                            return 'Data: ' + context[0].label;
                                        }}
                                    }}
                                }}
                            }}
                        }}
                    }});
                    
                    // Success Rate Doughnut Chart
                    const ctx2 = document.getElementById('successRateChart').getContext('2d');
                    new Chart(ctx2, {{
                        type: 'doughnut',
                        data: {{
                            labels: ['Completadas', 'Falhas', 'Em andamento'],
                            datasets: [{{
                                data: [
                                    data.summary.completed,
                                    data.summary.failed,
                                    data.summary.running
                                ],
                                backgroundColor: [
                                    'rgba(34, 197, 94, 0.8)',
                                    'rgba(239, 68, 68, 0.8)',
                                    'rgba(59, 130, 246, 0.8)'
                                ],
                                borderWidth: 0,
                                cutout: '70%'
                            }}]
                        }},
                        options: {{
                            responsive: true,
                            maintainAspectRatio: false,
                            plugins: {{
                                legend: {{ display: false }},
                                tooltip: {{
                                    callbacks: {{
                                        label: function(context) {{
                                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                            const percentage = ((context.raw / total) * 100).toFixed(1);
                                            return context.label + ': ' + context.raw + ' (' + percentage + '%)';
                                        }}
                                    }}
                                }}
                            }}
                        }}
                    }});
                    
                }} catch (error) {{
                    console.error('Error loading chart data:', error);
                    document.getElementById('chart-summary').textContent = 'Erro ao carregar dados';
                }}
            }}
            
            // Load charts when page loads
            document.addEventListener('DOMContentLoaded', loadChartData);
        </script>

        <!-- Recent Executions -->
        <div class="bg-white shadow rounded-lg overflow-hidden">
            <div class="px-6 py-4 border-b border-gray-200">
                <h2 class="text-lg font-medium text-gray-900">Execuções Recentes</h2>
            </div>
            <table class="min-w-full divide-y divide-gray-200">
                <thead class="bg-gray-50">
                    <tr>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Workflow</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Data</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Ações</th>
                    </tr>
                </thead>
                <tbody class="bg-white divide-y divide-gray-200">
"""
    
    if not recent_executions:
        html += """
                    <tr>
                        <td colspan="4" class="px-6 py-8 text-center text-gray-500">
                            Nenhuma execução encontrada.
                        </td>
                    </tr>
"""
    else:
        for execution, workflow in recent_executions:
            status_val = execution.status.value if hasattr(execution.status, 'value') else execution.status
            status_color = {
                "completed": "bg-green-100 text-green-800",
                "failed": "bg-red-100 text-red-800",
                "running": "bg-blue-100 text-blue-800",
                "pending": "bg-yellow-100 text-yellow-800",
            }.get(status_val, "bg-gray-100 text-gray-800")
            
            html += f"""
                    <tr>
                        <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                            {workflow.name}
                        </td>
                        <td class="px-6 py-4 whitespace-nowrap">
                            <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full {status_color}">
                                {status_val.upper()}
                            </span>
                        </td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                            {execution.created_at.strftime("%d/%m/%Y %H:%M")}
                        </td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm font-medium">
                            <a href="/executions/{execution.id}" class="text-indigo-600 hover:text-indigo-900">Ver</a>
                        </td>
                    </tr>
"""
    
    html += f"""
                </tbody>
            </table>
            <div class="px-6 py-4 border-t border-gray-200">
                <a href="/executions" class="text-indigo-600 hover:text-indigo-800 text-sm font-medium">
                    Ver todas as execuções →
                </a>
            </div>
        </div>

        <!-- Quick Actions -->
        <div class="mt-8 grid grid-cols-1 md:grid-cols-3 gap-6">
            <a href="/workflows/new" class="bg-indigo-600 text-white p-6 rounded-lg shadow hover:bg-indigo-700 transition-colors text-center">
                <div class="text-3xl mb-2">➕</div>
                <h3 class="font-semibold">Criar Workflow</h3>
                <p class="text-sm text-indigo-200">Novo workflow</p>
            </a>
            
            <a href="/workflows" class="bg-white p-6 rounded-lg shadow hover:shadow-lg transition-shadow text-center">
                <div class="text-3xl mb-2">🔄</div>
                <h3 class="font-semibold text-gray-900">Meus Workflows</h3>
                <p class="text-sm text-gray-500">Gerenciar workflows</p>
            </a>
            
            <a href="/docs" class="bg-white p-6 rounded-lg shadow hover:shadow-lg transition-shadow text-center">
                <div class="text-3xl mb-2">📚</div>
                <h3 class="font-semibold text-gray-900">API Docs</h3>
                <p class="text-sm text-gray-500">Documentação</p>
            </a>
        </div>
    </main>
</body>
</html>
"""
    return html


# Import and include routers
from app.api import auth, workflows, executions, webhooks, dashboard, notifications, audit, rbac, versions, api_keys, export, bulk, analytics, templates, webhook_configs, integrations
from app.api.dependencies import CacheMiddleware, RateLimitMiddleware, TimingMiddleware
from app.web import workflows_router, executions_router, audit as audit_web, dashboard_router

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(workflows.router, prefix="/api/workflows", tags=["workflows"])
app.include_router(executions.router, prefix="/api/executions", tags=["executions"])
app.include_router(notifications.router, prefix="/api", tags=["notifications"])
app.include_router(audit.router, prefix="/api", tags=["audit"])
app.include_router(rbac.router, prefix="/api", tags=["rbac"])
app.include_router(versions.router, tags=["versions"])
app.include_router(api_keys.router, prefix="/api", tags=["api-keys"])
app.include_router(export.router, prefix="/api", tags=["export"])
app.include_router(bulk.router, prefix="/api", tags=["bulk-operations"])
app.include_router(analytics.router, prefix="/api", tags=["analytics"])
app.include_router(templates.router, prefix="/api", tags=["templates"])
app.include_router(webhook_configs.router, prefix="/api", tags=["webhook-configs"])
app.include_router(integrations.router, prefix="/api", tags=["integrations"])
app.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
app.include_router(dashboard.router, prefix="/api", tags=["dashboard"])

# Web routes
app.include_router(dashboard_router)
app.include_router(workflows_router)
app.include_router(executions_router)
app.include_router(audit_web.router)
