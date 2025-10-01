"""Tests for P2 tenant isolation."""

import pytest
from fastapi.testclient import TestClient


class TestP2TenantIsolation:
    """Test tenant isolation for P2 components."""
    
    def test_thread_isolation_across_tenants(self, client: TestClient):
        """Test threads are isolated between tenants."""
        # Create two tenants
        tenant1_data = {"name": "Tenant 1", "slug": "tenant-1-p2-isolation"}
        tenant2_data = {"name": "Tenant 2", "slug": "tenant-2-p2-isolation"}
        
        tenant1_resp = client.post("/api/v1/tenants/", json=tenant1_data)
        tenant2_resp = client.post("/api/v1/tenants/", json=tenant2_data)
        
        tenant1_id = tenant1_resp.json()["id"]
        tenant2_id = tenant2_resp.json()["id"]
        
        # Create customers in each tenant
        customer_data = {"name": "Test Customer"}
        customer1_resp = client.post(f"/api/v1/tenants/{tenant1_id}/customers/", json=customer_data)
        customer2_resp = client.post(f"/api/v1/tenants/{tenant2_id}/customers/", json=customer_data)
        
        customer1_id = customer1_resp.json()["id"]
        customer2_id = customer2_resp.json()["id"]
        
        # Create threads in each tenant
        thread_data1 = {"customer_id": customer1_id, "platform": "whatsapp", "subject": "Tenant 1 Thread"}
        thread_data2 = {"customer_id": customer2_id, "platform": "whatsapp", "subject": "Tenant 2 Thread"}
        
        thread1_resp = client.post(f"/api/v1/tenants/{tenant1_id}/threads/", json=thread_data1)
        thread2_resp = client.post(f"/api/v1/tenants/{tenant2_id}/threads/", json=thread_data2)
        
        thread1_id = thread1_resp.json()["id"]
        thread2_id = thread2_resp.json()["id"]
        
        # Tenant 1 should only see its own threads
        response = client.get(f"/api/v1/tenants/{tenant1_id}/threads/")
        tenant1_threads = response.json()["items"]
        assert len(tenant1_threads) == 1
        assert tenant1_threads[0]["id"] == thread1_id
        assert tenant1_threads[0]["subject"] == "Tenant 1 Thread"
        
        # Tenant 2 should only see its own threads
        response = client.get(f"/api/v1/tenants/{tenant2_id}/threads/")
        tenant2_threads = response.json()["items"]
        assert len(tenant2_threads) == 1
        assert tenant2_threads[0]["id"] == thread2_id
        assert tenant2_threads[0]["subject"] == "Tenant 2 Thread"
        
        # Cross-tenant access should fail
        response = client.get(f"/api/v1/tenants/{tenant1_id}/threads/{thread2_id}")
        assert response.status_code == 404
        
        response = client.get(f"/api/v1/tenants/{tenant2_id}/threads/{thread1_id}")
        assert response.status_code == 404
    
    def test_message_isolation_across_tenants(self, client: TestClient):
        """Test messages are isolated between tenants."""
        # Setup two tenants with threads
        tenant1_data = {"name": "Tenant 1", "slug": "tenant-1-msg-isolation"}
        tenant2_data = {"name": "Tenant 2", "slug": "tenant-2-msg-isolation"}
        
        tenant1_resp = client.post("/api/v1/tenants/", json=tenant1_data)
        tenant2_resp = client.post("/api/v1/tenants/", json=tenant2_data)
        
        tenant1_id = tenant1_resp.json()["id"]
        tenant2_id = tenant2_resp.json()["id"]
        
        # Create customers and threads
        customer_data = {"name": "Test Customer"}
        customer1_resp = client.post(f"/api/v1/tenants/{tenant1_id}/customers/", json=customer_data)
        customer2_resp = client.post(f"/api/v1/tenants/{tenant2_id}/customers/", json=customer_data)
        
        customer1_id = customer1_resp.json()["id"]
        customer2_id = customer2_resp.json()["id"]
        
        thread_data = {"customer_id": customer1_id, "platform": "whatsapp"}
        thread1_resp = client.post(f"/api/v1/tenants/{tenant1_id}/threads/", json=thread_data)
        thread1_id = thread1_resp.json()["id"]
        
        thread_data = {"customer_id": customer2_id, "platform": "whatsapp"}
        thread2_resp = client.post(f"/api/v1/tenants/{tenant2_id}/threads/", json=thread_data)
        thread2_id = thread2_resp.json()["id"]
        
        # Create messages in each tenant
        message1_data = {
            "platform_message_id": "tenant1_msg",
            "type": "inbound",
            "content": "Message from tenant 1"
        }
        message2_data = {
            "platform_message_id": "tenant2_msg", 
            "type": "inbound",
            "content": "Message from tenant 2"
        }
        
        msg1_resp = client.post(f"/api/v1/tenants/{tenant1_id}/threads/{thread1_id}/messages/", json=message1_data)
        msg2_resp = client.post(f"/api/v1/tenants/{tenant2_id}/threads/{thread2_id}/messages/", json=message2_data)
        
        msg1_id = msg1_resp.json()["id"]
        msg2_id = msg2_resp.json()["id"]
        
        # Each tenant should only see its own messages
        response = client.get(f"/api/v1/tenants/{tenant1_id}/threads/{thread1_id}/messages/")
        tenant1_messages = response.json()["items"]
        assert len(tenant1_messages) == 1
        assert tenant1_messages[0]["content"] == "Message from tenant 1"
        
        response = client.get(f"/api/v1/tenants/{tenant2_id}/threads/{thread2_id}/messages/")
        tenant2_messages = response.json()["items"]
        assert len(tenant2_messages) == 1
        assert tenant2_messages[0]["content"] == "Message from tenant 2"
        
        # Cross-tenant message access should fail
        response = client.put(f"/api/v1/tenants/{tenant1_id}/messages/{msg2_id}", json={"content": "hacked"})
        assert response.status_code == 404
        
        response = client.put(f"/api/v1/tenants/{tenant2_id}/messages/{msg1_id}", json={"content": "hacked"})
        assert response.status_code == 404
    
    def test_event_isolation_across_tenants(self, client: TestClient):
        """Test thread events are isolated between tenants."""
        # Setup two tenants with threads
        tenant1_data = {"name": "Tenant 1", "slug": "tenant-1-event-isolation"}
        tenant2_data = {"name": "Tenant 2", "slug": "tenant-2-event-isolation"}
        
        tenant1_resp = client.post("/api/v1/tenants/", json=tenant1_data)
        tenant2_resp = client.post("/api/v1/tenants/", json=tenant2_data)
        
        tenant1_id = tenant1_resp.json()["id"]
        tenant2_id = tenant2_resp.json()["id"]
        
        # Create threads
        customer_data = {"name": "Test Customer"}
        customer1_resp = client.post(f"/api/v1/tenants/{tenant1_id}/customers/", json=customer_data)
        customer2_resp = client.post(f"/api/v1/tenants/{tenant2_id}/customers/", json=customer_data)
        
        customer1_id = customer1_resp.json()["id"]
        customer2_id = customer2_resp.json()["id"]
        
        thread_data = {"customer_id": customer1_id, "platform": "whatsapp"}
        thread1_resp = client.post(f"/api/v1/tenants/{tenant1_id}/threads/", json=thread_data)
        thread1_id = thread1_resp.json()["id"]
        
        thread_data = {"customer_id": customer2_id, "platform": "whatsapp"}
        thread2_resp = client.post(f"/api/v1/tenants/{tenant2_id}/threads/", json=thread_data)
        thread2_id = thread2_resp.json()["id"]
        
        # Perform state transitions to generate events
        transition_data = {
            "current_state": "new",
            "next_state": "acknowledged",
            "reason": "Tenant isolation test"
        }
        
        client.put(f"/api/v1/tenants/{tenant1_id}/threads/{thread1_id}/state", json=transition_data)
        client.put(f"/api/v1/tenants/{tenant2_id}/threads/{thread2_id}/state", json=transition_data)
        
        # Each tenant should only see events for its own threads
        response = client.get(f"/api/v1/tenants/{tenant1_id}/threads/{thread1_id}/events/")
        assert response.status_code == 200
        tenant1_events = response.json()["items"]
        assert len(tenant1_events) >= 1  # At least creation + transition events
        
        response = client.get(f"/api/v1/tenants/{tenant2_id}/threads/{thread2_id}/events/")
        assert response.status_code == 200
        tenant2_events = response.json()["items"]
        assert len(tenant2_events) >= 1
        
        # Cross-tenant event access should fail
        response = client.get(f"/api/v1/tenants/{tenant1_id}/threads/{thread2_id}/events/")
        assert response.status_code == 404
        
        response = client.get(f"/api/v1/tenants/{tenant2_id}/threads/{thread1_id}/events/")
        assert response.status_code == 404
    
    def test_platform_thread_id_isolation(self, client: TestClient):
        """Test platform_thread_id uniqueness is scoped to tenant."""
        # Create two tenants
        tenant1_data = {"name": "Tenant 1", "slug": "tenant-1-platform-isolation"}
        tenant2_data = {"name": "Tenant 2", "slug": "tenant-2-platform-isolation"}
        
        tenant1_resp = client.post("/api/v1/tenants/", json=tenant1_data)
        tenant2_resp = client.post("/api/v1/tenants/", json=tenant2_data)
        
        tenant1_id = tenant1_resp.json()["id"]
        tenant2_id = tenant2_resp.json()["id"]
        
        # Create customers
        customer_data = {"name": "Test Customer"}
        customer1_resp = client.post(f"/api/v1/tenants/{tenant1_id}/customers/", json=customer_data)
        customer2_resp = client.post(f"/api/v1/tenants/{tenant2_id}/customers/", json=customer_data)
        
        customer1_id = customer1_resp.json()["id"]
        customer2_id = customer2_resp.json()["id"]
        
        # Same platform_thread_id should be allowed in different tenants
        thread_data1 = {
            "customer_id": customer1_id,
            "platform": "whatsapp",
            "platform_thread_id": "shared_platform_id"
        }
        thread_data2 = {
            "customer_id": customer2_id,
            "platform": "whatsapp", 
            "platform_thread_id": "shared_platform_id"  # Same ID, different tenant
        }
        
        # Both should succeed (different tenants)
        response1 = client.post(f"/api/v1/tenants/{tenant1_id}/threads/", json=thread_data1)
        assert response1.status_code == 201
        
        response2 = client.post(f"/api/v1/tenants/{tenant2_id}/threads/", json=thread_data2)
        assert response2.status_code == 201
        
        # But duplicate within same tenant should fail
        response3 = client.post(f"/api/v1/tenants/{tenant1_id}/threads/", json=thread_data1)
        assert response3.status_code == 409
        assert response3.json()["error"] == "PLATFORM_THREAD_EXISTS"


