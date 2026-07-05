# Curated Resource Inventory Fix

## Run

- Run ID: 2026-07-03-curated-resource-inventory-fix
- Target repo: enclave-free/enclave.free
- Local frontend: http://127.0.0.1:5173
- Local gateway: http://127.0.0.1:18000
- Started: 2026-07-03
- Current status: Implemented and locally verified.

## Symptom

On the demo instance, the prompt `what resources do you have` produced a generic answer about the Curated Resources and Knowledge Base tool sets. The trace showed a structured-output correction, but no Curated Resources tool call. Because `find_resources` required a `help_type`, Sage had no good inventory path for listing the live Resource Directory.

## Fix

- Made `/internal/agent/resources/search` accept omitted or blank `help_type` as an inventory lookup.
- Kept existing referral lookup behavior when `help_type` is present.
- Limited inventory results to `ready` curated resources, excluding pending/archived entries.
- Preserved jurisdiction filtering when a jurisdiction is supplied.
- Updated the Sage `find_resources` tool contract so `help_type` is optional and should be omitted for inventory/list-all questions.
- Updated the runtime instruction: for prompts like `what resources do you have?`, call `find_resources` with no `help_type` instead of describing the tool catalog.

## Verification

- `python3 -m unittest backend.tests.test_resource_directory` passed: 17 tests.
- `cargo test -p sage-core find_resources_tool --lib` passed: 2 tests.
- `cargo test -p sage-core selected_tool_sets_expand_to_model_callable_tool_contracts --lib` passed: 1 test.
- `cargo test -p sage-core --lib` passed: 112 tests.
- `git diff --check` passed in the parent repo and `runtime/sage`.
- Rebuilt local `core-backend` and `sage` containers.
- Direct internal inventory request returned the local ready curated resources with `"help_type": null`.
- Live local `/llm/chat/stream` prompt `what resources do you have` used Curated Resources with query `curated resources inventory` and listed the ready resources.

## Remaining Demo Checks

After this patch is deployed to `demo.enclave.free`, verify the uploaded demo `test` resource is `ready`. A curated resource still will not appear to users if it is pending, archived, missing a contact method, missing a resource type, missing scope, or missing at least one help type.
