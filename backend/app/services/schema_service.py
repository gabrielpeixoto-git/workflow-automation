"""JSON Schema validation service."""

import json
import time
from datetime import datetime
from typing import Any
from uuid import UUID

import jsonschema
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging_config import get_logger
from app.models.schema import (
    SchemaStatus,
    SchemaType,
    SchemaValidationLog,
    ValidationResult,
    WorkflowSchema,
)
from app.models.workflow import Workflow

logger = get_logger(__name__)


class SchemaValidationError(Exception):
    """Schema validation error."""
    
    def __init__(self, message: str, errors: list | None = None):
        self.message = message
        self.errors = errors or []
        super().__init__(message)


class SchemaService:
    """Service for JSON Schema validation."""
    
    @staticmethod
    async def create_schema(
        db: AsyncSession,
        workflow: Workflow,
        name: str,
        schema_definition: dict,
        schema_type: SchemaType = SchemaType.JSON_SCHEMA,
        description: str | None = None,
        is_required: bool = True,
        fail_on_error: bool = True,
    ) -> WorkflowSchema:
        """Create a new schema for workflow validation."""
        schema = WorkflowSchema(
            workflow_id=workflow.id,
            organization_id=workflow.organization_id,
            name=name,
            schema_type=schema_type,
            schema_definition=schema_definition,
            description=description,
            is_required=is_required,
            fail_on_error=fail_on_error,
            status=SchemaStatus.ACTIVE,
            version=1,
        )
        db.add(schema)
        await db.commit()
        await db.refresh(schema)
        
        logger.info(
            "Schema created",
            schema_id=str(schema.id),
            workflow_id=str(workflow.id),
            schema_type=schema_type.value,
        )
        return schema
    
    @staticmethod
    async def update_schema(
        db: AsyncSession,
        schema: WorkflowSchema,
        name: str | None = None,
        schema_definition: dict | None = None,
        description: str | None = None,
        is_required: bool | None = None,
        fail_on_error: bool | None = None,
        status: SchemaStatus | None = None,
    ) -> WorkflowSchema:
        """Update schema (creates new version)."""
        # Create new version
        new_schema = WorkflowSchema(
            workflow_id=schema.workflow_id,
            organization_id=schema.organization_id,
            name=name or schema.name,
            schema_type=schema.schema_type,
            schema_definition=schema_definition or schema.schema_definition,
            description=description if description is not None else schema.description,
            is_required=is_required if is_required is not None else schema.is_required,
            fail_on_error=fail_on_error if fail_on_error is not None else schema.fail_on_error,
            status=status or schema.status,
            version=schema.version + 1,
            previous_version_id=schema.id,
        )
        db.add(new_schema)
        
        # Mark old schema as deprecated
        schema.status = SchemaStatus.DEPRECATED
        schema.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(new_schema)
        
        logger.info(
            "Schema updated to new version",
            schema_id=str(new_schema.id),
            previous_id=str(schema.id),
            version=new_schema.version,
        )
        return new_schema
    
    @staticmethod
    async def get_schemas_by_workflow(
        db: AsyncSession,
        workflow_id: UUID,
        status: SchemaStatus | None = SchemaStatus.ACTIVE,
    ) -> list[WorkflowSchema]:
        """Get schemas for a workflow."""
        query = select(WorkflowSchema).where(
            WorkflowSchema.workflow_id == workflow_id,
        )
        if status:
            query = query.where(WorkflowSchema.status == status)
        
        result = await db.execute(query)
        return result.scalars().all()
    
    @staticmethod
    async def get_schema(
        db: AsyncSession,
        schema_id: UUID,
    ) -> WorkflowSchema | None:
        """Get schema by ID."""
        result = await db.execute(
            select(WorkflowSchema).where(WorkflowSchema.id == schema_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def delete_schema(
        db: AsyncSession,
        schema: WorkflowSchema,
    ) -> None:
        """Delete schema (soft delete by marking as deprecated)."""
        schema.status = SchemaStatus.DEPRECATED
        schema.updated_at = datetime.utcnow()
        await db.commit()
        
        logger.info("Schema deprecated", schema_id=str(schema.id))
    
    @staticmethod
    async def validate_payload(
        db: AsyncSession,
        schema: WorkflowSchema,
        payload: dict,
        execution_id: UUID | None = None,
    ) -> dict[str, Any]:
        """Validate payload against schema.
        
        Returns validation result and logs the attempt.
        """
        start_time = time.time()
        errors = []
        result = ValidationResult.VALID
        error_message = None
        
        try:
            if schema.schema_type == SchemaType.JSON_SCHEMA:
                errors = SchemaService._validate_json_schema(
                    payload, schema.schema_definition
                )
            elif schema.schema_type == SchemaType.JSON_LOGIC:
                errors = SchemaService._validate_json_logic(
                    payload, schema.schema_definition
                )
            elif schema.schema_type == SchemaType.REGEX:
                errors = SchemaService._validate_regex(
                    payload, schema.schema_definition
                )
            else:
                errors = ["Unknown schema type"]
            
            if errors:
                result = ValidationResult.INVALID
                error_message = schema.error_message_template.format(
                    error=errors[0]
                ) if schema.error_message_template else f"Validation failed: {errors[0]}"
                
        except Exception as e:
            result = ValidationResult.ERROR
            error_message = f"Validation error: {str(e)}"
            errors = [str(e)]
            logger.error(
                "Schema validation error",
                schema_id=str(schema.id),
                error=str(e),
            )
        
        duration = (time.time() - start_time) * 1000  # Convert to ms
        
        # Log validation attempt
        log = SchemaValidationLog(
            schema_id=schema.id,
            workflow_id=schema.workflow_id,
            execution_id=execution_id,
            organization_id=schema.organization_id,
            result=result,
            payload=payload if result != ValidationResult.VALID else None,
            errors=errors if errors else None,
            error_message=error_message,
            validated_at=datetime.utcnow(),
            validation_duration_ms=duration,
        )
        db.add(log)
        await db.commit()
        
        return {
            "valid": result == ValidationResult.VALID,
            "result": result.value,
            "errors": errors,
            "error_message": error_message,
            "validation_duration_ms": duration,
        }
    
    @staticmethod
    def _validate_json_schema(
        payload: dict,
        schema_definition: dict,
    ) -> list[str]:
        """Validate payload using JSON Schema (Draft 7)."""
        validator = jsonschema.Draft7Validator(schema_definition)
        errors = []
        
        for error in validator.iter_errors(payload):
            errors.append(f"{error.path}: {error.message}")
        
        return errors
    
    @staticmethod
    def _validate_json_logic(
        payload: dict,
        logic_definition: dict,
    ) -> list[str]:
        """Validate payload using JSON Logic rules."""
        try:
            # Simple JSON Logic implementation
            # In production, use json-logic-py library
            if "and" in logic_definition:
                for rule in logic_definition["and"]:
                    if not SchemaService._evaluate_json_logic_rule(payload, rule):
                        return [f"Failed rule: {json.dumps(rule)}"]
            elif "or" in logic_definition:
                passed = False
                for rule in logic_definition["or"]:
                    if SchemaService._evaluate_json_logic_rule(payload, rule):
                        passed = True
                        break
                if not passed:
                    return [f"Failed all rules: {json.dumps(logic_definition)}"]
            else:
                if not SchemaService._evaluate_json_logic_rule(payload, logic_definition):
                    return [f"Failed rule: {json.dumps(logic_definition)}"]
            
            return []
        except Exception as e:
            return [f"JSON Logic error: {str(e)}"]
    
    @staticmethod
    def _evaluate_json_logic_rule(payload: dict, rule: dict) -> bool:
        """Evaluate a single JSON Logic rule."""
        if "==" in rule:
            return payload.get(rule["=="][0]) == rule["=="][1]
        elif "!=" in rule:
            return payload.get(rule["!="][0]) != rule["!="][1]
        elif ">" in rule:
            return payload.get(rule[">"][0], 0) > rule[">"][1]
        elif "<" in rule:
            return payload.get(rule["<"][0], 0) < rule["<"][1]
        elif ">=" in rule:
            return payload.get(rule[">="][0], 0) >= rule[">="][1]
        elif "<=" in rule:
            return payload.get(rule["<="][0], 0) <= rule["<="][1]
        elif "in" in rule:
            return payload.get(rule["in"][0]) in rule["in"][1]
        elif "has" in rule:
            return rule["has"] in payload
        return True
    
    @staticmethod
    def _validate_regex(
        payload: dict,
        patterns: dict,
    ) -> list[str]:
        """Validate payload using regex patterns."""
        import re
        
        errors = []
        for field, pattern in patterns.items():
            value = payload.get(field)
            if value is not None:
                if not re.match(pattern, str(value)):
                    errors.append(f"Field '{field}' does not match pattern '{pattern}'")
        
        return errors
    
    @staticmethod
    async def validate_workflow_payload(
        db: AsyncSession,
        workflow: Workflow,
        payload: dict,
        execution_id: UUID | None = None,
    ) -> dict[str, Any]:
        """Validate payload against all active schemas for a workflow."""
        schemas = await SchemaService.get_schemas_by_workflow(
            db, workflow.id, SchemaStatus.ACTIVE
        )
        
        if not schemas:
            return {
                "valid": True,
                "result": "no_schemas",
                "schema_validations": [],
            }
        
        all_valid = True
        failed_required = False
        schema_results = []
        
        for schema in schemas:
            validation = await SchemaService.validate_payload(
                db, schema, payload, execution_id
            )
            
            schema_results.append({
                "schema_id": str(schema.id),
                "schema_name": schema.name,
                "valid": validation["valid"],
                "errors": validation["errors"],
            })
            
            if not validation["valid"]:
                all_valid = False
                if schema.is_required and schema.fail_on_error:
                    failed_required = True
        
        return {
            "valid": all_valid and not failed_required,
            "result": "valid" if all_valid else "invalid",
            "failed_required": failed_required,
            "schema_validations": schema_results,
        }
    
    @staticmethod
    async def get_validation_logs(
        db: AsyncSession,
        schema_id: UUID | None = None,
        workflow_id: UUID | None = None,
        result: ValidationResult | None = None,
        limit: int = 50,
    ) -> list[SchemaValidationLog]:
        """Get validation logs."""
        query = select(SchemaValidationLog)
        
        if schema_id:
            query = query.where(SchemaValidationLog.schema_id == schema_id)
        if workflow_id:
            query = query.where(SchemaValidationLog.workflow_id == workflow_id)
        if result:
            query = query.where(SchemaValidationLog.result == result)
        
        query = query.order_by(SchemaValidationLog.validated_at.desc()).limit(limit)
        
        result = await db.execute(query)
        return result.scalars().all()
