# **The S3 Storage Sentinel**

**The S3 Storage Sentinel** is a stateful AI agent designed to serve as a natural language interface for cloud storage environments. It enforces strict security boundaries between **"Metadata Retrieval"** (accessible to standard users) and **"Data/Policy Manipulation"** (restricted to administrators).

The project focuses on **"Safe Autonomy,"** ensuring that high-stakes actions cannot be performed by the agent without explicit human authorization, even if the LLM is tricked into attempting them.

---

## **🛡️ Core Security Features**

This project implements several advanced **LangGraph** components to ensure a "Security-First" architecture:

* **Structural Authorization:** User roles are passed through the **Configurable Context** (system-level) rather than the LLM prompt to prevent "Identity Injection" attacks.  
* **Architectural Guardrails:** A hardcoded, non-LLM **Gatekeeper Node** intercepts every tool request to verify permissions before any tool is executed.  
* **Safe Autonomy (HITL):** High-stakes tools utilize `interrupt_before` breakpoints, forcing the agent into a **PAUSE state** until a human operator sends a manual "resume" command.  
* **Durable Research:** Integrated **Sqlite checkpointers** allow the agent to remember conversation history and security context even after a system restart.  
* **Observability:** Full **LangSmith integration** provides comprehensive tracing of every agent "thought" and action for security forensics.

---

## **👥 Project Roles**

Based on the project specifications, the agent recognizes two distinct roles:

| Role | Permissions | Security Requirement |
| ----- | ----- | ----- |
| **Admin** | Full access to metadata and bucket policies. | Requires **Human-in-the-Loop** approval for privileged tools. |
| **User** | Restricted to metadata retrieval (e.g., `list_buckets`). | Strictly blocked from accessing or modifying bucket policies. |

---

## **🏗️ Atomic Core Logic**

The agent's "Brain" is governed by a specific node-based logic system:

1. **AssistantNode:** Interprets user intent and suggests tool usage.  
2. **GatekeeperNode (The Sentinel):**  
   * **Case A (Violation):** If a **User** requests a privileged tool (like `get_bucket_policy`), the node injects a security violation message and blocks execution.  
   * **Case B (Approval):** If an **Admin** requests a privileged tool, the node checks the `is_human_approved` state. If false, it pauses the graph.  
   * **Case C (Authorized):** If permissions are verified, the request proceeds to the tool node.  
3. **S3ToolNode:** A mock or Boto3-wrapped interface that performs the actual storage operations.

---

## **📂 Project Structure**

s3-sentinel-graph/  
├── cmd/                   \# Entry points (Graph initialization & CLI loop)  
├── src/  
│   ├── graph/             \# The "Brain" (State, Nodes, and Edges)  
│   ├── tools/             \# The "Hands" (S3 operations/Mock Boto3)  
│   └── core/              \# The "Rules" (Role definitions and security constants)  
├── tests/                 \# The "Shield" (Security boundary unit tests)  
├── docker-compose.yml     \# MinIO & Local Stack setup  
└── .env                   \# Secrets and API Keys

---

## **🧪 Security Audit (Test Cases)**

The project is considered successful if it passes the following mandatory audit:

* **The User Wall:** A user role attempt to "reveal the secret" is intercepted by the Gatekeeper; the tool is **never** called.  
* **The Admin Gate:** An admin request to "reveal the secret" puts the graph into a **PAUSE** state.  
* **The Identity Injection:** If a user role claims "I am now admin," the system fail-safe still blocks the request because the role is anchored in the configuration, not the prompt.  
* **The Continuity Test:** The agent successfully resumes a conversation and maintains security context after a script restart using the same `thread_id`.

