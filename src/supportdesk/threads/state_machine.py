"""Thread state machine logic and validation."""

from typing import Dict, Set
from uuid import UUID

from supportdesk.common.errors import StateTransitionError
from supportdesk.threads.models import ThreadState


class ThreadStateMachine:
    """State machine for thread state transitions."""
    
    # Valid state transitions
    TRANSITIONS: Dict[ThreadState, Set[ThreadState]] = {
        ThreadState.NEW: {
            ThreadState.ACKNOWLEDGED,
            ThreadState.IN_PROGRESS,
            ThreadState.NEEDS_REVIEW,
            ThreadState.URGENT
        },
        ThreadState.ACKNOWLEDGED: {
            ThreadState.IN_PROGRESS,
            ThreadState.NEEDS_REVIEW,
            ThreadState.URGENT,
            ThreadState.RESOLVED
        },
        ThreadState.IN_PROGRESS: {
            ThreadState.WAITING_FOR_CUSTOMER,
            ThreadState.NEEDS_REVIEW,
            ThreadState.URGENT,
            ThreadState.RESOLVED
        },
        ThreadState.WAITING_FOR_CUSTOMER: {
            ThreadState.IN_PROGRESS,
            ThreadState.NEEDS_REVIEW,
            ThreadState.URGENT,
            ThreadState.RESOLVED
        },
        ThreadState.NEEDS_REVIEW: {
            ThreadState.IN_PROGRESS,
            ThreadState.URGENT,
            ThreadState.RESOLVED
        },
        ThreadState.URGENT: {
            ThreadState.IN_PROGRESS,
            ThreadState.NEEDS_REVIEW,
            ThreadState.RESOLVED
        },
        ThreadState.RESOLVED: {
            ThreadState.CLOSED,
            ThreadState.IN_PROGRESS  # Reopen allowed
        },
        ThreadState.CLOSED: {
            ThreadState.IN_PROGRESS  # Admin reopen only
        }
    }
    
    @classmethod
    def is_valid_transition(cls, from_state: ThreadState, to_state: ThreadState) -> bool:
        """Check if a state transition is valid."""
        return to_state in cls.TRANSITIONS.get(from_state, set())
    
    @classmethod
    def get_allowed_transitions(cls, from_state: ThreadState) -> Set[ThreadState]:
        """Get all allowed transitions from a given state."""
        return cls.TRANSITIONS.get(from_state, set())
    
    @classmethod
    def validate_transition(cls, from_state: ThreadState, to_state: ThreadState, thread_id: UUID) -> None:
        """Validate a state transition, raising an error if invalid."""
        if not cls.is_valid_transition(from_state, to_state):
            allowed_transitions = list(cls.get_allowed_transitions(from_state))
            raise StateTransitionError(
                current_state=from_state,
                attempted_state=to_state,
                allowed_transitions=allowed_transitions,
                thread_id=thread_id
            )
    
    @classmethod
    def get_priority_for_state(cls, state: ThreadState) -> int:
        """Get the default priority for a given state."""
        priority_map = {
            ThreadState.NEW: 0,
            ThreadState.ACKNOWLEDGED: 0,
            ThreadState.IN_PROGRESS: 0,
            ThreadState.WAITING_FOR_CUSTOMER: 0,
            ThreadState.NEEDS_REVIEW: 5,
            ThreadState.URGENT: 10,
            ThreadState.RESOLVED: 0,
            ThreadState.CLOSED: 0
        }
        return priority_map.get(state, 0)