class TestP2DataIntegrity:
    """Test data integrity across P2 components."""
    
    def test_cascade_delete_thread_with_messages_and_events(self, client: TestClient, tenant_id: str):
        """Test cascade deletion maintains data integrity."""
        # Create customer
        customer_data = {"name": "Test Customer"}
        customer_resp = client.post(f"/api/v1/tenants/{tenant_id}/customers/", json=customer_data)
        customer_id = customer_resp.json()["id"]
        
        # Create thread
        thread_data = {"customer_id": customer_id, "platform": "whatsapp"}
        thread_resp = client.post(f"/api/v1/tenants/{tenant_id}/threads/", json=thread_data)
        thread_id = thread_resp.json()["id"]
        
        # Add messages
        message_data = {
            "platform_message_id": "cascade_test_msg",
            "type": "inbound",
            "content": "This will be deleted"
        }
        client.post(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/messages/", json=message_data)
        
        # Perform state transition (creates events)
        transition_data = {
            "current_state": "new",
            "next_state": "acknowledged",
            "reason": "Cascade test"
        }
        client.put(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/state", json=transition_data)
        
        # Verify thread exists with messages and events
        response = client.get(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}")
        assert response.status_code == 200
        
        response = client.get(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/messages/")
        assert response.status_code == 200
        assert len(response.json()["items"]) >= 1
        
        response = client.get(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/events/")
        assert response.status_code == 200
        assert len(response.json()["items"]) >= 1
        
        # Delete customer (should cascade to thread, messages, and events)
        response = client.delete(f"/api/v1/tenants/{tenant_id}/customers/{customer_id}")
        assert response.status_code == 204
        
        # Thread should no longer exist
        response = client.get(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}")
        assert response.status_code == 404
        
        # Messages should no longer exist
        response = client.get(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/messages/")
        assert response.status_code == 404
        
        # Events should no longer exist
        response = client.get(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/events/")
        assert response.status_code == 404
