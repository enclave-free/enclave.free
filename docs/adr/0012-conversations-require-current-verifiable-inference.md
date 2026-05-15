# Conversations Require Current Verifiable Inference

Normal Conversation traffic should fail closed when current Verifiable Inference status is failed or missing, because Enclave Free's privacy promise depends on more than a reachable Model Provider endpoint. Deployment Automation should create historical Inference Verification Records automatically, and Admin-only diagnostics may still run so the Operator can repair provider configuration. This favors verifiable privacy over availability for ordinary Conversations while preserving an operational recovery path.
