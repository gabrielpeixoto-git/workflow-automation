"""Celery application configuration."""

from celery import Celery
from celery.signals import task_failure, task_prerun, task_success

from app.core.config import get_settings
from app.core.logging_config import configure_logging, get_logger

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(__name__)

celery_app = Celery(
    "workflow_automation",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.workflow_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max per task
    task_soft_time_limit=3000,  # Soft limit 50 min
    worker_prefetch_multiplier=1,  # One task at a time per worker
    task_acks_late=True,  # Ack after task completion
    result_expires=3600 * 24 * 7,  # Results expire after 7 days
    broker_connection_retry_on_startup=True,
    # Retry configuration
    task_default_retry_delay=60,  # 1 minute
    task_max_retries=3,
)

# Beat schedule - será configurado dinamicamente
celery_app.conf.beat_schedule = {
    "reload-scheduled-workflows": {
        "task": "app.celery_app.reload_schedule_task",
        "schedule": 300.0,  # Every 5 minutes
    },
}


@celery_app.task
async def reload_schedule_task():
    """Periodic task to reload beat schedule."""
    count = await reload_beat_schedule()
    return {"scheduled_workflows": count}


@task_prerun.connect
def task_prerun_handler(task_id, task, args, kwargs, **extras):
    """Log task start."""
    logger.info(
        "task_started",
        task_id=task_id,
        task_name=task.name,
    )


@task_success.connect
def task_success_handler(sender, result, **kwargs):
    """Log task success."""
    logger.info(
        "task_completed",
        task_id=sender.request.id,
        task_name=sender.name,
    )


@task_failure.connect
def task_failure_handler(sender, task_id, exception, args, kwargs, traceback, einfo, **extras):
    """Log task failure."""
    logger.error(
        "task_failed",
        task_id=task_id,
        task_name=sender.name,
        exception=str(exception),
    )


async def reload_beat_schedule():
    """Reload beat schedule with scheduled workflows from database."""
    import asyncio
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.db.database import AsyncSessionLocal
    from app.models.workflow import Workflow, StepType, TriggerType
    
    try:
        async with AsyncSessionLocal() as db:
            # Find all workflows with scheduled triggers
            result = await db.execute(
                select(Workflow)
                .options(selectinload(Workflow.steps))
                .where(
                    Workflow.status == "active",
                    Workflow.deleted_at.is_(None),
                )
            )
            workflows = result.scalars().all()
            
            new_schedule = {}
            
            for workflow in workflows:
                # Find scheduled trigger step
                for step in workflow.steps:
                    if (
                        step.step_type == StepType.TRIGGER 
                        and step.trigger_type == TriggerType.SCHEDULED
                        and step.is_active
                    ):
                        cron = step.config.get("cron", "")
                        if cron:
                            task_name = f"scheduled_workflow_{workflow.id}"
                            new_schedule[task_name] = {
                                "task": "app.tasks.workflow_tasks.execute_scheduled_workflow",
                                "schedule": celery.schedules.crontab(**_parse_cron(cron)),
                                "args": (str(workflow.id), str(workflow.organization_id)),
                            }
                            logger.info(
                                "added_scheduled_workflow",
                                workflow_id=str(workflow.id),
                                cron=cron,
                            )
            
            # Update the schedule
            celery_app.conf.beat_schedule = new_schedule
            
            logger.info(
                "beat_schedule_reloaded",
                scheduled_count=len(new_schedule),
            )
            
            return len(new_schedule)
            
    except Exception as e:
        logger.exception("reload_beat_schedule_error", error=str(e))
        return 0


def _parse_cron(cron: str) -> dict:
    """Parse cron expression to celery crontab kwargs.
    
    Format: minute hour day_of_month month day_of_week
    Example: 0 9 * * * (every day at 9:00 AM)
    """
    parts = cron.split()
    if len(parts) != 5:
        # Default to every hour if invalid
        return {"minute": 0}
    
    minute, hour, day_of_month, month, day_of_week = parts
    
    kwargs = {}
    
    if minute != "*":
        kwargs["minute"] = int(minute)
    if hour != "*":
        kwargs["hour"] = int(hour)
    if day_of_month != "*":
        kwargs["day_of_month"] = int(day_of_month)
    if month != "*":
        kwargs["month_of_year"] = int(month)
    if day_of_week != "*":
        kwargs["day_of_week"] = int(day_of_week)
    
    return kwargs


# Import celery schedules
import celery.schedules
