# Tech Stack

Language: Python 3.12+

Orchestration: LangGraph (Stateful graphs with Compiled Breakpoints).

LLM Interface: LangChain Community / OpenAI or Anthropic SDKs.

Storage Emulation: MinIO (S3-compatible API) via Docker.

SDK: boto3 (The standard for AWS/S3 interactions).

Persistence: SqliteSaver (Checkpointer for thread-id continuity).

Observability: LangSmith (For security forensics and trace audits).

Environment: python-dotenv for secret management.

# The "Graph-First" Rule

Logic belongs in Nodes: All decision-making, routing, and security checks must be written as standard Python functions within the LangGraph StateGraph.

No "Black Box" Agents: Do not use LangChain’s high-level create_react_agent or AgentExecutor. We will manually define the nodes (assistant, gatekeeper, tools) and the edges between them.

GraphAPI Primacy: Use the langgraph.graph API to define the flow. The LLM is merely a node that suggests a path; the Graph is the authority that permits it.

# The LangChain Boundary

Interface Only: LangChain libraries are restricted to:

ChatOpenAI / ChatAnthropic objects for model communication.

SystemMessage, HumanMessage, and ToolMessage for data structuring.

bind_tools() for passing our S3 tool schemas to the model.

No LangChain "Chains": Avoid using | (LCEL) for complex logic; use the Graph's add_edge and add_conditional_edges to make the flow explicit.

# Naming Conventions

Boolean State: Always prefix with is*, has*, or should\_ (e.g., is_vault_unlocked, should_require_approval).

Nodes: Use PascalCase for the logic description (e.g., GatekeeperNode, S3ToolNode).

Tools: Use snake_case with action-verb prefixes (e.g., fetch_bucket_list, generate_access_link).

Config: Authorization roles must be labeled as role: "admin" or role: "user" within the configurable object.

# The "Anti-Stack" (Constraints)

No requests for S3: Do not use the requests library for bucket interaction; use boto3 to ensure realistic IAM-like behavior.

No "Prompt-Only" Security: Do not rely on the System Prompt to block guests. Security logic MUST live in the Python Gatekeeper node.

No In-Memory Checkpointers: Do not use MemorySaver for the final delivery; use SqliteSaver to satisfy the "Continuity Test" requirement.

No Global State: Avoid global variables; all information must flow through the LangGraph State TypedDict.
