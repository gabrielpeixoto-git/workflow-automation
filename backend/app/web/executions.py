"""Web routes for execution management."""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_current_user, get_optional_user
from app.models.execution import ExecutionStatus, WorkflowExecution
from app.models.user import User
from app.models.workflow import Workflow

router = APIRouter(prefix="/executions", tags=["web-executions"])


@router.get("", response_class=HTMLResponse)
async def list_executions_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    status: str | None = Query(None),
    workflow_id: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
):
    """List executions with filters for user's organization."""
    # Build query with filters
    query = select(WorkflowExecution, Workflow).join(
        Workflow, WorkflowExecution.workflow_id == Workflow.id
    ).where(Workflow.organization_id == user.organization_id)
    
    # Apply status filter
    if status and status != "all":
        query = query.where(WorkflowExecution.status == status)
    
    # Apply workflow filter
    if workflow_id:
        query = query.where(WorkflowExecution.workflow_id == workflow_id)
    
    # Apply date filters
    if date_from:
        try:
            from_date = datetime.fromisoformat(date_from)
            query = query.where(WorkflowExecution.created_at >= from_date)
        except ValueError:
            pass
    
    if date_to:
        try:
            to_date = datetime.fromisoformat(date_to)
            # Add one day to include the full day
            to_date = to_date + timedelta(days=1)
            query = query.where(WorkflowExecution.created_at < to_date)
        except ValueError:
            pass
    
    # Execute query
    result = await db.execute(
        query.order_by(WorkflowExecution.created_at.desc()).limit(limit)
    )
    executions = result.all()
    
    # Get workflows for filter dropdown
    workflows_result = await db.execute(
        select(Workflow).where(
            Workflow.organization_id == user.organization_id,
            Workflow.deleted_at.is_(None),
        ).order_by(Workflow.name)
    )
    workflows = workflows_result.scalars().all()
    
    # Calculate filter counts
    status_counts = {}
    for s in ["completed", "failed", "running", "pending"]:
        count_result = await db.execute(
            select(func.count(WorkflowExecution.id))
            .join(Workflow)
            .where(
                Workflow.organization_id == user.organization_id,
                WorkflowExecution.status == s,
            )
        )
        status_counts[s] = count_result.scalar() or 0

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Execuções - Workflow Automation</title>
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
                    <span class="ml-2 text-gray-400">/</span>
                    <span class="ml-2 text-gray-900 font-medium">Execuções</span>
                </div>
            </div>
        </div>
    </nav>

    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div class="mb-6">
            <h1 class="text-2xl font-bold text-gray-900">Histórico de Execuções</h1>
            <p class="text-gray-500 mt-1">Filtre e visualize as execuções dos workflows</p>
        </div>

        <!-- Filter Bar -->
        <div class="bg-white shadow rounded-lg p-4 mb-6">
            <form method="get" class="flex flex-wrap gap-4 items-end">
                <!-- Status Filter -->
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Status</label>
                    <select name="status" class="rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 border p-2 text-sm">
                        <option value="all" {'selected' if status == 'all' or not status else ''}>Todos ({sum(status_counts.values())})</option>
                        <option value="completed" {'selected' if status == 'completed' else ''}>✅ Completados ({status_counts['completed']})</option>
                        <option value="failed" {'selected' if status == 'failed' else ''}>❌ Falhas ({status_counts['failed']})</option>
                        <option value="running" {'selected' if status == 'running' else ''}>🔄 Em andamento ({status_counts['running']})</option>
                        <option value="pending" {'selected' if status == 'pending' else ''}>⏳ Pendentes ({status_counts['pending']})</option>
                    </select>
                </div>

                <!-- Workflow Filter -->
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Workflow</label>
                    <select name="workflow_id" class="rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 border p-2 text-sm">
                        <option value="">Todos os workflows</option>
                        {''.join([f'<option value="{w.id}" {"selected" if workflow_id == str(w.id) else ""}>{w.name}</option>' for w in workflows])}
                    </select>
                </div>

                <!-- Date From -->
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">De</label>
                    <input type="date" name="date_from" value="{date_from or ''}"
                        class="rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 border p-2 text-sm">
                </div>

                <!-- Date To -->
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Até</label>
                    <input type="date" name="date_to" value="{date_to or ''}"
                        class="rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 border p-2 text-sm">
                </div>

                <!-- Limit -->
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Limite</label>
                    <select name="limit" class="rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 border p-2 text-sm">
                        <option value="25" {'selected' if limit == 25 else ''}>25</option>
                        <option value="50" {'selected' if limit == 50 else ''}>50</option>
                        <option value="100" {'selected' if limit == 100 else ''}>100</option>
                    </select>
                </div>

                <!-- Buttons -->
                <div class="flex gap-2">
                    <button type="submit" class="bg-indigo-600 text-white px-4 py-2 rounded-md hover:bg-indigo-700 text-sm font-medium">
                        Filtrar
                    </button>
                    <a href="/executions" class="bg-gray-200 text-gray-700 px-4 py-2 rounded-md hover:bg-gray-300 text-sm font-medium">
                        Limpar
                    </a>
                </div>
            </form>
        </div>

        <div class="bg-white shadow rounded-lg overflow-hidden">
            <table class="min-w-full divide-y divide-gray-200">
                <thead class="bg-gray-50">
                    <tr>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Workflow</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Trigger</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Início</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Término</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Ações</th>
                    </tr>
                </thead>
                <tbody class="bg-white divide-y divide-gray-200">
