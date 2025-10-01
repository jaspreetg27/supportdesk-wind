"""Tests for thread state machine."""

import pytest
from uuid import uuid4

from supportdesk.threads.models import ThreadState
from supportdesk.threads.state_machine import ThreadStateMachine
from supportdesk.common.errors import StateTransitionError


class TestStateMachine:
    """Test state machine logic."""
    
    def test_valid_transitions(self):
        """Test all valid state transitions."""
        valid_cases = [
            (ThreadState.NEW, ThreadState.ACKNOWLEDGED),
            (ThreadState.NEW, ThreadState.IN_PROGRESS),
            (ThreadState.NEW, ThreadState.NEEDS_REVIEW),
            (ThreadState.NEW, ThreadState.URGENT),
            (ThreadState.ACKNOWLEDGED, ThreadState.IN_PROGRESS),
            (ThreadState.ACKNOWLEDGED, ThreadState.NEEDS_REVIEW),
            (ThreadState.ACKNOWLEDGED, ThreadState.URGENT),
            (ThreadState.ACKNOWLEDGED, ThreadState.RESOLVED),
            (ThreadState.IN_PROGRESS, ThreadState.WAITING_FOR_CUSTOMER),
            (ThreadState.IN_PROGRESS, ThreadState.NEEDS_REVIEW),
            (ThreadState.IN_PROGRESS, ThreadState.URGENT),
            (ThreadState.IN_PROGRESS, ThreadState.RESOLVED),
            (ThreadState.WAITING_FOR_CUSTOMER, ThreadState.IN_PROGRESS),
            (ThreadState.WAITING_FOR_CUSTOMER, ThreadState.NEEDS_REVIEW),
            (ThreadState.WAITING_FOR_CUSTOMER, ThreadState.URGENT),
            (ThreadState.WAITING_FOR_CUSTOMER, ThreadState.RESOLVED),
            (ThreadState.NEEDS_REVIEW, ThreadState.IN_PROGRESS),
            (ThreadState.NEEDS_REVIEW, ThreadState.URGENT),
            (ThreadState.NEEDS_REVIEW, ThreadState.RESOLVED),
            (ThreadState.URGENT, ThreadState.IN_PROGRESS),
            (ThreadState.URGENT, ThreadState.NEEDS_REVIEW),
            (ThreadState.URGENT, ThreadState.RESOLVED),
            (ThreadState.RESOLVED, ThreadState.CLOSED),
            (ThreadState.RESOLVED, ThreadState.IN_PROGRESS),  # Reopen
            (ThreadState.CLOSED, ThreadState.IN_PROGRESS),  # Admin reopen
        ]
        
        for from_state, to_state in valid_cases:
            assert ThreadStateMachine.is_valid_transition(from_state, to_state), \
                f"Expected {from_state} -> {to_state} to be valid"
    
    def test_invalid_transitions(self):
        """Test invalid state transitions."""
        invalid_cases = [
            (ThreadState.NEW, ThreadState.RESOLVED),  # Skip intermediate states
            (ThreadState.NEW, ThreadState.CLOSED),
            (ThreadState.ACKNOWLEDGED, ThreadState.NEW),  # Backwards
            (ThreadState.IN_PROGRESS, ThreadState.NEW),
            (ThreadState.RESOLVED, ThreadState.NEW),
            (ThreadState.CLOSED, ThreadState.NEW),
            (ThreadState.CLOSED, ThreadState.ACKNOWLEDGED),
            (ThreadState.CLOSED, ThreadState.NEEDS_REVIEW),
        ]
        
        for from_state, to_state in invalid_cases:
            assert not ThreadStateMachine.is_valid_transition(from_state, to_state), \
                f"Expected {from_state} -> {to_state} to be invalid"
    
    def test_get_allowed_transitions(self):
        """Test getting allowed transitions for each state."""
        # Test specific states
        new_transitions = ThreadStateMachine.get_allowed_transitions(ThreadState.NEW)
        expected_new = {ThreadState.ACKNOWLEDGED, ThreadState.IN_PROGRESS, ThreadState.NEEDS_REVIEW, ThreadState.URGENT}
        assert new_transitions == expected_new
        
        closed_transitions = ThreadStateMachine.get_allowed_transitions(ThreadState.CLOSED)
        expected_closed = {ThreadState.IN_PROGRESS}  # Only admin reopen
        assert closed_transitions == expected_closed
    
    def test_validate_transition_success(self):
        """Test successful transition validation."""
        thread_id = uuid4()
        
        # Should not raise exception
        ThreadStateMachine.validate_transition(ThreadState.NEW, ThreadState.ACKNOWLEDGED, thread_id)
        ThreadStateMachine.validate_transition(ThreadState.RESOLVED, ThreadState.CLOSED, thread_id)
    
    def test_validate_transition_failure(self):
        """Test failed transition validation."""
        thread_id = uuid4()
        
        # Should raise StateTransitionError
        with pytest.raises(StateTransitionError) as exc_info:
            ThreadStateMachine.validate_transition(ThreadState.NEW, ThreadState.RESOLVED, thread_id)
        
        error = exc_info.value
        assert error.current_state == "new"
        assert error.attempted_state == "resolved"
        assert error.thread_id == thread_id
        assert len(error.allowed_transitions) > 0
    
    def test_get_priority_for_state(self):
        """Test priority mapping for states."""
        assert ThreadStateMachine.get_priority_for_state(ThreadState.NEW) == 0
        assert ThreadStateMachine.get_priority_for_state(ThreadState.ACKNOWLEDGED) == 0
        assert ThreadStateMachine.get_priority_for_state(ThreadState.NEEDS_REVIEW) == 5
        assert ThreadStateMachine.get_priority_for_state(ThreadState.URGENT) == 10
        assert ThreadStateMachine.get_priority_for_state(ThreadState.RESOLVED) == 0


def test_state_transition_returns_422_not_409_on_invalid(client, tenant_id: str, thread_id: str):
    """Test invalid state transitions return 422 with STATE_TRANSITION_INVALID."""
    # Try invalid transition
    transition_data = {
        "current_state": "new",
        "next_state": "closed",  # Invalid: can't go directly from new to closed
        "reason": "Invalid transition test"
    }
    
    response = client.put(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/state", json=transition_data)
    
    # Should return 422 (validation error), not 409 (conflict)
    assert response.status_code == 422
    error = response.json()
    assert error["error"] == "STATE_TRANSITION_INVALID"
    assert "allowed_transitions" in error["details"]
    assert "current_state" in error["details"]
    assert "attempted_state" in error["details"]
