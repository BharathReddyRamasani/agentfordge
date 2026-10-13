"""State machine: valid transitions pass, illegal transitions are rejected and persisted."""

import pytest

from app.core.database import SessionLocal
from app.models.project import Project, ProjectStatus
from app.orchestrator.state import InvalidTransitionError, can_transition, transition


def test_legal_prototype_loop_transitions():
    assert can_transition(ProjectStatus.CREATED, ProjectStatus.ANALYZING)
    assert can_transition(ProjectStatus.AWAITING_REVIEW, ProjectStatus.APPROVED)
    assert can_transition(ProjectStatus.AWAITING_REVIEW, ProjectStatus.CHANGES_REQUESTED)
    assert can_transition(ProjectStatus.PROTOTYPE_REBUILDING, ProjectStatus.AWAITING_REVIEW)


def test_illegal_transitions_rejected():
    # Engineering must never start without approval
    assert not can_transition(ProjectStatus.AWAITING_REVIEW, ProjectStatus.ENGINEERING)
    assert not can_transition(ProjectStatus.CREATED, ProjectStatus.APPROVED)
    assert not can_transition(ProjectStatus.PLANNING, ProjectStatus.APPROVED)
    assert not can_transition(ProjectStatus.COMPLETED, ProjectStatus.ENGINEERING)
    assert not can_transition(ProjectStatus.CHANGES_REQUESTED, ProjectStatus.APPROVED)


def test_transition_persists_and_rejects():
    db = SessionLocal()
    try:
        p = Project(owner_id=1, name="SM", description="x", status=ProjectStatus.CREATED)
        db.add(p)
        db.commit()
        transition(db, p, ProjectStatus.ANALYZING)
        assert p.status == ProjectStatus.ANALYZING
        with pytest.raises(InvalidTransitionError):
            transition(db, p, ProjectStatus.ENGINEERING)
        db.refresh(p)
        assert p.status == ProjectStatus.ANALYZING
    finally:
        db.close()
