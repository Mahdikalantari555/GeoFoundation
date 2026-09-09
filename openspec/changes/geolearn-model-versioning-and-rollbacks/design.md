# Design: geolearn-model-versioning-and-rollbacks

Versioned saves enable recovery from bad training batches.

## Version numbering

Monotonically increasing integer per key, zero-padded to 4 digits.
File: `models/<crop>__<region>/0001_2026-09-09T12:00:00Z.pkl`

## Rollback procedure

1. Load target version pkl file.
2. Replace in-memory classifier state.
3. Update classifier_state.version column to target version.
4. Insert rollback event into rollback_history table.
5. Return success.

## Garbage collection

After each save:
1. List all versions for the key.
2. Keep last 10 by version number.
3. Delete older .pkl files from disk.
4. Remove corresponding rows from version listing.

Rollback to a deleted version returns False with clear error message.
