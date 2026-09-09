# geolearn-personalization-profiles — Specification (v0.2)

Extends geolearn-core-framework with persistent user and region profiles.

## Requirements

### Requirement: UserProfile model
```python
@dataclass
class UserProfile:
    user_id: str
    region: str
    crop_type: str
    preferred_classifier: str  # "sgd" | "passive_aggressive" | "incremental_kmeans"
    trained_at: str | None   # ISO timestamp of last training
    n_training_samples: int
```

### Requirement: ProfileStore API
`ProfileStore(workspace_dir)` SHALL provide:
- `get_or_create(user_id, region) -> UserProfile`
- `update(user_id, region, **fields)` → mutates in place and persists
- `list_all() -> list[UserProfile]`

Storage is SQLite in `geolearn.db`, table `user_profiles`.

#### Scenario: Auto-create anonymous profile
- **WHEN** `store.get_or_create("anonymous", "khuzestan")` is called twice
- **THEN** both calls return the same profile object (idempotent)

### Requirement: Profile-driven classifier selection
`ClassifierStore.select_key(user_id, region, crop_type)` SHALL:
1. Look up profile for `(user_id, region)`
2. If profile exists and has a non-default `preferred_classifier`, use it
3. Otherwise fall back to default `"sgd"`

### Requirement: Backward compatibility
Existing code that does not use profiles continues to work. The default
`("unknown", "global")` key is still valid.
