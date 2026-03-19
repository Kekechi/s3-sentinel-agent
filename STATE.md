## **STATE.md: Implementation Snapshot**

* **Current Phase**: **Milestone 2 Complete** — The Gatekeeper.
* **Last Action**: GatekeeperNode security logic implemented. 11 unit tests passing, 2 integration tests available.
* **Blockers**: None.
* **Next Step**: Milestone 3 — The Admin HITL (LangGraph interrupt for admin approvals).

---

### What Was Implemented in M2

GatekeeperNode passthrough stub replaced with role-based access control. Guest ("user") role is blocked from `get_bucket_policy` via Python logic. Admin role is also blocked pending human approval (stub — real HITL interrupt is M3). Routing now branches on `is_blocked` state flag with a fail-closed default.

| File | What Changed |
|---|---|
| `src/graph/state.py` | Added `is_blocked: bool` to `AgentState` (now 5 fields) |
| `src/graph/nodes.py` | `GatekeeperNode` enforces Case A/B/C; imports `SENSITIVE_TOOLS`; returns delta dicts (fixed latent `return state` bug) |
| `src/graph/edges.py` | `route_after_gatekeeper` branches: `is_blocked=True` → `"AssistantNode"`, `is_blocked=False` → `"S3ToolNode"` |
| `cmd/main.py` | Expanded edge map to include `"AssistantNode"` route; added `--role` CLI arg via `sys.argv`; `is_blocked: True` in initial state |
| `tests/test_skeleton.py` | Added `is_blocked: True` to all state dicts and key assertions |
| `tests/test_gates.py` | **New file** — 7 unit tests + 1 integration test for all gatekeeper cases |

---

### Complete File Inventory

| File | Purpose |
|---|---|
| `src/graph/state.py` | `AgentState` TypedDict with 5 fields: `messages`, `is_policy_exposed`, `is_human_approved`, `is_blocked`, `role` |
| `src/graph/nodes.py` | `AssistantNode` (LLM + bound tools), `GatekeeperNode` (role-based access control), `S3ToolNode` (tool dispatch) |
| `src/graph/edges.py` | `route_after_assistant` (tool_calls → Gatekeeper, else → END), `route_after_gatekeeper` (is_blocked → AssistantNode, else → S3ToolNode) |
| `src/tools/s3_tools.py` | `list_buckets` and `get_bucket_policy` — hardcoded `@tool` functions |
| `src/core/security.py` | `SENSITIVE_TOOLS` and `ROLES` constants |
| `cmd/main.py` | `build_graph()` compiles the StateGraph; `main()` runs CLI loop with `--role` support |
| `tests/conftest.py` | Fixture to import `build_graph` from `cmd/main.py` via `importlib` |
| `tests/test_skeleton.py` | 4 unit tests + 1 integration: state instantiation, graph compilation, hello routing, edge routing (x2) |
| `tests/test_gates.py` | 7 unit tests + 1 integration: gatekeeper Case A/B/C, non-sensitive tool pass-through, edge routing (x2), end-to-end guest denial |
| `pytest.ini` | Registers `integration` custom mark |
| `requirements.txt` | `langgraph`, `langchain-openai`, `langchain-anthropic`, `python-dotenv`, `boto3`, `pytest` |
| `.env` | Placeholder secrets file (gitignored) |

---

### Types and Functions Reference

#### AgentState (`src/graph/state.py`)

```python
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]  # LangChain message history (reducer: add_messages)
    is_policy_exposed: bool   # True if get_bucket_policy returned data (NOT YET WIRED — M4)
    is_human_approved: bool   # True if admin approved a sensitive action (read by GatekeeperNode, NOT YET RESET — M3)
    is_blocked: bool          # Set by GatekeeperNode; read by route_after_gatekeeper. Fail-closed default: True
    role: str                 # "admin" or "user" — stored in state; migration to config["configurable"] deferred to M3
```

#### Nodes (`src/graph/nodes.py`)

| Function | Signature | Behavior |
|---|---|---|
| `AssistantNode` | `(state: AgentState) -> dict` | Invokes `gpt-4o-mini` with bound tools. Returns `{"messages": [AIMessage]}`. |
| `GatekeeperNode` | `(state: AgentState) -> dict` | Iterates `last_message.tool_calls`, checks each against `SENSITIVE_TOOLS`. Returns `{"is_blocked": True, "messages": [ToolMessage(...)]}` when blocked, or `{"is_blocked": False}` when authorized. |
| `S3ToolNode` | `(state: AgentState) -> dict` | Executes tool calls via `TOOLS_BY_NAME` lookup. Returns `{"messages": [ToolMessage(...)]}`. |

