# geolearn-model-versioning-and-rollbacks — Specification (v0.2)

Versioned classifier state with rollback capability to recover from corrupted training batches.

## Requirements

### Requirement: Versioned file naming
Every saved classifier is stored as:
`<workspace>/geolearn/models/<key>/<version:04d>_<timestamp>.pkl`
where `version` is a zero-padded monotonic integer (0001, 0002, ...).

#### Scenario: First save
- **WHEN** a classifier is saved for key `("wheat", "khuzestan")`
- **THEN** file is `.../wheat__khuzestan/0001_<ISO_TS>.pkl`

### Requirement: ModelVersion dataclass
```python
@dataclass
class ModelVersion:
    key: tuple[str, str]
    version: int
    timestamp: str      # ISO
    n_samples: int
    sha256: str         # of the pkl file
```

### Requirement: list_versions(key?)
Returns `list[ModelVersion]` sorted by version descending. When `key` is None,
returns versions for all keys.

### Requirement: rollback_to(key, version) -> bool
Restores the classifier at the given version. On success:
1. Loads the pkl file for that version.
2. Replaces the current active classifier in memory.
3. Logs the rollback event to `rollback_history` table in `geolearn.db`.
4. Returns True.

On failure (version doesn't exist): returns False, logs error.

#### Scenario: Successful rollback
- **WHEN** version 3 is corrupted and version 2 exists
- **THEN** after rollback, predictions use the version-2 weights

### Requirement: Garbage collection
After each save, retain only the last 10 versions per key. Older versions
are deleted from disk and removed from version listings.

### Requirement: GeoAgent tools
- `geo_list_model_versions(key?)` → list of version summaries
- `geo_rollback_model(key, version)` → result with before/after n_samples

## Non-goals

- Automatic rollback on degradation detection (manual trigger only)
- Cross-key version comparison
- Blockchain-style immutable audit trail
