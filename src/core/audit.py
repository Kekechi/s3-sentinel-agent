"""Audit instrumentation helpers for LangSmith tracing.

All functions are no-ops when tracing is not active (get_current_run_tree() returns None).
"""

from typing import Optional

from langsmith.run_helpers import get_current_run_tree


def tag_security_event(event_name: str) -> None:
    """Append a security event tag to the current LangSmith run.

    Args:
        event_name: e.g. "security_event:access_denied", "policy_exposed:true"
    """
    run_tree = get_current_run_tree()
    if run_tree is not None:
        run_tree.tags = run_tree.tags or []
        run_tree.tags.append(event_name)


def set_audit_metadata(
    *,
    role: Optional[str] = None,
    thread_id: Optional[str] = None,
    is_human_approved: Optional[bool] = None,
    is_blocked: Optional[bool] = None,
    is_policy_exposed: Optional[bool] = None,
) -> None:
    """Push audit-relevant fields into the current run's metadata.

    Only non-None values are written. No-op when tracing is inactive.
    """
    run_tree = get_current_run_tree()
    if run_tree is None:
        return
    metadata_update = {}
    if role is not None:
        metadata_update["role"] = role
    if thread_id is not None:
        metadata_update["thread_id"] = thread_id
    if is_human_approved is not None:
        metadata_update["is_human_approved"] = is_human_approved
    if is_blocked is not None:
        metadata_update["is_blocked"] = is_blocked
    if is_policy_exposed is not None:
        metadata_update["is_policy_exposed"] = is_policy_exposed
    run_tree.metadata.update(metadata_update)
