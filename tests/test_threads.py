"""Tests for thread operations."""

import pytest
from fastapi.testclient import TestClient
from uuid import uuid4

from supportdesk.threads.models import ThreadState, PlatformType


class TestThreadAPI:
    """Test thread API endpoints."""
    
    def test_create_thread_success(self, client: TestClient, tenant_id: str, customer_id: str):
        """Test successful thread creation."""
        thread_data = {
            "customer_id": customer_id,
            "platform": "whatsapp",
            "platform_thread_id": "wa_thread_123",
            "subject": "Product inquiry",
            "metadata": {"source": "mobile_app"}
        }
        
        response = client.post(f"/api/v1/tenants/{tenant_id}/threads/", json=thread_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["customer_id"] == customer_id
        assert data["platform"] == "whatsapp"
        assert data["platform_thread_id"] == "wa_thread_123"
        assert data["state"] == "new"
        assert data["priority"] == 0
        assert data["subject"] == "Product inquiry"
        assert data["message_count"] == 0
    
    def test_unique_platform_thread_id(self, client: TestClient, tenant_id: str, customer_id: str):
        """Test platform_thread_id uniqueness within tenant/platform."""
        thread_data = {
            "customer_id": customer_id,
            "platform": "whatsapp",
            "platform_thread_id": "wa_thread_duplicate",
            "subject": "First thread"
        }
        
        # Create first thread
        response1 = client.post(f"/api/v1/tenants/{tenant_id}/threads/", json=thread_data)
        assert response1.status_code == 201
        
        # Try to create duplicate
        response2 = client.post(f"/api/v1/tenants/{tenant_id}/threads/", json=thread_data)
        assert response2.status_code == 409
        error = response2.json()
        assert error["error"] == "PLATFORM_THREAD_EXISTS"
    
    def test_list_threads_filters(self, client: TestClient, tenant_id: str, customer_id: str):
        """Test thread listing with various filters."""
        # Create threads with different states and priorities
        threads_data = [
            {"customer_id": customer_id, "platform": "whatsapp", "subject": "Thread 1"},
            {"customer_id": customer_id, "platform": "instagram", "subject": "Thread 2"},
            {"customer_id": customer_id, "platform": "whatsapp", "subject": "Thread 3"}
        ]
        
        thread_ids = []
        for thread_data in threads_data:
            response = client.post(f"/api/v1/tenants/{tenant_id}/threads/", json=thread_data)
            assert response.status_code == 201
            thread_ids.append(response.json()["id"])
        
        # Test filtering by platform
        response = client.get(f"/api/v1/tenants/{tenant_id}/threads/?platform=whatsapp")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        
        # Test filtering by customer
        response = client.get(f"/api/v1/tenants/{tenant_id}/threads/?customer_id={customer_id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 3
    
    def test_thread_with_messages_included(self, client: TestClient, tenant_id: str, customer_id: str):
        """Test thread retrieval with message inclusion."""
        # Create thread
        thread_data = {"customer_id": customer_id, "platform": "whatsapp"}
        response = client.post(f"/api/v1/tenants/{tenant_id}/threads/", json=thread_data)
        thread_id = response.json()["id"]
        
        # Add messages
        message_data = {
            "platform_message_id": "msg_1",
            "type": "inbound",
            "content": "Hello, I need help"
        }
        client.post(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/messages/", json=message_data)
        
        # Get thread with messages
        response = client.get(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}?include_messages=latest")
        assert response.status_code == 200
        data = response.json()
        assert "messages" in data
        assert len(data["messages"]) == 1
        assert data["messages"][0]["content"] == "Hello, I need help"


class TestThreadStateMachine:
    """Test thread state transitions."""
    
    def test_valid_state_transitions(self, client: TestClient, tenant_id: str, thread_id: str):
        """Test all valid state transitions."""
        valid_transitions = [
            ("new", "acknowledged"),
            ("acknowledged", "in_progress"),
            ("in_progress", "resolved"),
            ("resolved", "closed")
        ]
        
        current_state = "new"
        for from_state, to_state in valid_transitions:
            assert current_state == from_state  # Verify we're in expected state
            
            transition_data = {
                "current_state": from_state,
                "next_state": to_state,
                "reason": f"Transitioning from {from_state} to {to_state}",
                "actor_type": "user"
            }
            
            response = client.put(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/state", json=transition_data)
            assert response.status_code == 200
            data = response.json()
            assert data["state"] == to_state
            current_state = to_state
    
    def test_invalid_state_transitions(self, client: TestClient, tenant_id: str, thread_id: str):
        """Test rejection of invalid transitions with 422."""
        # Try invalid transition: new -> resolved (skipping intermediate states)
        transition_data = {
            "current_state": "new",
            "next_state": "resolved",
            "reason": "Invalid direct transition"
        }
        
        response = client.put(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/state", json=transition_data)
        assert response.status_code == 422
        error = response.json()
        assert error["error"] == "STATE_TRANSITION_INVALID"
        assert "allowed_transitions" in error["details"]
    
    def test_state_event_logged(self, client: TestClient, tenant_id: str, thread_id: str):
        """Verify events are logged for each transition."""
        # Perform transition
        transition_data = {
            "current_state": "new",
            "next_state": "acknowledged",
            "reason": "Customer message received",
            "correlation_id": str(uuid4())
        }
        
        response = client.put(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/state", json=transition_data)
        assert response.status_code == 200
        
        # Check events
        response = client.get(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/events/")
        assert response.status_code == 200
        events = response.json()["items"]
        
        # Should have creation event + transition event
        assert len(events) >= 2
        transition_event = next(e for e in events if e["event_type"] == "state_transition")
        assert transition_event["old_state"] == "new"
        assert transition_event["new_state"] == "acknowledged"
        assert transition_event["correlation_id"] == transition_data["correlation_id"]
    
    def test_priority_escalation_rules(self, client: TestClient, tenant_id: str, thread_id: str):
        """Test automatic priority adjustments."""
        # Transition to urgent should set priority to 10
        transition_data = {
            "current_state": "new",
            "next_state": "urgent",
            "reason": "Critical issue"
        }
        
        response = client.put(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/state", json=transition_data)
        assert response.status_code == 200
        data = response.json()
        assert data["state"] == "urgent"
        assert data["priority"] == 10
        
        # Transition to resolved should set priority to 0
        transition_data = {
            "current_state": "urgent",
            "next_state": "resolved",
            "reason": "Issue resolved"
        }
        
        response = client.put(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/state", json=transition_data)
        assert response.status_code == 200
        data = response.json()
        assert data["state"] == "resolved"
        assert data["priority"] == 0


class TestThreadTenantIsolation:
    """Test thread tenant isolation."""
    
    def test_cross_tenant_thread_access_blocked(self, client: TestClient):
        """Verify threads cannot be accessed across tenants."""
        # Create two tenants
        tenant1_data = {"name": "Tenant 1", "slug": "tenant-1-isolation"}
        tenant2_data = {"name": "Tenant 2", "slug": "tenant-2-isolation"}
        
        tenant1_resp = client.post("/api/v1/tenants/", json=tenant1_data)
        tenant2_resp = client.post("/api/v1/tenants/", json=tenant2_data)
        
        tenant1_id = tenant1_resp.json()["id"]
        tenant2_id = tenant2_resp.json()["id"]
        
        # Create customer in tenant 1
        customer_data = {"name": "Test Customer"}
        customer_resp = client.post(f"/api/v1/tenants/{tenant1_id}/customers/", json=customer_data)
        customer_id = customer_resp.json()["id"]
        
        # Create thread in tenant 1
        thread_data = {"customer_id": customer_id, "platform": "whatsapp"}
        thread_resp = client.post(f"/api/v1/tenants/{tenant1_id}/threads/", json=thread_data)
        thread_id = thread_resp.json()["id"]
        
        # Try to access thread from tenant 2
        response = client.get(f"/api/v1/tenants/{tenant2_id}/threads/{thread_id}")
        assert response.status_code == 404


def test_threads_list_ordering_by_last_message_at(client: TestClient, tenant_id: str, customer_id: str):
    """Test thread listing uses last_message_at DESC NULLS LAST ordering."""
    # Create threads
    thread_ids = []
    for i in range(3):
        thread_data = {"customer_id": customer_id, "platform": "whatsapp", "subject": f"Thread {i}"}
        response = client.post(f"/api/v1/tenants/{tenant_id}/threads/", json=thread_data)
        thread_ids.append(response.json()["id"])
    
    # Add message to middle thread (should move it to top)
    message_data = {
        "platform_message_id": "msg_middle",
        "type": "inbound", 
        "content": "Message in middle thread"
    }
    client.post(f"/api/v1/tenants/{tenant_id}/threads/{thread_ids[1]}/messages/", json=message_data)
    
    # List threads - thread with message should be first
    response = client.get(f"/api/v1/tenants/{tenant_id}/threads/")
    assert response.status_code == 200
    threads = response.json()["items"]
    
    # Thread with message should be first (has last_message_at)
    assert threads[0]["id"] == thread_ids[1]
    # Other threads should be ordered by updated_at DESC
    assert threads[1]["id"] == thread_ids[2]  # Most recently created
    assert threads[2]["id"] == thread_ids[0]  # First created
