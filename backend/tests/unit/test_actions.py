"""Tests for workflow actions."""

import pytest
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.actions import (
    execute_http_action,
    execute_email_action,
    execute_transform_action,
)


class TestHTTPAction:
    """Test HTTP request action."""

    @pytest.mark.asyncio
    async def test_http_get_request(self):
        """Test successful HTTP GET request."""
        config = {
            "method": "GET",
            "url": "https://api.example.com/users",
            "headers": {"Authorization": "Bearer token123"},
        }
        context = {"user_id": "123"}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"users": [{"id": 1, "name": "John"}]}
        mock_response.text = '{"users": [{"id": 1, "name": "John"}]}'
        mock_response.headers = {"content-type": "application/json"}

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            result = await execute_http_action(config, context)

        assert result["status_code"] == 200
        assert result["data"]["users"][0]["name"] == "John"
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_http_post_with_template(self):
        """Test HTTP POST with template rendering."""
        config = {
            "method": "POST",
            "url": "https://api.example.com/users",
            "body": '{"name": "{{user_name}}", "email": "{{user_email}}"}',
            "headers": {"Content-Type": "application/json"},
        }
        context = {"user_name": "Jane", "user_email": "jane@example.com"}

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": 1, "name": "Jane"}
        mock_response.text = '{"id": 1, "name": "Jane"}'
        mock_response.headers = {}

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            result = await execute_http_action(config, context)

        assert result["status_code"] == 201
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_http_error_response(self):
        """Test HTTP action with error response."""
        config = {
            "method": "GET",
            "url": "https://api.example.com/notfound",
        }
        context = {}

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not found"
        mock_response.json.side_effect = Exception("Not JSON")
        mock_response.headers = {}

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            result = await execute_http_action(config, context)

        assert result["status_code"] == 404
        assert result["success"] is False


class TestTransformAction:
    """Test payload transformation action."""

    @pytest.mark.asyncio
    async def test_transform_copy_operation(self):
        """Test copy operation in transform."""
        config = {
            "operations": [
                {"type": "copy", "from": "source_name", "to": "target_name"}
            ]
        }
        context = {"source_name": "John Doe", "other_field": "value"}

        result = await execute_transform_action(config, context)

        assert result["target_name"] == "John Doe"
        assert result["source_name"] == "John Doe"  # Original preserved

    @pytest.mark.asyncio
    async def test_transform_set_operation(self):
        """Test set operation in transform."""
        config = {
            "operations": [
                {"type": "set", "key": "new_field", "value": "static_value"}
            ]
        }
        context = {"existing": "data"}

        result = await execute_transform_action(config, context)

        assert result["new_field"] == "static_value"
        assert result["existing"] == "data"

    @pytest.mark.asyncio
    async def test_transform_rename_operation(self):
        """Test rename operation in transform."""
        config = {
            "operations": [
                {"type": "rename", "from": "old_name", "to": "new_name"}
            ]
        }
        context = {"old_name": "value123", "other": "data"}

        result = await execute_transform_action(config, context)

        assert result["new_name"] == "value123"
        assert "old_name" not in result
        assert result["other"] == "data"

    @pytest.mark.asyncio
    async def test_transform_delete_operation(self):
        """Test delete operation in transform."""
        config = {
            "operations": [
                {"type": "delete", "key": "sensitive_data"}
            ]
        }
        context = {"sensitive_data": "secret", "public": "open"}

        result = await execute_transform_action(config, context)

        assert "sensitive_data" not in result
        assert result["public"] == "open"

    @pytest.mark.asyncio
    async def test_transform_multiple_operations(self):
        """Test multiple operations in sequence."""
        config = {
            "operations": [
                {"type": "copy", "from": "input", "to": "output"},
                {"type": "set", "key": "processed", "value": True},
                {"type": "delete", "key": "temp"},
            ]
        }
        context = {"input": "test data", "temp": "temporary"}

        result = await execute_transform_action(config, context)

        assert result["output"] == "test data"
        assert result["processed"] is True
        assert "temp" not in result


class TestEmailAction:
    """Test email sending action."""

    @pytest.mark.asyncio
    async def test_email_dev_mode_saves_to_file(self, tmp_path, monkeypatch):
        """Test that email is saved to file in dev mode (no SMTP)."""
        # Mock settings
        mock_settings = MagicMock()
        mock_settings.smtp_host = None
        mock_settings.smtp_port = 587
        mock_settings.smtp_from = "test@example.com"
        mock_settings.upload_dir = tmp_path
        
        with patch("app.services.actions.settings", mock_settings):
            config = {
                "to": "recipient@example.com",
                "subject": "Test Email",
                "body": "Hello {{name}}!",
            }
            context = {"name": "World"}

            result = await execute_email_action(config, context)

        assert result["email_sent"] is True
        assert result["to"] == "recipient@example.com"
        assert result["subject"] == "Test Email"
        assert result["mode"] == "development"
        assert "saved_to" in result
        
        # Verify file was created
        saved_file = Path(result["saved_to"])
        assert saved_file.exists()
        
        # Verify file contents
        with open(saved_file, "r") as f:
            saved_data = json.load(f)
            assert saved_data["to"] == "recipient@example.com"
            assert saved_data["body"] == "Hello World!"

    @pytest.mark.asyncio
    async def test_email_with_cc_and_bcc(self, tmp_path):
        """Test email with CC and BCC fields."""
        mock_settings = MagicMock()
        mock_settings.smtp_host = None
        mock_settings.smtp_port = 587
        mock_settings.smtp_from = "sender@example.com"
        mock_settings.upload_dir = tmp_path
        
        with patch("app.services.actions.settings", mock_settings):
            config = {
                "to": "primary@example.com",
                "cc": "cc@example.com",
                "bcc": "bcc@example.com",
                "subject": "Test with CC/BCC",
                "body": "Test message",
            }
            context = {}

            result = await execute_email_action(config, context)
            saved_file = Path(result["saved_to"])
            
            with open(saved_file, "r") as f:
                saved_data = json.load(f)
                assert saved_data["cc"] == "cc@example.com"
                assert saved_data["bcc"] == "bcc@example.com"

    @pytest.mark.asyncio
    async def test_email_html_mode(self, tmp_path):
        """Test HTML email saving."""
        mock_settings = MagicMock()
        mock_settings.smtp_host = None
        mock_settings.upload_dir = tmp_path
        
        with patch("app.services.actions.settings", mock_settings):
            config = {
                "to": "user@example.com",
                "subject": "HTML Email",
                "body": "<h1>Hello</h1><p>World</p>",
                "is_html": True,
            }
            context = {}

            result = await execute_email_action(config, context)
            saved_file = Path(result["saved_to"])
            
            with open(saved_file, "r") as f:
                saved_data = json.load(f)
                assert saved_data["is_html"] is True
                assert "<h1>" in saved_data["body"]
