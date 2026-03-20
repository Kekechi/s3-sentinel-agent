## **📂 FUTURE.md: SCOPE CONTROL & ITERATION LOG**

## **🚀 PHASE 3: ADVANCED SECURITY & UX**
- **Bucket-Level Read Restrictions**: Expand the `GatekeeperNode` to enforce metadata-driven checks on `list_objects` and `get_object` (currently out-of-scope for M4).
- **Multi-Variant Failure Logic**: Specific guidance for users on requesting elevated access.
- **Violation Thresholds**: Auto-terminate threads if a `user` triggers the Gatekeeper $N$ times.

## **🔐 PHASE 4: EXTENDED TOOLSET**
- **Policy Manipulation**: `put_bucket_policy` and `delete_bucket_policy` requiring multi-signature HITL.
- **Signed HITL Tokens**: Replace simple booleans with JWTs to prevent internal state spoofing.

## **🛠️ PHASE 5: REFINEMENT**
- **Regex-Based Masking**: Evaluate if Regex-based redaction is needed alongside Key-based redaction for unstructured tool outputs.
- **Dynamic Policy Injection**: Allowing the Admin to modify the "Fail-Open" vs "Fail-Closed" behavior via a special config flag.