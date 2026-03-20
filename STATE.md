## **STATE.md: Implementation Snapshot**

* **Current Phase**: **Milestone 4 Complete** — Storage & Policy Wiring.
* **Last Action**: Replaced hardcoded S3 tool stubs with live boto3 calls against MinIO. Wired `is_policy_exposed` flag. Added metadata-driven HITL via pre-flight `get_bucket_tagging` check. 29 unit tests + 2 minio integration tests + 2 LLM integration tests.
* **Blockers**: None.
* **Next Step**: Milestone 5 — The Sanitizer & Response Wall (ResponseSanitizerNode, error masking, data redaction).

---

### What Was Implemented in M4

Replaced hardcoded tool stubs with live boto3 calls via a shared `create_s3_client()` factory. Added MinIO infrastructure (Docker Compose + seed script). Wired `is_policy_exposed` as a high-water mark in S3ToolNode. Added `_check_bucket_restricted()` pre-flight tagging check in GatekeeperNode — admin HITL now only fires for `classification: restricted` buckets, untagged buckets pass through. Added autouse mock fixture so all tests run without MinIO.

| File | What Changed |
|---|---|
| `.env` | Added `MINIO_ROOT_USER=minioadmin`, `MINIO_ROOT_PASSWORD=minioadmin`, `MINIO_ENDPOINT_URL=http://localhost:9000` |
| `docker-compose.yml` | **New file** — MinIO service with ports 9000/9001, health check, named volume |
| `scripts/seed_minio.py` | **New file** — Idempotent seeding: creates `public-data` (untagged) and `restricted-confidential` (tagged `classification: restricted` + read policy) |
| `src/core/s3_client.py` | **New file** — `create_s3_client()` factory function (boto3 client for MinIO, no global state) |
| `src/tools/s3_tools.py` | Rewritten — `list_buckets` and `get_bucket_policy` now use live boto3 via `create_s3_client()`. Error handling for `NoSuchBucketPolicy` and general exceptions. |
| `src/graph/nodes.py` | Added `_check_bucket_restricted()` helper. `GatekeeperNode` admin path now does pre-flight tagging check before `interrupt()`. `S3ToolNode` now wires `is_policy_exposed` (high-water mark). Added imports for `create_s3_client` and `ClientError`. |
| `tests/conftest.py` | Added autouse `mock_s3_client` fixture — patches both `src.tools.s3_tools.create_s3_client` and `src.graph.nodes.create_s3_client`. Skipped for `@pytest.mark.minio` tests. |
| `tests/test_s3_tools.py` | **New file** — 4 tool unit tests + 3 `is_policy_exposed` tests + 2 minio integration tests |
| `tests/test_gates.py` | Added 5 tests: `_check_bucket_restricted` (restricted, untagged, error, no-bucket-name) + admin untagged pass-through |
| `tests/test_hitl.py` | Added 1 test: `test_admin_untagged_bucket_skips_interrupt` |
| `pytest.ini` | Added `minio` marker |

---

### Complete File Inventory

