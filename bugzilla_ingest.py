"""
Bugzilla bug ingestion for the student project.

Fetches live bugs from bugs.storage.hpecorp.net using the Bugzilla REST API
and upserts them into the local database.

Pipeline (mirrors bug_info.py exactly):
  1. Login to Bugzilla, fetch bugs by cf_build_id
  2. Filter: only status == REPRODUCE, assigned to a known engineer
  3. Fetch all comments for each qualifying bug
  4. Store Bug record (repro type) + one BugComment row per comment
  5. Regex-extract structured metadata (Test Name, Station, Build, etc.)
     from every comment → store BugTest + BugStation rows
  6. Strip structured metadata block from each comment text (same logic as
     strip_test_metadata_block in bug_info.py)
  7. Discard non-English and gdb/log-dump comments
  8. RAG filter: embed surviving comments + 3 repro-focused queries via
     sentence-transformers → pick top-3 per query (up to 9 unique)
  9. Build ChatHPE prompt (same system instruction as bug_info.py)
  10. Call real ChatHPE API → parse structured response → store MLAnalysis

Credentials are taken exclusively from the Flask app config (sourced from
.env). Nothing is written to disk or persisted outside the database.

Security note:
  - Credentials held in memory only for the lifetime of the ingestion call.
  - SSL verification disabled for internal HPE hosts (self-signed certs).
  - No bug data written to any external service, file, or log.
"""

import json
import logging
import os
import re
from datetime import datetime

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

log = logging.getLogger(__name__)

_BUGZ_HOST = os.getenv("BUGZ_HOST", "https://bugs.storage.hpecorp.net")

_VALID_PRIORITIES = {"P0", "P1", "P2", "P3", "P4"}

# ---------------------------------------------------------------------------
# RAG / NLP constants (identical to bug_info.py)
# ---------------------------------------------------------------------------
_RAG_QUERIES = [
    "what are the actions I need to perform to make this repro",
    "what are the config changes I need to make for this repro",
    "is a repro required right now or do I need to wait for more information",
]
_RAG_TOP_K = 3

# ---------------------------------------------------------------------------
# Metadata regex patterns (identical to bug_info.py _META_PATTERNS)
# ---------------------------------------------------------------------------
_META_PATTERNS = {
    "test_names":  re.compile(r"Test\s+Name\s*:\s*(.+)", re.IGNORECASE),
    "test_rings":  re.compile(r"Test\s+Ring\s+Name\s*:\s*(.+)", re.IGNORECASE),
    "builds":      re.compile(r"Build\s+Version\s*:\s*(.+)", re.IGNORECASE),
    "nodes":       re.compile(r"Number\s+Of\s+Nodes\s*:\s*(.+)", re.IGNORECASE),
    "controllers": re.compile(r"Controller\s+Types\s*:\s*(.+)", re.IGNORECASE),
    "odin_links":  re.compile(r"Odin\s+Link\s*:\s*(\S+)", re.IGNORECASE),
    "nfs_paths":   re.compile(r"NFS\s+Path\s*:\s*(\S+)", re.IGNORECASE),
    "signatures":  re.compile(r"Signature\s*:\s*(.+)", re.IGNORECASE),
    "test_plans":  re.compile(r"Test\s+Plan\s+Name\s*:\s*(.+)", re.IGNORECASE),
    "exec_starts": re.compile(r"Execution\s+Start\s*:\s*(.+)", re.IGNORECASE),
    "exec_ends":   re.compile(r"Execution\s+End\s*:\s*(.+)", re.IGNORECASE),
    "failure_types": re.compile(r"Failure\s+Type\s*:\s*(.+)", re.IGNORECASE),
}

# Structured block markers (identical to bug_info.py)
_META_BLOCK_START = re.compile(r"^\s*Test\s+Name\s*:", re.IGNORECASE | re.MULTILINE)
_META_BLOCK_END_ANCHOR = re.compile(r"KVAR\s+Info\s+for\s+cluster", re.IGNORECASE)
_STRUCTURED_FIELD_LABELS = re.compile(
    r"^\s*(Test\s+Name|Test\s+History|Test\s+Plan\s+Name|Test\s+Ring\s+Name|"
    r"Execution\s+Start|Execution\s+End|Triager|Controller\s+Types|"
    r"Number\s+Of\s+Nodes|Failure\s+Type|Build\s+Version|NFS\s+Path|"
    r"URL\s+Path|Odin\s+Link|Recover\s+Status|Signature|"
    r"Bug\s+Summary|Path\s+to\s+Oldest|Corefile\s+Summary|Auto\s+Analysis|"
    r"Panic\s+Backtrace|Last\s+\d+\s+Lines|Steps\s+to\s+Reproduce|"
    r"Term\s+Error|IO\s+Tool\s+Versions|Unexpected\s+Cores|"
    r"Detected\s+Expected\s+Crash|Cluster\s+time\s+difference|"
    r"Post\s+Test\s+Analysis|Test\s+Binary\s+Core|Host\s+Info|"
    r"Array\s+Info|KVAR\s+Info|IO\s+Stall)",
    re.IGNORECASE,
)

