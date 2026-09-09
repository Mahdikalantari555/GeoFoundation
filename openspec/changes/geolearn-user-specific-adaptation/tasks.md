# Tasks: geolearn-user-specific-adaptation

- [ ] Task 1: UserSettings + UserSettingsStore
  - Acceptance: Dataclass with all fields + defaults. Store with get_or_default, update, list_all. SQLite table `user_settings` auto-created.
  - Verify: `pytest libs/geolearn/tests/test_user_settings.py -v`
  - Files: `libs/geolearn/geolearn/user_settings.py`, `libs/geolearn/tests/test_user_settings.py`

- [ ] Task 2: Threshold override in prediction path
  - Acceptance: When user_id is passed to predict, user's confidence_threshold overrides global default. Missing user falls back to 0.6.
  - Verify: test with custom threshold, test with missing user, test at exact threshold boundary.
  - Files: `libs/geolearn/geolearn/classifier.py` (extend predict signature)

- [ ] Task 3: GeoAgent tools
  - Acceptance: `geo_get_user_settings(user_id?)` and `geo_update_user_settings(user_id, partial_settings)` registered; return structured ToolResult.
  - Verify: tool names appear in registry; call returns expected shape.
  - Files: `libs/geoagent/src/geoagent/tools/geolearn_tools.py` (extend)

- [ ] Task 4: Gates
  - Acceptance: all tests green; ruff/mypy clean.
  - Verify: `conda run -n geospatial pytest libs/geolearn/tests -q && conda run -n geospatial ruff check libs/geolearn/src libs/geoagent/src && conda run -n geospatial mypy --strict libs/geolearn/src`
  - Files: all above

Dependencies: 1→2→3, all→4.