| File | Purpose |
|---|---|
| `src/graph/state.py` | `AgentState` TypedDict with 4 fields: `messages`, `is_policy_exposed`, `is_human_approved`, `is_blocked` |
| `src/graph/nodes.py` | `AssistantNode` (LLM + bound tools), `_check_bucket_restricted` (pre-flight tagging), `GatekeeperNode` (role-based access + metadata-driven interrupt), `S3ToolNode` (tool dispatch + approval reset + policy exposure wiring) |
| `src/graph/edges.py` | `route_after_assistant` (tool_calls → Gatekeeper, else → END), `route_after_gatekeeper` (is_blocked → AssistantNode, else → S3ToolNode) |
| `src/tools/s3_tools.py` | `list_buckets` and `get_bucket_policy` — live boto3 `@tool` functions via `create_s3_client()` |
| `src/core/s3_client.py` | `create_s3_client()` factory — returns boto3 S3 client configured for MinIO endpoint |
| `src/core/security.py` | `SENSITIVE_TOOLS` and `ROLES` constants |
| `cli/main.py` | `build_graph(checkpointer=None)` compiles the StateGraph; `main()` runs CLI loop with SqliteSaver, `--role`, and interrupt handling |
| `docker-compose.yml` | MinIO service (ports 9000/9001, health check, `minio-data` volume) |
| `scripts/seed_minio.py` | Idempotent bucket seeding: `public-data` (untagged), `restricted-confidential` (tagged + policy) |
| `tests/conftest.py` | `build_graph`, `build_graph_with_checkpointer`, `mock_s3_client` (autouse) fixtures |
| `tests/test_skeleton.py` | 4 unit tests + 1 integration: state instantiation, graph compilation, hello routing, edge routing (x2) |
| `tests/test_gates.py` | 12 unit tests + 1 integration: Case A blocking, non-sensitive pass-through, fail-closed defaults (x2), edge routing (x2), `_check_bucket_restricted` (x4), admin untagged pass-through, end-to-end guest denial |
| `tests/test_hitl.py` | 6 unit tests + 0 integration: interrupt pauses, approve resumes, deny blocks, approval resets, untagged skips interrupt, checkpointer compiles |
| `tests/test_s3_tools.py` | 7 unit tests + 2 minio integration: list_buckets JSON, get_bucket_policy (success, no-policy, error), policy_exposed (success, error, high-water-mark), live list, live policy |
| `pytest.ini` | Registers `integration` and `minio` custom marks |
| `requirements.txt` | `langgraph`, `langchain-openai`, `langchain-anthropic`, `langgraph-checkpoint-sqlite`, `python-dotenv`, `boto3`, `pytest` |
| `run.py` | Project entry point — imports and calls `cli.main.main()` |
| `.env` | Secrets: API keys + MinIO credentials (gitignored) |

---

### Types and Functions Reference

#### AgentState (`src/graph/state.py`)

```python
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]  # LangChain message history (reducer: add_messages)
    is_policy_exposed: bool   # High-water mark: True once get_bucket_policy succeeds. Never resets to False.
    is_human_approved: bool   # Set True by GatekeeperNode on approval; reset False by S3ToolNode after execution
    is_blocked: bool          # Set by GatekeeperNode; read by route_after_gatekeeper. Fail-closed default: True
```

**Note**: `role` lives in `config["configurable"]["role"]`, not in AgentState. `is_policy_exposed` is now wired (M4).

#### S3 Client Factory (`src/core/s3_client.py`)

```python
def create_s3_client() -> boto3.client:
```
Returns a boto3 S3 client configured for MinIO via env vars (`MINIO_ENDPOINT_URL`, `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`). Called per-invocation inside tool functions and `_check_bucket_restricted` — no global state.

#### Nodes (`src/graph/nodes.py`)

| Function | Signature | Behavior |
|---|---|---|
| `AssistantNode` | `(state: AgentState) -> dict` | Invokes `gpt-4o-mini` with bound tools. Returns `{"messages": [AIMessage]}`. |
| `_check_bucket_restricted` | `(tool_call: dict) -> bool` | Pre-flight tagging check via `get_bucket_tagging`. Returns `True` if `classification=restricted` found, if any non-tagging error occurs, or if `bucket_name` is missing (fail-closed). Returns `False` only for `NoSuchTagSet` (untagged bucket). |
| `GatekeeperNode` | `(state: AgentState, config: RunnableConfig) -> dict` | Extracts `role` from config (default: `"user"`). User + sensitive → Security Violation. Admin + sensitive + restricted bucket → `interrupt()`. Admin + sensitive + untagged bucket → pass through. Returns `{"is_blocked": True/False, ...}`. |
| `S3ToolNode` | `(state: AgentState) -> dict` | Executes tool calls via `TOOLS_BY_NAME` lookup. Sets `is_policy_exposed: True` on successful `get_bucket_policy` (high-water mark). Returns `{"messages": [...], "is_human_approved": False, "is_policy_exposed": <bool>}`. |

#### GatekeeperNode Decision Matrix (M4 — metadata-driven)