"""

    if not executions:
        html += """
                    <tr>
                        <td colspan="6" class="px-6 py-12 text-center text-gray-500">
                            Nenhuma execução encontrada.
                            <a href="/workflows" class="text-indigo-600 hover:text-indigo-800 ml-1">Executar um workflow</a>
                        </td>
                    </tr>
"""
    else:
        for execution, workflow in executions:
            # Handle status color
            status_val = execution.status.value if hasattr(execution.status, 'value') else execution.status
            status_color = {
                "pending": "bg-yellow-100 text-yellow-800",
                "running": "bg-blue-100 text-blue-800",
                "completed": "bg-green-100 text-green-800",
                "failed": "bg-red-100 text-red-800",
                "cancelled": "bg-gray-100 text-gray-800",
                "retrying": "bg-orange-100 text-orange-800",
            }.get(status_val, "bg-gray-100 text-gray-800")
            
            trigger_type_val = execution.trigger_type.value if hasattr(execution.trigger_type, 'value') else execution.trigger_type
            
            started_at = execution.started_at.strftime("%d/%m/%Y %H:%M") if execution.started_at else "-"
            completed_at = execution.completed_at.strftime("%d/%m/%Y %H:%M") if execution.completed_at else "-"
            
            html += f"""
                    <tr>
                        <td class="px-6 py-4 whitespace-nowrap">
                            <div class="text-sm font-medium text-gray-900">{workflow.name}</div>
                            <div class="text-sm text-gray-500">v{workflow.version}</div>
                        </td>
                        <td class="px-6 py-4 whitespace-nowrap">
                            <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full {status_color}">
                                {status_val.upper()}
                            </span>
                        </td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                            {trigger_type_val or '-'}
                        </td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                            {started_at}
                        </td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                            {completed_at}
                        </td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm font-medium">
                            <a href="/executions/{execution.id}" class="text-indigo-600 hover:text-indigo-900">Ver detalhes</a>
                        </td>
                    </tr>
"""

    html += """
                </tbody>
            </table>
        </div>

        <div class="mt-6">
            <a href="/workflows" class="text-gray-600 hover:text-gray-900">← Voltar aos Workflows</a>
        </div>
    </main>
