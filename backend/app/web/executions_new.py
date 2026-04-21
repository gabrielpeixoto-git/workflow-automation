"""Enhanced web routes for execution management with timeline view."""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_current_user, get_optional_user
from app.models.execution import ExecutionLog, ExecutionStatus, WorkflowExecution
from app.models.user import User
from app.models.workflow import Workflow
from app.web.components import get_base_layout, get_empty_state, get_status_badge

router = APIRouter(prefix="/executions", tags=["web-executions"])


@router.get("", response_class=HTMLResponse)
async def list_executions_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    status: Optional[str] = Query(None),
    workflow_id: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
):
    """List executions with timeline view."""
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
            to_date = datetime.fromisoformat(date_to) + timedelta(days=1)
            query = query.where(WorkflowExecution.created_at < to_date)
        except ValueError:
            pass

    # Get total count
    count_query = select(func.count(WorkflowExecution.id)).join(
        Workflow
    ).where(Workflow.organization_id == user.organization_id)
    if status and status != "all":
        count_query = count_query.where(WorkflowExecution.status == status)
    if workflow_id:
        count_query = count_query.where(WorkflowExecution.workflow_id == workflow_id)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    total_pages = (total + per_page - 1) // per_page

    # Get executions with pagination
    offset = (page - 1) * per_page
    result = await db.execute(
        query.order_by(WorkflowExecution.created_at.desc()).offset(offset).limit(per_page)
    )
    executions = result.all()

    # Get workflows for filter
    workflows_result = await db.execute(
        select(Workflow).where(
            Workflow.organization_id == user.organization_id,
            Workflow.deleted_at.is_(None),
        ).order_by(Workflow.name)
    )
    workflows = workflows_result.scalars().all()

    # Get status counts
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

    # Build content
    content = await _build_executions_content(
        executions, status, workflow_id, date_from, date_to,
        page, total_pages, total, per_page, workflows, status_counts
    )

    return HTMLResponse(content=get_base_layout("Execuções", content, user, "executions"))


