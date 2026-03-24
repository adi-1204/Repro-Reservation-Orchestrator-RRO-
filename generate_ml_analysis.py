"""
Generate ML analysis for bugs using the real ChatHPE API.

Credentials are loaded from the Flask app config (sourced from .env).
No bug data is written outside the local database.

Usage:
    python generate_ml_analysis.py
    python generate_ml_analysis.py --force
"""

import argparse
import re
import sys
from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError

from app import create_app, db
from app.models.bug import Bug
from app.models.bug_comments import BugComment
from app.models.bug_tests import BugTest
from app.models.ml_analysis import MLAnalysis

import chathpe_client


def build_prompt(bug, comments, test_name):
    lines = [
        f"Bug {bug.bug_code} Analysis Request",
        "",
        "You are analyzing a software bug report. Based on the following bug details and engineer comments, provide a structured analysis.",
        "",
        f"Bug ID: {bug.bug_code}",
        f"Priority: {bug.priority}",
        f"Component: {bug.summary or ''}",
        f"Test Name: {test_name}",
        "",
        "Engineer Comments:",
        "---",
    ]

    if comments:
        for idx, comment in enumerate(comments, start=1):
            creator = comment.creator or "Unknown"
            created = comment.creation_time.isoformat() if comment.creation_time else "Unknown"
            text = (comment.text or "").strip()
            lines.extend(
                [
                    f"Comment {idx} (by {creator} on {created}):",
                    text,
                    "",
                ]
            )
    else:
        lines.extend(["No engineer comments found.", ""])

    lines.extend(
        [
            "---",
            "",
            "Please provide:",
            "1. Repro Actions: Step-by-step actions needed to reproduce this bug",
            "2. Config Changes: Any configuration changes required before reproduction",
            "3. Repro Readiness: Is this bug ready to reproduce? (one of: \"Ready\", \"Needs more runs\", \"Not ready\", \"Already fixed\")",
            "4. Summary: A concise 2-3 sentence summary of the bug, root cause, and current status",
            "",
            "Format your response exactly as:",
            "REPRO_ACTIONS: <content>",
            "CONFIG_CHANGES: <content>",
            "REPRO_READINESS: <content>",
            "SUMMARY: <content>",
        ]
    )

    return "\n".join(lines)


def extract_repro_readiness(comments):
    if not comments:
        return "Needs more runs"
    text = (comments[0].text or "").strip()
    match = re.search(r"Developer\s+Progress:\s*(\S+)", text)
    if match:
        return match.group(1).strip()
    return "Needs more runs"


def parse_analysis_fields(message_text):
    """
    Parse structured ChatHPE response into analysis fields.

    Expects the model to respond in the format requested by the prompt:
        REPRO_ACTIONS: <content>
        CONFIG_CHANGES: <content>
        REPRO_READINESS: <content>
        SUMMARY: <content>

    Falls back gracefully if the model does not follow the exact format.
    """
    text = (message_text or "").strip()
    parsed = {
        "repro_actions":   None,
        "config_changes":  None,
        "repro_readiness": None,
        "summary":         None,
    }

    # Primary pattern: structured labels as requested in the prompt
    field_patterns = {
        "repro_actions":   r"REPRO_ACTIONS:\s*(.*?)(?=\nREPRO_ACTIONS:|\nCONFIG_CHANGES:|\nREPRO_READINESS:|\nSUMMARY:|$)",
        "config_changes":  r"CONFIG_CHANGES:\s*(.*?)(?=\nREPRO_ACTIONS:|\nCONFIG_CHANGES:|\nREPRO_READINESS:|\nSUMMARY:|$)",
        "repro_readiness": r"REPRO_READINESS:\s*(.*?)(?=\nREPRO_ACTIONS:|\nCONFIG_CHANGES:|\nREPRO_READINESS:|\nSUMMARY:|$)",
        "summary":         r"SUMMARY:\s*(.*?)(?=\nREPRO_ACTIONS:|\nCONFIG_CHANGES:|\nREPRO_READINESS:|\nSUMMARY:|$)",
    }

    matched_any = False
    for field, pattern in field_patterns.items():
        match = re.search(pattern, text, flags=re.DOTALL)
        if match:
            parsed[field] = match.group(1).strip()
            matched_any = True

    if not matched_any:
        # Model didn't follow the structured format — use full response as summary
        parsed["repro_actions"]   = "See summary"
        parsed["config_changes"]  = "See summary"
        parsed["repro_readiness"] = "Needs more runs"
        parsed["summary"]         = text
    else:
        defaults = {
            "repro_actions":   "See summary",
            "config_changes":  "See summary",
            "repro_readiness": "Needs more runs",
            "summary":         "See summary",
        }
        for field, default in defaults.items():
            if not parsed[field]:
                parsed[field] = default

    return parsed


