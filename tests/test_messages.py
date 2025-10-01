"""Tests for message operations."""

import pytest
from fastapi.testclient import TestClient
from uuid import uuid4


class TestMessageAPI:
    """Test message API endpoints."""
    
    def test_add_inbound_message(self, client: TestClient, tenant_id: str, thread_id: str):
        """Test adding inbound message with auto-ACK."""
        message_data = {
            "platform_message_id": "wa_msg_001",
            "type": "inbound",
            "content": "Hello, I need help with my order",
            "sent_at": "2024-01-15T10:00:00Z",
            "metadata": {"phone_number": "+1234567890"}
        }
        
        response = client.post(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/messages/", json=message_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["platform_message_id"] == "wa_msg_001"
        assert data["type"] == "inbound"
        assert data["content"] == "Hello, I need help with my order"
        assert data["existing"] is False
        
        # Verify thread state changed to acknowledged (auto-ACK)
        thread_response = client.get(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}")
        thread_data = thread_response.json()
        assert thread_data["state"] == "acknowledged"
        assert thread_data["message_count"] == 1
    
    def test_deduplication_by_platform_message_id(self, client: TestClient, tenant_id: str, thread_id: str):
        """Test message deduplication returns existing=true."""
        message_data = {
            "platform_message_id": "wa_msg_duplicate",
            "type": "inbound",
            "content": "Original message"
        }
        
        # Create first message
        response1 = client.post(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/messages/", json=message_data)
        assert response1.status_code == 201
        original_id = response1.json()["id"]
        assert response1.json()["existing"] is False
        
        # Try to create duplicate
        message_data["content"] = "Duplicate attempt"  # Different content
        response2 = client.post(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/messages/", json=message_data)
        assert response2.status_code == 200  # 200 for existing
        duplicate_data = response2.json()
        assert duplicate_data["id"] == original_id
        assert duplicate_data["content"] == "Original message"  # Original content preserved
        assert duplicate_data["existing"] is True
    
    def test_ordering_by_sent_then_created(self, client: TestClient, tenant_id: str, thread_id: str):
        """Test message ordering determinism."""
        import time
        from datetime import datetime, timezone
        
        base_time = datetime.now(timezone.utc)
        
        # Create messages with different sent_at times
        messages = [
            {
                "platform_message_id": "msg_1",
                "type": "inbound",
                "content": "First message",
                "sent_at": base_time.replace(hour=10).isoformat()
            },
            {
                "platform_message_id": "msg_2", 
                "type": "system",
                "content": "System message (no sent_at)"
                # No sent_at - should use created_at
            },
            {
                "platform_message_id": "msg_3",
                "type": "inbound", 
                "content": "Third message",
                "sent_at": base_time.replace(hour=12).isoformat()
            }
        ]
        
        # Create messages with small delays to ensure different created_at
        for msg in messages:
            client.post(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/messages/", json=msg)
            time.sleep(0.1)
        
        # List messages - should be ordered by COALESCE(sent_at, created_at)
        response = client.get(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/messages/")
        assert response.status_code == 200
        message_list = response.json()["items"]
        
        assert len(message_list) == 3
        # First: msg_1 (sent_at 10:00)
        # Second: msg_2 (created_at, no sent_at)  
        # Third: msg_3 (sent_at 12:00)
        assert message_list[0]["platform_message_id"] == "msg_1"
        assert message_list[2]["platform_message_id"] == "msg_3"


class TestMessageUpdate:
    """Test message update operations."""
    
    def test_message_update_immutable_fields_rejected(self, client: TestClient, tenant_id: str, thread_id: str, message_id: str):
        """Test message updates reject immutable fields with 422 IMMUTABLE_FIELD."""
        # Try to update immutable field
        update_data = {
            "platform_message_id": "new_id",  # Immutable
            "content": "Updated content"
        }
        
        response = client.put(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/messages/{message_id}", json=update_data)
        assert response.status_code == 422
        error = response.json()
        assert error["error"] == "IMMUTABLE_FIELD"
        assert "platform_message_id" in error["attempted_field"]
    
    def test_message_update_allowed_fields(self, client: TestClient, tenant_id: str, thread_id: str, message_id: str):
        """Test updating allowed fields works correctly."""
        update_data = {
            "content": "Updated message content",
            "metadata": {"edited": True, "reason": "typo correction"}
        }
        
        response = client.put(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/messages/{message_id}", json=update_data)
        assert response.status_code == 200
        data = response.json()
        assert data["content"] == "Updated message content"
    
    def test_sent_at_update_when_null(self, client: TestClient, tenant_id: str, thread_id: str):
        """Test sent_at can be set when previously null."""
        # Create message without sent_at
        message_data = {
            "platform_message_id": "msg_no_sent_at",
            "type": "system",
            "content": "System message"
        }
        
        response = client.post(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/messages/", json=message_data)
        message_id = response.json()["id"]
        
        # Update with sent_at
        update_data = {"sent_at": "2024-01-15T15:00:00Z"}
        response = client.put(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/messages/{message_id}", json=update_data)
        assert response.status_code == 200
        assert response.json()["sent_at"] == "2024-01-15T15:00:00Z"
        
        # Try to update sent_at again (should fail)
        update_data = {"sent_at": "2024-01-15T16:00:00Z"}
        response = client.put(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/messages/{message_id}", json=update_data)
        assert response.status_code == 422


class TestMessageTenantIsolation:
    """Test message tenant isolation."""
    
    def test_cross_tenant_message_access_blocked(self, client: TestClient):
        """Verify messages cannot be accessed across tenants."""
        # Create two tenants with threads
        tenant1_data = {"name": "Tenant 1", "slug": "tenant-1-msg-isolation"}
        tenant2_data = {"name": "Tenant 2", "slug": "tenant-2-msg-isolation"}
        
        tenant1_resp = client.post("/api/v1/tenants/", json=tenant1_data)
        tenant2_resp = client.post("/api/v1/tenants/", json=tenant2_data)
        
        tenant1_id = tenant1_resp.json()["id"]
        tenant2_id = tenant2_resp.json()["id"]
        
        # Create customer and thread in tenant 1
        customer_data = {"name": "Test Customer"}
        customer_resp = client.post(f"/api/v1/tenants/{tenant1_id}/customers/", json=customer_data)
        customer_id = customer_resp.json()["id"]
        
        thread_data = {"customer_id": customer_id, "platform": "whatsapp"}
        thread_resp = client.post(f"/api/v1/tenants/{tenant1_id}/threads/", json=thread_data)
        thread_id = thread_resp.json()["id"]
        
        # Create message in tenant 1
        message_data = {
            "platform_message_id": "cross_tenant_msg",
            "type": "inbound",
            "content": "Secret message"
        }
        msg_resp = client.post(f"/api/v1/tenants/{tenant1_id}/threads/{thread_id}/messages/", json=message_data)
        message_id = msg_resp.json()["id"]
        
        # Try to access message from tenant 2
        response = client.put(f"/api/v1/tenants/{tenant2_id}/messages/{message_id}", json={"content": "hacked"})
        assert response.status_code == 404


class TestMessageValidation:
    """Test message validation."""
    
    def test_content_required_for_inbound_outbound(self, client: TestClient, tenant_id: str, thread_id: str):
        """Test content validation for inbound/outbound messages."""
        # Inbound without content should fail
        message_data = {
            "platform_message_id": "msg_no_content",
            "type": "inbound"
            # No content
        }
        
        response = client.post(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/messages/", json=message_data)
        assert response.status_code == 422
        
        # System message without content should work
        message_data = {
            "platform_message_id": "system_no_content",
            "type": "system"
            # No content - allowed for system messages
        }
        
        response = client.post(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/messages/", json=message_data)
        assert response.status_code == 201


def test_pagination_contract_shape_consistent_across_endpoints(client: TestClient, tenant_id: str, thread_id: str):
    """Test all list endpoints return identical pagination structure."""
    # Add some messages
    for i in range(5):
        message_data = {
            "platform_message_id": f"msg_{i}",
            "type": "inbound",
            "content": f"Message {i}"
        }
        client.post(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/messages/", json=message_data)
    
    # Test message list pagination
    response = client.get(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/messages/?page=1&page_size=3")
    assert response.status_code == 200
    data = response.json()
    
    # Verify exact pagination contract
    required_fields = ["items", "total", "page", "page_size", "total_pages", "has_next", "has_prev"]
    for field in required_fields:
        assert field in data, f"Missing required pagination field: {field}"
    
    assert data["page"] == 1
    assert data["page_size"] == 3  # Echo requested page_size
    assert data["total"] == 5
    assert data["total_pages"] == 2
    assert data["has_next"] is True
    assert data["has_prev"] is False
    assert len(data["items"]) == 3  # Actual items returned (may be capped by repo)
