"""Export API routes for CSV and PDF generation."""

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, DBSession, RequireAuditView, RequireWorkflowView
from app.core.logging_config import get_logger
from app.models.audit_log import AuditAction, AuditLog
from app.models.execution import ExecutionStatus, WorkflowExecution
from app.models.workflow import Workflow
from app.services.export_service import ExportService

logger = get_logger(__name__)
router = APIRouter(prefix="/export", tags=["export"])


# Request/Response Schemas

class ExportAuditLogsRequest(BaseModel):
    """Export audit logs request."""
    
    format: str = Field(default="csv", pattern="^(csv|pdf)$")
    action: AuditAction | None = None
    resource_type: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None


class ExportExecutionsRequest(BaseModel):
    """Export executions request."""
    
    format: str = Field(default="csv", pattern="^(csv|pdf)$")
    workflow_id: UUID | None = None
    status: ExecutionStatus | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None


class ExportWorkflowsRequest(BaseModel):
    """Export workflows request."""
    
    format: str = Field(default="csv", pattern="^(csv|pdf)$")
    include_inactive: bool = Field(default=False)


@router.post("/audit-logs")
async def export_audit_logs(
    request: ExportAuditLogsRequest,
    db: DBSession,
    user: RequireAuditView,
) -> Any:
    """Export audit logs to CSV or PDF.
    
    Returns:
        CSV file or PDF report with audit logs
    """
    # Build query
    query = select(AuditLog).where(
        AuditLog.organization_id == user.organization_id
    ).order_by(AuditLog.created_at.desc())
    
    # Apply filters
    if request.action:
        query = query.where(AuditLog.action == request.action)
    if request.resource_type:
        query = query.where(AuditLog.resource_type == request.resource_type)
    if request.date_from:
        query = query.where(AuditLog.created_at >= request.date_from)
    if request.date_to:
        query = query.where(AuditLog.created_at <= request.date_to)
    
    # Limit to 10,000 records for performance
    query = query.limit(10000)
    
    result = await db.execute(query)
    logs = result.scalars().all()
    
    if not logs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No audit logs found for the specified criteria",
        )
    
    if request.format == "csv":
        # Generate CSV
        csv_content = ExportService.export_audit_logs_to_csv(logs)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"audit_logs_{timestamp}.csv"
        
        return PlainTextResponse(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            },
        )
    
    else:  # PDF
        # Generate PDF report
        data = {
            "Resumo": {
                "Total de Registros": len(logs),
                "Organização": str(user.organization_id),
                "Exportado por": user.email,
            },
            "Logs": [
                {
                    "Data": log.created_at.strftime("%d/%m/%Y %H:%M") if log.created_at else "-",
                    "Usuário": log.user_email or "Sistema",
                    "Ação": log.action.value if log.action else "-",
                    "Tipo": log.resource_type or "-",
                    "Descrição": (log.description or "-")[:50],
                }
                for log in logs[:100]  # Limit to first 100 for PDF
            ],
        }
        
        pdf_bytes = ExportService.generate_pdf_report(
            title="Relatório de Auditoria",
            data=data,
            date_from=request.date_from,
            date_to=request.date_to,
        )
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"audit_logs_{timestamp}.pdf"
        
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            },
        )


@router.post("/executions")
async def export_executions(
    request: ExportExecutionsRequest,
    db: DBSession,
    user: CurrentUser,
) -> Any:
    """Export executions to CSV or PDF.
    
    Returns:
        CSV file or PDF report with execution data
    """
    # Build query
    query = select(WorkflowExecution).where(
        WorkflowExecution.organization_id == user.organization_id
    ).order_by(WorkflowExecution.created_at.desc())
    
    # Apply filters
    if request.workflow_id:
        query = query.where(WorkflowExecution.workflow_id == request.workflow_id)
    if request.status:
        query = query.where(WorkflowExecution.status == request.status)
    if request.date_from:
        query = query.where(WorkflowExecution.created_at >= request.date_from)
    if request.date_to:
        query = query.where(WorkflowExecution.created_at <= request.date_to)
    
    # Limit to 10,000 records
    query = query.limit(10000)
    
    result = await db.execute(query)
    executions = result.scalars().all()
    
    if not executions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No executions found for the specified criteria",
        )
    
    if request.format == "csv":
        # Generate CSV
        csv_content = ExportService.export_executions_to_csv(executions)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"executions_{timestamp}.csv"
        
        return PlainTextResponse(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            },
        )
    
    else:  # PDF
        # Calculate statistics
        status_counts = {}
        total_duration = 0
        count_with_duration = 0
        
        for exec in executions:
            status_val = exec.status.value if exec.status else "unknown"
            status_counts[status_val] = status_counts.get(status_val, 0) + 1
            if exec.duration_seconds:
                total_duration += exec.duration_seconds
                count_with_duration += 1
        
        avg_duration = total_duration / count_with_duration if count_with_duration > 0 else 0
        
        data = {
            "Resumo": {
                "Total de Execuções": len(executions),
                "Duração Média": f"{avg_duration:.2f}s",
            },
            "Por Status": status_counts,
            "Execuções Recentes": [
                {
                    "ID": str(exec.id)[:8],
                    "Status": exec.status.value if exec.status else "-",
                    "Início": exec.started_at.strftime("%d/%m %H:%M") if exec.started_at else "-",
                    "Duração": f"{exec.duration_seconds}s" if exec.duration_seconds else "-",
                }
                for exec in executions[:50]
            ],
        }
        
        pdf_bytes = ExportService.generate_pdf_report(
            title="Relatório de Execuções",
            data=data,
            date_from=request.date_from,
            date_to=request.date_to,
        )
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"executions_{timestamp}.pdf"
        
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            },
        )


