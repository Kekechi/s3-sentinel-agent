## **🗺️ ROADMAP.md: Strategic Implementation Path**

## **Phase 1: Foundations (Complete)**

* **M1: The Skeleton** ✅  
  * Defined AgentState and basic StateGraph structure.  
  * Verified graph compilation and basic routing.  
* **M2: The Gatekeeper** ✅  
  * Implemented role-based blocking in GatekeeperNode.  
  * Achieved 11 passing unit tests for Case A/B/C logic.

## ---

**Phase 2: Authority & Persistence (Current)**

**Milestone 3: The Admin HITL (Human-In-The-Loop)**

*Objective: Transform hard blocks into interactive pauses using LangGraph's native state management.*

* **Task 3.1: Persistence Layer (SqliteSaver)**  
  * Initialize SqliteSaver in cmd/main.py to allow the graph to remember its state across process restarts.  
  * Requirement: Support for thread\_id continuity.  
* **Task 3.2: The Interrupt Hook**  
  * Replace the "Case B" ToolMessage stub in GatekeeperNode with a formal interrupt() call.  
  * Behavior: The graph must stop and wait for an external state update when an Admin requests a sensitive tool.  
* **Task 3.3: Configuration Migration**  
  * Move the role field from AgentState to the config\["configurable"\] object.  
  * Ensures roles are provided by the trusted host environment, not the user's chat history.  
* **Task 3.4: Approval Reset Logic**  
  * Modify S3ToolNode to reset is\_human\_approved to False immediately after execution.  
  * Prevents "Approval Carryover" where one permission grants access to subsequent sensitive calls.

## ---

**Phase 3: Integration & Audit (Future)**

**Milestone 4: Storage & Policy Wiring**

*Objective: Transition from hardcoded mocks to a functional S3-compatible backend.*

* **Task 4.1: MinIO Integration**  
  * Connect boto3 tools to a local MinIO container via docker-compose.  
* **Task 4.2: Policy Exposure Logic**  
  * Wire the is\_policy\_exposed flag to trigger True permanently if get\_bucket\_policy successfully returns data.

**Milestone 5: Observability & Forensic Audit**

*Objective: Ensure every decision is traceable for security audits.*

* **Task 5.1: LangSmith Trace Audits**  
  * Configure LangSmith for "Security Forensics" to track exactly why the Gatekeeper permitted or denied an action.
