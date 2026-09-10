# geolearn-user-specific-adaptation — Specification (v0.2)

Stores per-user confidence thresholds and behavior preferences, applied on top
of region-specific adaptation.

## Requirements

### Requirement: UserSettings model
```python
@dataclass
class UserSettings:
    user_id: str
    confidence_threshold: float   # default 0.6
    preferred_classifier: str     # default "sgd"
    auto_train_on_feedback: bool  # default True
    updated_at: str               # ISO timestamp
```

### Requirement: Settings store API
`UserSettingsStore(workspace_dir)` SHALL provide:
- `get_or_default(user_id) -> UserSettings`
- `update(user_id, **fields) -> UserSettings`
- `list_all() -> list[UserSettings]`

Persisted in `user_settings` table in `geolearn.db`.

### Requirement: Threshold override in prediction
When `OnlineClassifier.predict()` is called with a `user_id`, the user's
`confidence_threshold` overrides the instance default before the abstain
decision is made.

#### Scenario: User lowers threshold
- **WHEN** user settings set `confidence_threshold=0.4`
- **THEN** predictions with confidence 0.45 are accepted (not abstained)

#### Scenario: Missing settings
- **WHEN** no settings exist for a user_id
- **THEN** the global default (0.6) is used

### Requirement: GeoAgent tools
Two new tools are exposed:
- `geo_get_user_settings(user_id?)` → returns current settings
- `geo_update_user_settings(user_id, partial_settings)` → updates fields present

## Non-goals

- Multi-factor authentication
- Shared settings across users
- Settings sync between devices
