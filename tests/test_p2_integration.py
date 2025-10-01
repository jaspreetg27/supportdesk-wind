"""Integration tests for P2 implementation."""

import pytest
from fastapi.testclient import TestClient


class TestP2Integration:
    """Test P2 integration and end-to-end flows."""
    
    def test_complete_thread_lifecycle(self, client: TestClient, tenant_id: str, customer_id: str):
        """Test complete thread lifecycle from creation to closure."""
        # 1. Create thread
        thread_data = {
            "customer_id": customer_id,
            "platform": "whatsapp",
            "platform_thread_id": "wa_lifecycle_test",
            "subject": "Complete lifecycle test"
        }
        
        response = client.post(f"/api/v1/tenants/{tenant_id}/threads/", json=thread_data)
        assert response.status_code == 201
        thread_id = response.json()["id"]
        assert response.json()["state"] == "new"
        
        # 2. Add inbound message (triggers auto-ACK)
        message_data = {
            "platform_message_id": "lifecycle_msg_1",
            "type": "inbound",
            "content": "I need help with my order"
        }
        
        response = client.post(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/messages/", json=message_data)
        assert response.status_code == 201
        
        # 3. Verify auto-acknowledgment
        response = client.get(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}")
        assert response.json()["state"] == "acknowledged"
        
        # 4. Transition to in_progress
        transition_data = {
            "current_state": "acknowledged",
            "next_state": "in_progress",
            "reason": "Agent picked up the case",
            "actor_type": "user"
        }
        
        response = client.put(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/state", json=transition_data)
        assert response.status_code == 200
        assert response.json()["state"] == "in_progress"
        
        # 5. Add outbound message
        outbound_message = {
            "platform_message_id": "lifecycle_msg_2",
            "type": "outbound",
            "content": "I can help you with that. What's your order number?"
        }
        
        response = client.post(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/messages/", json=outbound_message)
        assert response.status_code == 201
        
        # 6. Transition to resolved
        transition_data = {
            "current_state": "in_progress",
            "next_state": "resolved",
            "reason": "Issue resolved successfully"
        }
        
        response = client.put(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/state", json=transition_data)
        assert response.status_code == 200
        thread_data = response.json()
        assert thread_data["state"] == "resolved"
        assert thread_data["priority"] == 0  # Auto-reset on resolved
        
        # 7. Close thread
        transition_data = {
            "current_state": "resolved",
            "next_state": "closed",
            "reason": "Customer confirmed resolution"
        }
        
        response = client.put(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/state", json=transition_data)
        assert response.status_code == 200
        assert response.json()["state"] == "closed"
        
        # 8. Verify complete audit trail
        response = client.get(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/events/")
        events = response.json()["items"]
        
        # Should have: creation, auto-ack, manual transitions
        event_types = [e["event_type"] for e in events]
        assert "thread_created" in event_types
        assert "state_transition" in event_types
        
        # Count state transitions
        transitions = [e for e in events if e["event_type"] == "state_transition"]
        assert len(transitions) >= 4  # new->ack, ack->progress, progress->resolved, resolved->closed
        
        # 9. Verify message count and ordering
        response = client.get(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/messages/")
        messages = response.json()["items"]
        assert len(messages) == 2
        
        # Messages should be ordered by sent_at/created_at
        assert messages[0]["type"] == "inbound"
        assert messages[1]["type"] == "outbound"
    
    def test_urgent_escalation_flow(self, client: TestClient, tenant_id: str, customer_id: str):
        """Test urgent escalation flow."""
        # Create thread
        thread_data = {"customer_id": customer_id, "platform": "whatsapp"}
        response = client.post(f"/api/v1/tenants/{tenant_id}/threads/", json=thread_data)
        thread_id = response.json()["id"]
        
        # Escalate to urgent
        transition_data = {
            "current_state": "new",
            "next_state": "urgent",
            "reason": "Critical system outage reported"
        }
        
        response = client.put(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/state", json=transition_data)
        assert response.status_code == 200
        thread_data = response.json()
        
        # Verify urgent state and priority
        assert thread_data["state"] == "urgent"
        assert thread_data["priority"] == 10  # Max priority for urgent
        
        # Verify escalation event
        response = client.get(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/events/")
        events = response.json()["items"]
        
        urgent_transition = next(e for e in events if e["new_state"] == "urgent")
        assert urgent_transition["old_state"] == "new"
        assert "Critical system outage" in urgent_transition["metadata"]["reason"]
    
    def test_message_deduplication_flow(self, client: TestClient, tenant_id: str, thread_id: str):
        """Test message deduplication in realistic scenario."""
        # Simulate webhook retry scenario
        message_data = {
            "platform_message_id": "webhook_retry_msg",
            "type": "inbound",
            "content": "This message might be delivered multiple times",
            "sent_at": "2024-01-15T10:00:00Z"
        }
        
        # First delivery
        response1 = client.post(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/messages/", json=message_data)
        assert response1.status_code == 201
        original_data = response1.json()
        assert original_data["existing"] is False
        
        # Webhook retry (same platform_message_id)
        response2 = client.post(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/messages/", json=message_data)
        assert response2.status_code == 200  # 200 for existing
        retry_data = response2.json()
        assert retry_data["existing"] is True
        assert retry_data["id"] == original_data["id"]
        
        # Verify only one message exists
        response = client.get(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/messages/")
        messages = response.json()["items"]
        duplicates = [m for m in messages if m["platform_message_id"] == "webhook_retry_msg"]
        assert len(duplicates) == 1
    
    def test_pagination_consistency_across_endpoints(self, client: TestClient, tenant_id: str, customer_id: str):
        """Test pagination contract consistency across all P2 endpoints."""
        # Create thread with messages and events
        thread_data = {"customer_id": customer_id, "platform": "whatsapp"}
        response = client.post(f"/api/v1/tenants/{tenant_id}/threads/", json=thread_data)
        thread_id = response.json()["id"]
        
        # Add multiple messages
        for i in range(7):
            message_data = {
                "platform_message_id": f"pagination_msg_{i}",
                "type": "inbound",
                "content": f"Message {i}"
            }
            client.post(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/messages/", json=message_data)
        
        # Generate events
        transition_data = {
            "current_state": "new",
            "next_state": "acknowledged",
            "reason": "Pagination test"
        }
        client.put(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/state", json=transition_data)
        
        # Test pagination on all endpoints
        endpoints = [
            f"/api/v1/tenants/{tenant_id}/threads/",
            f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/messages/",
            f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/events/"
        ]
        
        for endpoint in endpoints:
            response = client.get(f"{endpoint}?page=1&page_size=3")
            assert response.status_code == 200
            data = response.json()
            
            # Verify pagination contract
            required_fields = ["items", "total", "page", "page_size", "total_pages", "has_next", "has_prev"]
            for field in required_fields:
                assert field in data, f"Missing {field} in {endpoint}"
            
            assert data["page"] == 1
            assert data["page_size"] == 3  # Echo requested
            assert isinstance(data["total"], int)
            assert isinstance(data["total_pages"], int)
            assert isinstance(data["has_next"], bool)
            assert isinstance(data["has_prev"], bool)
            assert len(data["items"]) <= 3  # Actual items (may be capped)
    
    def test_cross_platform_thread_uniqueness(self, client: TestClient, tenant_id: str, customer_id: str):
        """Test platform_thread_id uniqueness across platforms."""
        # Same platform_thread_id on different platforms should be allowed
        thread_data1 = {
            "customer_id": customer_id,
            "platform": "whatsapp",
            "platform_thread_id": "shared_id_123"
        }
        
        thread_data2 = {
            "customer_id": customer_id,
            "platform": "instagram",  # Different platform
            "platform_thread_id": "shared_id_123"  # Same ID
        }
        
        # Both should succeed
        response1 = client.post(f"/api/v1/tenants/{tenant_id}/threads/", json=thread_data1)
        assert response1.status_code == 201
        
        response2 = client.post(f"/api/v1/tenants/{tenant_id}/threads/", json=thread_data2)
        assert response2.status_code == 201
        
        # Same platform should fail
        response3 = client.post(f"/api/v1/tenants/{tenant_id}/threads/", json=thread_data1)
        assert response3.status_code == 409
        assert response3.json()["error"] == "PLATFORM_THREAD_EXISTS"
    
    def test_thread_reopen_flow(self, client: TestClient, tenant_id: str, thread_id: str):
        """Test thread reopen functionality."""
        # Progress thread to resolved
        transitions = [
            ("new", "acknowledged"),
            ("acknowledged", "in_progress"),
            ("in_progress", "resolved")
        ]
        
        for from_state, to_state in transitions:
            transition_data = {
                "current_state": from_state,
                "next_state": to_state,
                "reason": f"Moving to {to_state}"
            }
            response = client.put(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/state", json=transition_data)
            assert response.status_code == 200
        
        # Reopen resolved thread
        reopen_data = {
            "current_state": "resolved",
            "next_state": "in_progress",
            "reason": "Customer reported issue not fully resolved"
        }
        
        response = client.put(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/state", json=reopen_data)
        assert response.status_code == 200
        assert response.json()["state"] == "in_progress"
        
        # Verify reopen event
        response = client.get(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/events/")
        events = response.json()["items"]
        
        reopen_event = next(e for e in events if e["old_state"] == "resolved" and e["new_state"] == "in_progress")
        assert "not fully resolved" in reopen_event["metadata"]["reason"]
