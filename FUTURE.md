## **📂 FUTURE.md: SCOPE CONTROL & ITERATION LOG**

This document captures out-of-scope ideas and complex requirements identified during the Discovery Phase of the **Atomic Core**. These features are deferred to prevent "Waterfall" bloat and ensure the initial security gates are hardened first.

## **🚀 PHASE 2: INFRASTRUCTURE & REALISM**

- **MinIO Integration**: Transition from the "Python List" mock to a live Dockerized MinIO instance using the boto3 SDK.

- **Real IAM Simulation**: Map the role: "admin" and role: "user" configurations to actual S3 Bucket Policies and IAM-like behavior within the storage layer.

- **Automated Forensics**: Integrate **LangSmith** trace audits to automatically flag any session where is_policy_exposed is True for security review.

## **🔐 PHASE 3: ADVANCED SECURITY & UX**

- **Multi-Variant Failure Logic**: Expand the "Security Violation" messages to include specific guidance for users on how to request elevated access via official channels.
- **Violation Thresholds**: Implement a violation_count in the AgentState. If a "User" role triggers the GatekeeperNode more than $N$ times, the graph will auto-terminate the thread and lock the thread_id.
- **Signed HITL Tokens**: Replace the simple is_human_approved boolean with a signed cryptographic token or JWT passed from the Trusted Channel to prevent internal state spoofing.

## **🛠️ PHASE 4: EXTENDED TOOLSET**

- **Policy Manipulation**: Add tools for put_bucket_policy and delete_bucket_policy, requiring even stricter multi-signature approvals in the HITL flow.
- **Resource State Tracking**: Expand the TypedDict to track which specific buckets were accessed, creating a granular "Access Manifest" within the state.
