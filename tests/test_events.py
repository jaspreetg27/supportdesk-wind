"""Tests for thread event operations."""

import pytest
from fastapi.testclient import TestClient
from uuid import uuid4


class TestThreadEventAPI:
    """Test thread event API endpoints."""
    
    def test_event_pagination_ordering(self, client: TestClient, tenant_id: str, thread_id: str):
        """Test event pagination ordering (newest first)."""
        # Perform several state transitions to generate events
        transitions = [
            ("new", "acknowledged", "First transition"),
            ("acknowledged", "in_progress", "Second transition"),
            ("in_progress", "resolved", "Third transition")
        ]
        
        for from_state, to_state, reason in transitions:
            transition_data = {
                "current_state": from_state,
                "next_state": to_state,
                "reason": reason
            }
            response = client.put(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/state", json=transition_data)
            assert response.status_code == 200
        
        # Get events - should be ordered newest first
        response = client.get(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/events/")
        assert response.status_code == 200
        events = response.json()["items"]
        
        # Should have creation event + 3 transitions = 4 events minimum
        assert len(events) >= 4
        
        # Events should be ordered by created_at DESC (newest first)
        transition_events = [e for e in events if e["event_type"] == "state_transition"]
        assert len(transition_events) == 3
        
        # Most recent transition should be first
        assert transition_events[0]["new_state"] == "resolved"
        assert transition_events[1]["new_state"] == "in_progress" 
        assert transition_events[2]["new_state"] == "acknowledged"
    
    def test_event_metadata_contents(self, client: TestClient, tenant_id: str, thread_id: str):
        """Test event metadata contents."""
        correlation_id = str(uuid4())
        
        transition_data = {
            "current_state": "new",
            "next_state": "acknowledged",
            "reason": "Customer message received",
            "actor_type": "system",
            "correlation_id": correlation_id,
            "metadata": {
                "message_count": 1,
                "trigger": "auto_ack"
            }
        }
        
        response = client.put(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/state", json=transition_data)
        assert response.status_code == 200
        
        # Get events and verify metadata
        response = client.get(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/events/")
        events = response.json()["items"]
        
        transition_event = next(e for e in events if e["correlation_id"] == correlation_id)
        assert transition_event["actor_type"] == "system"
        assert transition_event["correlation_id"] == correlation_id
        assert "reason" in transition_event["metadata"]
        assert "message_count" in transition_event["metadata"]
        assert "trigger" in transition_event["metadata"]


def test_thread_event_includes_actor_and_correlation_id(client: TestClient, tenant_id: str, thread_id: str):
    """Test all events include actor_type, actor_id, and correlation_id."""
    correlation_id = str(uuid4())
    
    # Perform transition with full actor info
    transition_data = {
        "current_state": "new",
        "next_state": "acknowledged", 
        "reason": "Manual acknowledgment",
        "actor_type": "user",
        "actor_id": str(uuid4()),
        "correlation_id": correlation_id
    }
    
    response = client.put(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/state", json=transition_data)
    assert response.status_code == 200
    
    # Verify event has all required fields
    response = client.get(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/events/")
    events = response.json()["items"]
    
    transition_event = next(e for e in events if e["correlation_id"] == correlation_id)
    
    # Required audit fields
    assert "actor_type" in transition_event
    assert "actor_id" in transition_event  
    assert "correlation_id" in transition_event
    assert transition_event["actor_type"] == "user"
    assert transition_event["actor_id"] == transition_data["actor_id"]
    assert transition_event["correlation_id"] == correlation_id


class TestEventTenantIsolation:
    """Test event tenant isolation."""
    
    def test_cross_tenant_event_access_blocked(self, client: TestClient):
        """Verify events cannot be accessed across tenants."""
        # Create two tenants
        tenant1_data = {"name": "Tenant 1", "slug": "tenant-1-event-isolation"}
        tenant2_data = {"name": "Tenant 2", "slug": "tenant-2-event-isolation"}
        
        tenant1_resp = client.post("/api/v1/tenants/", json=tenant1_data)
        tenant2_resp = client.post("/api/v1/tenants/", json=tenant2_data)
        
        tenant1_id = tenant1_resp.json()["id"]
        tenant2_id = tenant2_resp.json()["id"]
        
        # Create thread in tenant 1
        customer_data = {"name": "Test Customer"}
        customer_resp = client.post(f"/api/v1/tenants/{tenant1_id}/customers/", json=customer_data)
        customer_id = customer_resp.json()["id"]
        
        thread_data = {"customer_id": customer_id, "platform": "whatsapp"}
        thread_resp = client.post(f"/api/v1/tenants/{tenant1_id}/threads/", json=thread_data)
        thread_id = thread_resp.json()["id"]
        
        # Try to access events from tenant 2
        response = client.get(f"/api/v1/tenants/{tenant2_id}/threads/{thread_id}/events/")
        assert response.status_code == 404  # Thread not found in tenant 2


class TestEventPagination:
    """Test event pagination."""
    
    def test_event_pagination_contract(self, client: TestClient, tenant_id: str, thread_id: str):
        """Test event pagination follows contract."""
        # Generate multiple events with valid state transitions
        transitions = [
            ("new", "acknowledged"),
            ("acknowledged", "in_progress"),
            ("in_progress", "waiting_for_customer"),
            ("waiting_for_customer", "in_progress"),
            ("in_progress", "resolved")
        ]
        
        for i, (from_state, to_state) in enumerate(transitions):
            transition_data = {
                "current_state": from_state,
                "next_state": to_state,
                "reason": f"Transition {i}"
            }
            
            response = client.put(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/state", json=transition_data)
            # All transitions should succeed now
            assert response.status_code == 200
        
        # Test pagination
        response = client.get(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/events/?page=1&page_size=3")
        assert response.status_code == 200
        data = response.json()
        
        # Verify pagination contract
        required_fields = ["items", "total", "page", "page_size", "total_pages", "has_next", "has_prev"]
        for field in required_fields:
            assert field in data
        
        assert data["page"] == 1
        assert data["page_size"] == 3
        assert len(data["items"]) <= 3  # May be less due to repo limit
