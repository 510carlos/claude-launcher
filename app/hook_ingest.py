from __future__ import annotations

from app.models import SessionHookPayload, SessionStatus
from app.registry import SessionHistoryStore, SessionRegistry


def ingest_session_hook(*, registry: SessionRegistry, history_store: SessionHistoryStore, payload: SessionHookPayload) -> dict:
    target = registry.find_session(
        session_id=payload.session_id,
        workspot=payload.workspot,
        label=payload.label,
        statuses={SessionStatus.pending, SessionStatus.running},
    )
    if not target:
        return {"status": "error", "message": "No matching session found for hook payload."}

    updated = registry.mark_session(
        target.id,
        status=payload.status,
        url=payload.url,
        branch=payload.branch,
        metadata=payload.metadata,
        source=payload.source,
    )
    if updated and payload.url:
        history_store.save_session(
            payload.url,
            workspot=updated.workspot,
            worktree=updated.branch if updated.worktree_path else None,
            label=updated.label,
        )
    return {
        "status": "ok",
        "session": updated.model_dump(mode="json") if updated else None,
    }
