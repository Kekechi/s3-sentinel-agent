## **🗺️ ROADMAP.md: High-Level Milestones**

| Milestone | Description | Success Criteria |
| :---- | :---- | :---- |
| **M1: The Skeleton** | Define AgentState and the basic StateGraph structure. | Graph compiles and routes "Hello" messages. |
| **M2: The Gatekeeper** | Implement GatekeeperNode Python logic for role-based blocking. | Guest role is blocked from get\_bucket\_policy via Python code. |
| **M3: The Admin HITL** | Integrate LangGraph interrupt for Admin approvals. | Graph pauses; resumes only after is\_human\_approved is True. |
| **M4: Storage Layer** | Connect boto3 to a local MinIO instance. | Real S3-API calls succeed within the S3ToolNode. |
| **M5: Continuity** | Implement SqliteSaver for session persistence. | Thread IDs allow resuming a paused Admin request after a restart. |

## 