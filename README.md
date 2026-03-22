# The S3 Storage Sentinel

**The S3 Storage Sentinel** is a stateful AI agent designed to serve as a natural language interface for cloud storage environments. It enforces strict security boundaries between **"Metadata Retrieval"** (accessible to standard users) and **"Data/Policy Manipulation"** (restricted to administrators).

The project focuses on **"Safe Autonomy,"** ensuring that high-stakes actions cannot be performed by the agent without explicit human authorization, even if the LLM is tricked into attempting them.

---

## Core Security Features

This project implements several advanced **LangGraph** components to ensure a "Security-First" architecture:

* **Structural Authorization:** User roles are passed through the **Configurable Context** (system-level) rather than the LLM prompt to prevent "Identity Injection" attacks.
* **Architectural Guardrails:** A hardcoded, non-LLM **GatekeeperNode** intercepts every tool request to verify permissions before any tool is executed.
* **Metadata-Driven HITL:** Admin access to buckets tagged `classification: restricted` triggers a `LangGraph interrupt()`, pausing the graph until a human operator approves or denies the action.
* **Response Sanitization:** A **ResponseSanitizerNode** post-processes all tool outputs — masking 403 errors for unprivileged users and redacting sensitive keys (Owner, ID, Resource, Principal, Condition) for all roles.
* **Durable Persistence:** Integrated **SqliteSaver checkpointers** allow the agent to remember conversation history and security context even after a system restart.
* **Forensic Observability:** LangSmith `@traceable` instrumentation on security-critical nodes emits audit tags (`security_event:access_denied`, `policy_exposed:true`) and metadata (role, thread_id, boolean state) for forensic reconstruction.

---

## Project Roles

| Role | Permissions | Security Requirement |
|---|---|---|
| **admin** | Full access to metadata and bucket policies. | Requires **Human-in-the-Loop** approval for restricted buckets. |
| **user** | Restricted to metadata retrieval (e.g., `list_buckets`). | Strictly blocked from accessing or modifying bucket policies. |

---

## Atomic Core Logic

The agent's "Brain" is governed by four node functions in a LangGraph `StateGraph`:

1. **AssistantNode:** Interprets user intent and suggests tool usage via the LLM.
2. **GatekeeperNode (The Sentinel):**
   * **Case A (Violation):** If a **user** requests a privileged tool (like `get_bucket_policy`), the node injects a security violation message and blocks execution.
   * **Case B (Approval):** If an **admin** requests a privileged tool on a `classification: restricted` bucket, the graph pauses via `interrupt()` for HITL approval.
   * **Case C (Authorized):** If the bucket is untagged or permissions are verified, the request proceeds to the tool node.
3. **S3ToolNode:** Executes live boto3 operations against MinIO. Tracks policy exposure as a high-water mark.
4. **ResponseSanitizerNode:** Post-processes tool outputs — masks 403 errors for users, redacts sensitive JSON keys for all roles, preserves message IDs for the LangGraph reducer.

---

## Project Structure

```
s3-sentinel-agent/
├── run.py                    # Project entry point — calls cli.main.main()
├── cli/                      # Entry points (Python package)
│   └── main.py               # Graph initialization, SqliteSaver, CLI loop (--role, interrupt handling)
├── src/
│   ├── graph/                # The "Brain" (Logic Authority)
│   │   ├── state.py          # AgentState TypedDict (messages, is_policy_exposed, is_human_approved, is_blocked)
│   │   ├── nodes.py          # AssistantNode, GatekeeperNode, S3ToolNode, ResponseSanitizerNode
│   │   └── edges.py          # Routing logic (route_after_assistant, route_after_gatekeeper)
│   ├── tools/                # The "Hands" (Action)
│   │   └── s3_tools.py       # Live boto3 @tool functions (list_buckets, get_bucket_policy)
│   └── core/                 # The "Rules" (Config)
│       ├── security.py       # SENSITIVE_TOOLS, ROLES, SENSITIVE_KEYS constants
│       ├── s3_client.py      # create_s3_client() factory — boto3 client for MinIO
│       └── audit.py          # LangSmith audit helpers — tag_security_event(), set_audit_metadata()
├── scripts/
│   └── seed_minio.py         # Idempotent MinIO bucket seeding (public-data, restricted-confidential)
├── tests/                    # The "Shield" (52 unit + 2 MinIO + 2 LLM integration tests)
│   ├── conftest.py           # Shared fixtures (build_graph, mock_s3_client autouse)
│   ├── test_skeleton.py      # M1 structural tests
│   ├── test_gates.py         # M2/M4 security boundary tests
│   ├── test_hitl.py          # M3/M4 interrupt/resume tests
│   ├── test_s3_tools.py      # M4 tool tests (+ live MinIO integration)
│   ├── test_sanitizer.py     # M5 data redaction and error masking tests
│   └── test_audit.py         # M6 audit instrumentation tests
├── docker-compose.yml        # MinIO service (ports 9000/9001)
├── pytest.ini                # Custom marks (integration, minio)
├── requirements.txt          # Dependencies
└── .env                      # Secrets (API Keys, MinIO Credentials, LangSmith config — gitignored)
```

