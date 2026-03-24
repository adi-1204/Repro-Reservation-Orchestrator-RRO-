# Changelog — Changes Since Last Commit

> **Date:** March 23, 2026

---

## New Files Added

| File | Purpose |
|---|---|
| `bugzilla_ingest.py` | Fetches real bugs from the external bug tracking API, upserts them into the DB, and triggers AI analysis. Includes `retry_pending_analysis()` for retrying failed analyses. |
| `chathpe_client.py` | Wraps all AI analysis API calls (`get_session_id`, `set_preferences`, `call_chatlite`) and provides `load_creds_from_config()` to read credentials from Flask app config (sourced from `.env`). |
| `run_ingest_now.py` | CLI script to manually trigger bug ingestion from the external bug tracking API. |
| `run_retry_now.py` | CLI script to manually retry pending AI analysis. |
| `check_analysis.py` | Diagnostic script to inspect ML analysis records. |
| `check_db_state.py` | Diagnostic script to inspect overall database state. |
| `check_tests.py` | Diagnostic script to inspect bug test records. |
| `fix_basicio.py` | One-off script to fix base I/O data issues. |
| `fix_dup_tests.py` | One-off script to remove duplicate bug test entries. |
| `fix_orphaned_bugs.py` | One-off script to clean up orphaned bug records. |
| `rro_local.db` | SQLite database file for local development (no MySQL required). |

---

## Modified Files

### `.gitignore`
- Added credential JSON files to prevent sensitive files from being committed.
- Added mock data files to prevent test data from being committed.
- Added `*.log` to exclude log files.

---

### `README.md`
- Expanded the `.env` setup section with new required variables for external API credentials.
- Added security warnings (never commit `.env` or credential files).
- Added documentation on automatic ingestion behaviour when a workgroup is created/updated.
- Added mock development instructions for running without real credentials.
- Removed the old minimal `.env` example block.

---

### `app/__init__.py`
- Added `_start_analysis_retry_scheduler()` — launches a **daemon background thread** on app startup.
  - Waits 60 seconds after startup, then calls `retry_pending_analysis()` every **30 minutes**.
  - Skips the retry cycle gracefully if AI analysis credentials are unavailable.

---

### `app/config.py`
- **SQLite fallback:** If `DB_HOST` is not set in `.env`, the app now uses a local `rro_local.db` SQLite file instead of failing to start.
- **New config keys** (all sourced from `.env`):
  - Bug tracking API credentials
  - AI analysis API credentials

---

### `app/models/` — Index Name Deduplication

Multiple models previously had duplicate SQLAlchemy index names (`idx_bug`, `idx_status`) which caused conflicts. All renamed to be unique per table:

| File | Old Index Name | New Index Name |
|---|---|---|
| `app/models/bug.py` | `idx_status` | `idx_bug_status` |
| `app/models/bug_comments.py` | `idx_bug` | `idx_bug_comment_bug` |
| `app/models/bug_stations.py` | `idx_bug` | `idx_bug_station_bug` |
| `app/models/bug_tests.py` | `idx_bug` | `idx_bug_test_bug` |
| `app/models/ml_analysis.py` | `idx_bug` | `idx_ml_analysis_bug` |
| `app/models/workgroup.py` | `idx_status` | `idx_workgroup_status` |

---

### `app/routes/managerDashboard.py`

**Background Ingestion System:**
- Added `_ingest_jobs` dict + lock to track per-workgroup ingestion status (`idle | running | done | error`).
- Added `_run_ingestion_thread()` — background thread that:
  1. Builds an email → `User.id` map from the engineer table.
  2. Loads AI analysis credentials from app config.
  3. Runs `BugIngester.ingest()` for the workgroup's build version.
  4. Updates the job status on completion or error.
- Added `_trigger_ingestion()` — helper to launch the ingestion thread.

**`create_workgroup` endpoint:**
- Triggers background ingestion immediately after a workgroup is created.
- Response now includes `"ingestion_started": true`.

**`update_workgroup` endpoint:**
- Detects if `release_version` or the engineer roster changed.
- Re-triggers ingestion when either changes.

**`delete_workgroup` endpoint:**
- Now cascades deletion of all related records before deleting the workgroup:
  - `MLAnalysis`, `BugComment`, `BugTest`, `BugStation`, `Bug`
  - Filtered by `Bug.resource_group == workgroup.release_version`.

**New endpoint — `GET /api/workgroups/<id>/ingest_status`:**
- Returns ingestion progress for polling from the frontend.
- Response: `{ "status": "idle|running|done|error", "ingested": int, "updated": int, "errors": [...] }`

---

### `app/routes/bugDashboard.py`

**Bug filtering tightened (security/correctness fix):**
- Removed `or_(Bug.engineer_id.is_(None))` from all role-based filters — unassigned bugs are no longer visible to any user.
- Workgroup view now also filters by `Bug.resource_group == workgroup.release_version` to enforce build version scoping.
- Manager view uses a clean `select()` subquery instead of the previous `func.distinct()` subquery.
- Engineer view now strictly filters `Bug.engineer_id == user_id` only.
- Same tightened filters applied to the `bug_stats` endpoint.

---

### `app/static/js/bugManagement.js`

- **New `cleanAnalysisField()` function:**
  - Strips LLM-added `"Answer:"` prefixes from response text.
  - Returns `null` for responses containing `"not found in provided context"`.
- **ML Analysis display now distinguishes two states:**
  - `"Pending analysis…"` — no analysis record exists yet.
  - `"Not found in bug comments"` — record exists but the field has no usable content.

---

### `generate_ml_analysis.py`

**Rewritten to use the real external AI API:**
- Removed all mock HTTP helpers — replaced with calls to the AI analysis client module.
- Removed `--mock-port` CLI argument; credentials now come from Flask app config.
- Removed `strip_markdown_bold()` — no longer needed with structured output format.
- `clean_response_text()` removed (was stripping mock-specific text).
- `parse_analysis_fields()` updated:
  - New structured label patterns: `REPRO_ACTIONS:`, `CONFIG_CHANGES:`, `REPRO_READINESS:`, `SUMMARY:`.
  - Now also populates `repro_readiness` from the structured response.
  - Falls back to full response as `summary` if the model doesn't follow the format.
- `generate()` now accepts an optional `flask_app` argument for use from background threads.
- Skip logic simplified: no longer special-cases `"Bug UNKNOWN"` summaries.

---

### `run.py`
- Added `use_reloader=False` to `app.run()` to prevent Flask's watchdog reloader from killing background ingestion and ML retry threads.

---

### `requirements.txt`
- Updated with new package dependencies (binary diff — includes packages for external API integration and HTTP client libraries).
