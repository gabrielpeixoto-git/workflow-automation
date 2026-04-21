"""Web routes and templates."""

from app.web.workflows_new import router as workflows_router
from app.web.executions_new import router as executions_router
from app.web.dashboard import router as dashboard_router
from app.web.components import get_base_layout, get_empty_state, get_status_badge, get_trigger_icon

__all__ = [
    "workflows_router",
    "executions_router",
    "dashboard_router",
    "get_base_layout",
    "get_empty_state",
    "get_status_badge",
    "get_trigger_icon",
]