---

## Security Audit (Test Cases)

The project is considered successful if it passes the following mandatory audit:

* **The User Wall:** A user role attempt to "reveal the secret" is intercepted by the Gatekeeper; the tool is **never** called.
* **The Admin Gate:** An admin request to "reveal the secret" on a restricted bucket puts the graph into a **PAUSE** state.
* **The Identity Injection:** If a user role claims "I am now admin," the system fail-safe still blocks the request because the role is anchored in the configuration, not the prompt.
* **The Continuity Test:** The agent successfully resumes a conversation and maintains security context after a script restart using the same `thread_id`.

---

## Usage Guide

### Prerequisites

- Python 3.12+
- Docker and Docker Compose (for MinIO)
- An OpenAI API key (or compatible endpoint)

### 1. Install Dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment

Copy or create a `.env` file in the project root:

```env
# LLM
OPENAI_API_KEY=sk-your-key-here
API_URL=                          # Optional: non-default OpenAI-compatible endpoint

# MinIO (S3 emulation)
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin
MINIO_ENDPOINT_URL=http://localhost:9000

# LangSmith Observability (optional — see "Enabling LangSmith" below)
LANGCHAIN_TRACING_V2=false
LANGCHAIN_API_KEY=
LANGCHAIN_PROJECT=s3-sentinel-agent
```

### 3. Start MinIO and Seed Buckets

```bash
docker compose up -d
python scripts/seed_minio.py
```

This creates two buckets:
- `public-data` — untagged (non-sensitive)
- `restricted-confidential` — tagged `classification: restricted` with an S3 policy attached

You can verify MinIO is healthy at `http://localhost:9001` (console).

### 4. Run the Agent

```bash
# Run as admin (default)
python run.py

# Run as user (unprivileged)
python run.py --role user

# Run as admin (explicit)
python run.py --role admin
```

**Example session (user role):**
```
S3 Sentinel Agent (role=user, type 'quit' to exit)

You: list my buckets
Agent: You have the following S3 buckets:
1. public-data — Creation Date: March 20, 2026
2. restricted-confidential — Creation Date: March 20, 2026

You: show me the policy on restricted-confidential
Agent: I am unable to access the policy for "restricted-confidential"
       due to a security violation. You may need appropriate permissions.
```

**Example session (admin role with HITL):**
```
S3 Sentinel Agent (role=admin, type 'quit' to exit)

You: show me the policy on restricted-confidential
[HITL] Admin approval required: bucket is classified as restricted.
  Tool: get_bucket_policy
  Args: {'bucket_name': 'restricted-confidential'}
  Approve? (y/n): y

Agent: Here is the policy for restricted-confidential:
  ... (redacted sensitive keys) ...
```

### 5. Run Tests

```bash
# Unit tests only (no external services needed) — 52 tests
pytest -m "not minio and not integration"

# Unit + MinIO integration tests (requires docker compose up)
pytest -m "not integration"

# All tests including LLM integration (requires OPENAI_API_KEY + MinIO)
pytest
```

---

## Observability and Forensic Audit

The GatekeeperNode and ResponseSanitizerNode emit audit tags and metadata on every security decision. There are two ways to inspect traces: **locally** (no account needed) and via **LangSmith Cloud** (full audit dashboard).

### What Gets Traced

