# Milestone 1: The Skeleton — Tactical Plan

**Goal:** Define `AgentState`, build the basic `StateGraph`, and prove it compiles and routes a "Hello" message end-to-end.

**Success Criteria (from ROADMAP.md):** Graph compiles and routes "Hello" messages.

---

## Step 0: Project Scaffolding

- [ ] **0.1** Create the folder hierarchy defined in ARCHITECTURE.md:
  ```
  cmd/
  src/graph/
  src/tools/
  src/core/
  tests/
  ```
- [ ] **0.2** Add `__init__.py` files to `src/`, `src/graph/`, `src/tools/`, `src/core/`, and `tests/` to make them importable packages.
- [ ] **0.3** Create a `.env` file with a placeholder for the LLM API key (e.g., `OPENAI_API_KEY=`). No real secrets committed.
- [ ] **0.4** Create `requirements.txt` with pinned dependencies: `langgraph`, `langchain-openai` (or `langchain-anthropic`), `python-dotenv`, `boto3`.

**Verification:** `python -c "import src.graph"` succeeds with no errors.

---

## Step 1: Define `AgentState` (`src/graph/state.py`)

- [ ] **1.1** Define `AgentState` as a `TypedDict` with the fields from SPEC.md:
  - `messages`: `Annotated[list, add_messages]` (LangGraph message reducer)
  - `is_policy_exposed`: `bool` (default `False`)
  - `is_human_approved`: `bool` (default `False`)
  - `role`: `str` (`"admin"` | `"user"`)

**Verification:** File imports cleanly — `from src.graph.state import AgentState` raises no errors.

---

## Step 2: Define Stub Nodes (`src/graph/nodes.py`)

- [ ] **2.1** `AssistantNode` — A function that takes `AgentState`, calls the LLM with `state["messages"]`, and returns `{"messages": [ai_response]}`. Uses `ChatOpenAI` (or `ChatAnthropic`) loaded via `python-dotenv`.
- [ ] **2.2** `GatekeeperNode` — A **stub** function that takes `AgentState` and passes through to the next node unconditionally (full logic deferred to M2).
- [ ] **2.3** `S3ToolNode` — A **stub** function that returns a placeholder `ToolMessage` (real boto3 logic deferred to M4).

**Verification:** Each function is importable and callable with a minimal state dict without crashing.

---

## Step 3: Define Routing Edges (`src/graph/edges.py`)

- [ ] **3.1** Write a `route_after_assistant` function that inspects the last AI message:
  - If the message has `tool_calls` → route to `"GatekeeperNode"`
  - Otherwise → route to `END`
- [ ] **3.2** Write a `route_after_gatekeeper` function (stub for M1):
  - Always routes to `"S3ToolNode"` (security logic deferred to M2).

**Verification:** Functions return correct string keys for both branches given mock state.

---

## Step 4: Compile the Graph (`cmd/main.py`)

- [ ] **4.1** Build the `StateGraph(AgentState)`:
  - Add nodes: `AssistantNode`, `GatekeeperNode`, `S3ToolNode`.
  - Set entry point: `AssistantNode`.
  - Add conditional edge from `AssistantNode` using `route_after_assistant`.
  - Add fixed edge from `GatekeeperNode` → `S3ToolNode`.
  - Add fixed edge from `S3ToolNode` → `AssistantNode`.
- [ ] **4.2** Call `graph.compile()` and confirm no exceptions.
- [ ] **4.3** Implement a minimal CLI loop:
  - Accept user input.
  - Invoke the compiled graph with `{"messages": [HumanMessage(content=input)], "role": "admin"}`.
  - Print the final AI response.

**Verification:** Running `python cmd/main.py` → typing "Hello" → receiving a coherent LLM reply with no errors.

---

## Step 5: Define Placeholder Tools (`src/tools/s3_tools.py`)

- [ ] **5.1** Define `list_buckets` tool using the `@tool` decorator — returns a hardcoded list of bucket names.
- [ ] **5.2** Define `get_bucket_policy` tool using the `@tool` decorator — returns a hardcoded policy JSON string.
- [ ] **5.3** Bind both tools to the LLM in `AssistantNode` via `model.bind_tools([list_buckets, get_bucket_policy])`.

**Verification:** Asking "List my S3 buckets" triggers a `tool_calls` entry in the AI message, routing through GatekeeperNode → S3ToolNode → back to AssistantNode with a final answer.

---

## Step 6: Placeholder Security Constants (`src/core/security.py`)

- [ ] **6.1** Define `SENSITIVE_TOOLS = ["get_bucket_policy"]` — the list of tools that will require gatekeeper intervention in M2.
- [ ] **6.2** Define `ROLES = {"admin", "user"}` — valid role values.

**Verification:** Importable constants; no logic yet.

---

## Step 7: Smoke Test (`tests/test_skeleton.py`)

- [ ] **7.1** Test: `AgentState` TypedDict can be instantiated with all required fields.
- [ ] **7.2** Test: Graph compiles without error.
- [ ] **7.3** Test: Invoking the graph with a "Hello" `HumanMessage` returns a state containing at least 2 messages (the input + an AI reply).
- [ ] **7.4** Test: `route_after_assistant` returns `END` when the last message has no tool calls.

**Verification:** `pytest tests/test_skeleton.py` — all green.

---

## Execution Order

```
Step 0  (scaffolding)
  → Step 1  (state)
    → Step 2  (nodes) + Step 5  (tools) + Step 6  (security constants)  [parallel]
      → Step 3  (edges)
        → Step 4  (graph assembly + CLI)
          → Step 7  (tests)
```

---

## Out of Scope (Deferred)

| Concern | Deferred To |
|---|---|
| Gatekeeper blocking logic | M2 |
| HITL interrupt / `is_human_approved` flow | M3 |
| Real boto3 + MinIO connection | M4 |
| SqliteSaver persistence | M5 |
| Docker-compose setup | M4 |
