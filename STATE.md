## **STATE.md: Implementation Snapshot**

* **Current Phase**: **Milestone 3 Complete** — The Admin HITL.
* **Last Action**: Real HITL interrupt/resume flow via `interrupt()`, SqliteSaver persistence, config-based role, approval reset. 16 unit tests passing, 2 integration tests available.
* **Blockers**: None.
* **Next Step**: Milestone 4 — Storage & Policy Wiring (MinIO integration, `is_policy_exposed` wiring).

---

### What Was Implemented in M3

Replaced the Case B dead-end stub with a real Human-In-The-Loop flow using LangGraph's `interrupt()`. Added SqliteSaver for persistence (required by interrupt). Migrated `role` from user-mutable `AgentState` into trusted `config["configurable"]` (fail-closed default: `"user"`). Added approval reset in S3ToolNode to prevent carryover.

| File | What Changed |
|---|---|
| `requirements.txt` | Added `langgraph-checkpoint-sqlite>=2.0.0` |
| `src/graph/state.py` | Removed `role: str` field (5 → 4 fields) |
| `src/graph/nodes.py` | `GatekeeperNode` takes `config: RunnableConfig`; Case B replaced with `interrupt()`; approved path sets `is_human_approved: True`; `S3ToolNode` resets `is_human_approved: False` |
| `cmd/main.py` | `build_graph()` accepts optional `checkpointer`; `main()` uses `SqliteSaver`, `thread_id` + `role` in config, interrupt resume loop via `state.next` check |
| `tests/conftest.py` | Added `build_graph_with_checkpointer` fixture (SqliteSaver in-memory) |
| `tests/test_skeleton.py` | Removed `role` from all state dicts; updated key assertion from 5 to 4; integration tests pass `config` |
| `tests/test_gates.py` | `_make_state()` no longer takes `role`; all `GatekeeperNode` calls pass `config`; removed Case B/C stub tests; added fail-closed tests for missing/empty config |
| `tests/test_hitl.py` | **New file** — 4 interrupt tests + 1 checkpointer test |

---

### Complete File Inventory

| File | Purpose |
|---|---|
| `src/graph/state.py` | `AgentState` TypedDict with 4 fields: `messages`, `is_policy_exposed`, `is_human_approved`, `is_blocked` |
| `src/graph/nodes.py` | `AssistantNode` (LLM + bound tools), `GatekeeperNode` (role-based access + interrupt), `S3ToolNode` (tool dispatch + approval reset) |
| `src/graph/edges.py` | `route_after_assistant` (tool_calls → Gatekeeper, else → END), `route_after_gatekeeper` (is_blocked → AssistantNode, else → S3ToolNode) |
| `src/tools/s3_tools.py` | `list_buckets` and `get_bucket_policy` — hardcoded `@tool` functions |
| `src/core/security.py` | `SENSITIVE_TOOLS` and `ROLES` constants |
| `cmd/main.py` | `build_graph(checkpointer=None)` compiles the StateGraph; `main()` runs CLI loop with SqliteSaver, `--role`, and interrupt handling |
| `tests/conftest.py` | `build_graph` fixture (importlib); `build_graph_with_checkpointer` fixture (SqliteSaver in-memory) |
| `tests/test_skeleton.py` | 4 unit tests + 1 integration: state instantiation, graph compilation, hello routing, edge routing (x2) |
| `tests/test_gates.py` | 7 unit tests + 1 integration: Case A blocking, non-sensitive pass-through, fail-closed defaults (x2), edge routing (x2), end-to-end guest denial |
| `tests/test_hitl.py` | 5 tests: interrupt pauses graph, approve resumes, deny produces denial message, approval resets after execution, checkpointer compiles |
| `pytest.ini` | Registers `integration` custom mark |
| `requirements.txt` | `langgraph`, `langchain-openai`, `langchain-anthropic`, `langgraph-checkpoint-sqlite`, `python-dotenv`, `boto3`, `pytest` |
| `.env` | Placeholder secrets file (gitignored) |

---

### Types and Functions Reference

#### AgentState (`src/graph/state.py`)

```python
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]  # LangChain message history (reducer: add_messages)
    is_policy_exposed: bool   # True if get_bucket_policy returned data (NOT YET WIRED — M4)
    is_human_approved: bool   # Set True by GatekeeperNode on approval; reset False by S3ToolNode after execution
    is_blocked: bool          # Set by GatekeeperNode; read by route_after_gatekeeper. Fail-closed default: True
```

**Note**: `role` was removed from AgentState in M3. It now lives in `config["configurable"]["role"]`.

#### Nodes (`src/graph/nodes.py`)

| Function | Signature | Behavior |
|---|---|---|
| `AssistantNode` | `(state: AgentState) -> dict` | Invokes `gpt-4o-mini` with bound tools. Returns `{"messages": [AIMessage]}`. |
| `GatekeeperNode` | `(state: AgentState, config: RunnableConfig) -> dict` | Extracts `role` from `config["configurable"]` (default: `"user"`). For sensitive tools: user → Security Violation; admin → `interrupt()` for HITL approval. Returns `{"is_blocked": True, "messages": [...]}` when blocked, or `{"is_blocked": False, "is_human_approved": True}` when authorized. |
| `S3ToolNode` | `(state: AgentState) -> dict` | Executes tool calls via `TOOLS_BY_NAME` lookup. Returns `{"messages": [ToolMessage(...)], "is_human_approved": False}`. Resets approval flag to prevent carryover. |

