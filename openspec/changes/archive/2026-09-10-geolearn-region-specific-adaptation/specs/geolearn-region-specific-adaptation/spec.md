# geolearn-region-specific-adaptation — Specification (v0.2)

Adds hierarchical per-region classifier keys with optional sub-region support
and cold-start weight transfer from parent classifiers.

## Requirements

### Requirement: Hierarchical key resolution
`ClassifierStore.get_or_create_key(crop_type, region, sub_region=None) -> str`
SHALL return a dotted key string like `"wheat.khuzestan"` or
`"wheat.khuzestan.dezful"`. Parent classifiers are looked up automatically.

#### Scenario: Sub-region inherits from region
- **WHEN** key `("wheat", "khuzestan", "dezful")` is accessed but only
  `("wheat", "khuzestan")` exists
- **THEN** the sub-region classifier is initialized with the parent's weights

### Requirement: Weight transfer on first access
The first `partial_fit()` call on a sub-region key that inherited from a parent
copies the parent's `coef_` and `intercept_` before accumulating its own gradient.

#### Scenario: Transfer preserves parent state
- **WHEN** parent classifier has trained on 200 samples
- **THEN** sub-region starts with the same coefficients, then diverges as
  its own samples arrive

### Requirement: geo_select_region tool
GeoAgent tool `geo_select_region(crop_type, region)` SHALL return the active
classifier key and current training sample count for that key.

### Requirement: Schema migration
The `classifier_state` table gains an optional `sub_region TEXT` column
(null for legacy entries). Migration runs automatically on first access.

## Non-goals

- Cross-region knowledge distillation (beyond initial weight copy)
- Dynamic region hierarchy creation (regions must be known ahead of time)
