## **📄 SPEC.md: THE FUNCTIONAL CONTRACT (ATOMIC CORE)**

This specification defines the "User Wall" and "Admin HITL" patterns. Implementation is strictly bound by the "Graph-First" Rule.

## **1\. State Definition**

The AgentState TypedDict is the single source of truth for the session:

- **messages**: Standard LangChain message history.

- **is_policy_exposed**: Boolean; defaults to False. Set to True permanently if get_bucket_policy returns data.

- **is_human_approved**: Boolean; defaults to False. Reset to False after every tool execution node to prevent "Approval Carryover."
- **role**: String ("admin" | "user"); extracted from config\["configurable"\].

## **2\. Node Logic**

- **AssistantNode**:
  - Interface: ChatOpenAI or ChatAnthropic.

  - Behavior: Suggests tools based on user prompt.

- **GatekeeperNode (Python Only)**:
  - **Case A (Guest Violation)**: If role \== "user" and tool is get_bucket_policy → Inject ToolMessage(content="Security Violation: Unauthorized").

  - **Case B (Admin Approval Required)**: If role \== "admin" and tool is get_bucket_policy and is_human_approved \== False → Set Graph state to PAUSE.
  - **Case C (Authorized)**: If check passes or is_human_approved \== True → Route to S3ToolNode.

- **S3ToolNode (Mock Boto3)**:
  - Implements list_buckets and get_bucket_policy using a hardcoded list/string to simulate an S3 backend.

## **3\. Security Boundaries**

- **No Prompt Security**: LLM system prompts are forbidden from enforcing roles.

- **Out-of-Band HITL**: The "Resume" signal must originate from a separate trusted channel, not the user's chat interface.
