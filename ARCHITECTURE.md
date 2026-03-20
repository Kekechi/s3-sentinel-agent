## **ARCHITECTURE.md: The Structural Map**

This document serves as the **Anchor**. All code implementation must fit into these defined slots.

## **1\. Folder Hierarchy**

```
s3-sentinel-graph/
├── run.py                 # Project entry point — calls cli.main.main()
├── cli/                   # Entry points (Python package)
│   ├── __init__.py
│   └── main.py            # Graph initialization, SqliteSaver, CLI loop (--role, interrupt handling)
├── src/
│   ├── graph/             # The "Brain" (Logic Authority)
│   │   ├── state.py       # AgentState TypedDict definition (4 fields)
│   │   ├── nodes.py       # Assistant, _check_bucket_restricted, Gatekeeper (with interrupt + tagging), Tool, and Sanitizer nodes
│   │   └── edges.py       # Routing logic (Conditional & Fixed)
│   ├── tools/             # The "Hands" (Action)
│   │   └── s3_tools.py    # Live boto3 @tool functions (list_buckets, get_bucket_policy) via create_s3_client()
│   └── core/              # The "Rules" (Config)
│       ├── security.py    # Role definitions and sensitive tool constants
│       └── s3_client.py   # create_s3_client() factory — boto3 client for MinIO (no global state)
├── scripts/               # Operational scripts
│   └── seed_minio.py      # Idempotent MinIO bucket seeding (public-data, restricted-confidential)
├── tests/                 # The "Shield"
│   ├── conftest.py        # Shared fixtures (build_graph, build_graph_with_checkpointer, mock_s3_client autouse)
│   ├── test_skeleton.py   # M1 structural tests (state, compilation, routing)
│   ├── test_gates.py      # M2/M4 security boundary tests (gatekeeper cases, edge routing, fail-closed, tagging)
│   ├── test_hitl.py       # M3/M4 interrupt/resume tests (pause, approve, deny, reset, untagged skip)
│   ├── test_s3_tools.py   # M4 tool tests (list_buckets, get_bucket_policy, is_policy_exposed wiring, live MinIO)
│   └── test_sanitizer.py  # M5 data redaction and error masking tests (not yet created)
├── docker-compose.yml     # MinIO service (ports 9000/9001, health check, minio-data volume)
├── pytest.ini             # Custom marks (integration, minio)
├── requirements.txt       # Dependencies (langgraph, langchain, checkpoint-sqlite, boto3, pytest)
└── .env                   # Secrets (API Keys, MinIO Credentials — gitignored)
```

## **2\. Data Flow & Boundary Map**

The system follows a strict **"Outside-In"** security model. The LLM resides in the inner circle (AssistantNode) but cannot touch the outside world without passing through the Python **GatekeeperNode**.

- **The Trust Boundary**: The GatekeeperNode is the only node permitted to transition state to the S3ToolNode.
- **The Pre-Flight Check (M4)**: For admin users requesting sensitive tools, GatekeeperNode calls `_check_bucket_restricted()` which queries `get_bucket_tagging` via boto3. Only buckets tagged `classification: restricted` trigger HITL interrupt. Untagged buckets pass through. Errors are fail-closed (treated as restricted).
- **The HITL Loop**: For restricted buckets, admin requests trigger interrupt() which pauses the graph. The CLI detects the pause via app.get_state(config).next and prompts for approval. Resume is sent via Command(resume=True/False).
- **Role Isolation**: The role field lives in config\["configurable"\], not in AgentState. The LLM cannot mutate it through message history. Missing role defaults to "user" (fail-closed).
- **Policy Exposure Tracking (M4)**: S3ToolNode sets `is_policy_exposed: True` as a high-water mark when `get_bucket_policy` successfully retrieves data. Once set, it never resets to False for the session.
- **The Post-Execution Scrub (M5)**: All data flowing from S3ToolNode back to the AssistantNode (and ultimately the user) must pass through the **ResponseSanitizerNode**. This node performs error masking for unprivileged users and key-based redaction for sensitive metadata.

## **3\. Persistence Layer**

- **Checkpointer**: SqliteSaver from langgraph-checkpoint-sqlite. Required for interrupt() to serialize and resume graph state.
- **CLI**: Uses SqliteSaver.from_conn_string("s3_sentinel.db") with a uuid4 thread_id per session.
- **Tests**: Use SqliteSaver.from_conn_string(":memory:") for ephemeral in-memory persistence (still SqliteSaver, not MemorySaver — per CLAUDE.md constraint).

## **4\. Config Schema**

```Python
config = {
 "configurable": {
 "thread_id": str, # UUID — identifies the conversation thread for persistence
 "role": str, # "admin" or "user" — trusted host-environment parameter
 }
}
```

## **5\. Infrastructure (M4)**

- **MinIO**: S3-compatible object storage running via `docker-compose.yml`. Ports 9000 (S3 API) and 9001 (console).
- **Credentials**: `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, `MINIO_ENDPOINT_URL` in `.env`.
- **Seeding**: `scripts/seed_minio.py` creates two buckets:
  - `public-data` — untagged, no policy (represents non-sensitive data)
  - `restricted-confidential` — tagged `classification: restricted`, has `s3:GetObject` policy (represents sensitive data)
- **S3 Client Factory**: `src/core/s3_client.py` provides `create_s3_client()` which returns a boto3 client per-call. Shared by tools and GatekeeperNode. No global state.

## **6\. Sanitization Logic (Milestone 5\)**

To prevent information leakage, the ResponseSanitizerNode implements the following rules:

1. **Error Masking**: If role \== "user" and a tool returns a 403 Forbidden or Access Denied, the output is rewritten to "Error: Bucket not found" to prevent bucket existence discovery.
2. **Redaction**: Successful outputs are filtered to remove sensitive infrastructure keys:
   - AccountID
   - ARN (Amazon Resource Names)
   - Owner ID fields
   - Internal IP addresses

## **7\. Test Infrastructure (M4)**

- **Autouse Mock**: `tests/conftest.py` provides `mock_s3_client` fixture that auto-patches `create_s3_client` at both import sites (`src.tools.s3_tools` and `src.graph.nodes`). All tests run without MinIO unless marked `@pytest.mark.minio`.
- **Pytest Markers**: `integration` (requires live LLM), `minio` (requires running MinIO container).
- **Mock defaults**: Returns restricted tags, policy with `s3:GetObject`, two buckets (`public-data`, `restricted-confidential`). Fail-closed in test context.