| Role | Tool | Bucket Tag | Result |
|---|---|---|---|
| `"user"` | `get_bucket_policy` | any | **BLOCKED** — `"Security Violation: Unauthorized"` |
| `"admin"` | `get_bucket_policy` | `classification: restricted` | **PAUSED** — `interrupt()` for HITL approval |
| `"admin"` (approved) | `get_bucket_policy` | restricted | **ALLOWED** — `is_human_approved: True`, `is_blocked: False` |
| `"admin"` (denied) | `get_bucket_policy` | restricted | **BLOCKED** — `"Admin denied the action."` |
| `"admin"` | `get_bucket_policy` | untagged / not restricted | **ALLOWED** — no HITL needed |
| missing/empty role | `get_bucket_policy` | any | **BLOCKED** — fail-closed (defaults to `"user"`) |
| any | `list_buckets` | n/a | **ALLOWED** |

#### Edge Routers (`src/graph/edges.py`)

| Function | Logic |
|---|---|
| `route_after_assistant` | Has `tool_calls` → `"GatekeeperNode"` · No tool_calls → `END` |
| `route_after_gatekeeper` | `is_blocked` is `True` (or missing) → `"AssistantNode"` · `is_blocked` is `False` → `"S3ToolNode"` |

#### Tools (`src/tools/s3_tools.py`)

| Function | Args | Returns | Sensitive? |
|---|---|---|---|
| `list_buckets` | none | Live JSON from `client.list_buckets()` with `.isoformat()` dates | No |
| `get_bucket_policy` | `bucket_name: str` | Live policy JSON from `client.get_bucket_policy()`, or error JSON on `NoSuchBucketPolicy`/other exceptions | **Yes** |

#### Constants (`src/core/security.py`)

| Name | Value |
|---|---|
| `SENSITIVE_TOOLS` | `["get_bucket_policy"]` |
| `ROLES` | `{"admin", "user"}` |

#### Key Imports Added in M4

| Import | Source | Used In |
|---|---|---|
| `create_s3_client` | `src.core.s3_client` | `src/graph/nodes.py` (`_check_bucket_restricted`), `src/tools/s3_tools.py` |
| `ClientError` | `botocore.exceptions` | `src/graph/nodes.py` (`_check_bucket_restricted`) |

#### Test Fixtures (`tests/conftest.py`)

| Fixture | Returns | Notes |
|---|---|---|
| `build_graph` | `Callable` — the `build_graph(checkpointer=None)` function | Imported from `cli.main` |
| `build_graph_with_checkpointer` | Compiled graph app with in-memory SqliteSaver | Yielded inside context manager; uses `build_graph` fixture |
| `mock_s3_client` | `MagicMock` — pre-configured boto3 client mock | Autouse; patches `src.tools.s3_tools.create_s3_client` and `src.graph.nodes.create_s3_client`. Skipped for `@pytest.mark.minio` tests. Default: returns restricted tags, policy with `s3:GetObject`, two buckets. |

---

### Graph Flow (Current — M4)

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
                   ├── admin + sensitive → _check_bucket_restricted()
                   │       ├── restricted → interrupt() PAUSES graph
                   │       │       ↓
                   │       │   CLI prompts admin → Command(resume=True/False)
                   │       │       ├── approved → is_blocked=False → S3ToolNode → AssistantNode
                   │       │       └── denied → BLOCKED (Admin denied) → AssistantNode
                   │       └── untagged → is_blocked=False → S3ToolNode → AssistantNode
                   └── non-sensitive → is_blocked=False → S3ToolNode → AssistantNode

S3ToolNode post-execution:
  - Resets is_human_approved to False
  - Sets is_policy_exposed to True if get_bucket_policy succeeded (high-water mark)