@router.get("/{execution_id}", response_class=HTMLResponse)
async def view_execution_page(
    request: Request,
    execution_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """View execution details with timeline."""
    # Get execution with workflow
    result = await db.execute(
        select(WorkflowExecution, Workflow).join(
            Workflow, WorkflowExecution.workflow_id == Workflow.id
        ).where(
            WorkflowExecution.id == execution_id,
            Workflow.organization_id == user.organization_id,
        )
    )
    execution_data = result.first()

    if not execution_data:
        raise HTTPException(status_code=404, detail="Execution not found")

    execution, workflow = execution_data

    # Get execution logs
    logs_result = await db.execute(
        select(ExecutionLog).where(
            ExecutionLog.execution_id == execution_id
        ).order_by(ExecutionLog.created_at)
    )
    logs = logs_result.scalars().all()

    # Build timeline
    timeline_html = _build_timeline(execution, logs)

    # Build content
    content = f"""
    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <!-- Header -->
        <div class="mb-8">
            <div class="flex items-center space-x-2 text-sm text-gray-500 mb-2">
                <a href="/executions" class="hover:text-gray-700">
                    <i class="fas fa-arrow-left mr-1"></i>Voltar
                </a>
                <span>/</span>
                <span>Execução</span>
            </div>
            <div class="flex items-center justify-between">
                <div>
                    <h1 class="text-3xl font-bold text-gray-900">{workflow.name}</h1>
                    <p class="text-gray-500 mt-1">Execução iniciada em {execution.created_at.strftime('%d/%m/%Y %H:%M:%S')}</p>
                </div>
                <div class="flex items-center space-x-3">
                    {get_status_badge(execution.status.value if hasattr(execution.status, 'value') else execution.status)}
                </div>
            </div>
        </div>

        <!-- Execution Info Cards -->
        <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
            <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
                <div class="text-sm text-gray-500 mb-1">Status</div>
                <div class="font-semibold">{get_status_badge(execution.status.value if hasattr(execution.status, 'value') else execution.status)}</div>
            </div>
            <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
                <div class="text-sm text-gray-500 mb-1">Trigger</div>
                <div class="font-semibold text-gray-900">{execution.trigger_type or 'Manual'}</div>
            </div>
            <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
                <div class="text-sm text-gray-500 mb-1">Iniciado</div>
                <div class="font-semibold text-gray-900">{execution.created_at.strftime('%H:%M:%S')}</div>
            </div>
            <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
                <div class="text-sm text-gray-500 mb-1">Duração</div>
                <div class="font-semibold text-gray-900">
                    {_format_duration(execution.started_at, execution.completed_at)}
                </div>
            </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <!-- Timeline -->
            <div class="lg:col-span-2">
                <div class="bg-white rounded-xl shadow-sm border border-gray-200">
                    <div class="px-6 py-4 border-b border-gray-200">
                        <h2 class="text-lg font-semibold text-gray-900">
                            <i class="fas fa-stream text-indigo-600 mr-2"></i>Timeline de Execução
                        </h2>
                    </div>
                    <div class="p-6">
                        {timeline_html}
                    </div>
                </div>
            </div>

            <!-- Sidebar -->
            <div class="space-y-6">
                <!-- Input Data -->
                <div class="bg-white rounded-xl shadow-sm border border-gray-200">
                    <div class="px-6 py-4 border-b border-gray-200">
                        <h3 class="text-sm font-semibold text-gray-900">Dados de Entrada</h3>
                    </div>
                    <div class="p-4">
                        <pre class="bg-gray-50 rounded-lg p-3 text-xs overflow-x-auto"><code>{execution.input_data or '{}'}</code></pre>
                    </div>
                </div>

                <!-- Output Data -->
                <div class="bg-white rounded-xl shadow-sm border border-gray-200">
                    <div class="px-6 py-4 border-b border-gray-200">
                        <h3 class="text-sm font-semibold text-gray-900">Dados de Saída</h3>
                    </div>
                    <div class="p-4">
                        <pre class="bg-gray-50 rounded-lg p-3 text-xs overflow-x-auto"><code>{execution.output_data or 'N/A'}</code></pre>
                    </div>
                </div>

                <!-- Error (if failed) -->
                {f"""
                <div class="bg-red-50 rounded-xl shadow-sm border border-red-200">
                    <div class="px-6 py-4 border-b border-red-200">
                        <h3 class="text-sm font-semibold text-red-800">
                            <i class="fas fa-exclamation-triangle mr-1"></i>Erro
                        </h3>
                    </div>
                    <div class="p-4">
                        <p class="text-sm text-red-700">{execution.error_message}</p>
                    </div>
                </div>
                """ if execution.error_message else ''}
            </div>
        </div>
    </main>
    """

    return HTMLResponse(content=get_base_layout(f"Execução #{execution_id[:8]}", content, user, "executions"))


def _build_timeline(execution, logs) -> str:
    """Build timeline HTML for execution."""
    if not logs:
        return '<p class="text-gray-500 text-center py-8">Nenhum log disponível</p>'

    timeline_items = ""
    for i, log in enumerate(logs):
        # Determine icon and color based on log level/status
        if log.level == "error":
            icon = "fa-times-circle"
            color = "text-red-500"
            bg_color = "bg-red-50"
        elif log.level == "warning":
            icon = "fa-exclamation-triangle"
            color = "text-yellow-500"
            bg_color = "bg-yellow-50"
        elif log.level == "success":
            icon = "fa-check-circle"
            color = "text-green-500"
            bg_color = "bg-green-50"
        else:
            icon = "fa-info-circle"
            color = "text-blue-500"
            bg_color = "bg-blue-50"

        # Time since start
        time_str = log.created_at.strftime('%H:%M:%S.%f')[:-3]

        timeline_items += f"""
        <div class="flex gap-4">
            <div class="flex flex-col items-center">
                <div class="w-10 h-10 rounded-full {bg_color} flex items-center justify-center">
                    <i class="fas {icon} {color}"></i>
                </div>
                {'' if i == len(logs) - 1 else '<div class="w-0.5 flex-1 bg-gray-200 my-2"></div>'}
            </div>
            <div class="flex-1 pb-8">
                <div class="flex items-center justify-between mb-1">
                    <span class="text-sm font-medium text-gray-900">{log.message}</span>
                    <span class="text-xs text-gray-500">{time_str}</span>
                </div>
                {f'<p class="text-sm text-gray-600">{log.details}</p>' if log.details else ''}
            </div>
        </div>
        """

    return f'<div class="space-y-0">{timeline_items}</div>'


def _format_duration(started_at, completed_at) -> str:
    """Format execution duration."""
    if not started_at:
        return "N/A"
    if not completed_at:
        return "Executando..."

    duration = completed_at - started_at
    seconds = duration.total_seconds()

    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}min"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


