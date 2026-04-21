"""Action executors for workflow steps."""

import csv
import io
import json
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)
settings = get_settings()


async def execute_http_action(config: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Execute HTTP request action."""
    method = config.get("method", "GET").upper()
    url = config.get("url", "")
    headers = config.get("headers", {})
    timeout = config.get("timeout", 30)
    body_template = config.get("body", "")

    # Replace template variables in URL and body
    url = _render_template(url, context)
    body = _render_template(body_template, context) if body_template else None

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            if method == "GET":
                response = await client.get(url, headers=headers)
            elif method == "POST":
                response = await client.post(url, headers=headers, content=body)
            elif method == "PUT":
                response = await client.put(url, headers=headers, content=body)
            elif method == "PATCH":
                response = await client.patch(url, headers=headers, content=body)
            elif method == "DELETE":
                response = await client.delete(url, headers=headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

        response.raise_for_status()

        # Try to parse JSON response
        try:
            response_data = response.json()
        except json.JSONDecodeError:
            response_data = {"response_text": response.text}

        return {
            "http_status": response.status_code,
            "http_response": response_data,
        }

    except httpx.TimeoutException:
        raise Exception(f"HTTP request timeout after {timeout}s")
    except httpx.HTTPStatusError as e:
        raise Exception(f"HTTP error {e.response.status_code}: {e.response.text}")
    except Exception as e:
        raise Exception(f"HTTP request failed: {str(e)}")


async def execute_email_action(config: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Execute email action with SMTP support and file-based fallback."""
    import aiosmtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    from datetime import datetime
    import json
    
    to = config.get("to", "")
    subject = config.get("subject", "")
    body_template = config.get("body", "")
    cc = config.get("cc", "")
    bcc = config.get("bcc", "")
    is_html = config.get("is_html", False)

    # Render templates
    to = _render_template(to, context)
    subject = _render_template(subject, context)
    body = _render_template(body_template, context)
    cc = _render_template(cc, context) if cc else ""
    bcc = _render_template(bcc, context) if bcc else ""

    # Log the email attempt
    logger.info(
        "Email action: to=%s, subject=%s, smtp_host=%s",
        to,
        subject,
        settings.smtp_host or "not configured",
    )

    # Prepare email data
    email_data = {
        "to": to,
        "subject": subject,
        "body": body,
        "cc": cc,
        "bcc": bcc,
        "is_html": is_html,
        "from": settings.smtp_from if settings.smtp_host else "dev@workflow.local",
        "timestamp": datetime.utcnow().isoformat(),
    }

    # Check if SMTP is configured
    if not settings.smtp_host or settings.smtp_host == "sandbox.smtp.mailtrap.io":
        # Development mode: save email to file instead of sending
        email_file = settings.upload_dir / f"email_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        with open(email_file, "w", encoding="utf-8") as f:
            json.dump(email_data, f, indent=2, ensure_ascii=False)
        
        logger.info("Email saved to file (dev mode): %s", email_file)
        return {
            "email_sent": True,
            "to": to,
            "subject": subject,
            "mode": "development",
            "saved_to": str(email_file),
            "note": "Email salvo em arquivo (modo desenvolvimento). SMTP não envia emails reais.",
        }

    # Production mode: try to send via SMTP
    try:
        # Build email message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.smtp_from
        msg["To"] = to
        
        if cc:
            msg["Cc"] = cc
        if bcc:
            msg["Bcc"] = bcc

        # Attach body (HTML or plain text)
        if is_html:
            msg.attach(MIMEText(body, "html", "utf-8"))
        else:
            msg.attach(MIMEText(body, "plain", "utf-8"))

        # Connect and send via SMTP
        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user,
            password=settings.smtp_password,
            start_tls=True,
        )

        logger.info("Email sent successfully to %s", to)
        
        return {
            "email_sent": True,
            "to": to,
            "subject": subject,
            "from": settings.smtp_from,
            "smtp_host": settings.smtp_host,
        }
        
    except Exception as e:
        # If SMTP fails, save to file as fallback
        logger.error("SMTP failed, saving to file: %s", str(e))
        email_file = settings.upload_dir / f"email_failed_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        with open(email_file, "w", encoding="utf-8") as f:
            json.dump(email_data, f, indent=2, ensure_ascii=False)
        
        return {
            "email_sent": False,
            "to": to,
            "subject": subject,
            "smtp_error": str(e),
            "saved_to": str(email_file),
            "mode": "fallback",
            "note": "Falha no SMTP, email salvo em arquivo.",
        }