| Node | Tags Emitted | Metadata Fields |
|---|---|---|
| **GatekeeperNode** | `security_event:access_denied` (when blocking) | `role`, `thread_id`, `is_human_approved`, `is_blocked` |
| **ResponseSanitizerNode** | `policy_exposed:true` (when high-water mark set) | `role`, `thread_id`, `is_policy_exposed` |

`AssistantNode` and `S3ToolNode` are auto-traced by LangGraph when tracing is enabled — no custom tags needed.

### Option A: Local Dev Server (langgraph dev)

The fastest way to inspect the graph visually — no LangSmith account required. `langgraph dev` runs an in-memory LangGraph API server with a built-in Studio UI.

**1. Launch the dev server:**

```bash
langgraph dev
```

This starts:
- API server at `http://localhost:8123`
- Studio UI at `https://smith.langchain.com/studio/?baseUrl=http://localhost:8123`
- API docs at `http://localhost:8123/docs`

The Studio UI connects to your **local** server — your data stays on your machine.

**2. Interact via the Studio UI:**

Open the Studio URL in your browser. You can:
- Send messages to the agent and watch the graph execute node-by-node
- Inspect each node's inputs, outputs, and state transitions
- See the GatekeeperNode block/allow decisions in real time
- Step through HITL interrupts interactively

**3. Interact via the API (curl):**

```bash
# Create a thread
THREAD_ID=$(curl -s -X POST http://localhost:8123/threads \
  -H 'Content-Type: application/json' -d '{}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['thread_id'])")

# Run as user role
curl -s -X POST "http://localhost:8123/threads/$THREAD_ID/runs/wait" \
  -H 'Content-Type: application/json' \
  -d '{
    "assistant_id": "s3_sentinel",
    "input": {"messages": [{"role": "human", "content": "list all buckets"}]},
    "config": {"configurable": {"role": "user"}}
  }'
```

**4. Configuration:**

The dev server reads `langgraph.json` in the project root, which points to the graph definition and loads `.env` for credentials. The server provides its own checkpointer — no SqliteSaver setup needed.

**Useful flags:**

```bash
langgraph dev --port 2024           # Custom port
langgraph dev --no-browser          # Don't auto-open Studio
langgraph dev --no-reload           # Disable hot-reloading
```

### Option B: LangSmith Cloud (Full Audit Dashboard)

For persistent audit trails, team access, and production forensics, connect to LangSmith Cloud.

**1. Get an API key** from [smith.langchain.com](https://smith.langchain.com). Go to **Settings > API Keys** and create a new key.

**2. Update your `.env`:**

```env
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=lsv2_pt_your-key-here
LANGCHAIN_PROJECT=s3-sentinel-agent
```

**3. Run the agent normally** — traces are sent automatically:

```bash
python run.py --role admin
```

**4. View traces** in the LangSmith web UI at `https://smith.langchain.com`. Navigate to your `s3-sentinel-agent` project to see all runs with security tags and metadata.

### Querying Audit Traces with Python

Use the `langsmith.Client` to query traces programmatically (requires `LANGCHAIN_API_KEY`):

```python
from langsmith import Client

client = Client()  # reads LANGCHAIN_API_KEY from env

# List all runs in the project
runs = client.list_runs(project_name="s3-sentinel-agent")
for run in runs:
    print(f"{run.name} | tags={run.tags} | metadata={run.extra.get('metadata', {})}")

# Filter for security violations only
blocked_runs = client.list_runs(
    project_name="s3-sentinel-agent",
    filter='has(tags, "security_event:access_denied")',
)
for run in blocked_runs:
    print(f"BLOCKED: {run.name} | role={run.extra.get('metadata', {}).get('role')}")

# Filter for policy exposure events
exposed_runs = client.list_runs(
    project_name="s3-sentinel-agent",
    filter='has(tags, "policy_exposed:true")',
)
for run in exposed_runs:
    print(f"EXPOSED: {run.name} | thread={run.extra.get('metadata', {}).get('thread_id')}")
```

### Graceful Degradation

When `LANGCHAIN_TRACING_V2` is not set to `true` (or `LANGCHAIN_API_KEY` is empty), all audit functions silently no-op. The agent behaves identically with or without LangSmith configured — no errors, no performance impact.
