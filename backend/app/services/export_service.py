"""Export service for CSV and PDF generation."""

import csv
import io
from datetime import datetime
from typing import Any
from uuid import UUID

from app.core.logging_config import get_logger
from app.models.audit_log import AuditLog
from app.models.execution import WorkflowExecution
from app.models.workflow import Workflow

logger = get_logger(__name__)


class ExportService:
    """Service for exporting data to various formats."""
    
    @staticmethod
    def export_to_csv(data: list[dict], headers: list[str]) -> str:
        """Export data to CSV format.
        
        Returns:
            CSV content as string
        """
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader()
        writer.writerows(data)
        return output.getvalue()
    
    @staticmethod
    def export_audit_logs_to_csv(logs: list[AuditLog]) -> str:
        """Export audit logs to CSV."""
        data = []
        for log in logs:
            data.append({
                "id": str(log.id),
                "timestamp": log.created_at.isoformat() if log.created_at else "",
                "user_email": log.user_email or "Sistema",
                "action": log.action.value if log.action else "",
                "resource_type": log.resource_type or "",
                "resource_id": log.resource_id or "",
                "description": log.description or "",
                "ip_address": log.ip_address or "",
            })
        
        headers = [
            "id", "timestamp", "user_email", "action", "resource_type",
            "resource_id", "description", "ip_address"
        ]
        
        return ExportService.export_to_csv(data, headers)
    
    @staticmethod
    def export_executions_to_csv(executions: list[WorkflowExecution]) -> str:
        """Export executions to CSV."""
        data = []
        for exec in executions:
            data.append({
                "id": str(exec.id),
                "workflow_id": str(exec.workflow_id),
                "status": exec.status.value if exec.status else "",
                "trigger_type": exec.trigger_type or "",
                "started_at": exec.started_at.isoformat() if exec.started_at else "",
                "completed_at": exec.completed_at.isoformat() if exec.completed_at else "",
                "duration_seconds": exec.duration_seconds or 0,
                "error_message": (exec.error_message or "")[:200],  # Limit length
            })
        
        headers = [
            "id", "workflow_id", "status", "trigger_type", "started_at",
            "completed_at", "duration_seconds", "error_message"
        ]
        
        return ExportService.export_to_csv(data, headers)
    
    @staticmethod
    def export_workflows_to_csv(workflows: list[Workflow]) -> str:
        """Export workflows to CSV."""
        data = []
        for wf in workflows:
            data.append({
                "id": str(wf.id),
                "name": wf.name,
                "slug": wf.slug,
                "description": (wf.description or "")[:200],
                "status": wf.status.value if wf.status else "",
                "version": wf.version,
                "created_at": wf.created_at.isoformat() if wf.created_at else "",
                "updated_at": wf.updated_at.isoformat() if wf.updated_at else "",
                "steps_count": len(wf.steps) if wf.steps else 0,
            })
        
        headers = [
            "id", "name", "slug", "description", "status",
            "version", "created_at", "updated_at", "steps_count"
        ]
        
        return ExportService.export_to_csv(data, headers)
    
    @staticmethod
    def generate_pdf_report(
        title: str,
        data: dict[str, Any],
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> bytes:
        """Generate a simple PDF report.
        
        Note: In production, use a proper PDF library like ReportLab or WeasyPrint.
        This is a simplified version using HTML to PDF conversion.
        """
        try:
            from weasyprint import HTML, CSS
            
            # Build HTML content
            html_content = ExportService._build_pdf_html(
                title, data, date_from, date_to
            )
            
            # Convert to PDF
            html = HTML(string=html_content)
            pdf_bytes = html.write_pdf()
            
            return pdf_bytes
            
        except ImportError:
            logger.warning("weasyprint not installed, using fallback")
            # Return a simple text representation as fallback
            return ExportService._generate_text_fallback(
                title, data, date_from, date_to
            ).encode("utf-8")
    
    @staticmethod
    def _build_pdf_html(
        title: str,
        data: dict[str, Any],
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> str:
        """Build HTML content for PDF."""
        date_range = ""
        if date_from and date_to:
            date_range = f"<p>Período: {date_from.strftime('%d/%m/%Y')} - {date_to.strftime('%d/%m/%Y')}</p>"
        
        # Build table rows from data
        rows = ""
        for section_name, section_data in data.items():
            if isinstance(section_data, list):
                rows += f"<tr><td colspan='2'><h3>{section_name}</h3></td></tr>"
                for item in section_data:
                    if isinstance(item, dict):
                        for key, value in item.items():
                            rows += f"<tr><td><strong>{key}</strong></td><td>{value}</td></tr>"
                    else:
                        rows += f"<tr><td>{item}</td><td></td></tr>"
            elif isinstance(section_data, dict):
                rows += f"<tr><td colspan='2'><h3>{section_name}</h3></td></tr>"
                for key, value in section_data.items():
                    rows += f"<tr><td><strong>{key}</strong></td><td>{value}</td></tr>"
            else:
                rows += f"<tr><td><strong>{section_name}</strong></td><td>{section_data}</td></tr>"
        
        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 40px;
        }}
        h1 {{
            color: #333;
            border-bottom: 2px solid #007bff;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #555;
            margin-top: 30px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #f5f5f5;
            font-weight: bold;
        }}
        .footer {{
            margin-top: 40px;
            font-size: 12px;
            color: #999;
            border-top: 1px solid #ddd;
            padding-top: 10px;
        }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    {date_range}
    <p>Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</p>
    
    <table>
        {rows}
    </table>
    
    <div class="footer">
        Workflow Automation System - Relatório Exportado
    </div>
</body>
</html>"""
    
    @staticmethod
    def _generate_text_fallback(
        title: str,
        data: dict[str, Any],
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> str:
        """Generate simple text fallback when PDF library not available."""
        lines = [
            "=" * 60,
            title,
            "=" * 60,
            "",
        ]
        
        if date_from and date_to:
            lines.append(f"Período: {date_from.strftime('%d/%m/%Y')} - {date_to.strftime('%d/%m/%Y')}")
            lines.append("")
        
        lines.append(f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        lines.append("")
        
        for section_name, section_data in data.items():
            lines.append("-" * 60)
            lines.append(section_name)
            lines.append("-" * 60)
            
            if isinstance(section_data, list):
                for i, item in enumerate(section_data, 1):
                    lines.append(f"\nItem {i}:")
                    if isinstance(item, dict):
                        for key, value in item.items():
                            lines.append(f"  {key}: {value}")
                    else:
                        lines.append(f"  {item}")
            elif isinstance(section_data, dict):
                for key, value in section_data.items():
                    lines.append(f"{key}: {value}")
            else:
                lines.append(str(section_data))
            
            lines.append("")
        
        lines.append("=" * 60)
        lines.append("Workflow Automation System - Relatório Exportado")
        lines.append("=" * 60)
        
        return "\n".join(lines)
