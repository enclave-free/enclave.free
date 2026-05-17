import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


class PrototypeCompatibilityDocsTest(unittest.TestCase):
    def test_tool_docs_describe_sage_gateway_routes_not_python_fallbacks(self) -> None:
        tools = (REPO_ROOT / "docs/tools.md").read_text(encoding="utf-8")

        self.assertIn("Gateway routes public Agent Runtime requests to Sage", tools)
        self.assertIn("Python no longer owns or exposes these public Agent Runtime routes", tools)
        self.assertIn("routes are absent from the Enclave Control Plane", tools)
        self.assertNotIn("sage_route_required", tools)
        self.assertNotIn("use `/llm/chat` for assistant-style turns", tools)
        self.assertNotIn("Current `/query` responses include", tools)

    def test_current_architecture_names_absent_python_handlers_not_legacy_runtime(self) -> None:
        architecture = (REPO_ROOT / "ARCHITECTURE_CURRENT.md").read_text(encoding="utf-8")

        self.assertIn("Python does not expose public handlers for `/llm/chat`, `/query`, `/session-defaults`, or `/admin/tools/execute`", architecture)
        self.assertIn("obsolete public Agent Runtime routes are absent from the Enclave Control Plane", architecture)
        self.assertNotIn("legacy Python handler remains", architecture)
        self.assertNotIn("legacy Python router still exists", architecture)
        self.assertNotIn("legacy AI route implementations", architecture)

    def test_current_architecture_names_chunk_retrieval_for_sage_context(self) -> None:
        architecture = (REPO_ROOT / "ARCHITECTURE_CURRENT.md").read_text(encoding="utf-8")
        planned = (REPO_ROOT / "ARCHITECTURE_PLANNED.md").read_text(encoding="utf-8")
        integration_tests = (REPO_ROOT / "docs/integration-tests.md").read_text(encoding="utf-8")

        self.assertIn("chunk Retrieval for Sage context", architecture)
        self.assertIn("The current Document Library Retrieval architecture is intentionally a half-RAG, half-agent path", architecture)
        self.assertIn("The Enclave Control Plane owns Document Ingestion, Document Access, chunk embeddings, and Retrieval hydration", architecture)
        self.assertIn("Sage owns Conversation behavior and consumes retrieved chunks as Agent Runtime context", architecture)
        self.assertIn("Graph-first RAG remains deferred", architecture)
        self.assertIn("deferred architecture, not the current prototype completeness bar", planned)
        self.assertIn("2B", integration_tests)
        self.assertIn("Chunk Retrieval evaluation", integration_tests)

    def test_streaming_docs_do_not_call_llm_chat_a_compatibility_path(self) -> None:
        root_readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        cutover = (REPO_ROOT / "docs/prototype-sage-cutover.md").read_text(encoding="utf-8")

        self.assertIn("non-streaming companion path", root_readme)
        self.assertIn("non-streaming companion path", cutover)
        self.assertNotIn("non-streaming compatibility path", root_readme)
        self.assertNotIn("non-streaming compatibility path", cutover)

    def test_admin_assistant_docs_describe_gateway_transport_and_active_defaults(self) -> None:
        assistant = (REPO_ROOT / "docs/admin-config-assistant.md").read_text(encoding="utf-8")

        self.assertIn("Gateway routes this request to Sage", assistant)
        self.assertIn("Sage-owned session defaults", assistant)
        self.assertIn("Python does not expose public `/llm/chat` or `/session-defaults` handlers", assistant)
        self.assertNotIn("Transport: uses `POST /llm/chat`", assistant)
        self.assertNotIn("Reads `/session-defaults`", assistant)

    def test_locale_provider_copy_does_not_teach_maple_aliases(self) -> None:
        locale_dir = REPO_ROOT / "frontend/src/i18n/locales"
        checked_keys = (
            '"llmHelp"',
            '"llm"',
            '"shareSecretsHint"',
            '"LLM_PROVIDER"',
            '"LLM_MODEL"',
            '"LLM_API_URL"',
            '"LLM_API_KEY"',
        )
        violations = []
        for path in sorted(locale_dir.glob("*.json")):
            if path.name.startswith("._"):
                continue
            text = path.read_text(encoding="utf-8")
            lines = text.splitlines()
            for line_number, line in enumerate(lines, start=1):
                if "Maple" not in line and "MAPLE_" not in line:
                    continue
                window = "\n".join(lines[max(0, line_number - 25):line_number])
                if any(key in window for key in checked_keys):
                    violations.append(f"{path.name}:{line_number}: {line.strip()}")

        self.assertEqual(violations, [])

    def test_dumb_gateway_docs_do_not_keep_removed_internal_compatibility_endpoints_alive(self) -> None:
        gateway = (REPO_ROOT / "docs/dumb-gateway-foundation.md").read_text(encoding="utf-8")

        self.assertIn("Removed Python compatibility endpoints are absent", gateway)
        self.assertNotIn("internal_contract_removed", gateway)
        self.assertNotIn("Compatibility endpoints still exist in Python", gateway)
        self.assertNotIn("`POST /internal/agent/auth-context`", gateway)

    def test_sage_cutover_docs_name_absent_handlers_instead_of_legacy_python_runtime(self) -> None:
        cutover = (REPO_ROOT / "docs/prototype-sage-cutover.md").read_text(encoding="utf-8")

        self.assertIn("Python no longer exposes public Agent Runtime handlers", cutover)
        self.assertIn("Obsolete internal compatibility endpoints are absent from Python", cutover)
        self.assertNotIn("legacy Python `/llm/chat` and `/query` code still exists", cutover)
        self.assertNotIn("compatibility internal endpoints", cutover)

    def test_sqlite_encryption_docs_route_admin_chat_tools_through_gateway_sage(self) -> None:
        sqlite_encryption = (REPO_ROOT / "docs/sqlite-encryption.md").read_text(encoding="utf-8")

        self.assertIn("admin chat tool flow goes through Gateway to Sage", sqlite_encryption)
        self.assertIn("Python remains the internal safe DB executor", sqlite_encryption)
        self.assertNotIn("Raw tool results for this flow are fetched via `/admin/tools/execute`", sqlite_encryption)
        self.assertNotIn("db-query runs via `/llm/chat`", sqlite_encryption)

    def test_docs_index_names_active_sage_boundary_not_legacy_naming(self) -> None:
        readme = (REPO_ROOT / "docs/README.md").read_text(encoding="utf-8")

        self.assertIn("Some older docs may describe historical behavior", readme)
        self.assertIn("Sage hard-cut docs in `Start Here` are authoritative", readme)
        self.assertNotIn("Some older docs still use legacy `Enclave` naming", readme)

    def test_admin_deployment_docs_describe_llm_settings_as_diagnostics(self) -> None:
        deployment = (REPO_ROOT / "docs/admin-deployment-config.md").read_text(encoding="utf-8")

        self.assertIn("Model Provider Deployment Settings On This Prototype", deployment)
        self.assertIn("Python-side Model Provider labeling and validation", deployment)
        self.assertIn("Python-side model metadata and diagnostics", deployment)
        self.assertNotIn("Model Provider Compatibility Settings On This Prototype", deployment)
        self.assertNotIn("legacy Python Model Provider client config", deployment)
        self.assertNotIn("remaining legacy client paths", deployment)

    def test_agent_settings_surface_is_not_described_as_compatibility_layer(self) -> None:
        checked_paths = [
            REPO_ROOT / "backend/app/ai_config.py",
            REPO_ROOT / "backend/app/database.py",
            REPO_ROOT / "backend/app/models.py",
            REPO_ROOT / "frontend/src/types/config.ts",
            REPO_ROOT / "frontend/src/hooks/useAdminConfig.ts",
        ]

        violations = []
        for path in checked_paths:
            text = path.read_text(encoding="utf-8")
            if "Agent Settings Compatibility" in text or "compatibility router" in text:
                violations.append(str(path.relative_to(REPO_ROOT)))
            if "keeps the compatibility table name" in text:
                violations.append(str(path.relative_to(REPO_ROOT)))

        self.assertEqual(violations, [])

    def test_mock_email_docs_and_locales_do_not_teach_mock_smtp_alias(self) -> None:
        checked_paths = [
            REPO_ROOT / "docs/email-auth.md",
            REPO_ROOT / "docs/authentication.md",
            REPO_ROOT / "docs/sqlite-admin-system.md",
            REPO_ROOT / "frontend/src/pages/AdminDeploymentConfig.tsx",
            REPO_ROOT / "frontend/src/types/config.ts",
        ]
        checked_paths.extend(sorted((REPO_ROOT / "frontend/src/i18n/locales").glob("*.json")))

        violations = []
        for path in checked_paths:
            if path.name.startswith("._"):
                continue
            text = path.read_text(encoding="utf-8")
            if "MOCK_SMTP" in text or "mockSmtp" in text:
                violations.append(str(path.relative_to(REPO_ROOT)))

        self.assertEqual(violations, [])

    def test_sqlite_admin_docs_route_chat_db_tool_through_sage(self) -> None:
        sqlite_admin = (REPO_ROOT / "docs/sqlite-admin-system.md").read_text(encoding="utf-8")

        self.assertIn("For the Sage-owned admin chat tool", sqlite_admin)
        self.assertIn("Sage authorizes the tool turn and delegates safe SQL execution to Python", sqlite_admin)
        self.assertNotIn("`/admin/tools/execute` + `/llm/chat` flow", sqlite_admin)

    def test_security_checklist_does_not_claim_python_owns_public_query_sessions(self) -> None:
        checklist = (REPO_ROOT / "docs/security-data-protection-checklist.md").read_text(encoding="utf-8")

        self.assertIn("Public query-session routes are Sage-owned", checklist)
        self.assertIn("Python lifecycle evidence covers Sage-to-Python deletion/tombstone reporting", checklist)
        self.assertNotIn("Evidence: `backend/app/query.py`", checklist)
        self.assertNotIn("curl -i http://localhost:8000/query/session/test-session-id", checklist)

    def test_smoke_docs_name_gateway_and_port_shadowing_check(self) -> None:
        checked_paths = [
            REPO_ROOT / "README.md",
            REPO_ROOT / "AGENTS.md",
            REPO_ROOT / "docs/security-data-protection-checklist.md",
            REPO_ROOT / "docs/lifecycle-confidentiality-runbook.md",
        ]

        missing = []
        for path in checked_paths:
            text = path.read_text(encoding="utf-8")
            if "enclave-api-gateway" not in text:
                missing.append(f"{path.relative_to(REPO_ROOT)}: gateway container")
            if "lsof -nP -iTCP:8000 -sTCP:LISTEN" not in text:
                missing.append(f"{path.relative_to(REPO_ROOT)}: port shadowing check")

        self.assertEqual(missing, [])

    def test_lifecycle_cleanup_docs_split_safe_wording_from_data_migrations(self) -> None:
        runbook = (REPO_ROOT / "docs/lifecycle-confidentiality-runbook.md").read_text(encoding="utf-8")

        self.assertIn("Safe documentation and terminology cleanup", runbook)
        self.assertIn("Data-affecting cleanup remains a separate migration slice", runbook)
        self.assertIn("removing legacy plaintext user/profile storage assumptions", runbook)
        self.assertNotIn("removing legacy Qdrant plaintext payload handling require", runbook)
        self.assertNotIn("Migration may land later", runbook)

    def test_qdrant_plaintext_repair_docs_name_removed_support(self) -> None:
        runbook = (REPO_ROOT / "docs/lifecycle-confidentiality-runbook.md").read_text(encoding="utf-8")

        self.assertIn("Legacy Retrieval payload repair support has been removed", runbook)
        self.assertIn("support_removal_ready: true", runbook)
        self.assertIn("preview no longer depends on Qdrant repair actions", runbook)
        self.assertNotIn("operator-reviewed execution completed without `retrieval_payload` failures", runbook)

    def test_user_profile_plaintext_removal_record_names_removed_support(self) -> None:
        record = (REPO_ROOT / "docs/user-profile-plaintext-migration-plan.md").read_text(encoding="utf-8")
        docs_index = (REPO_ROOT / "docs/README.md").read_text(encoding="utf-8")
        checklist = (REPO_ROOT / "docs/security-data-protection-checklist.md").read_text(encoding="utf-8")

        self.assertIn("Plaintext-era User Profile compatibility has been removed", record)
        self.assertIn("does not fall back to `LOWER(email)`", record)
        self.assertIn("/admin/profile-plaintext-migration/inventory` is absent", record)
        self.assertIn("/admin/profile-plaintext-migration/migrate` is absent", record)
        self.assertIn("migrate_encrypt_existing_data` is absent", record)
        self.assertIn("First-admin setup no longer preflights or migrates", record)
        self.assertNotIn("Run `POST /admin/profile-plaintext-migration/migrate`", record)
        self.assertNotIn("keep the fallback reads", record)
        self.assertIn("user-profile-plaintext-migration-plan.md", docs_index)
        self.assertIn("Legacy User Profile plaintext fallback support has been removed", checklist)


if __name__ == "__main__":
    unittest.main()
