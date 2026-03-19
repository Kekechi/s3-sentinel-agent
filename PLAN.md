# Milestone 2: The Gatekeeper — Implementation Plan

## Context

M1 built the skeleton: `AgentState`, three graph nodes (AssistantNode, GatekeeperNode, S3ToolNode), conditional edges, and mock S3 tools. GatekeeperNode is currently a passthrough stub (`return state`). M2 replaces it with real role-based access control so that **guest ("user") role is blocked from `get_bucket_policy` via Python code** — not prompt instructions.

---

## Files to Modify

| File | Change |
|---|---|
| `src/graph/state.py` | Add `is_blocked: bool` field |
| `src/graph/nodes.py` | Replace GatekeeperNode stub with security logic |
| `src/graph/edges.py` | Replace route_after_gatekeeper stub with branching |
| `cmd/main.py` | Expand edge map + add `--role` CLI arg |
| `src/core/security.py` | No changes needed (SENSITIVE_TOOLS already defined) |
| `tests/test_skeleton.py` | Add `is_blocked` to existing state dicts |
| `tests/test_gates.py` | **New file** — security boundary tests |

---

## Steps

### Step 1: Add `is_blocked` to AgentState
**File:** `src/graph/state.py`
- Add `is_blocked: bool` to the `AgentState` TypedDict
- This gives the edge router a clean signal to inspect after the gatekeeper runs

### Step 2: Implement GatekeeperNode logic
**File:** `src/graph/nodes.py`
- Import `SENSITIVE_TOOLS` from `src.core.security`
- Replace the passthrough stub with logic that iterates over `last_message.tool_calls`:
  - **Case A (Guest + sensitive tool):** Inject `ToolMessage(content="Security Violation: Unauthorized")`, set `is_blocked=True`
  - **Case B (Admin + sensitive tool + not approved):** Inject `ToolMessage(content="Action requires human approval.")`, set `is_blocked=True` *(stub for M3 HITL)*
  - **Case C (Authorized):** Non-sensitive tool OR admin with approval → set `is_blocked=False`, return no messages
- Return only the delta dict, not the full state (fix the latent `return state` bug)

### Step 3: Implement route_after_gatekeeper branching
**File:** `src/graph/edges.py`
- If `state["is_blocked"]` is `True` → return `"AssistantNode"` (LLM processes the denial ToolMessage and responds to user)
- If `False` → return `"S3ToolNode"` (proceed to execute tools)

### Step 4: Update graph wiring and CLI
**File:** `cmd/main.py`
- Expand the conditional edge map for GatekeeperNode to include `"AssistantNode"`:
  ```python
  {"S3ToolNode": "S3ToolNode", "AssistantNode": "AssistantNode"}
  ```
- Add `is_blocked: False` to the initial state in `app.invoke()`
- Add `--role` CLI argument (defaults to `"admin"`) via `sys.argv`

### Step 5: Update existing M1 tests
**File:** `tests/test_skeleton.py`
- Add `"is_blocked": False` to every state dict in the 5 existing tests
- Update the `set(state.keys())` assertion to include `"is_blocked"`

### Step 6: Create security boundary tests
**File:** `tests/test_gates.py` *(new)*

Helper: `_make_state(role, tool_name, is_human_approved=False)` — builds an `AgentState` with a synthetic `AIMessage` containing one `tool_call`.

| Test | Asserts |
|---|---|
| `test_guest_blocked_on_sensitive_tool` | Case A: returns `is_blocked=True`, ToolMessage contains "Security Violation" |
| `test_guest_allowed_on_nonsensitive_tool` | `list_buckets` → `is_blocked=False`, no injected messages |
| `test_admin_blocked_without_approval` | Case B stub: `is_blocked=True` |
| `test_admin_allowed_with_approval` | Case C: `is_blocked=False` |
| `test_admin_allowed_on_nonsensitive_tool` | `list_buckets` → `is_blocked=False` |
| `test_route_blocked_goes_to_assistant` | `is_blocked=True` → routes to `"AssistantNode"` |
| `test_route_authorized_goes_to_s3tool` | `is_blocked=False` → routes to `"S3ToolNode"` |
| `test_guest_violation_end_to_end` | *(integration, @pytest.mark.integration)* Full graph with role="user" asking for bucket policy → final response is a denial, no policy data |

---

## Verification

1. `pytest tests/test_skeleton.py -m "not integration"` — existing tests pass with new `is_blocked` field
2. `pytest tests/test_gates.py -m "not integration"` — all 7 unit tests pass (no LLM needed)
3. `pytest tests/test_gates.py -m integration` — end-to-end guest violation test passes
4. Manual: `python cmd/main.py --role user` → ask for bucket policy → blocked
5. Manual: `python cmd/main.py --role admin` → ask to list buckets → works normally

## Deferred to Later Milestones

| Item | Milestone |
|---|---|
| Real HITL interrupt/PAUSE for admin approval | M3 |
| `role` migration to `config["configurable"]` | M3 |
| `is_human_approved` reset after tool execution | M3 |
| `is_policy_exposed` set to True on policy retrieval | M4 |
