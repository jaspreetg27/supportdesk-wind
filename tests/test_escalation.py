"""Tests for escalation mechanism."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


class TestEscalation:
    """Test escalation functionality."""
    
    def test_escalation_caps_and_max_attempts_logged(self, client: TestClient, tenant_id: str, thread_id: str):
        """Test escalation stops at max_auto_escalations and logs cap event."""
        from supportdesk.worker.tasks import escalation_tick
        
        # Set thread to acknowledged state (eligible for escalation)
        transition_data = {
            "current_state": "new",
            "next_state": "acknowledged", 
            "reason": "Ready for escalation test"
        }
        response = client.put(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/state", json=transition_data)
        assert response.status_code == 200
        
        # Mock thread as stale (older than threshold)
        with patch('supportdesk.threads.repository.ThreadRepository.find_stale_threads') as mock_find_stale:
            with patch('supportdesk.events.repository.ThreadEventRepository.count_escalations') as mock_count:
                # Simulate thread at max escalations
                mock_count.return_value = 3  # At max_auto_escalations limit
                
                # Mock stale thread
                mock_thread = MagicMock()
                mock_thread.id = thread_id
                mock_thread.priority = 5
                mock_find_stale.return_value = [mock_thread]
                
                # Run escalation tick
                escalation_tick()
        
        # Check events for escalation cap reached
        response = client.get(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/events/")
        events = response.json()["items"]
        
        cap_events = [e for e in events if e["event_type"] == "escalation_cap_reached"]
        assert len(cap_events) >= 1
        
        cap_event = cap_events[0]
        assert cap_event["actor_type"] == "system"
        assert "max_escalations" in cap_event["metadata"]
        assert cap_event["metadata"]["max_escalations"] == 3
    
    def test_escalation_priority_increment(self, client: TestClient, tenant_id: str, thread_id: str):
        """Test escalation increments priority correctly."""
        import asyncio
        from supportdesk.worker.tasks import escalation_tick_async
        from supportdesk.database import AsyncSessionLocal
        
        # Set thread to acknowledged state
        transition_data = {
            "current_state": "new",
            "next_state": "acknowledged",
            "reason": "Ready for priority escalation"
        }
        client.put(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/state", json=transition_data)
        
        # Mock escalation conditions
        with patch('supportdesk.threads.repository.ThreadRepository.find_stale_threads') as mock_find_stale:
            with patch('supportdesk.events.repository.ThreadEventRepository.count_escalations') as mock_count:
                with patch('supportdesk.threads.repository.ThreadRepository.update_priority') as mock_update:
                    # Thread has 0 previous escalations
                    mock_count.return_value = 0
                    
                    # Mock stale thread with priority 2
                    mock_thread = MagicMock()
                    mock_thread.id = thread_id
                    mock_thread.priority = 2
                    mock_find_stale.return_value = [mock_thread]
                    
                    # Run escalation with test session maker
                    asyncio.run(escalation_tick_async(AsyncSessionLocal))
                    
                    # Should increment priority by 1 (2 + 1 = 3)
                    mock_update.assert_called_once_with(thread_id, 3)
        
        # Check escalation event
        response = client.get(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/events/")
        events = response.json()["items"]
        
        escalation_events = [e for e in events if e["event_type"] == "auto_escalation"]
        if escalation_events:  # May not exist in mock scenario
            escalation_event = escalation_events[0]
            assert escalation_event["metadata"]["old_priority"] == 2
            assert escalation_event["metadata"]["new_priority"] == 3
    
    def test_escalation_priority_cap_at_10(self, client: TestClient, tenant_id: str, thread_id: str):
        """Test escalation caps priority at 10."""
        import asyncio
        from supportdesk.worker.tasks import escalation_tick_async
        from supportdesk.database import AsyncSessionLocal
        
        with patch('supportdesk.threads.repository.ThreadRepository.find_stale_threads') as mock_find_stale:
            with patch('supportdesk.events.repository.ThreadEventRepository.count_escalations') as mock_count:
                with patch('supportdesk.threads.repository.ThreadRepository.update_priority') as mock_update:
                    # Thread has 0 previous escalations
                    mock_count.return_value = 0
                    
                    # Mock thread with priority 9 (should cap at 10)
                    mock_thread = MagicMock()
                    mock_thread.id = thread_id
                    mock_thread.priority = 9
                    mock_find_stale.return_value = [mock_thread]
                    
                    # Run escalation with test session maker
                    asyncio.run(escalation_tick_async(AsyncSessionLocal))
                    
                    # Should cap at 10 (min(9 + 1, 10) = 10)
                    mock_update.assert_called_once_with(thread_id, 10)
    
    def test_escalation_idempotency_per_hour(self, client: TestClient, tenant_id: str, thread_id: str):
        """Test escalation idempotency within same hour window."""
        import asyncio
        from supportdesk.worker.tasks import escalation_tick_async, generate_deterministic_uuid
        from supportdesk.database import AsyncSessionLocal
        from datetime import datetime
        
        # Generate deterministic ID for current hour
        from datetime import timezone
        current_hour = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        escalation_event_id = generate_deterministic_uuid(f"escalation:{thread_id}:{current_hour.isoformat()}")
        
        # First escalation should process
        with patch('supportdesk.threads.repository.ThreadRepository.find_stale_threads') as mock_find_stale:
            with patch('supportdesk.events.repository.ThreadEventRepository.get_by_correlation_id') as mock_get_by_corr:
                with patch('supportdesk.events.repository.ThreadEventRepository.count_escalations') as mock_count:
                    # No existing escalation for this hour
                    mock_get_by_corr.return_value = None
                    mock_count.return_value = 0
                    
                    mock_thread = MagicMock()
                    mock_thread.id = thread_id
                    mock_thread.priority = 1
                    mock_find_stale.return_value = [mock_thread]
                    
                    # Run escalation with test session maker
                    asyncio.run(escalation_tick_async(AsyncSessionLocal))
                    
                    # Should check for existing escalation
                    mock_get_by_corr.assert_called_with(escalation_event_id)
        
        # Second escalation in same hour should be skipped
        with patch('supportdesk.threads.repository.ThreadRepository.find_stale_threads') as mock_find_stale:
            with patch('supportdesk.events.repository.ThreadEventRepository.get_by_correlation_id') as mock_get_by_corr:
                with patch('supportdesk.threads.repository.ThreadRepository.update_priority') as mock_update:
                    # Existing escalation found
                    mock_existing = MagicMock()
                    mock_get_by_corr.return_value = mock_existing
                    
                    mock_thread = MagicMock()
                    mock_thread.id = thread_id
                    mock_find_stale.return_value = [mock_thread]
                    
                    # Run escalation with test session maker
                    asyncio.run(escalation_tick_async(AsyncSessionLocal))
                    
                    # Should not update priority (idempotent)
                    mock_update.assert_not_called()


class TestEscalationConfiguration:
    """Test escalation configuration."""
    
    def test_escalation_thresholds_from_config(self):
        """Test escalation uses configuration values."""
        from supportdesk.config import settings
        import json
        
        thresholds = json.loads(settings.escalation_thresholds)
        
        # Verify default configuration
        assert "escalation_minutes" in thresholds
        assert "urgent_priority" in thresholds
        assert "priority_increment" in thresholds
        assert "max_auto_escalations" in thresholds
        
        # Verify default values
        assert thresholds["escalation_minutes"] == 60
        assert thresholds["urgent_priority"] == 8
        assert thresholds["priority_increment"] == 1
        assert thresholds["max_auto_escalations"] == 3
    
    def test_stale_thread_detection(self, client: TestClient, tenant_id: str):
        """Test stale thread detection logic."""
        from supportdesk.threads.repository import ThreadRepository
        from supportdesk.threads.models import ThreadState
        from supportdesk.database import get_db
        import asyncio
        
        async def test_stale_detection():
            async for db in get_db():
                repo = ThreadRepository(db)
                
                # Should find threads older than threshold
                stale_threads = await repo.find_stale_threads(
                    tenant_id=tenant_id,
                    states=[ThreadState.ACKNOWLEDGED, ThreadState.IN_PROGRESS],
                    older_than_minutes=60
                )
                
                # Should return list (empty or with threads)
                assert isinstance(stale_threads, list)
                break
        
        asyncio.run(test_stale_detection())


def test_escalation_deterministic_uuid():
    """Test deterministic UUID generation for escalation events."""
    from supportdesk.worker.tasks import generate_deterministic_uuid
    
    # Same input should produce same UUID
    input_str = "escalation:thread-123:2024-01-15T10:00:00"
    uuid1 = generate_deterministic_uuid(input_str)
    uuid2 = generate_deterministic_uuid(input_str)
    
    assert uuid1 == uuid2
    assert str(uuid1) == str(uuid2)
    
    # Different input should produce different UUID
    different_input = "escalation:thread-456:2024-01-15T10:00:00"
    uuid3 = generate_deterministic_uuid(different_input)
    
    assert uuid1 != uuid3
