"""Dashboard web routes with Chart.js visualizations."""

from typing import Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_optional_user
from app.db.database import get_db
from app.models.user import User
from app.models.workflow import Workflow, WorkflowStatus
from app.models.execution import WorkflowExecution, ExecutionStatus
from app.models.audit_log import AuditLog

router = APIRouter(prefix="/dashboard", tags=["web-dashboard"])


@router.get("", response_class=HTMLResponse)
async def dashboard_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
    days: int = Query(7, ge=1, le=30),
):
    """Dashboard page with Chart.js visualizations."""
    # Show login page if not authenticated
    if not user:
        return HTMLResponse(content=_get_login_html(), status_code=200)
    
    # Get metrics for the dashboard
    metrics = await _get_dashboard_metrics(db, user.organization_id, days)
    
    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard - Workflow Automation</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
</head>
<body class="bg-gray-100 min-h-screen">
    <!-- Navigation -->
    <nav class="bg-indigo-600 text-white shadow-lg">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="flex justify-between h-16">
                <div class="flex items-center space-x-4">
                    <i class="fas fa-robot text-2xl"></i>
                    <span class="font-bold text-xl">Workflow Automation</span>
                </div>
                <div class="flex items-center space-x-6">
                    <a href="/dashboard" class="text-white hover:text-indigo-200 font-medium border-b-2 border-white pb-1">
                        <i class="fas fa-chart-line mr-2"></i>Dashboard
                    </a>
                    <a href="/workflows" class="text-indigo-200 hover:text-white font-medium">
                        <i class="fas fa-project-diagram mr-2"></i>Workflows
                    </a>
                    <a href="/workflows/executions" class="text-indigo-200 hover:text-white font-medium">
                        <i class="fas fa-play-circle mr-2"></i>Execuções
                    </a>
                    <a href="/audit" class="text-indigo-200 hover:text-white font-medium">
                        <i class="fas fa-shield-alt mr-2"></i>Auditoria
                    </a>
                    <div class="relative group">
                        <button class="flex items-center space-x-2 hover:text-indigo-200">
                            <i class="fas fa-user-circle text-xl"></i>
                            <span>{user.email}</span>
                        </button>
                    </div>
                </div>
            </div>
        </div>
    </nav>

    <!-- Main Content -->
    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <!-- Header -->
        <div class="flex justify-between items-center mb-8">
            <div>
                <h1 class="text-3xl font-bold text-gray-900">
                    <i class="fas fa-chart-line text-indigo-600 mr-3"></i>Dashboard
                </h1>
                <p class="text-gray-600 mt-1">Visão geral do sistema e métricas</p>
            </div>
            <div class="flex space-x-2">
                <a href="?days=7" class="px-4 py-2 rounded-lg {'bg-indigo-600 text-white' if days == 7 else 'bg-white text-gray-700 hover:bg-gray-50'} font-medium shadow">
                    7 dias
                </a>
                <a href="?days=14" class="px-4 py-2 rounded-lg {'bg-indigo-600 text-white' if days == 14 else 'bg-white text-gray-700 hover:bg-gray-50'} font-medium shadow">
                    14 dias
                </a>
                <a href="?days=30" class="px-4 py-2 rounded-lg {'bg-indigo-600 text-white' if days == 30 else 'bg-white text-gray-700 hover:bg-gray-50'} font-medium shadow">
                    30 dias
                </a>
            </div>
        </div>

        <!-- Stats Cards -->
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            <!-- Workflows Card -->
            <div class="bg-white rounded-xl shadow-md p-6 border-l-4 border-blue-500">
                <div class="flex items-center justify-between">
                    <div>
                        <p class="text-gray-500 text-sm font-medium">Total Workflows</p>
                        <p class="text-3xl font-bold text-gray-900 mt-1">{metrics['total_workflows']}</p>
                    </div>
                    <div class="bg-blue-100 p-3 rounded-full">
                        <i class="fas fa-project-diagram text-blue-600 text-xl"></i>
                    </div>
                </div>
                <div class="mt-4 flex items-center text-sm">
                    <span class="text-green-600 font-medium">
                        <i class="fas fa-check-circle mr-1"></i>{metrics['active_workflows']} ativos
                    </span>
                </div>
            </div>

            <!-- Executions Card -->
            <div class="bg-white rounded-xl shadow-md p-6 border-l-4 border-purple-500">
                <div class="flex items-center justify-between">
                    <div>
                        <p class="text-gray-500 text-sm font-medium">Execuções</p>
                        <p class="text-3xl font-bold text-gray-900 mt-1">{metrics['total_executions']}</p>
                    </div>
                    <div class="bg-purple-100 p-3 rounded-full">
                        <i class="fas fa-play-circle text-purple-600 text-xl"></i>
                    </div>
                </div>
                <div class="mt-4 flex items-center text-sm space-x-4">
                    <span class="text-green-600">
                        <i class="fas fa-check mr-1"></i>{metrics['success_executions']} sucesso
                    </span>
                    <span class="text-red-600">
                        <i class="fas fa-times mr-1"></i>{metrics['failed_executions']} falhas
                    </span>
                </div>
            </div>

            <!-- Success Rate Card -->
            <div class="bg-white rounded-xl shadow-md p-6 border-l-4 border-green-500">
                <div class="flex items-center justify-between">
                    <div>
                        <p class="text-gray-500 text-sm font-medium">Taxa de Sucesso</p>
                        <p class="text-3xl font-bold text-gray-900 mt-1">{metrics['success_rate']:.1f}%</p>
                    </div>
                    <div class="bg-green-100 p-3 rounded-full">
                        <i class="fas fa-percentage text-green-600 text-xl"></i>
                    </div>
                </div>
                <div class="mt-4">
                    <div class="w-full bg-gray-200 rounded-full h-2">
                        <div class="bg-green-500 h-2 rounded-full transition-all" style="width: {metrics['success_rate']}%"></div>
                    </div>
                </div>
            </div>

            <!-- Health Score Card -->
            <div class="bg-white rounded-xl shadow-md p-6 border-l-4 {'border-green-500' if metrics['health_score'] >= 80 else 'border-yellow-500' if metrics['health_score'] >= 50 else 'border-red-500'}">
                <div class="flex items-center justify-between">
                    <div>
                        <p class="text-gray-500 text-sm font-medium">Health Score</p>
                        <p class="text-3xl font-bold {'text-green-600' if metrics['health_score'] >= 80 else 'text-yellow-600' if metrics['health_score'] >= 50 else 'text-red-600'} mt-1">
                            {metrics['health_score']:.0f}
                        </p>
                    </div>
                    <div class="{'bg-green-100' if metrics['health_score'] >= 80 else 'bg-yellow-100' if metrics['health_score'] >= 50 else 'bg-red-100'} p-3 rounded-full">
                        <i class="fas fa-heartbeat {'text-green-600' if metrics['health_score'] >= 80 else 'text-yellow-600' if metrics['health_score'] >= 50 else 'text-red-600'} text-xl"></i>
                    </div>
                </div>
                <div class="mt-4 text-sm text-gray-600">
                    {'Sistema saudável' if metrics['health_score'] >= 80 else 'Atenção necessária' if metrics['health_score'] >= 50 else 'Problemas detectados'}
                </div>
            </div>
        </div>

        <!-- Charts Row 1 -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
            <!-- Executions Chart -->
            <div class="bg-white rounded-xl shadow-md p-6">
                <h3 class="text-lg font-bold text-gray-900 mb-4">
                    <i class="fas fa-chart-bar text-indigo-600 mr-2"></i>Execuções por Dia
                </h3>
                <canvas id="executionsChart" height="250"></canvas>
            </div>

            <!-- Status Distribution Chart -->
            <div class="bg-white rounded-xl shadow-md p-6">
                <h3 class="text-lg font-bold text-gray-900 mb-4">
                    <i class="fas fa-chart-pie text-indigo-600 mr-2"></i>Distribuição de Status
                </h3>
                <canvas id="statusChart" height="250"></canvas>
            </div>
        </div>

        <!-- Charts Row 2 -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
            <!-- Workflow Status Chart -->
            <div class="bg-white rounded-xl shadow-md p-6">
                <h3 class="text-lg font-bold text-gray-900 mb-4">
                    <i class="fas fa-tasks text-indigo-600 mr-2"></i>Status dos Workflows
                </h3>
                <canvas id="workflowChart" height="250"></canvas>
            </div>

            <!-- Recent Activity -->
            <div class="bg-white rounded-xl shadow-md p-6">
                <h3 class="text-lg font-bold text-gray-900 mb-4">
                    <i class="fas fa-history text-indigo-600 mr-2"></i>Atividade Recente
                </h3>
                <div class="space-y-3 max-h-64 overflow-y-auto">
                    {_get_recent_activity_html(metrics['recent_activity'])}
                </div>
            </div>
        </div>

        <!-- Quick Actions -->
        <div class="bg-white rounded-xl shadow-md p-6">
            <h3 class="text-lg font-bold text-gray-900 mb-4">
                <i class="fas fa-bolt text-indigo-600 mr-2"></i>Ações Rápidas
            </h3>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                <a href="/workflows/create" class="flex items-center justify-center space-x-2 bg-indigo-600 text-white px-4 py-3 rounded-lg hover:bg-indigo-700 transition">
                    <i class="fas fa-plus"></i>
                    <span>Novo Workflow</span>
                </a>
                <a href="/workflows" class="flex items-center justify-center space-x-2 bg-green-600 text-white px-4 py-3 rounded-lg hover:bg-green-700 transition">
                    <i class="fas fa-play"></i>
                    <span>Executar Workflow</span>
                </a>
                <a href="/workflows/executions" class="flex items-center justify-center space-x-2 bg-purple-600 text-white px-4 py-3 rounded-lg hover:bg-purple-700 transition">
                    <i class="fas fa-list"></i>
                    <span>Ver Execuções</span>
                </a>
                <a href="/audit" class="flex items-center justify-center space-x-2 bg-gray-600 text-white px-4 py-3 rounded-lg hover:bg-gray-700 transition">
                    <i class="fas fa-shield-alt"></i>
                    <span>Auditoria</span>
                </a>
            </div>
        </div>
    </main>

    <script>
        // Chart.js Configurations
        const chartColors = {{
            indigo: '#4f46e5',
            green: '#10b981',
            red: '#ef4444',
            yellow: '#f59e0b',
            blue: '#3b82f6',
            gray: '#6b7280'
        }};

        // Executions by Day Chart
        const executionsCtx = document.getElementById('executionsChart').getContext('2d');
        new Chart(executionsCtx, {{
            type: 'line',
            data: {{
                labels: {metrics['chart_data']['days']},
                datasets: [
                    {{
                        label: 'Sucesso',
                        data: {metrics['chart_data']['success_by_day']},
                        borderColor: chartColors.green,
                        backgroundColor: 'rgba(16, 185, 129, 0.1)',
                        tension: 0.4,
                        fill: true
                    }},
                    {{
                        label: 'Falhas',
                        data: {metrics['chart_data']['failed_by_day']},
                        borderColor: chartColors.red,
                        backgroundColor: 'rgba(239, 68, 68, 0.1)',
                        tension: 0.4,
                        fill: true
                    }}
                ]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        position: 'bottom'
                    }}
                }},
                scales: {{
                    y: {{
                        beginAtZero: true,
                        ticks: {{
                            stepSize: 1
                        }}
                    }}
                }}
            }}
        }});

        // Status Distribution Chart
        const statusCtx = document.getElementById('statusChart').getContext('2d');
        new Chart(statusCtx, {{
            type: 'doughnut',
            data: {{
                labels: ['Sucesso', 'Falha', 'Pendente', 'Executando'],
                datasets: [{{
                    data: [
                        {metrics['success_executions']},
                        {metrics['failed_executions']},
                        {metrics['pending_executions']},
                        {metrics['running_executions']}
                    ],
                    backgroundColor: [
                        chartColors.green,
                        chartColors.red,
                        chartColors.yellow,
                        chartColors.blue
                    ]
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        position: 'bottom'
                    }}
                }}
            }}
        }});

        // Workflow Status Chart
        const workflowCtx = document.getElementById('workflowChart').getContext('2d');
        new Chart(workflowCtx, {{
            type: 'bar',
            data: {{
                labels: ['Ativos', 'Inativos', 'Rascunho'],
                datasets: [{{
                    label: 'Workflows',
                    data: [
                        {metrics['active_workflows']},
                        {metrics['inactive_workflows']},
                        {metrics['draft_workflows']}
                    ],
                    backgroundColor: [
                        chartColors.green,
                        chartColors.gray,
                        chartColors.yellow
                    ]
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        display: false
                    }}
                }},
                scales: {{
                    y: {{
                        beginAtZero: true,
                        ticks: {{
                            stepSize: 1
                        }}
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>"""
    
    return HTMLResponse(content=html)


def _get_login_html() -> str:
    """Get login page HTML."""
    return """<!DOCTYPE html>
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
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email, password })
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    localStorage.setItem('token', data.access_token);
                    window.location.reload();
                } else {
                    document.getElementById('error').textContent = data.detail || 'Login failed';
                    document.getElementById('error').classList.remove('hidden');
                }
            } catch (error) {
                document.getElementById('error').textContent = 'Network error';
                document.getElementById('error').classList.remove('hidden');
            }
        });
    </script>
</body>
</html>"""


def _get_recent_activity_html(activities: list) -> str:
    """Generate HTML for recent activity items."""
    if not activities:
        return '<p class="text-gray-500 text-center py-4">Nenhuma atividade recente</p>'
    
    html = ""
    for activity in activities:
        icon_class = {
            'success': 'fas fa-check-circle text-green-500',
            'failed': 'fas fa-times-circle text-red-500',
            'warning': 'fas fa-exclamation-triangle text-yellow-500',
            'info': 'fas fa-info-circle text-blue-500',
        }.get(activity.get('type', 'info'), 'fas fa-info-circle text-blue-500')
        
        html += f"""
        <div class="flex items-center space-x-3 p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition">
            <i class="{icon_class} text-lg"></i>
            <div class="flex-1">
                <p class="text-sm font-medium text-gray-900">{activity.get('title', 'Atividade')}</p>
                <p class="text-xs text-gray-500">{activity.get('description', '')}</p>
            </div>
            <span class="text-xs text-gray-400">{activity.get('time', '')}</span>
        </div>
        """
    
    return html


async def _get_dashboard_metrics(db, organization_id: str, days: int) -> dict:
    """Get dashboard metrics from database."""
    from datetime import datetime, timedelta
    
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Workflow counts
    result = await db.execute(
        select(
            func.count(Workflow.id).label('total'),
            func.sum(func.case((Workflow.status == WorkflowStatus.ACTIVE, 1), else_=0)).label('active'),
            func.sum(func.case((Workflow.status == WorkflowStatus.INACTIVE, 1), else_=0)).label('inactive'),
            func.sum(func.case((Workflow.status == WorkflowStatus.DRAFT, 1), else_=0)).label('draft'),
        ).where(
            Workflow.organization_id == organization_id,
        )
    )
    workflow_stats = result.one()
    
    # Execution counts
    result = await db.execute(
        select(
            func.count(WorkflowExecution.id).label('total'),
            func.sum(func.case((WorkflowExecution.status == ExecutionStatus.COMPLETED, 1), else_=0)).label('success'),
            func.sum(func.case((WorkflowExecution.status == ExecutionStatus.FAILED, 1), else_=0)).label('failed'),
            func.sum(func.case((WorkflowExecution.status == ExecutionStatus.PENDING, 1), else_=0)).label('pending'),
            func.sum(func.case((WorkflowExecution.status == ExecutionStatus.RUNNING, 1), else_=0)).label('running'),
        ).where(
            WorkflowExecution.organization_id == organization_id,
            WorkflowExecution.started_at >= start_date,
        )
    )
    execution_stats = result.one()
    
    # Daily execution stats for chart
    daily_stats = {}
    for i in range(days):
        day = (datetime.utcnow() - timedelta(days=i)).strftime('%Y-%m-%d')
        daily_stats[day] = {'success': 0, 'failed': 0}
    
    result = await db.execute(
        select(
            func.date(WorkflowExecution.started_at).label('day'),
            WorkflowExecution.status,
            func.count(WorkflowExecution.id).label('count'),
        ).where(
            WorkflowExecution.organization_id == organization_id,
            WorkflowExecution.started_at >= start_date,
        ).group_by(
            func.date(WorkflowExecution.started_at),
            WorkflowExecution.status,
        )
    )
    
    for row in result.all():
        day = row.day.strftime('%Y-%m-%d') if row.day else None
        if day and day in daily_stats:
            if row.status == ExecutionStatus.COMPLETED:
                daily_stats[day]['success'] = row.count
            elif row.status == ExecutionStatus.FAILED:
                daily_stats[day]['failed'] = row.count
    
    # Prepare chart data
    days_list = sorted(daily_stats.keys())
    success_by_day = [daily_stats[day]['success'] for day in days_list]
    failed_by_day = [daily_stats[day]['failed'] for day in days_list]
    
    # Format day labels
    day_labels = [datetime.strptime(day, '%Y-%m-%d').strftime('%d/%m') for day in days_list]
    
    # Calculate success rate
    total_exec = execution_stats.total or 0
    success_exec = execution_stats.success or 0
    success_rate = (success_exec / total_exec * 100) if total_exec > 0 else 0
    
    # Health score calculation
    health_score = min(100, success_rate + (10 if workflow_stats.active and workflow_stats.active > 0 else 0))
    
    # Recent activity (last 10 executions)
    result = await db.execute(
        select(WorkflowExecution, Workflow.name.label('workflow_name'))
        .join(Workflow, WorkflowExecution.workflow_id == Workflow.id)
        .where(
            WorkflowExecution.organization_id == organization_id,
        )
        .order_by(WorkflowExecution.started_at.desc())
        .limit(10)
    )
    
    recent_activity = []
    for row in result.all():
        execution = row.WorkflowExecution
        workflow_name = row.workflow_name
        
        status_type = {
            ExecutionStatus.COMPLETED: 'success',
            ExecutionStatus.FAILED: 'failed',
            ExecutionStatus.PENDING: 'info',
            ExecutionStatus.RUNNING: 'info',
        }.get(execution.status, 'info')
        
        recent_activity.append({
            'type': status_type,
            'title': f"Workflow '{workflow_name}'",
            'description': f"Status: {execution.status.value}",
            'time': execution.started_at.strftime('%H:%M') if execution.started_at else '-',
        })
    
    return {
        'total_workflows': workflow_stats.total or 0,
        'active_workflows': workflow_stats.active or 0,
        'inactive_workflows': workflow_stats.inactive or 0,
        'draft_workflows': workflow_stats.draft or 0,
        'total_executions': execution_stats.total or 0,
        'success_executions': execution_stats.success or 0,
        'failed_executions': execution_stats.failed or 0,
        'pending_executions': execution_stats.pending or 0,
        'running_executions': execution_stats.running or 0,
        'success_rate': success_rate,
        'health_score': health_score,
        'chart_data': {
            'days': day_labels,
            'success_by_day': success_by_day,
            'failed_by_day': failed_by_day,
        },
        'recent_activity': recent_activity,
    }
