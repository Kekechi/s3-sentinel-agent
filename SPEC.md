## **📄 SPEC.md: THE FUNCTIONAL CONTRACT (MILESTONE 4)**

This specification defines the "User Wall," "Admin HITL," and "Response Sanitization" patterns. Implementation is strictly bound by the "Graph-First" Rule.

## **1. State Definition**
The `AgentState` TypedDict is the single source of truth for the session:
- **messages**: Standard LangChain message history (Annotated with `add_messages`).
- **is_policy_exposed**: Boolean; defaults to False. Set to True in `S3ToolNode` if `get_bucket_policy` succeeds.
- **is_human_approved**: Boolean; defaults to False. Reset to False by `S3ToolNode` after every execution.
- **is_blocked**: Boolean; defaults to True. Logic-controlled by `GatekeeperNode`.

## **2. Node Logic**

### **AssistantNode**
- **Interface**: ChatOpenAI or ChatAnthropic.
- **Behavior**: Suggests tools (e.g., `list_buckets`, `get_bucket_policy`) based on intent.

### **GatekeeperNode (Hybrid Policy)**
- **User Role**: Flat denial for `get_bucket_policy`. Returns `is_blocked: True` and injects "Security Violation".
- **Admin Role (Metadata-Driven)**: 
  - Performs "Pre-Flight" check via `boto3.get_bucket_tagging`.
  - **Case A**: If tag `classification: restricted` exists AND `is_human_approved == False` → `interrupt()` for HITL.
  - **Case B**: If bucket is untagged ("Fail-Open") or not restricted → `is_blocked: False`.

### **S3ToolNode (Live Boto3)**
- **Integration**: Uses a root-access `boto3.client` with `endpoint_url` for MinIO.
- **Audit**: Pushes `policy_exposed: true` and `UnauthorizedAccessAttempt` (with `thread_id`) tags to LangSmith.

### **ResponseSanitizerNode (New Post-Processor)**
- **Error Masking**: If `role == "user"` and tool returns `403 Forbidden`, rewrites to "Error: Bucket not found".
- **Data Redaction**: Uses Key-based redaction to scrub sensitive fields (e.g., ARNs, AccountIDs) from successful outputs.

## **3. Infrastructure Boundary**
- **MinIO**: System runs via `docker-compose`.
- **Seeding**: Startup script creates `public-data` (untagged) and `restricted-confidential` (tagged `restricted`).