# gdb/log dump line detector (identical to bug_info.py)
_GDB_HEX_LINE = re.compile(
    r"(#\d+\s+0x[0-9a-fA-F]+|"
    r"\(gdb\)|"
    r"0x[0-9a-fA-F]{8,}|"
    r"^\s*\d{4}-\d{2}-\d{2}.*MDT.*\{)",
    re.MULTILINE,
)

# ---------------------------------------------------------------------------
# Field mapping helpers
# ---------------------------------------------------------------------------

_STATUS_MAP = {
    "CONFIRMED":   "pending",
    "NEW":         "pending",
    "ASSIGNED":    "running",
    "IN_PROGRESS": "running",
    "REOPENED":    "pending",
    "RESOLVED":    "completed",
    "VERIFIED":    "completed",
    "CLOSED":      "completed",
    "REPRODUCE":   "running",
}


def _map_status(bugz_status):
    return _STATUS_MAP.get((bugz_status or "").upper(), "pending")


def _map_priority(bugz_priority):
    p = (bugz_priority or "P2").upper()
    return p if p in _VALID_PRIORITIES else "P2"


def _parse_bugz_datetime(raw):
    if not raw:
        return None
    clean = str(raw).strip().rstrip("Z")[:26]
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
        try:
            return datetime.strptime(clean, fmt)
        except ValueError:
            continue
    return None


def _parse_int(val):
    try:
        return int(str(val).strip())
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Metadata extraction helpers (mirrors bug_info.py)
# ---------------------------------------------------------------------------

def _extract_all_test_metadata(comments_raw):
    """Scan all comment texts and return a dict of sets keyed by field name."""
    result = {k: set() for k in _META_PATTERNS}
    for c in comments_raw:
        text = c if isinstance(c, str) else c.get("text", "")
        for field, pattern in _META_PATTERNS.items():
            for m in pattern.finditer(text):
                val = m.group(1).strip()
                if val:
                    result[field].add(val)
    return result


def _extract_comment_metadata(text):
    """
    Extract metadata from a single comment text.
    Returns a dict keyed by field name → first matched value (str or None).
    Each comment's structured block has exactly one test name, one station, etc.
    """
    result = {}
    for field, pattern in _META_PATTERNS.items():
        m = pattern.search(text)
        result[field] = m.group(1).strip() if m else None
    return result


def _strip_test_metadata_block(text):
    """
    Remove the structured test-report header from a comment.
    Identical logic to strip_test_metadata_block in bug_info.py.
    """
    lines = text.splitlines()
    start_idx = None
    for i, line in enumerate(lines):
        if _META_BLOCK_START.search(line):
            start_idx = i
            break
    if start_idx is None:
        return text

    end_idx = start_idx
    kvar_seen = False
    i = start_idx
    while i < len(lines):
        line = lines[i]
        if _META_BLOCK_END_ANCHOR.search(line):
            kvar_seen = True
        if kvar_seen:
            if i > start_idx and line.strip() \
                    and not lines[i].startswith(" ") \
                    and not lines[i].startswith("\t") \
                    and not _STRUCTURED_FIELD_LABELS.search(line) \
                    and not re.match(r"^\s*(qld_|iostuck_|nvf_|bcm_|rcopy_|gfc_|lld_)", line):
                break
        end_idx = i
        i += 1

    before = "\n".join(lines[:start_idx]).strip()
    after  = "\n".join(lines[end_idx + 1:]).strip()
    return "\n\n".join(part for part in (before, after) if part).strip()


# ---------------------------------------------------------------------------
# Language + dump filters (mirrors bug_info.py)
# ---------------------------------------------------------------------------

try:
    from langdetect import detect as _langdetect_detect
    _LANGDETECT_AVAILABLE = True
except ImportError:
    _LANGDETECT_AVAILABLE = False


def _is_likely_english(text):
    if not text or not text.strip():
        return False
    if _LANGDETECT_AVAILABLE:
        try:
            return _langdetect_detect(text) == "en"
        except Exception:
            pass
    ascii_count = sum(1 for c in text if ord(c) < 128)
    return (ascii_count / max(len(text), 1)) >= 0.90


# ---------------------------------------------------------------------------
# RAG filter (mirrors bug_info.py filter_relevant_comments_rag)
# ---------------------------------------------------------------------------

