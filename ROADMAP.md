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

## **Milestone 6: The Nervous System (Current) 🟦**

* **Goal**: Implement deep observability and security event logging.  
* **Task 6.1: LangSmith Instrumentation**: Add @traceable decorators to security-critical nodes (GatekeeperNode, ResponseSanitizerNode).  
* **Task 6.2: Security Event Tagging**:  
  * Tag traces with security\_event: access\_denied when is\_blocked is True.  
  * Tag traces with policy\_exposed: true when high-water mark is hit.  
* **Task 6.3: Metadata Forensics**: Push role, thread\_id, and is\_human\_approved status into LangSmith metadata fields for audit filtering.  
* **Task 6.4: Audit Validation**: Create tests/test\_audit.py to ensure that even "redacted" runs are fully reconstructible by an auditor in the backend.

## 