def generate(force=False, flask_app=None):
    """
    Generate ML analysis for all bugs using the real ChatHPE API.

    Args:
        force: Regenerate analysis even when a summary already exists.
        flask_app: Optional existing Flask app instance. When called from a
                   background thread that already owns an app context, pass the
                   app here to avoid creating a second instance.
    """
    analyzed = 0
    skipped = 0
    errors = 0
    pending_commits = 0

    app = flask_app if flask_app is not None else create_app()

    with app.app_context():
        # --- Initialise ChatHPE session ---
        try:
            creds = chathpe_client.load_creds_from_config(app.config)
        except ValueError as exc:
            print(f"ChatHPE credential error: {exc}")
            sys.exit(1)

        try:
            session_id = chathpe_client.get_session_id(creds["client_id"], creds["jwt_token"])
            chathpe_client.set_preferences(
                session_id,
                creds["client_id"],
                creds["jwt_token"],
                creds["user_id"],
                creds["username"],
            )
        except Exception as exc:
            print(f"Failed to initialise ChatHPE session: {exc}")
            sys.exit(1)

        try:
            bugs = Bug.query.order_by(Bug.id.asc()).all()

            for bug in bugs:
                existing = MLAnalysis.query.filter_by(bug_id=bug.id).first()
                has_summary = existing and existing.summary is not None

                if not force and has_summary:
                    print(f"[{bug.bug_code}] Skipping - already analysed (use --force to regenerate)")
                    skipped += 1
                    continue

                comments = (
                    BugComment.query
                    .filter_by(bug_id=bug.id)
                    .order_by(BugComment.comment_bugzilla_id.asc(), BugComment.id.asc())
                    .all()
                )

                first_test = BugTest.query.filter_by(bug_id=bug.id).first()
                test_name = (first_test.test_name or "N/A") if first_test else "N/A"

                prompt = build_prompt(bug, comments, test_name)

                try:
                    message = chathpe_client.call_chatlite(
                        session_id,
                        prompt,
                        creds["client_id"],
                        creds["jwt_token"],
                        creds["user_id"],
                        creds["username"],
                    )
                    parsed = parse_analysis_fields(message)
                except Exception as exc:
                    print(f"[{bug.bug_code}] Error - ChatHPE call failed: {exc}")
                    errors += 1
                    continue

                if existing is None:
                    existing = MLAnalysis(bug_id=bug.id)
                    db.session.add(existing)

                existing.repro_actions   = parsed["repro_actions"]
                existing.config_changes  = parsed["config_changes"]
                existing.repro_readiness = (
                    parsed["repro_readiness"] or extract_repro_readiness(comments)
                )
                existing.summary       = parsed["summary"]
                existing.generated_at  = datetime.utcnow()

                analyzed += 1
                pending_commits += 1
                print(f"[{bug.bug_code}] ChatHPE analysis generated.")

                if pending_commits >= 5:
                    db.session.commit()
                    pending_commits = 0

            if pending_commits > 0:
                db.session.commit()

            print("\nChatHPE analysis generation complete.")
            print(f"  Analysed: {analyzed}")
            print(f"  Skipped:  {skipped}")
            print(f"  Errors:   {errors}")

        except SQLAlchemyError as exc:
            db.session.rollback()
            print(f"Database error while generating analysis: {exc}")
            sys.exit(1)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate bug analysis using the real ChatHPE API."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate analysis even if a summary already exists.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    generate(force=args.force)