from sentence_transformers import SentenceTransformer
import numpy as np


def _cosine_similarity(a, b):
    denom = (np.linalg.norm(a) * np.linalg.norm(b))
    return float(np.dot(a, b) / denom) if denom else 0.0


def _filter_comments_rag(comments_raw, model, max_chars_each=800):
    """
    Clean, filter, embed and RAG-rank comments.
    Returns a list of dicts: {text, matched_queries}.
    Identical logic to filter_relevant_comments_rag in bug_info.py.
    """
    cleaned = []
    for idx, c in enumerate(comments_raw):
        raw_text = c if isinstance(c, str) else c.get("text", "")
        prose = _strip_test_metadata_block(raw_text)
        if not prose.strip():
            continue
        non_empty = [l for l in prose.splitlines() if l.strip()]
        if non_empty:
            dump = sum(1 for l in non_empty if _GDB_HEX_LINE.search(l))
            if dump / len(non_empty) > 0.35:
                continue
        if not _is_likely_english(prose):
            continue
        cleaned.append((idx, prose))

    if not cleaned:
        return []

    texts = [c[1] for c in cleaned]
    try:
        c_embs = model.encode(texts, show_progress_bar=False)
        q_embs = model.encode(_RAG_QUERIES, show_progress_bar=False)
    except Exception as exc:
        log.warning("Embedding failed: %s", exc)
        return []

    selected = {}
    for q_idx, q_emb in enumerate(q_embs):
        scores = [(_cosine_similarity(q_emb, c_embs[i]), i) for i in range(len(cleaned))]
        scores.sort(key=lambda x: -x[0])
        for _, c_pos in scores[:_RAG_TOP_K]:
            orig_idx, prose = cleaned[c_pos]
            truncated = prose[:max_chars_each] + ("…" if len(prose) > max_chars_each else "")
            if orig_idx in selected:
                if _RAG_QUERIES[q_idx] not in selected[orig_idx]["matched_queries"]:
                    selected[orig_idx]["matched_queries"].append(_RAG_QUERIES[q_idx])
            else:
                selected[orig_idx] = {
                    "text": truncated,
                    "matched_queries": [_RAG_QUERIES[q_idx]],
                }
    return list(selected.values())


# ---------------------------------------------------------------------------
# ChatHPE prompt (identical system instruction to bug_info.py)
# ---------------------------------------------------------------------------

_SYSTEM_INSTRUCTION = (
    "You are a precise bug analysis assistant for HPE storage engineers.\n"
    "\n"
    "STRICT RULES – follow these without exception:\n"
    "- Answer using ONLY the metadata table and engineer comments provided below. "
    "Do NOT use any knowledge from outside this context.\n"
    "- If a piece of information is not present in the provided context, "
    "write exactly: 'not found in provided context' – never guess or infer.\n"
    "- Do NOT paraphrase, generalise, or combine information in a way that changes "
    "its meaning. Quote or closely paraphrase the source comment where possible.\n"
    "- Do NOT fabricate CLI commands, file paths, KVARs, flag names, or bug references "
    "that do not appear verbatim in the comments.\n"
    "- If you are uncertain about any detail, say so explicitly.\n"
    "\n"
    "Answer the following three questions in order, using a numbered section for each:\n"
    "\n"
    "1. REPRO ACTIONS\n"
    "   Question: What exact actions must the engineer perform to reproduce this bug?\n"
    "   Answer: List every concrete step, CLI command, or procedure mentioned in the "
    "comments. Quote commands exactly as written. If none are specified, write "
    "'not found in provided context'.\n"
    "\n"
    "2. CONFIG CHANGES\n"
    "   Question: What configuration changes (KVARs, flags, system settings, touchfiles, "
    "tuning parameters) are needed for reproduction?\n"
    "   Answer: List each setting with its exact name and value as stated in the comments. "
    "If none are mentioned, write 'not found in provided context'.\n"
    "\n"
    "3. REPRO READINESS\n"
    "   Question: Should the engineer start reproducing NOW, or must they wait for "
    "more information / a fix / a specific build?\n"
    "   Answer: State the recommendation clearly (NOW / WAIT) and explain the reason "
    "using only evidence from the comments. If the comments are ambiguous, say so.\n"
    "\n"
    "After the three sections, add a short SUMMARY (2-3 sentences) covering the "
    "failure signature and the most critical finding from the comments.\n"
    "\n"
    "Reminder: every claim must be traceable to a specific comment in the context below."
)