async def execute_database_action(
    config: dict[str, Any],
    context: dict[str, Any],
    db: AsyncSession,
) -> dict[str, Any]:
    """Execute database write action with real INSERT/UPSERT."""
    from sqlalchemy import text, insert, update
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from datetime import datetime
    
    table = config.get("table", "")
    operation = config.get("operation", "insert")
    field_mapping = config.get("field_mapping", {})
    
    if not table:
        raise ValueError("Table name is required")
    
    # Render values from context and special variables
    data = {}
    for key, template in field_mapping.items():
        if isinstance(template, str):
            if template == "{{now}}" or template == "now":
                data[key] = datetime.utcnow().isoformat()
            else:
                # Render template from context
                data[key] = _render_template(template, context)
        else:
            data[key] = template
    
    if not data:
        raise ValueError("No data to insert")
    
    try:
        if operation == "insert":
            # Simple INSERT
            columns = ", ".join(data.keys())
            placeholders = ", ".join([f":{k}" for k in data.keys()])
            sql = text(f"INSERT INTO {table} ({columns}) VALUES ({placeholders})")
            await db.execute(sql, data)
            await db.commit()
            
        elif operation == "upsert":
            # UPSERT (INSERT OR UPDATE) for PostgreSQL
            # This requires a unique constraint on the table
            columns = list(data.keys())
            
            # Build INSERT ... ON CONFLICT DO UPDATE
            set_clause = ", ".join([f"{k} = EXCLUDED.{k}" for k in columns])
            
            sql = text(f"""
                INSERT INTO {table} ({', '.join(columns)})
                VALUES ({', '.join([f':{k}' for k in columns])})
                ON CONFLICT DO UPDATE SET {set_clause}
            """)
            await db.execute(sql, data)
            await db.commit()
        else:
            raise ValueError(f"Unknown operation: {operation}")
        
        logger.info(
            "Database %s successful: table=%s, data=%s",
            operation,
            table,
            data,
        )
        
        return {
            "database_write": True,
            "operation": operation,
            "table": table,
            "data": data,
            "records": 1,
        }
        
    except Exception as e:
        await db.rollback()
        logger.error(
            "Database write failed: table=%s, error=%s",
            table,
            str(e),
        )
        raise ValueError(f"Database write failed: {str(e)}")


async def execute_transform_action(config: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Execute payload transformation action."""
    transformations = config.get("transformations", [])
    result = context.copy()

    for transform in transformations:
        op = transform.get("operation")
        target = transform.get("target_field")
        source = transform.get("source_field")
        value = transform.get("value")

        if op == "copy" and source:
            result[target] = context.get(source)
        elif op == "set":
            result[target] = _render_template(value, context) if isinstance(value, str) else value
        elif op == "delete" and target in result:
            del result[target]
        elif op == "rename" and source:
            result[target] = result.pop(source, None)

    return result


async def execute_export_csv_action(config: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Execute CSV export action."""
    data_path = config.get("data_path", "data")
    filename_template = config.get("filename", "export.csv")
    fields = config.get("fields", [])

    filename = _render_template(filename_template, context)

    # Get data from context
    data = context.get(data_path, [])
    if not isinstance(data, list):
        data = [data]

    # Generate CSV
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for row in data:
        if isinstance(row, dict):
            writer.writerow({k: str(row.get(k, "")) for k in fields})

    csv_content = output.getvalue()

    # Save to file
    file_path = settings.upload_dir / filename
    with open(file_path, "w", newline="") as f:
        f.write(csv_content)

    return {
        "csv_exported": True,
        "filename": filename,
        "file_path": str(file_path),
        "records": len(data),
    }


async def execute_export_pdf_action(config: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Execute PDF export action."""
    from weasyprint import HTML

    template_html = config.get("template", "")
    filename_template = config.get("filename", "export.pdf")

    filename = _render_template(filename_template, context)
    html_content = _render_template(template_html, context)

    # Save to file
    file_path = settings.upload_dir / filename
    HTML(string=html_content).write_pdf(str(file_path))

    return {
        "pdf_exported": True,
        "filename": filename,
        "file_path": str(file_path),
    }


async def execute_notify_action(config: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Execute notification action."""
    message_template = config.get("message", "")
    level = config.get("level", "info")

    message = _render_template(message_template, context)

    logger.info(
        "Notify action: level=%s, message=%s",
        level,
        message,
    )

    # In production, implement actual notification
    # This could be websocket, push notification, etc.

    return {
        "notified": True,
        "level": level,
        "message": message,
    }


def _render_template(template: str, context: dict[str, Any]) -> str:
    """Simple template rendering with {{variable}} syntax."""
    if not template:
        return template

    result = template
    for key, value in context.items():
        placeholder = f"{{{{{key}}}}}"
        if placeholder in result:
            result = result.replace(placeholder, str(value))

    return result