#### GatekeeperNode Decision Matrix (M3 — interrupt-based)

| Role | Tool | Mechanism | Result |
|---|---|---|---|
| `"user"` | `get_bucket_policy` | ToolMessage | **BLOCKED** — `"Security Violation: Unauthorized"` |
| `"admin"` | `get_bucket_policy` | `interrupt()` | **PAUSED** — graph stops, CLI prompts for y/n |
| `"admin"` (approved) | `get_bucket_policy` | `interrupt()` returns `True` | **ALLOWED** — `is_human_approved: True`, `is_blocked: False` |
| `"admin"` (denied) | `get_bucket_policy` | `interrupt()` returns `False` | **BLOCKED** — `"Admin denied the action."` |
| missing/empty role | `get_bucket_policy` | defaults to `"user"` | **BLOCKED** — fail-closed |
| any | `list_buckets` | (no check) | **ALLOWED** |

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

#### Key Imports Added in M3

| Import | Source | Used In |
|---|---|---|
| `RunnableConfig` | `langchain_core.runnables` | `GatekeeperNode` signature |
| `interrupt` | `langgraph.types` | `GatekeeperNode` HITL pause |
| `Command` | `langgraph.types` | `cmd/main.py` resume signal |
| `SqliteSaver` | `langgraph.checkpoint.sqlite` | `cmd/main.py`, `tests/conftest.py`, `tests/test_hitl.py` |

#### Test Fixtures (`tests/conftest.py`)

| Fixture | Returns | Notes |
|---|---|---|
| `build_graph` | `Callable` — the `build_graph(checkpointer=None)` function | Imported via `importlib` from `cmd/main.py` |
| `build_graph_with_checkpointer` | Compiled graph app with in-memory SqliteSaver | Yielded inside context manager; uses `build_graph` fixture |

---

### Graph Flow (Current — M3)

```
User Input
    ↓
AssistantNode (LLM suggests tools)
    ↓
route_after_assistant
    ├── no tool_calls → END
    └── has tool_calls → GatekeeperNode
                            ↓
                   role from config["configurable"] (default: "user")
                            ↓
                   ┌── user + sensitive → BLOCKED (Security Violation) → AssistantNode
                   ├── admin + sensitive → interrupt() PAUSES graph
                   │       ↓
                   │   CLI prompts admin → Command(resume=True/False)
                   │       ├── approved → is_blocked=False → S3ToolNode → AssistantNode
                   │       └── denied → BLOCKED (Admin denied) → AssistantNode
                   └── non-sensitive → is_blocked=False → S3ToolNode → AssistantNode
```

**Interrupt behavior (LangGraph 1.x)**: `interrupt()` does NOT raise `GraphInterrupt`. The graph returns a result with `__interrupt__` key and `app.get_state(config).next` is non-empty. Resume by invoking with `Command(resume=value)`.

---

### Test Coverage

| File | Unit | Integration | LLM Required? |
|---|---|---|---|
| `tests/test_skeleton.py` | 4 | 1 | Integration only |
| `tests/test_gates.py` | 7 | 1 | Integration only |
| `tests/test_hitl.py` | 5 | 0 | No (uses `update_state` to inject tool calls) |
| **Total** | **16** | **2** | |

Run unit tests: `pytest -m "not integration"`
Run all tests: `pytest` (requires `OPENAI_API_KEY`)

---

### Architectural Decisions (Cumulative)

1. **`cmd/` is not a Python package.** No `__init__.py` — `cmd` shadows stdlib. Tests import via `importlib`.
2. **LLM configured with `base_url` from env.** Supports non-default OpenAI-compatible endpoints.
3. **Integration tests marked separately.** `@pytest.mark.integration` for tests requiring live LLM key.
4. **Fail-closed default.** `is_blocked` defaults to `True` everywhere. Missing `role` in config defaults to `"user"` (unprivileged).
5. **All-or-nothing blocking.** If any tool_call in a message is sensitive and unauthorized, the entire message is blocked. No partial execution.
6. **Delta returns from nodes.** Nodes return only changed keys, not full state, to avoid re-adding messages through the `add_messages` reducer.
7. **Interrupt, not exception.** LangGraph 1.x `interrupt()` returns inline (no `GraphInterrupt` exception). The CLI checks `state.next` to detect paused graphs.
8. **Config-based role (M3).** `role` moved from `AgentState` to `config["configurable"]` so the LLM cannot mutate it through message history. Default is `"user"` (fail-closed).
9. **Approval is per-action (M3).** `is_human_approved` is set `True` by GatekeeperNode on approval and reset to `False` by S3ToolNode after execution. Each sensitive action requires independent approval.

---

### Pending Dependencies for M4 (Storage & Policy Wiring)

| Item | Detail | Where |
|---|---|---|
| **`is_policy_exposed` wiring** | Flag exists but is never set to `True`. Should trigger when `get_bucket_policy` succeeds in S3ToolNode. | `src/graph/nodes.py` (S3ToolNode) |
| **MinIO/boto3 integration** | Replace hardcoded `list_buckets` and `get_bucket_policy` with real boto3 calls against a MinIO container. | `src/tools/s3_tools.py`, `docker-compose.yml` |
| **Docker Compose setup** | `docker-compose.yml` exists but MinIO service may not be configured for the tools. | `docker-compose.yml` |
| **LangSmith trace audits** | Deferred to M5. No observability wiring yet. | Future |
