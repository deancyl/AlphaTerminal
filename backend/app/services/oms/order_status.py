"""
Order Status State Machine

Implements a finite state machine for order lifecycle management.
All state transitions are validated against VALID_TRANSITIONS.

States:
- STAGED: Created but not submitted
- SUBMITTED: Sent to broker
- VALIDATED: Passed pre-trade checks
- PENDING: Waiting for execution
- PARTIAL_FILLED: Partially executed
- FILLED: Fully executed
- CANCELLED: User cancelled
- REJECTED: Broker rejected
- EXPIRED: Order expired (GTC, day orders)
"""

from enum import Enum
from typing import Dict, List, Set


class OrderStatus(Enum):
    """Order lifecycle states with clear semantics."""
    
    STAGED = "staged"
    SUBMITTED = "submitted"
    VALIDATED = "validated"
    PENDING = "pending"
    PARTIAL_FILLED = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


# State transition matrix: from_state -> [allowed_to_states]
VALID_TRANSITIONS: Dict[OrderStatus, List[OrderStatus]] = {
    OrderStatus.STAGED: [
        OrderStatus.SUBMITTED,
        OrderStatus.CANCELLED,
    ],
    OrderStatus.SUBMITTED: [
        OrderStatus.VALIDATED,
        OrderStatus.REJECTED,
    ],
    OrderStatus.VALIDATED: [
        OrderStatus.PENDING,
        OrderStatus.REJECTED,
    ],
    OrderStatus.PENDING: [
        OrderStatus.PARTIAL_FILLED,
        OrderStatus.FILLED,
        OrderStatus.CANCELLED,
        OrderStatus.EXPIRED,
    ],
    OrderStatus.PARTIAL_FILLED: [
        OrderStatus.FILLED,
        OrderStatus.CANCELLED,
    ],
    # Terminal states - no transitions allowed
    OrderStatus.FILLED: [],
    OrderStatus.CANCELLED: [],
    OrderStatus.REJECTED: [],
    OrderStatus.EXPIRED: [],
}


def is_valid_transition(from_status: OrderStatus, to_status: OrderStatus) -> bool:
    """Check if a state transition is valid."""
    allowed = VALID_TRANSITIONS.get(from_status, [])
    return to_status in allowed


def get_allowed_transitions(status: OrderStatus) -> List[OrderStatus]:
    """Get all allowed next states for a given status."""
    return VALID_TRANSITIONS.get(status, []).copy()


def is_terminal_status(status: OrderStatus) -> bool:
    """Check if the status is terminal (no further transitions)."""
    return len(VALID_TRANSITIONS.get(status, [])) == 0


def get_active_statuses() -> Set[OrderStatus]:
    """Get all statuses that represent active (non-terminal) orders."""
    return {
        OrderStatus.STAGED,
        OrderStatus.SUBMITTED,
        OrderStatus.VALIDATED,
        OrderStatus.PENDING,
        OrderStatus.PARTIAL_FILLED,
    }


def get_terminal_statuses() -> Set[OrderStatus]:
    """Get all terminal statuses (order lifecycle ended)."""
    return {
        OrderStatus.FILLED,
        OrderStatus.CANCELLED,
        OrderStatus.REJECTED,
        OrderStatus.EXPIRED,
    }