```

---

### Test Coverage

| File | Unit | MinIO Integration | LLM Integration |
|---|---|---|---|
| `tests/test_skeleton.py` | 4 | 0 | 1 |
| `tests/test_gates.py` | 12 | 0 | 1 |
| `tests/test_hitl.py` | 6 | 0 | 0 |
| `tests/test_s3_tools.py` | 7 | 2 | 0 |
| **Total** | **29** | **2** | **2** |

Run unit tests only: `pytest -m "not minio and not integration"`
Run with MinIO: `pytest -m "not integration"` (requires `docker-compose up -d && python scripts/seed_minio.py`)
Run all tests: `pytest` (requires MinIO + `OPENAI_API_KEY`)

---

### Architectural Decisions (Cumulative)

1. **`cli/` is a Python package.** Renamed from `cmd/` to avoid shadowing Python's stdlib `cmd` module (which broke `pdb`/pytest). Entry point is `run.py` at project root.
2. **LLM configured with `base_url` from env.** Supports non-default OpenAI-compatible endpoints.
3. **Integration tests marked separately.** `@pytest.mark.integration` for tests requiring live LLM key. `@pytest.mark.minio` for tests requiring running MinIO container.
4. **Fail-closed default.** `is_blocked` defaults to `True` everywhere. Missing `role` in config defaults to `"user"` (unprivileged).
5. **All-or-nothing blocking.** If any tool_call in a message is sensitive and unauthorized, the entire message is blocked. No partial execution.
6. **Delta returns from nodes.** Nodes return only changed keys, not full state, to avoid re-adding messages through the `add_messages` reducer.
7. **Interrupt, not exception.** LangGraph 1.x `interrupt()` returns inline (no `GraphInterrupt` exception). The CLI checks `state.next` to detect paused graphs.
8. **Config-based role (M3).** `role` moved from `AgentState` to `config["configurable"]` so the LLM cannot mutate it through message history. Default is `"user"` (fail-closed).
9. **Approval is per-action (M3).** `is_human_approved` is set `True` by GatekeeperNode on approval and reset to `False` by S3ToolNode after execution. Each sensitive action requires independent approval.
10. **S3 client factory, not global (M4).** `create_s3_client()` returns a boto3 client per-call. Both tools and GatekeeperNode share the factory. No global state per CLAUDE.md.
11. **Metadata-driven HITL (M4).** Admin HITL only fires for buckets tagged `classification: restricted`. Untagged buckets pass through without interrupt. `NoSuchTagSet` is treated as "untagged" (not restricted). All other errors are fail-closed.
12. **Policy exposure is a high-water mark (M4).** `is_policy_exposed` is set `True` once `get_bucket_policy` succeeds and never resets to `False`. Differs from `is_human_approved` which resets per-action.
13. **Autouse mock for test isolation (M4).** `mock_s3_client` fixture patches both `src.tools.s3_tools.create_s3_client` and `src.graph.nodes.create_s3_client`. Must patch at import site, not definition site, due to `from ... import` creating local references.
14. **MinIO normalizes policy JSON (M4).** MinIO converts `"Action": "s3:GetObject"` to `"Action": ["s3:GetObject"]` (string → list). Tests must handle both formats.

---

### Pending Dependencies for M5 (The Sanitizer & Response Wall)

| Item | Detail | Where |
|---|---|---|
| **ResponseSanitizerNode** | New node between S3ToolNode and AssistantNode. Performs error masking and data redaction. | `src/graph/nodes.py` (new function), `cli/main.py` (add to graph) |
| **Error Masking** | If `role == "user"` and tool returns `403 Forbidden` / `Access Denied`, rewrite to `"Error: Bucket not found"` to prevent bucket existence discovery. | `src/graph/nodes.py` (ResponseSanitizerNode) |
| **Data Redaction** | Key-based redaction to scrub sensitive fields (ARNs, AccountIDs, Owner IDs, internal IPs) from successful outputs before they reach the LLM or user. | `src/graph/nodes.py` (ResponseSanitizerNode) |
| **Graph topology change** | Current: `S3ToolNode → AssistantNode`. Must become: `S3ToolNode → ResponseSanitizerNode → AssistantNode`. | `cli/main.py` (edges) |
| **test_sanitizer.py** | New test file for redaction and error masking tests. Listed in ARCHITECTURE.md but not yet created. | `tests/test_sanitizer.py` |
| **LangSmith trace audits** | Deferred to M6. No observability wiring yet. | Future |