</body>
</html>
"""
    return html


@router.get("/{execution_id}", response_class=HTMLResponse)
async def execution_detail_page(
    execution_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Show execution details with step logs."""
    result = await db.execute(
        select(WorkflowExecution, Workflow)
        .join(Workflow, WorkflowExecution.workflow_id == Workflow.id)
        .where(
            WorkflowExecution.id == execution_id,
            Workflow.organization_id == user.organization_id,
        )
    )
    execution_data = result.first()
    
    if not execution_data:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    execution, workflow = execution_data
    
    # Get step logs
    from app.models.execution import ExecutionLog
    logs_result = await db.execute(
        select(ExecutionLog)
        .where(ExecutionLog.execution_id == execution_id)
        .order_by(ExecutionLog.step_order)
    )
    step_logs = logs_result.scalars().all()

    status_val = execution.status.value if hasattr(execution.status, 'value') else execution.status
    trigger_type_val = execution.trigger_type.value if hasattr(execution.trigger_type, 'value') else execution.trigger_type
    
    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Execução #{str(execution.id)[:8]} - Workflow Automation</title>
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
                    <span class="ml-2 text-gray-400">/</span>
                    <a href="/executions" class="ml-4 text-gray-600 hover:text-gray-900">Execuções</a>
                    <span class="ml-2 text-gray-400">/</span>
                    <span class="ml-2 text-gray-900 font-medium">#{str(execution.id)[:8]}</span>
                </div>
            </div>
        </div>
    </nav>

    <main class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div class="mb-6">
            <h1 class="text-2xl font-bold text-gray-900">Detalhes da Execução</h1>
            <p class="text-gray-500 mt-1">Workflow: {workflow.name} (v{workflow.version})</p>
        </div>

        <!-- Execution Info -->
        <div class="bg-white shadow rounded-lg p-6 mb-6">
            <h2 class="text-lg font-medium text-gray-900 mb-4">Informações Gerais</h2>
            <div class="grid grid-cols-2 gap-4 text-sm">
                <div>
                    <span class="text-gray-500">Execution ID:</span>
                    <span class="ml-2 font-mono">{execution.id}</span>
                </div>
                <div>
                    <span class="text-gray-500">Correlation ID:</span>
                    <span class="ml-2 font-mono">{execution.correlation_id}</span>
                </div>
                <div>
                    <span class="text-gray-500">Status:</span>
                    <span class="ml-2 font-semibold">{status_val.upper()}</span>
                </div>
                <div>
                    <span class="text-gray-500">Trigger:</span>
                    <span class="ml-2">{trigger_type_val or '-'}</span>
                </div>
                <div>
                    <span class="text-gray-500">Iniciado em:</span>
                    <span class="ml-2">{execution.started_at.strftime("%d/%m/%Y %H:%M:%S") if execution.started_at else '-'}</span>
                </div>
                <div>
                    <span class="text-gray-500">Concluído em:</span>
                    <span class="ml-2">{execution.completed_at.strftime("%d/%m/%Y %H:%M:%S") if execution.completed_at else '-'}</span>
                </div>
            </div>
            
            {f'<div class="mt-4 p-3 bg-red-50 border border-red-200 rounded"><span class="text-red-700"><strong>Erro:</strong> {execution.error_message}</span></div>' if execution.error_message else ''}
        </div>

        <!-- Step Logs -->
        <div class="bg-white shadow rounded-lg p-6">
            <h2 class="text-lg font-medium text-gray-900 mb-4">Logs por Step</h2>
            <div class="space-y-4">
"""

    if not step_logs:
        html += '<p class="text-gray-500">Nenhum log disponível.</p>'
    else:
        for log in step_logs:
            log_status = log.status.value if hasattr(log.status, 'value') else log.status
            status_color = {
                "pending": "bg-yellow-100 text-yellow-800 border-yellow-200",
                "running": "bg-blue-100 text-blue-800 border-blue-200",
                "completed": "bg-green-100 text-green-800 border-green-200",
                "failed": "bg-red-100 text-red-800 border-red-200",
                "skipped": "bg-gray-100 text-gray-800 border-gray-200",
            }.get(log_status, "bg-gray-100 text-gray-800 border-gray-200")
            
            duration = f"{log.duration_ms}ms" if log.duration_ms else "-"
            
            html += f"""
                <div class="border rounded-lg p-4 {status_color}">
                    <div class="flex justify-between items-start">
                        <div>
                            <div class="flex items-center gap-2">
                                <span class="text-xs font-semibold uppercase">{log_status}</span>
                                <span class="text-sm font-medium">{log.step_name}</span>
                                <span class="text-xs text-gray-500">(Order: {log.step_order})</span>
                            </div>
                            <div class="text-xs text-gray-600 mt-1">Type: {log.step_type}</div>
                        </div>
                        <div class="text-xs text-gray-500">
                            Duração: {duration}
                        </div>
                    </div>
                    {f'<div class="mt-2 text-xs text-red-700 bg-red-50 p-2 rounded"><strong>Erro:</strong> {log.error_message}</div>' if log.error_message else ''}
                </div>
"""

    html += f"""
            </div>
        </div>

        <div class="mt-6 flex justify-between">
            <a href="/executions" class="text-gray-600 hover:text-gray-900">← Voltar ao histórico</a>
            <a href="/workflows/{workflow.id}/run" class="bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700">
                ▶ Executar Novamente
            </a>
        </div>
    </main>
</body>
</html>
"""
    return html
