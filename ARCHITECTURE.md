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
│   │   ├── nodes.py       # Assistant, Gatekeeper (with interrupt), Tool, and Sanitizer nodes
│   │   └── edges.py       # Routing logic (Conditional & Fixed)
│   ├── tools/             # The "Hands" (Action)
│   │   └── s3_tools.py    # Boto3 integration (MinIO backend)
│   └── core/              # The "Rules" (Config)
│       └── security.py    # Role definitions and sensitive tool constants
├── tests/                 # The "Shield"
│   ├── conftest.py        # Shared fixtures (build_graph, build_graph_with_checkpointer)
│   ├── test_skeleton.py   # M1 structural tests (state, compilation, routing)
│   ├── test_gates.py      # M2 security boundary tests (gatekeeper cases, edge routing, fail-closed)
│   ├── test_hitl.py       # M3 interrupt/resume tests (pause, approve, deny, reset)
│   └── test_sanitizer.py  # M4 data redaction and error masking tests
├── docker-compose.yml     # MinIO & Local Stack setup
├── pytest.ini             # Custom marks (integration)
├── requirements.txt       # Dependencies (langgraph, langchain, checkpoint-sqlite, boto3, pytest)
└── .env                   # Secrets (API Keys, MinIO Credentials — gitignored)
```

## **2\. Data Flow & Boundary Map**

The system follows a strict **"Outside-In"** security model. The LLM resides in the inner circle (AssistantNode) but cannot touch the outside world without passing through the Python **GatekeeperNode**.

- **The Trust Boundary**: The GatekeeperNode is the only node permitted to transition state to the S3ToolNode.
- **The HITL Loop**: For sensitive actions (get_bucket_policy), admin requests trigger interrupt() which pauses the graph. The CLI detects the pause via app.get_state(config).next and prompts for approval. Resume is sent via Command(resume=True/False).
- **Role Isolation**: The role field lives in config\["configurable"\], not in AgentState. The LLM cannot mutate it through message history. Missing role defaults to "user" (fail-closed).
- **The Post-Execution Scrub**: All data flowing from S3ToolNode back to the AssistantNode (and ultimately the user) must pass through the **ResponseSanitizerNode**. This node performs error masking for unprivileged users and key-based redaction for sensitive metadata.

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

## **5\. Sanitization Logic (Milestone 4\)**

To prevent information leakage, the ResponseSanitizerNode implements the following rules:

1. **Error Masking**: If role \== "user" and a tool returns a 403 Forbidden or Access Denied, the output is rewritten to "Error: Bucket not found" to prevent bucket existence discovery.
2. **Redaction**: Successful outputs are filtered to remove sensitive infrastructure keys:
   - AccountID
   - ARN (Amazon Resource Names)
   - Owner ID fields
   - Internal IP addresses
