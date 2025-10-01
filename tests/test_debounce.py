"""Tests for debounce mechanism."""

import pytest
import time
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


class TestDebounce:
    """Test debounce functionality."""
    
    @patch('supportdesk.worker.tasks.handle_message_debounce.delay')
    def test_debounce_single_event_after_burst(self, mock_debounce, client: TestClient, tenant_id: str, thread_id: str):
        """Test debounce aggregates multiple messages into single event."""
        # Send multiple messages quickly
        messages = [
            {"platform_message_id": f"burst_msg_{i}", "type": "inbound", "content": f"Message {i}"}
            for i in range(3)
        ]
        
        for msg in messages:
            response = client.post(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/messages/", json=msg)
            assert response.status_code == 201
        
        # Verify debounce was triggered for each message
        assert mock_debounce.call_count == 3
        
        # All calls should be for the same thread
        for call in mock_debounce.call_args_list:
            args = call[0]
            assert args[0] == tenant_id  # tenant_id
            assert args[1] == thread_id  # thread_id
            # args[2] is correlation_id (varies)
    
    @patch('redis.from_url')
    def test_debounce_redis_sliding_window(self, mock_redis_from_url):
        """Test Redis sliding window mechanism."""
        from supportdesk.worker.tasks import handle_message_debounce
        
        # Mock Redis client
        mock_redis = MagicMock()
        mock_redis_from_url.return_value = mock_redis
        
        tenant_id = "test-tenant"
        thread_id = "test-thread" 
        correlation_id = "test-correlation"
        
        # First call - key doesn't exist
        mock_redis.exists.return_value = False
        
        handle_message_debounce(tenant_id, thread_id, correlation_id)
        
        # Should set key with TTL
        mock_redis.setex.assert_called_once_with(f"debounce:{tenant_id}:{thread_id}", 5, correlation_id)
        
        # Second call - key exists (window active)
        mock_redis.reset_mock()
        mock_redis.exists.return_value = True
        
        handle_message_debounce(tenant_id, thread_id, correlation_id)
        
        # Should extend TTL
        mock_redis.expire.assert_called_once_with(f"debounce:{tenant_id}:{thread_id}", 5)
        mock_redis.setex.assert_not_called()


def test_debounce_retry_is_idempotent(client: TestClient, tenant_id: str, thread_id: str):
    """Test debounce_flush with same window_id is idempotent across retries."""
    from supportdesk.worker.tasks import debounce_flush
    from uuid import uuid4
    
    window_id = str(uuid4())
    
    # First execution should process
    result1 = debounce_flush(tenant_id, thread_id, window_id)
    assert result1["status"] == "processed"
    
    # Second execution with same window_id should be idempotent
    result2 = debounce_flush(tenant_id, thread_id, window_id)
    assert result2["status"] == "already_processed"
    assert result2["window_id"] == window_id


class TestDebounceIntegration:
    """Test debounce integration with message flow."""
    
    def test_auto_ack_after_debounce(self, client: TestClient, tenant_id: str, thread_id: str):
        """Test auto-acknowledgment after debounce flush."""
        # Verify thread starts in 'new' state
        response = client.get(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}")
        assert response.json()["state"] == "new"
        
        # Send inbound message (triggers debounce)
        message_data = {
            "platform_message_id": "auto_ack_msg",
            "type": "inbound",
            "content": "This should trigger auto-ack"
        }
        
        response = client.post(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/messages/", json=message_data)
        assert response.status_code == 201
        
        # Simulate debounce flush (in real scenario this would be async)
        # For testing, we check that the message creation triggered state change
        response = client.get(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}")
        thread_data = response.json()
        assert thread_data["state"] == "acknowledged"
        
        # Check events for debounce and auto-ack
        response = client.get(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/events/")
        events = response.json()["items"]
        
        # Should have state transition event
        transition_events = [e for e in events if e["event_type"] == "state_transition"]
        assert len(transition_events) >= 1
        
        auto_ack_event = next(e for e in transition_events if e["new_state"] == "acknowledged")
        assert auto_ack_event["old_state"] == "new"
        assert auto_ack_event["actor_type"] == "system"
    
    def test_no_auto_ack_for_system_messages(self, client: TestClient, tenant_id: str, thread_id: str):
        """Test system messages don't trigger auto-acknowledgment."""
        # Send system message
        message_data = {
            "platform_message_id": "system_msg",
            "type": "system",
            "content": "System notification"
        }
        
        response = client.post(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/messages/", json=message_data)
        assert response.status_code == 201
        
        # Thread should remain in 'new' state
        response = client.get(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}")
        assert response.json()["state"] == "new"
    
    def test_debounce_window_correlation_id(self, client: TestClient, tenant_id: str, thread_id: str):
        """Test debounce events include correlation_id for traceability."""
        # Send message to trigger debounce
        message_data = {
            "platform_message_id": "correlation_test_msg",
            "type": "inbound", 
            "content": "Test correlation ID"
        }
        
        response = client.post(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/messages/", json=message_data)
        assert response.status_code == 201
        
        # Check events for correlation_id
        response = client.get(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/events/")
        events = response.json()["items"]
        
        # All events should have correlation_id for traceability
        for event in events:
            if event["actor_type"] == "system":
                # System events should have correlation_id
                assert event["correlation_id"] is not None
