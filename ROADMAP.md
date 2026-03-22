## **🗺️ ROADMAP.md: Strategic Implementation Path**

## **Phase 1: Foundations & Security Logic (Complete)**

* **Milestone 1: The Skeleton** ✅  
  * Defined AgentState and established the core StateGraph structure.  
  * Verified basic routing and tool binding.  
* **Milestone 2: The Gatekeeper** ✅  
  * Implemented hard-coded Python Role-Based Access Control (RBAC).  
  * Established "fail-closed" defaults for unauthorized tool requests.  
* **Milestone 3: The Admin HITL** ✅  
  * Integrated SqliteSaver for session persistence.  
  * Implemented LangGraph interrupt() for out-of-band Admin approvals.  
  * Migrated role to trusted configuration to prevent prompt injection.

## **Phase 2: Infrastructure & Integration (Complete)**

* **Milestone 4: Storage & Policy Wiring** ✅  
  * Deployed MinIO S3-compatible backend via Docker Compose.  
  * Integrated boto3 tools with live infrastructure.  
  * Implemented **Metadata-Driven Gates**: Gatekeeper now checks bucket tags (classification: restricted) before triggering interrupts.  
  * Wired is\_policy\_exposed flag to trigger permanently on successful policy retrieval.

## **Phase 3: The Response Wall (Current)**

**Milestone 5: Sanitization & Redaction**

*Objective: Ensure the LLM and User only see scrubbed, safe data.*

* **Task 5.1: ResponseSanitizerNode Implementation**  
  * Insert the new node into the graph topology between S3ToolNode and AssistantNode.  
* **Task 5.2: Error Masking**  
  * Logic: If role \== "user" and a tool returns 403 Forbidden, rewrite the output to "Error: Bucket not found".  
  * Goal: Prevent bucket existence discovery via error messages.  
* **Task 5.3: Data Redaction Engine**  
  * Implement recursive scrubbing for ARNs, AccountIDs, and Owner IDs in tool outputs.  
  * Ensure compatibility with MinIO's normalized JSON structures (handling both strings and lists).  
* **Task 5.4: Sanitization Validation**  
  * Create tests/test\_sanitizer.py to verify that sensitive infrastructure details never reach the LLM context.  
* **Task 5.5: Final Continuity & Audit Test**  
  * Verify the full flow: Admin Request \-\> Interrupt \-\> Approval \-\> Execution \-\> Sanitization \-\> Scrubbed Response.

## 