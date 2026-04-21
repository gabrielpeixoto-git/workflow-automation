"""Workflow API routes."""

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Query, status

from app.api.schemas import WorkflowCreate, WorkflowResponse, WorkflowUpdate
from app.core.deps import (
    CurrentUser, DBSession, RequireEditor, get_client_info,
    RequireWorkflowView, RequireWorkflowCreate, RequireWorkflowEdit,
    RequireWorkflowDelete, RequireWorkflowActivate,
)
from app.core.logging_config import get_logger
from app.models.workflow import WorkflowStatus
from app.services.workflow_service import WorkflowService

logger = get_logger(__name__)
router = APIRouter()


@router.get("", response_model=list[WorkflowResponse])
async def list_workflows(
    db: DBSession,
    user: RequireWorkflowView,
    status: WorkflowStatus | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> Any:
    """List workflows for current user's organization."""
    workflows = await WorkflowService.get_workflows(
        db=db,
        organization_id=user.organization_id,
        status=status,
        skip=skip,
        limit=limit,
    )
    return workflows


@router.post("", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    request: Request,
    data: WorkflowCreate,
    db: DBSession,
    user: RequireWorkflowCreate,
) -> Any:
    """Create a new workflow."""
    ip_address, user_agent = get_client_info(request)
    
    workflow = await WorkflowService.create_workflow(
        db=db,
        user=user,
        data=data,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return workflow


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: UUID,
    db: DBSession,
    user: RequireWorkflowView,
) -> Any:
    """Get workflow by ID."""
    workflow = await WorkflowService.get_workflow(
        db=db,
        workflow_id=workflow_id,
        organization_id=user.organization_id,
    )
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )
    return workflow


@router.put("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    request: Request,
    workflow_id: UUID,
    data: WorkflowUpdate,
    db: DBSession,
    user: RequireWorkflowEdit,
) -> Any:
    """Update workflow."""
    workflow = await WorkflowService.get_workflow(
        db=db,
        workflow_id=workflow_id,
        organization_id=user.organization_id,
    )
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )
    
    ip_address, user_agent = get_client_info(request)
    
    workflow = await WorkflowService.update_workflow(
        db=db,
        workflow=workflow,
        user=user,
        data=data,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return workflow


@router.delete("/{workflow_id}")
async def delete_workflow(
    request: Request,
    workflow_id: UUID,
    db: DBSession,
    user: RequireWorkflowDelete,
) -> dict[str, str]:
    """Delete workflow (soft delete)."""
    workflow = await WorkflowService.get_workflow(
        db=db,
        workflow_id=workflow_id,
        organization_id=user.organization_id,
    )
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )
    
    ip_address, user_agent = get_client_info(request)
    
    await WorkflowService.delete_workflow(
        db=db,
        workflow=workflow,
        user=user,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return {"message": "Workflow deleted successfully"}


@router.post("/{workflow_id}/activate", response_model=WorkflowResponse)
async def activate_workflow(
    request: Request,
    workflow_id: UUID,
    db: DBSession,
    user: RequireWorkflowActivate,
) -> Any:
    """Activate workflow."""
    workflow = await WorkflowService.get_workflow(
        db=db,
        workflow_id=workflow_id,
        organization_id=user.organization_id,
    )
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )
    
    ip_address, user_agent = get_client_info(request)
    
    workflow = await WorkflowService.activate_workflow(
        db=db,
        workflow=workflow,
        user=user,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return workflow


@router.post("/{workflow_id}/deactivate", response_model=WorkflowResponse)
async def deactivate_workflow(
    request: Request,
    workflow_id: UUID,
    db: DBSession,
    user: RequireEditor,
) -> Any:
    """Deactivate workflow."""
    workflow = await WorkflowService.get_workflow(
        db=db,
        workflow_id=workflow_id,
        organization_id=user.organization_id,
    )
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )
    
    ip_address, user_agent = get_client_info(request)
    
    workflow = await WorkflowService.deactivate_workflow(
        db=db,
        workflow=workflow,
        user=user,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return workflow


@router.post("/{workflow_id}/duplicate", response_model=WorkflowResponse)
async def duplicate_workflow(
    request: Request,
    workflow_id: UUID,
    db: DBSession,
    user: RequireEditor,
    new_name: str | None = None,
) -> Any:
    """Duplicate workflow."""
    workflow = await WorkflowService.get_workflow(
        db=db,
        workflow_id=workflow_id,
        organization_id=user.organization_id,
    )
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )
    
    ip_address, user_agent = get_client_info(request)
    
    new_workflow = await WorkflowService.duplicate_workflow(
        db=db,
        workflow=workflow,
        user=user,
        new_name=new_name,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return new_workflow


@router.post("/reload-schedule", status_code=status.HTTP_200_OK)
async def reload_schedule(
    user: CurrentUser,
) -> dict:
    """Reload beat schedule with scheduled workflows.
    
    This endpoint reloads the Celery Beat schedule to include
    all workflows with scheduled triggers.
    """
    from app.celery_app import reload_beat_schedule
    
    try:
        count = await reload_beat_schedule()
        logger.info(
            "schedule_reloaded_manually",
            user_id=str(user.id),
            scheduled_count=count,
        )
        return {
            "status": "success",
            "scheduled_workflows": count,
            "message": f"{count} workflows agendados recarregados",
        }
    except Exception as e:
        logger.exception("reload_schedule_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao recarregar schedule: {str(e)}",
        )


@router.post("/test-email", status_code=status.HTTP_200_OK)
async def test_email_config(
    user: CurrentUser,
    db: DBSession,
) -> dict:
    """Test SMTP email configuration.
    
    Sends a test email to verify SMTP settings are working.
    """
    from app.core.config import get_settings
    from app.services.actions import execute_email_action
    
    settings = get_settings()
    
    if not settings.smtp_host:
        return {
            "status": "warning",
            "configured": False,
            "message": "SMTP não configurado. Configure SMTP_HOST, SMTP_USER e SMTP_PASSWORD.",
            "current_settings": {
                "smtp_host": settings.smtp_host,
                "smtp_port": settings.smtp_port,
                "smtp_from": settings.smtp_from,
                "smtp_user": settings.smtp_user,
                "has_password": bool(settings.smtp_password),
            },
        }
    
    try:
        # Send test email
        test_context = {
            "user_name": user.full_name or user.email,
            "user_email": user.email,
            "timestamp": str(datetime.utcnow()),
        }
        
        result = await execute_email_action(
            config={
                "to": user.email,
                "subject": "Teste de Configuração SMTP - Workflow Automation",
                "body": f"""Olá {{{{user_name}}}},

Este é um email de teste do sistema Workflow Automation.

✅ Se você está recebendo este email, a configuração SMTP está funcionando corretamente!

Detalhes:
- Usuário: {{{{user_email}}}}
- Horário: {{{{timestamp}}}}
- Servidor SMTP: {settings.smtp_host}:{settings.smtp_port}

Atenciosamente,
Sistema Workflow Automation
""",
            },
            context=test_context,
        )
        
        logger.info("Email test sent to %s via %s", user.email, settings.smtp_host)
        
        return {
            "status": "success",
            "configured": True,
            "email_sent": result.get("email_sent"),
            "to": result.get("to"),
            "message": f"Email de teste enviado com sucesso para {user.email}!",
            "smtp_config": {
                "host": settings.smtp_host,
                "port": settings.smtp_port,
                "from": settings.smtp_from,
                "user": settings.smtp_user,
            },
        }
        
    except Exception as e:
        logger.exception("email_test_failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Falha ao enviar email de teste: {str(e)}",
        )
