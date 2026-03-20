## **🗺️ ROADMAP.md: Strategic Implementation Path**

## **Phase 1: Foundations (Complete)**

- **M1: The Skeleton** ✅
  - Defined AgentState and basic StateGraph structure.
  - Verified graph compilation and basic routing.
- **M2: The Gatekeeper** ✅
  - Implemented role-based blocking in GatekeeperNode.
  - Achieved 11 passing unit tests for Case A/B/C logic.

## **Phase 2: Authority & Persistence (Complete)**

**Milestone 3: The Admin HITL (Human-In-The-Loop)** ✅

- **Task 3.1: Persistence Layer (SqliteSaver)**
  - Initialized SqliteSaver in cli/main.py to allow the graph to remember its state across process restarts.
- **Task 3.2: The Interrupt Hook**
  - Replaced the "Case B" ToolMessage stub in GatekeeperNode with a formal interrupt() call.
- **Task 3.3: Configuration Migration**
  - Moved the role field from AgentState to the config\["configurable"\] object to ensure it is provided by the trusted host environment.
- **Task 3.4: Approval Reset Logic**
  - Modified S3ToolNode to reset is_human_approved to False immediately after execution to prevent "Approval Carryover."

## **Phase 3: Integration & Sanitization (Current)**

**Milestone 4: Storage & Policy Wiring**

- **Task 4.1: MinIO Infrastructure Setup**
  - Configure docker-compose.yml with a MinIO service and a seeding script to create public-data and restricted-confidential buckets.
- **Task 4.2: Live Boto3 Tool Integration**
  - Replace hardcoded mocks in src/tools/s3_tools.py with real boto3.client calls using the MinIO endpoint_url.
- **Task 4.3: Policy Exposure & Tagging Logic**
  - Wire the is_policy_exposed flag in AgentState to trigger True if get_bucket_policy successfully retrieves data.
  - Implement the "Pre-Flight" check in GatekeeperNode using boto3.get_bucket_tagging to detect classification: restricted.

**Milestone 5: The Sanitizer & Response Wall**

- **Task 5.1: ResponseSanitizerNode Implementation**
  - Create a new node that executes after S3ToolNode but before returning to the AssistantNode.
- **Task 5.2: Error Masking (The "User Wall")**
  - Implement logic to catch 403 Forbidden errors for "user" roles and rewrite them as "Error: Bucket not found."
- **Task 5.3: Data Redaction (The "Scrubber")**
  - Implement key-based redaction to scrub sensitive fields (ARNs, AccountIDs) from successful tool outputs before they reach the LLM or user.

## **Phase 4: Observability & Audit (Future)**

**Milestone 6: Observability & Forensic Audit**

_Objective: Ensure every decision is traceable for security audits._

- **Task 6.1: LangSmith Trace Audits**
  - Configure LangSmith for "Security Forensics" to track exactly why the Gatekeeper permitted or denied an action.
- **Task 6.2: Security Tagging**
  - Implement automatic tagging of UnauthorizedAccessAttempt and policy_exposed: true in LangSmith traces for high-priority security review.

##
