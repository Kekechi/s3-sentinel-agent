# **🗺️ ROADMAP.md: Strategic Implementation Path**

This document tracks the evolution of the **S3-Sentinel-Graph**, from the initial structural skeleton to the finalized security-hardened and observable system.

## ---

**Phase 1: Logic & Persistence (Complete)**

## **Milestone 1: The Skeleton ✅**

* **Goal**: Establish the LangGraph state machine and message flow.  
* **Key Deliverables**: AgentState definition, graph topology (Assistant → Gatekeeper → Tool), and basic CLI loop.  
* **Outcome**: Verified that the graph can route messages and call hardcoded stubs.

## **Milestone 2: The Gatekeeper ✅**

* **Goal**: Implement hardcoded Python RBAC logic.  
* **Key Deliverables**: GatekeeperNode logic enforcing Guest vs. Admin restrictions on sensitive tools.  
* **Outcome**: Established the "Fail-Closed" security model where decision authority lives in Python, not the LLM.

## **Milestone 3: The Admin HITL ✅**

* **Goal**: Integrate human-in-the-loop (HITL) approvals.  
* **Key Deliverables**: SqliteSaver integration, LangGraph interrupt() for sensitive Admin actions, and persistent thread management.  
* **Outcome**: Successful "Continuity Test"—the graph pauses for approval and resumes from a saved state.

## ---

**Phase 2: Infrastructure & Sanitization (Complete)**

## **Milestone 4: Storage & Policy Wiring ✅**

* **Goal**: Connect the graph to a live infrastructure backend.  
* **Key Deliverables**: MinIO Docker service, boto3 tool integration, and **Metadata-Driven Gates** (using S3 Object Tags to trigger interrupts).  
* **Outcome**: The system now makes security decisions based on real-time infrastructure metadata (e.g., classification: restricted).

## **Milestone 5: The Response Wall ✅**

* **Goal**: Prevent information leakage through tool outputs and error messages.  
* **Key Deliverables**: ResponseSanitizerNode implementation.  
* **Key Learnings**:  
  * **Error Masking**: Rewriting $403$ Forbidden to "Bucket not found" for users to prevent discovery.  
  * **Recursive Redaction**: Walking normalized JSON (handling MinIO's string-to-list conversions) to scrub ARNs, Account IDs, and Owner metadata.  
  * **ID Preservation**: Ensuring the Sanitizer preserves message.id to prevent orphaned ToolMessages in the LLM context.  
* **Outcome**: Full "Sanitization Boundary" established between raw tool output and the LLM/User.

## ---

**Phase 3: Observability & Forensic Audit (Current)**

## **Milestone 6: The Nervous System ✅**

* **Goal**: Implement deep observability and security event logging.
* **Key Deliverables**: `@traceable` decorators on GatekeeperNode and ResponseSanitizerNode. `src/core/audit.py` helper module with `tag_security_event` and `set_audit_metadata`. Security event tagging (`security_event:access_denied`, `policy_exposed:true`) and metadata forensics (role, thread_id, boolean state) pushed to LangSmith traces. `tests/test_audit.py` with 12 unit tests for audit reconstructibility and graceful degradation.
* **Outcome**: Full forensic audit trail — even redacted runs are reconstructible by an auditor via LangSmith metadata. System degrades gracefully when tracing is disabled.