@router.post("/workflows")
async def export_workflows(
    request: ExportWorkflowsRequest,
    db: DBSession,
    user: RequireWorkflowView,
) -> Any:
    """Export workflows to CSV or PDF.
    
    Returns:
        CSV file or PDF report with workflow data
    """
    # Build query
    query = select(Workflow).where(
        Workflow.organization_id == user.organization_id,
    )
    
    # Include or exclude inactive
    if not request.include_inactive:
        from app.models.workflow import WorkflowStatus
        query = query.where(Workflow.status == WorkflowStatus.ACTIVE)
    
    query = query.order_by(Workflow.created_at.desc()).limit(10000)
    
    result = await db.execute(query)
    workflows = result.scalars().all()
    
    if not workflows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No workflows found",
        )
    
    if request.format == "csv":
        # Load steps for each workflow
        for wf in workflows:
            await db.refresh(wf, ["steps"])
        
        # Generate CSV
        csv_content = ExportService.export_workflows_to_csv(workflows)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"workflows_{timestamp}.csv"
        
        return PlainTextResponse(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            },
        )
    
    else:  # PDF
        # Calculate statistics
        status_counts = {}
        total_steps = 0
        
        for wf in workflows:
            status_val = wf.status.value if wf.status else "unknown"
            status_counts[status_val] = status_counts.get(status_val, 0) + 1
            total_steps += len(wf.steps) if wf.steps else 0
        
        data = {
            "Resumo": {
                "Total de Workflows": len(workflows),
                "Média de Passos": f"{total_steps / len(workflows):.1f}" if workflows else "0",
            },
            "Por Status": status_counts,
            "Workflows": [
                {
                    "Nome": wf.name,
                    "Slug": wf.slug,
                    "Status": wf.status.value if wf.status else "-",
                    "Versão": wf.version,
                    "Passos": len(wf.steps) if wf.steps else 0,
                }
                for wf in workflows[:50]
            ],
        }
        
        pdf_bytes = ExportService.generate_pdf_report(
            title="Relatório de Workflows",
            data=data,
        )
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"workflows_{timestamp}.pdf"
        
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            },
        )


@router.get("/formats")
async def list_export_formats(
    user: CurrentUser,
) -> Any:
    """List available export formats and options."""
    return {
        "formats": [
            {
                "value": "csv",
                "label": "CSV (Comma Separated Values)",
                "description": "Formato de dados estruturados compatível com Excel e Google Sheets",
                "mime_type": "text/csv",
                "extension": ".csv",
            },
            {
                "value": "pdf",
                "label": "PDF (Portable Document Format)",
                "description": "Relatório formatado em PDF com estatísticas",
                "mime_type": "application/pdf",
                "extension": ".pdf",
            },
        ],
        "entities": [
            {
                "value": "audit-logs",
                "label": "Logs de Auditoria",
                "description": "Histórico de ações do sistema",
                "permissions": ["audit:view"],
            },
            {
                "value": "executions",
                "label": "Execuções",
                "description": "Histórico de execuções de workflows",
                "permissions": ["execution:view"],
            },
            {
                "value": "workflows",
                "label": "Workflows",
                "description": "Lista de workflows e suas configurações",
                "permissions": ["workflow:view"],
            },
        ],
    }
