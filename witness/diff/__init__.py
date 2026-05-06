"""Behavioral diff: compare two traces."""
from witness.diff.behavioral import (
    DecisionAlignment,
    DecisionChange,
    TraceDiff,
    diff,
)

__all__ = ["diff", "TraceDiff", "DecisionAlignment", "DecisionChange"]
