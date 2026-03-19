## **🏗️ ARCHITECTURE.md: The Structural Map**

This document serves as the **Anchor**. All code implementation must fit into these defined slots.

## **1\. Folder Hierarchy**

s3-sentinel-graph/
├── cmd/                   \# Entry points
│   └── main.py            \# Graph initialization & CLI loop (--role support)
├── src/
│   ├── graph/             \# The "Brain" (Logic Authority)
│   │   ├── state.py       \# AgentState TypedDict definition (5 fields)
│   │   ├── nodes.py       \# Assistant, Gatekeeper, and Tool nodes
│   │   └── edges.py       \# Routing logic (Conditional & Fixed)
│   ├── tools/             \# The "Hands" (Action)
│   │   └── s3\_tools.py    \# Boto3-wrapped S3 operations
│   └── core/              \# The "Rules" (Config)
│       └── security.py    \# Role definitions and IAM-like constants
├── tests/                 \# The "Shield"
│   ├── conftest.py        \# Shared fixtures (build\_graph via importlib)
│   ├── test\_skeleton.py   \# M1 structural tests (state, compilation, routing)
│   └── test\_gates.py      \# M2 security boundary tests (gatekeeper cases, edge routing)
├── docker-compose.yml     \# MinIO & Local Stack setup
└── .env                   \# Secrets (API Keys, MinIO Credentials)

## **2\. Data Flow & Boundary Map**

The system follows a strict **"Outside-In"** security model. The LLM resides in the inner circle (AssistantNode) but cannot touch the outside world without passing through the Python **GatekeeperNode**.

* **The Trust Boundary**: The GatekeeperNode is the only node permitted to transition state to the S3ToolNode.  
* **The HITL Loop**: For sensitive actions (get\_bucket\_policy), the Graph enters a PAUSE state using LangGraph's breakpoints. The "Resume" signal is an out-of-band state update.