async def _build_executions_content(
    executions, status, workflow_id, date_from, date_to,
    page, total_pages, total, per_page, workflows, status_counts
) -> str:
    """Build executions list content."""

    # Build filter pills
    filter_pills = ""
    if status and status != "all":
        filter_pills += f'<span class="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-blue-100 text-blue-800 mr-2">Status: {status} <a href="?{build_query_string(workflow_id=workflow_id, date_from=date_from, date_to=date_to)}" class="ml-2"><i class="fas fa-times"></i></a></span>'
    if workflow_id:
        workflow_name = next((w.name for w in workflows if str(w.id) == workflow_id), "Unknown")
        filter_pills += f'<span class="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-green-100 text-green-800 mr-2">Workflow: {workflow_name} <a href="?{build_query_string(status=status, date_from=date_from, date_to=date_to)}" class="ml-2"><i class="fas fa-times"></i></a></span>'

    # Build executions list
    if not executions:
        executions_list = get_empty_state(
            "fa-history",
            "Nenhuma execução encontrada",
            "As execuções dos workflows aparecerão aqui.",
            '<a href="/workflows" class="inline-flex items-center px-4 py-2 border border-transparent rounded-lg shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700"><i class="fas fa-play mr-2"></i>Executar Workflow</a>'
        )
    else:
        executions_list = '<div class="space-y-4">'
        for execution, workflow in executions:
            status_val = execution.status.value if hasattr(execution.status, 'value') else execution.status

            # Calculate duration
            duration = ""
            if execution.started_at and execution.completed_at:
                delta = execution.completed_at - execution.started_at
                duration = f"{delta.total_seconds():.1f}s"
            elif execution.started_at:
                duration = "Executando..."

            executions_list += f"""
            <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-5 hover:shadow-md transition-shadow">
                <div class="flex items-center justify-between">
                    <div class="flex items-center space-x-4">
                        <div class="flex-shrink-0">
                            {get_status_badge(status_val)}
                        </div>
                        <div>
                            <h3 class="text-lg font-semibold text-gray-900">{workflow.name}</h3>
                            <div class="flex items-center space-x-4 text-sm text-gray-500 mt-1">
                                <span><i class="fas fa-calendar mr-1"></i>{execution.created_at.strftime('%d/%m/%Y %H:%M')}</span>
                                <span><i class="fas fa-clock mr-1"></i>{duration}</span>
                                <span><i class="fas fa-bolt mr-1"></i>{execution.trigger_type or 'Manual'}</span>
                            </div>
                        </div>
                    </div>
                    <div class="flex items-center space-x-2">
                        <a href="/executions/{execution.id}" class="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-lg text-gray-700 bg-white hover:bg-gray-50">
                            <i class="fas fa-eye mr-2"></i>Detalhes
                        </a>
                    </div>
                </div>
            </div>
            """
        executions_list += '</div>'

    # Build pagination
    pagination = ""
    if total_pages > 1:
        pagination = '<div class="flex items-center justify-between mt-8">'
        pagination += f'<div class="text-sm text-gray-500">Mostrando {(page-1)*per_page + 1} a {min(page*per_page, total)} de {total}</div>'
        pagination += '<div class="flex items-center space-x-2">'

        if page > 1:
            pagination += f'<a href="?{build_query_string(status=status, workflow_id=workflow_id, date_from=date_from, date_to=date_to, page=page-1)}" class="px-3 py-2 border border-gray-300 rounded-lg text-sm text-gray-700 hover:bg-gray-50"><i class="fas fa-chevron-left"></i></a>'

        start_page = max(1, page - 2)
        end_page = min(total_pages, page + 2)
        for p in range(start_page, end_page + 1):
            if p == page:
                pagination += f'<span class="px-3 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium">{p}</span>'
            else:
                pagination += f'<a href="?{build_query_string(status=status, workflow_id=workflow_id, date_from=date_from, date_to=date_to, page=p)}" class="px-3 py-2 border border-gray-300 rounded-lg text-sm text-gray-700 hover:bg-gray-50">{p}</a>'

        if page < total_pages:
            pagination += f'<a href="?{build_query_string(status=status, workflow_id=workflow_id, date_from=date_from, date_to=date_to, page=page+1)}" class="px-3 py-2 border border-gray-300 rounded-lg text-sm text-gray-700 hover:bg-gray-50"><i class="fas fa-chevron-right"></i></a>'

        pagination += '</div></div>'

    return f"""
    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <!-- Header -->
        <div class="flex items-center justify-between mb-8">
            <div>
                <h1 class="text-3xl font-bold text-gray-900">Histórico de Execuções</h1>
                <p class="text-gray-500 mt-1">Visualize e monitore as execuções dos workflows</p>
            </div>
            <a href="/workflows" class="inline-flex items-center px-4 py-2 border border-transparent rounded-lg shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700">
                <i class="fas fa-play mr-2"></i>Executar Workflow
            </a>
        </div>

        <!-- Filter Bar -->
        <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-4 mb-6">
            <form method="get" class="flex flex-wrap gap-3 items-end">
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Status</label>
                    <select name="status" class="rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 border p-2.5 text-sm">
                        <option value="all" {'selected' if status == 'all' or not status else ''}>Todos ({sum(status_counts.values())})</option>
                        <option value="completed" {'selected' if status == 'completed' else ''}>Concluídos ({status_counts['completed']})</option>
                        <option value="failed" {'selected' if status == 'failed' else ''}>Falhas ({status_counts['failed']})</option>
                        <option value="running" {'selected' if status == 'running' else ''}>Executando ({status_counts['running']})</option>
                        <option value="pending" {'selected' if status == 'pending' else ''}>Pendentes ({status_counts['pending']})</option>
                    </select>
                </div>
                <div class="flex-1 min-w-48">
                    <label class="block text-sm font-medium text-gray-700 mb-1">Workflow</label>
                    <select name="workflow_id" class="w-full rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 border p-2.5 text-sm">
                        <option value="">Todos os workflows</option>
                        {''.join([f'<option value="{w.id}" {"selected" if workflow_id == str(w.id) else ""}>{w.name}</option>' for w in workflows])}
                    </select>
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">De</label>
                    <input type="date" name="date_from" value="{date_from or ''}"
                        class="rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 border p-2.5 text-sm">
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Até</label>
                    <input type="date" name="date_to" value="{date_to or ''}"
                        class="rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 border p-2.5 text-sm">
                </div>
                <div class="flex gap-2">
                    <button type="submit" class="bg-indigo-600 text-white px-4 py-2.5 rounded-lg hover:bg-indigo-700 text-sm font-medium">
                        <i class="fas fa-filter mr-1"></i>Filtrar
                    </button>
                    <a href="/executions" class="bg-gray-100 text-gray-700 px-4 py-2.5 rounded-lg hover:bg-gray-200 text-sm font-medium">
                        <i class="fas fa-times mr-1"></i>Limpar
                    </a>
                </div>
            </form>

            {f'<div class="mt-3 flex items-center flex-wrap">{filter_pills}</div>' if filter_pills else ''}
        </div>

        <!-- Executions List -->
        {executions_list}

        <!-- Pagination -->
        {pagination}
    </main>
    """


def build_query_string(**kwargs) -> str:
    """Build query string from kwargs."""
    params = []
    for key, value in kwargs.items():
        if value:
            params.append(f"{key}={value}")
    return "&".join(params)