def _build_prompt(bug_id, metadata, filtered_comments):
    def _join(s):
        return " | ".join(sorted(s)) if s else "—"

    meta_lines = [
        f"Bug ID       : {bug_id}",
        f"Test Name(s) : {_join(metadata.get('test_names', set()))}",
        f"Station(s)   : {_join(metadata.get('test_rings', set()))}",
        f"Build(s)     : {_join(metadata.get('builds', set()))}",
        f"Nodes        : {_join(metadata.get('nodes', set()))}",
        f"Controllers  : {_join(metadata.get('controllers', set()))}",
        f"Odin link(s) : {_join(metadata.get('odin_links', set()))}",
    ]
    meta_str = "\n".join(meta_lines)

    lines = [
        _SYSTEM_INSTRUCTION,
        "",
        f"=== Bug {bug_id} – Metadata Table ===",
        meta_str,
        "",
        "=== Relevant Engineer Comments ===",
    ]
    for i, item in enumerate(filtered_comments, start=1):
        labels = ", ".join(item["matched_queries"])
        lines.append(f"\n[Comment {i}] [RE: {labels}]")
        lines.append(item["text"])

    prompt = "\n".join(lines)
    MAX_CHARS = 8000
    if len(prompt) > MAX_CHARS:
        header = "\n".join(lines[:lines.index("=== Relevant Engineer Comments ===")+1])
        budget = max(200, (MAX_CHARS - len(header)) // max(len(filtered_comments), 1))
        trimmed = [header]
        for i, item in enumerate(filtered_comments, start=1):
            labels = ", ".join(item["matched_queries"])
            trimmed.append(f"\n[Comment {i}] [RE: {labels}]")
            trimmed.append(item["text"][:budget] + "…")
        prompt = "\n".join(trimmed)
    return prompt


# ---------------------------------------------------------------------------
# ChatHPE response parser
# ---------------------------------------------------------------------------

def _parse_chathpe_response(text):
    """
    Parse the structured ChatHPE response into (repro_actions, config_changes,
    repro_readiness, summary). Falls back to using full text as summary.
    """
    text = (text or "").strip()
    result = {
        "repro_actions":   None,
        "config_changes":  None,
        "repro_readiness": None,
        "summary":         None,
    }

    # Try numbered section headings (e.g. "1. REPRO ACTIONS\n   ...")
    section_patterns = [
        ("repro_actions",   r"1\.\s*REPRO\s+ACTIONS\s*\n(.*?)(?=\n\s*2\.\s*CONFIG|\Z)"),
        ("config_changes",  r"2\.\s*CONFIG\s+CHANGES\s*\n(.*?)(?=\n\s*3\.\s*REPRO\s+READINESS|\Z)"),
        ("repro_readiness", r"3\.\s*REPRO\s+READINESS\s*\n(.*?)(?=\n\s*SUMMARY|\Z)"),
        ("summary",         r"SUMMARY[:\s]*\n?(.*?)(?=\Z)"),
    ]
    matched = False
    for field, pat in section_patterns:
        m = re.search(pat, text, re.DOTALL | re.IGNORECASE)
        if m:
            result[field] = m.group(1).strip()
            matched = True

    if not matched:
        # Markdown numbered fallback used by local mock API:
        # 1. **Failure Signature**: ...
        # 2. **Key Engineer Findings**: ...
        # 3. **Reproduction Steps / Config Changes**: ...
        numbered = re.findall(
            r"(?ms)^\s*(\d+)\.\s*(?:\*\*)?([^:\n*]+?)(?:\*\*)?\s*:\s*(.*?)(?=^\s*\d+\.\s|\n+\s*\*|(?:\n{2,}|\Z))",
            text,
        )
        if numbered:
            by_idx = {int(idx): body.strip() for idx, _title, body in numbered}
            by_title = {title.strip().lower(): body.strip() for _idx, title, body in numbered}

            # Prefer semantic title mapping first.
            for title, body in by_title.items():
                if "config" in title:
                    result["config_changes"] = body
                    matched = True
                if "repro" in title and ("step" in title or "action" in title):
                    result["repro_actions"] = body
                    matched = True
                if "readiness" in title or "finding" in title:
                    result["repro_readiness"] = body
                    matched = True

            # Positional fallback if semantic mapping missed any fields.
            if not result["repro_actions"] and by_idx.get(1):
                result["repro_actions"] = by_idx[1]
                matched = True
            if not result["repro_readiness"] and by_idx.get(2):
                result["repro_readiness"] = by_idx[2]
                matched = True
            if not result["config_changes"] and by_idx.get(3):
                result["config_changes"] = by_idx[3]
                matched = True

            if not result["summary"]:
                plain = re.sub(r"\*+", "", text).strip()
                result["summary"] = plain

    if not matched:
        # Flat label fallback
        flat = [
            ("repro_actions",   r"REPRO_ACTIONS:\s*(.*?)(?=\nCONFIG_CHANGES:|$)"),
            ("config_changes",  r"CONFIG_CHANGES:\s*(.*?)(?=\nREPRO_READINESS:|$)"),
            ("repro_readiness", r"REPRO_READINESS:\s*(.*?)(?=\nSUMMARY:|$)"),
            ("summary",         r"SUMMARY:\s*(.*?)(?=$)"),
        ]
        for field, pat in flat:
            m = re.search(pat, text, re.DOTALL | re.IGNORECASE)
            if m:
                result[field] = m.group(1).strip()
                matched = True

    if not matched:
        result["repro_actions"]   = "See summary"
        result["config_changes"]  = "See summary"
        result["repro_readiness"] = "Needs more runs"
        result["summary"]         = text

    defaults = {
        "repro_actions":   "See summary",
        "config_changes":  "See summary",
        "repro_readiness": "Needs more runs",
        "summary":         "See summary",
    }
    for field, default in defaults.items():
        if not result[field]:
            result[field] = default

    return result


# ---------------------------------------------------------------------------
# Main ingestion class
# ---------------------------------------------------------------------------

class BugzillaIngester:
    """
    Fetches REPRODUCE bugs from Bugzilla for a given build version, upserts
    them into the student project database with full comment rows, extracts
    test metadata (BugTest + BugStation), RAG-filters comments, and generates
    ChatHPE ML analysis — all identical to the bug_info.py pipeline.

    Usage (inside a Flask app context):
        ingester = BugzillaIngester("3.3.1.648", bugz_user, bugz_password)
        result = ingester.ingest(db.session, user_email_map, chathpe_creds)
    """

    def __init__(self, release_version, bugz_user, bugz_password):
        if not bugz_user or not bugz_password:
            raise ValueError(
                "Bugzilla credentials are missing. "
                "Set BUGZ_USER and BUGZ_PASSWORD in .env."
            )
        self.release_version = release_version
        self._user = bugz_user
        self._password = bugz_password
        self._token = None

    # ------------------------------------------------------------------
    # Bugzilla REST helpers
    # ------------------------------------------------------------------

    def _get(self, path, params=None):
        url = _BUGZ_HOST + path
        resp = requests.get(url, params=params, timeout=30, verify=False)
        resp.raise_for_status()
        return resp.json()

    def login(self):
        data = self._get(
            "/rest/login",
            params={"login": self._user, "password": self._password},
        )
        self._token = data["token"]
        print(f"[Bugzilla] Login successful.", flush=True)

    def fetch_bugs(self):
        if not self._token:
            self.login()
        data = self._get(
            "/rest/bug",
            params={"token": self._token, "cf_build_id": self.release_version},
        )
        return data.get("bugs", [])

    def fetch_comments(self, bug_id):
        if not self._token:
            self.login()
        data = self._get(
            f"/rest/bug/{bug_id}/comment",
            params={"token": self._token},
        )
        return (
            data.get("bugs", {})
                .get(str(bug_id), {})
                .get("comments", [])
        )

    # ------------------------------------------------------------------
    # Main ingestion entry point
    # ------------------------------------------------------------------

    def ingest(self, db_session, user_email_map, chathpe_creds=None, workgroup_id=None):
        """
        Fetch bugs, filter to REPRODUCE status, upsert Bug + BugComment +
        BugTest + BugStation rows, then generate ChatHPE ML analysis via RAG.

        Args:
            db_session:      SQLAlchemy session.
            user_email_map:  {lowercase email -> User.id} for engineer linking.
            chathpe_creds:   dict with client_id/jwt_token/user_id/username
                             (None = skip analysis step).
            workgroup_id:    Workgroup ID to associate bugs with (None = no FK link).

        Returns:
            dict: {ingested, updated, skipped, errors}
        """
        from app.models.bug import Bug
        from app.models.bug_comments import BugComment
        from app.models.bug_tests import BugTest
        from app.models.bug_stations import BugStation
        from app.models.ml_analysis import MLAnalysis
        from app.models.build import Build

        stats = {"ingested": 0, "updated": 0, "skipped": 0, "errors": []}

        # 1. Authenticate
        try:
            self.login()
        except Exception as exc:
            msg = f"Bugzilla login failed: {exc}"
            print(f"[Bugzilla] ERROR: {msg}", flush=True)
            stats["errors"].append(msg)
            return stats

        # 2. Fetch all bugs for this build version
        try:
            raw_bugs = self.fetch_bugs()
        except Exception as exc:
            msg = f"Failed to fetch bugs for {self.release_version}: {exc}"
            print(f"[Bugzilla] ERROR: {msg}", flush=True)
            stats["errors"].append(msg)
            return stats

        print(f"[Bugzilla] Fetched {len(raw_bugs)} total bugs for build {self.release_version}.", flush=True)

        # Ensure the main release build exists in global table
        rel_build = Build.query.get(self.release_version)
        if not rel_build:
            rel_build = Build(version=self.release_version)
            db_session.add(rel_build)
            db_session.flush()

        # 3. Filter to REPRODUCE only (same as bug_info.py makeTable)
        repro_bugs = [b for b in raw_bugs if (b.get("status") or "").upper() == "REPRODUCE"]
        print(f"[Bugzilla] {len(repro_bugs)} bug(s) have status REPRODUCE.", flush=True)

        # 4. Load local MiniLM model once (reused across all bugs)
        # Check for local model folder first
        _base_dir = os.path.dirname(os.path.abspath(__file__))
        _model_path = os.path.join(_base_dir, "all-MiniLM-L6-v2")
        if not os.path.exists(_model_path):
            # Fallback to downloading by name if local folder is missing
            print(f"[Ingest] Local model not found at {_model_path}, using name 'all-MiniLM-L6-v2' instead.", flush=True)
            _model_path_or_name = "all-MiniLM-L6-v2"
        else:
            _model_path_or_name = _model_path
            
        print(f"[Ingest] Loading model from {_model_path_or_name}...", flush=True)
        embedding_model = SentenceTransformer(_model_path_or_name)
        print("[Ingest] Model loaded.", flush=True)

        # 5. Set up ChatHPE session once (reused across all bugs)
        chathpe_session_id = None
        if chathpe_creds:
            import chathpe_client
            try:
                chathpe_session_id = chathpe_client.get_session_id(
                    chathpe_creds["client_id"], chathpe_creds["jwt_token"]
                )
                chathpe_client.set_preferences(
                    chathpe_session_id,
                    chathpe_creds["client_id"],
                    chathpe_creds["jwt_token"],
                    chathpe_creds["user_id"],
                    chathpe_creds["username"],
                )
                print(f"[ChatHPE] Session ready: {chathpe_session_id}", flush=True)
            except Exception as exc:
                print(f"[ChatHPE] WARNING: Could not start session: {exc}", flush=True)
                chathpe_session_id = None

        # 6. Process each REPRODUCE bug
        for raw in repro_bugs:
            bug_id_str = str(raw.get("id", ""))
            if not bug_id_str:
                stats["skipped"] += 1
                continue

            try:
                print(f"\n[Ingest] Processing bug {bug_id_str}...", flush=True)

                existing = Bug.query.filter_by(bug_id=bug_id_str).first()
                is_new = existing is None
                bug = existing if not is_new else Bug()

                # Core fields — status is always "running" for REPRODUCE bugs
                bug.bug_id      = bug_id_str
                bug.bug_name      = (raw.get("summary") or "")[:255]
                bug.priority      = _map_priority(raw.get("priority"))
                bug.status        = "running"   # REPRODUCE → running
                bug.bug_type      = "repro"     # REPRODUCE → repro table
                bug.component       = (raw.get("component") or "")[:255]
                # Always use the workgroup's release_version so cascade delete
                # in delete_workgroup() can find these bugs reliably.
                bug.workgroup_id = workgroup_id

                assignee = (raw.get("assigned_to") or "").lower()
                bug.engineer_id = user_email_map.get(assignee)

                if is_new:
                    db_session.add(bug)
                    db_session.flush()

                # 6a. Fetch all comments for this bug
                try:
                    raw_comments = self.fetch_comments(raw["id"])
                except Exception as exc:
                    print(f"[Ingest] WARNING: Could not fetch comments for bug {bug_id_str}: {exc}", flush=True)
                    raw_comments = []

                print(f"[Ingest] Bug {bug_id_str}: {len(raw_comments)} comment(s).", flush=True)

                # 6b. Store one BugComment row per comment
                existing_comment_ids: set = set()
                if not is_new:
                    existing_comment_ids = {
                        c.comment_bugzilla_id
                        for c in BugComment.query.filter_by(bug_id=bug.bug_id).all()
                        if c.comment_bugzilla_id is not None
                    }

                for c in raw_comments:
                    c_bugz_id = c.get("id")
                    if c_bugz_id in existing_comment_ids:
                        continue
                    db_session.add(BugComment(
                        bug_id=bug.bug_id,
                        creator=c.get("creator", ""),
                        text=c.get("text", ""),
                    ))

                # 6c. Regex-extract structured metadata from all comments
                metadata = _extract_all_test_metadata(raw_comments)
                
                # Assign global build from metadata
                b_val = None
                if metadata.get("builds"):
                    # Use the first/most common build version found in comments
                    b_val = next(iter(metadata["builds"]), None)
                
                # FALLBACK: If no build found in comments, use the main release version
                if not b_val:
                    b_val = self.release_version

                if b_val:
                    b_obj = Build.query.get(b_val)
                    if not b_obj:
                        b_obj = Build(version=b_val)
                        db_session.add(b_obj)
                        db_session.flush()
                    bug.build_id = b_obj.version

                print(
                    f"[Ingest] Bug {bug_id_str}: build={bug.build_id}, stations={metadata['test_rings']}, "
                    f"test_names={metadata['test_names']}", flush=True
                )

                # 6d. Upsert BugTest rows (Minimalist)
                if not is_new:
                    BugTest.query.filter_by(bug_id=bug.bug_id).delete()

                merged_tests: dict = {}
                for c in raw_comments:
                    text = c if isinstance(c, str) else c.get("text", "")
                    cm = _extract_comment_metadata(text)
                    test_name = cm.get("test_names")
                    if not test_name:
                        continue
                    _basename = test_name.replace("\\", "/").rsplit("/", 1)[-1]
                    short_name = re.split(r"(?<=\.py)\s+", _basename, maxsplit=1)[0].strip()[:100]
                    station   = (cm.get("test_rings") or "")[:100]
                    build     = (cm.get("builds") or self.release_version)[:50]
                    nodes_raw = cm.get("nodes")
                    nodes     = _parse_int(nodes_raw) if nodes_raw else None
                    config    = f"N{nodes}" if nodes else None

                    key = (short_name, station, build)
                    if key not in merged_tests:
                        merged_tests[key] = {
                            "test_name":    short_name,
                            "station_name": station,
                            "build_id":     build,
                            "configuration": config
                        }

                for fields in merged_tests.values():
                    db_session.add(BugTest(bug_id=bug.bug_id, **fields))

                # 6e. Upsert BugStation rows
                if not is_new:
                    BugStation.query.filter_by(bug_id=bug.bug_id).delete()
                for station_name in metadata["test_rings"]:
                    if station_name:
                        db_session.add(BugStation(
                            bug_id=bug.bug_id,
                            station_name=station_name[:100],
                        ))

                db_session.flush()

                # 6f. RAG filter + ChatHPE analysis
                ml_analysis = None
                if chathpe_session_id and embedding_model:
                    try:
                        filtered = _filter_comments_rag(raw_comments, embedding_model)
                        print(f"[RAG] Bug {bug_id_str}: {len(filtered)} comment(s) selected.", flush=True)

                        if filtered:
                            import chathpe_client as _cc
                            prompt = _build_prompt(bug_id_str, metadata, filtered)
                            response_text = _cc.call_chatlite(
                                chathpe_session_id,
                                prompt,
                                chathpe_creds["client_id"],
                                chathpe_creds["jwt_token"],
                                chathpe_creds["user_id"],
                                chathpe_creds["username"],
                            )
                            parsed = _parse_chathpe_response(response_text)

                            existing_ml = MLAnalysis.query.filter_by(bug_id=bug.bug_id).first()
                            if existing_ml is None:
                                existing_ml = MLAnalysis(bug_id=bug.bug_id)
                                db_session.add(existing_ml)
                            existing_ml.repro_actions   = parsed["repro_actions"]
                            existing_ml.config_changes  = parsed["config_changes"]
                            existing_ml.repro_readiness = parsed["repro_readiness"]
                            existing_ml.summary         = parsed["summary"]
                            existing_ml.generated_at    = datetime.utcnow()
                            ml_analysis = True
                            print(f"[ChatHPE] Bug {bug_id_str}: analysis stored.", flush=True)
                        else:
                            print(f"[ChatHPE] Bug {bug_id_str}: no suitable comments after RAG — skipping.", flush=True)
                    except Exception as exc:
                        print(f"[ChatHPE] Bug {bug_id_str}: analysis failed: {exc}", flush=True)
                        stats["errors"].append(f"Bug {bug_id_str} ChatHPE: {exc}")

                if is_new:
                    stats["ingested"] += 1
                else:
                    stats["updated"] += 1

            except Exception as exc:
                msg = f"Bug {bug_id_str}: {exc}"
                print(f"[Ingest] ERROR: {msg}", flush=True)
                stats["errors"].append(msg)
                db_session.rollback()
                continue

        # 7. Final commit
        try:
            db_session.commit()
        except Exception as exc:
            db_session.rollback()
            msg = f"Final commit failed: {exc}"
            print(f"[Ingest] ERROR: {msg}", flush=True)
            stats["errors"].append(msg)

        print(
            f"\n[Ingest] Done — ingested: {stats['ingested']}, updated: {stats['updated']}, "
            f"skipped: {stats['skipped']}, errors: {len(stats['errors'])}",
            flush=True,
        )
        return stats


# ---------------------------------------------------------------------------
# ML Analysis retry — runs on pending bugs using comments already in DB
# ---------------------------------------------------------------------------

def retry_pending_analysis(db_session, chathpe_creds):
    """
    Find all repro bugs whose MLAnalysis is missing or has null repro_actions
    (i.e. ChatHPE was unavailable during ingestion) and re-run the analysis
    using comments already stored in BugComment rows.

    Called by the background scheduler every 30 minutes.
    Returns the number of bugs successfully analysed.
    """
    from app.models.bug import Bug
    from app.models.bug_comments import BugComment
    from app.models.ml_analysis import MLAnalysis

    # Find bugs that still need analysis
    repro_bugs = Bug.query.filter_by(bug_type="repro").all()
    def _is_bad_repro_actions(ml):
        """Return True if the repro_actions field needs to be retried."""
        if ml is None:
            return True
        val = (ml.repro_actions or "").strip()
        if not val:
            return True
        # Strip the "Answer:" prefix the LLM sometimes prepends
        cleaned = re.sub(r"^Answer:\s*", "", val, flags=re.IGNORECASE).strip()
        return cleaned.lower() in (
            "see summary",
            "not found in provided context",
            "pending analysis...",
        )

    pending = [
        b for b in repro_bugs
        if _is_bad_repro_actions(MLAnalysis.query.filter_by(bug_id=b.bug_id).first())
    ]

    if not pending:
        print("[Retry] No bugs pending analysis.", flush=True)
        return 0

    print(f"[Retry] {len(pending)} bug(s) need analysis.", flush=True)

    # Load local MiniLM model
    _model_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "all-MiniLM-L6-v2",
    )
    try:
        model = SentenceTransformer(_model_path)
    except Exception as exc:
        print(f"[Retry] Could not load embedding model: {exc}", flush=True)
        return 0

    # Start a fresh ChatHPE session
    import chathpe_client as _cc
    try:
        session_id = _cc.get_session_id(
            chathpe_creds["client_id"], chathpe_creds["jwt_token"]
        )
        _cc.set_preferences(
            session_id,
            chathpe_creds["client_id"],
            chathpe_creds["jwt_token"],
            chathpe_creds["user_id"],
            chathpe_creds["username"],
        )
        print(f"[Retry] ChatHPE session ready: {session_id}", flush=True)
    except Exception as exc:
        print(f"[Retry] ChatHPE session failed: {exc} — will retry later.", flush=True)
        return 0

    analysed = 0
    for bug in pending:
        try:
            # Load stored comments from DB
            stored = BugComment.query.filter_by(bug_id=bug.bug_id).all()
            raw_comments = [{"text": c.text} for c in stored]
            if not raw_comments:
                print(f"[Retry] Bug {bug.bug_code}: no comments in DB — skipping.", flush=True)
                continue

            print(f"[Retry] Bug {bug.bug_code}: {len(raw_comments)} comment(s) from DB.", flush=True)

            # Extract metadata and RAG-filter
            metadata = _extract_all_test_metadata(raw_comments)
            filtered = _filter_comments_rag(raw_comments, model)
            if not filtered:
                print(f"[Retry] Bug {bug.bug_code}: no suitable comments after RAG.", flush=True)
                continue

            print(f"[Retry] Bug {bug.bug_code}: {len(filtered)} RAG chunk(s).", flush=True)

            prompt = _build_prompt(bug.bug_code, metadata, filtered)
            response_text = _cc.call_chatlite(
                session_id, prompt,
                chathpe_creds["client_id"], chathpe_creds["jwt_token"],
                chathpe_creds["user_id"], chathpe_creds["username"],
            )
            parsed = _parse_chathpe_response(response_text)

            ml = MLAnalysis.query.filter_by(bug_id=bug.bug_id).first()
            if ml is None:
                ml = MLAnalysis(bug_id=bug.bug_id)
                db_session.add(ml)
            ml.repro_actions   = parsed["repro_actions"]
            ml.config_changes  = parsed["config_changes"]
            ml.repro_readiness = parsed["repro_readiness"]
            ml.summary         = parsed["summary"]
            ml.generated_at    = datetime.utcnow()
            db_session.commit()
            analysed += 1
            print(f"[Retry] Bug {bug.bug_code}: analysis stored.", flush=True)

        except Exception as exc:
            print(f"[Retry] Bug {bug.bug_code}: failed — {exc}", flush=True)
            db_session.rollback()

    print(f"[Retry] Done — {analysed}/{len(pending)} bugs analysed.", flush=True)
    return analysed

