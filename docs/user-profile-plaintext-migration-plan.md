# User/Profile Plaintext Removal Record

Plaintext-era User Profile compatibility has been removed from the prototype.

## Removed Behavior

- `get_user_by_email` is blind-index-only and does not fall back to `LOWER(email)`.
- `/admin/profile-plaintext-migration/inventory` is absent.
- `/admin/profile-plaintext-migration/migrate` is absent.
- `profile_plaintext_migration_inventory` is absent.
- `migrate_encrypt_existing_data` is absent.
- First-admin setup no longer preflights or migrates plaintext-era profile rows.

## Active Behavior

- Current writes encrypt email and name into `encrypted_email` and `encrypted_name`.
- Current email lookup uses `email_blind_index`.
- Dynamic fields with `encryption_enabled = 1` write encrypted values.
- Dynamic fields with `encryption_enabled = 0` remain operator-selected plaintext by product choice and may still be used for chat context.

## Validation

Regression coverage verifies that plaintext-only `users.email` rows are not reachable, current encrypted users remain reachable by blind index, and the removed admin migration endpoints return 404.
