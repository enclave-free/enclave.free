# User/Profile Plaintext Migration Plan

This plan covers the remaining plaintext-era User Profile storage support that protects existing deployments. It is a data-safety migration plan, not prototype compatibility cleanup.

## Inventory

Plaintext-era storage still exists in schema and read paths:

- `users.email`: deprecated plaintext email column. Current writes set it to `NULL`; legacy rows may still have values.
- `users.name`: deprecated plaintext display-name column. Current writes set it to `NULL`; legacy rows may still have values.
- `user_field_values.value`: plaintext dynamic profile field value. Encrypted fields write `NULL` here; fields explicitly configured with `encryption_enabled = 0` still use this column by operator choice and may be included in chat context.
- `get_user_by_email`: first uses `email_blind_index`, then falls back to `LOWER(email)` so legacy accounts remain reachable until migration evidence proves the fallback is unnecessary.
- `get_user`: returns encrypted blobs for current rows and plaintext fields only when legacy or operator-plaintext values exist.
- `get_user_chat_context_values`: intentionally reads only plaintext field values for fields where `include_in_chat = 1` and `encryption_enabled = 0`.
- `migrate_encrypt_existing_data`: encrypts legacy `users.email`, `users.name`, and encrypted-field `user_field_values.value` rows when an admin key is available, then clears migrated plaintext.

## Chosen Path

Retain plaintext-era columns and fallback reads until an operator-reviewed migration has completed and validation proves no legacy protected profile data depends on them. Do not remove plaintext-era columns or fallback reads as part of broad compatibility cleanup.

This keeps three cases distinct:

- Legacy protected data: old `users.email`, `users.name`, and encrypted-field `user_field_values.value` rows that should be migrated to encrypted storage.
- Operator plaintext by choice: field definitions with `encryption_enabled = 0`, especially when `include_in_chat = 1`.
- Active encrypted data: current writes with encrypted columns populated and plaintext protected columns cleared.

## Migration Procedure

1. Take a SQLite backup and record the exact application commit, schema, and `SECRET_KEY` state. This is the backup and rollback point.
2. Confirm an admin pubkey exists and that admin NIP-07 decryption still works in the UI.
3. Inventory rows:
   - count non-null `users.email`
   - count non-null `users.name`
   - count non-null `user_field_values.value` joined to field definitions where `encryption_enabled = 1`
   - separately count `user_field_values.value` where `encryption_enabled = 0`
4. Resolve duplicate legacy emails before migration, because `email_blind_index` is unique.
5. Run `migrate_encrypt_existing_data`.
6. Re-run the inventory. Protected legacy counts should be zero. Operator-plaintext counts may remain only for `encryption_enabled = 0`.
7. Verify public/admin interface tests:
   - legacy email lookup still resolves before migration
   - email lookup resolves through `email_blind_index` after migration
   - `GET /users/me/profile` or equivalent profile reads preserve current encrypted profile access
   - admin profile views can decrypt migrated `email`, `name`, and encrypted dynamic fields
   - `include_in_chat` plaintext fields still behave as operator-configured plaintext, not as migrated protected PII
8. Keep rollback simple: restore the SQLite backup if migration validation fails. Do not continue to column removal until backup restore has been tested.

## Removal Criteria

Plaintext-era support can be removed only after all of these are true:

- Protected legacy inventory stays at zero across at least one operator-reviewed migration run.
- `get_user_by_email` fallback to `LOWER(email)` is proven unused in validation evidence.
- All public/admin interface tests listed above pass against migrated data.
- Operator-plaintext fields are either still supported by an explicit non-legacy path or removed through a separate product decision.
- A backup and rollback note is attached to the migration evidence.
- A follow-up issue explicitly scopes schema removal for `users.email`, `users.name`, and protected uses of `user_field_values.value`.

Until those criteria are met, keep the fallback reads and `migrate_encrypt_existing_data` available.
