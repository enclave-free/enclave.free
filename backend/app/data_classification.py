"""Operator-visible Instance data classification registry."""

from copy import deepcopy


DATA_CLASSIFICATIONS = [
    {
        "key": "pii_fields",
        "label": "PII Fields",
        "classification": "sensitive_instance_data",
        "lifecycle_term": "User Profiles",
        "summary": "User email, name, and configured User Profile fields.",
    },
    {
        "key": "uploaded_documents",
        "label": "Uploaded Documents",
        "classification": "sensitive_instance_content",
        "lifecycle_term": "Document Library",
        "summary": "Operator-provided source files and extracted document content.",
    },
    {
        "key": "derived_chunks_embeddings",
        "label": "Derived Chunks and Embeddings",
        "classification": "derived_instance_content",
        "lifecycle_term": "Retrieval Index",
        "summary": "Chunk text and vector data derived from uploaded Documents.",
    },
    {
        "key": "secrets",
        "label": "Secrets and Credentials",
        "classification": "deployment_secret",
        "lifecycle_term": "Deployment Settings",
        "summary": "API keys, signing secrets, SMTP credentials, and encryption keys.",
    },
    {
        "key": "audit_log_evidence",
        "label": "Audit Log Evidence",
        "classification": "governance_evidence",
        "lifecycle_term": "Audit Log",
        "summary": "Operator-visible evidence of security-relevant and state-changing actions.",
    },
    {
        "key": "inference_verification_records",
        "label": "Inference Verification Records",
        "classification": "governance_evidence",
        "lifecycle_term": "Inference Verification Record",
        "summary": "Provider attestation evidence for Verifiable Inference checks.",
    },
    {
        "key": "user_memory",
        "label": "User Memory",
        "classification": "sage_context",
        "lifecycle_term": "User Memory",
        "summary": "Sage-owned context about a User or User Type.",
    },
    {
        "key": "session_memory",
        "label": "Session Memory",
        "classification": "conversation_state",
        "lifecycle_term": "Sage Session Memory",
        "summary": "Agent Runtime state for Conversation continuity.",
    },
    {
        "key": "copied_exports",
        "label": "Copied Exports",
        "classification": "deployment_surface",
        "lifecycle_term": "Copied Export",
        "summary": "Operator- or user-created copies that leave active product storage.",
    },
]


def get_data_classification_inventory() -> dict:
    items = deepcopy(DATA_CLASSIFICATIONS)
    return {
        "items": items,
        "summary": {
            "total": len(items),
            "sensitive": len([
                item for item in items
                if item["classification"] in {"sensitive_instance_data", "sensitive_instance_content"}
            ]),
            "governance_evidence": len([
                item for item in items
                if item["classification"] == "governance_evidence"
            ]),
            "deployment_surface": len([
                item for item in items
                if item["classification"] == "deployment_surface"
            ]),
        },
    }