#### GatekeeperNode Decision Matrix

| Role | Tool | is_human_approved | Result | ToolMessage Content |
|---|---|---|---|---|
| `"user"` | `get_bucket_policy` | any | **BLOCKED** | `"Security Violation: Unauthorized"` |
| `"admin"` | `get_bucket_policy` | `False` | **BLOCKED** | `"Action requires human approval."` |
| `"admin"` | `get_bucket_policy` | `True` | ALLOWED | (none) |
| any | `list_buckets` | any | ALLOWED | (none) |

#### Edge Routers (`src/graph/edges.py`)

| Function | Logic |
|---|---|
| `route_after_assistant` | Has `tool_calls` → `"GatekeeperNode"` · No tool_calls → `END` |
| `route_after_gatekeeper` | `is_blocked` is `True` (or missing) → `"AssistantNode"` · `is_blocked` is `False` → `"S3ToolNode"` |

#### Tools (`src/tools/s3_tools.py`)

| Function | Args | Returns | Sensitive? |
|---|---|---|---|
| `list_buckets` | none | Hardcoded JSON array of 3 buckets | No |
| `get_bucket_policy` | `bucket_name: str` | Hardcoded S3 bucket policy JSON | **Yes** |

#### Constants (`src/core/security.py`)

| Name | Value |
|---|---|
| `SENSITIVE_TOOLS` | `["get_bucket_policy"]` |
| `ROLES` | `{"admin", "user"}` |

---

### Graph Flow (Current)

```
User Input
    ↓
AssistantNode (LLM suggests tools)
    ↓
route_after_assistant
    ├── no tool_calls → END
    └── has tool_calls → GatekeeperNode
                            ↓
                   route_after_gatekeeper
                     ├── is_blocked=True → AssistantNode (LLM explains denial)
                     └── is_blocked=False → S3ToolNode → AssistantNode (loop)
```

---

### Test Coverage

| File | Unit | Integration | LLM Required? |
|---|---|---|---|
| `tests/test_skeleton.py` | 4 | 1 | Integration only |
| `tests/test_gates.py` | 7 | 1 | Integration only |
| **Total** | **11** | **2** | |

Run unit tests: `pytest -m "not integration"`
Run all tests: `pytest` (requires `OPENAI_API_KEY`)

---

### Architectural Decisions (Cumulative)

1. **`cmd/` is not a Python package.** No `__init__.py` — `cmd` shadows stdlib. Tests import via `importlib`.
2. **LLM configured with `base_url` from env.** Supports non-default OpenAI-compatible endpoints.
3. **Integration tests marked separately.** `@pytest.mark.integration` for tests requiring live LLM key.
4. **Fail-closed default.** `is_blocked` defaults to `True` everywhere — initial state, `state.get()` fallback. If the field is missing, the system blocks.
5. **All-or-nothing blocking.** If any tool_call in a message is sensitive and unauthorized, the entire message is blocked. No partial execution.
6. **Delta returns from nodes.** GatekeeperNode returns only changed keys, not full state, to avoid re-adding messages through the `add_messages` reducer.

---

### Pending Dependencies for M3 (The Admin HITL)

| Item | Detail | Where |
|---|---|---|
| **Replace Case B stub with `interrupt()`** | GatekeeperNode currently blocks admin+sensitive with a ToolMessage. M3 must replace this with LangGraph's `interrupt()` / compiled breakpoint to PAUSE the graph. | `src/graph/nodes.py:51-58` |
| **`is_human_approved` reset after tool execution** | SPEC requires this flag reset to `False` after every S3ToolNode execution to prevent "Approval Carryover." | `src/graph/nodes.py` (S3ToolNode) |
| **Role migration to `config["configurable"]`** | SPEC says role is "extracted from `config['configurable']`". Currently in `AgentState` directly. | `src/graph/state.py`, `src/graph/nodes.py`, `cmd/main.py` |
| **Out-of-band resume signal** | SPEC requires the "Resume" signal from a separate trusted channel, not the user's chat. | `cmd/main.py` |
| **`is_policy_exposed` wiring** | Flag exists but is never set to `True`. Should trigger when `get_bucket_policy` succeeds. | `src/graph/nodes.py` (S3ToolNode), deferred to M3 or M4 |
