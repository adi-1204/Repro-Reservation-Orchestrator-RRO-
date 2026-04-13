"""
app/routes/run.py
-----------------
Handles the Run page (GET) and run submission endpoints (POST).
"""

from flask import Blueprint, jsonify, redirect, render_template, request, url_for

from app.auth_utils import (
    get_current_auth_token,
    get_current_role,
    get_current_user_id,
)
from app.extensions import db
from app.models.bug import Bug
from app.models.run_parameters import RunParameter

run_bp = Blueprint("run", __name__)


def _serialize_run_entry(run):
    bug = run.bug
    return {
        "id": run.id,
        "bug_code": bug.bug_code if bug else None,
        "bug_name": bug.bug_name if bug else None,
        "test_name": run.test_name,
        "run_mode": run.run_mode,
        "run_type": run.run_type,
        "workflow": run.workflow,
        "run_count": run.run_count,
        "provision_setup": run.provision_setup,
        "do_checkout_update": bool(run.do_checkout_update),
        "status": run.status,
        "submitted_at": run.submitted_at.isoformat() if run.submitted_at else None,
    }


# ── Page route ────────────────────────────────────────────────────────────────

@run_bp.route("/run", methods=["GET"])
def run_page():
    """Serve the Run page. Engineers only."""
    if not get_current_user_id():
        return redirect(url_for("auth.login"))
    if get_current_role() != "Engineer":
        return redirect(url_for("auth.login"))
    return render_template("run.html", auth_token=get_current_auth_token())


# ── Submit endpoint ─────────────────────────────────────────────────────────────

@run_bp.route("/api/run/submit", methods=["POST"])
@run_bp.route("/api/runs", methods=["POST"])
def submit_run():
    """
    Accepts run payload, validates it, resolves bug_code to Bug PK,
    stores a Run_Parameters row, and returns run id.
    """
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({"success": False, "error": "Not logged in"}), 401

    data = request.get_json(silent=True) or {}

    required_fields = ["bug_id", "run_type", "run_mode"]
    missing = [field for field in required_fields if data.get(field) in (None, "")]
    if missing:
        return jsonify({
            "success": False,
            "error": f"Missing required fields: {', '.join(missing)}"
        }), 400

    run_type = str(data.get("run_type", "")).strip()
    run_mode = str(data.get("run_mode", "")).strip()
    if run_type not in {"quick", "comprehensive"}:
        return jsonify({"success": False, "error": "Invalid run_type"}), 400
    if run_mode not in {"run_tests", "config_and_execute"}:
        return jsonify({"success": False, "error": "Invalid run_mode"}), 400

    bug_code = str(data.get("bug_id", "")).strip()
    bug = Bug.query.filter_by(bug_code=bug_code).first()
    if not bug:
        return jsonify({"success": False, "error": "Bug not found"}), 404

    run_count = data.get("run_count")
    if run_count in (None, ""):
        run_count = None
    else:
        try:
            run_count = int(run_count)
        except (TypeError, ValueError):
            return jsonify({"success": False, "error": "run_count must be an integer"}), 400

    provision_setup = data.get("provision_setup")
    if isinstance(provision_setup, list):
        provision_setup = ",".join(str(x).strip() for x in provision_setup if str(x).strip())

    do_checkout_update = bool(data.get("do_checkout_update", False))

    test_name_value = data.get("test_name")
    if isinstance(test_name_value, list):
        test_name_value = ", ".join(str(x).strip() for x in test_name_value if str(x).strip())

    run_parameter = RunParameter(
        bug_id=bug.id,
        run_mode=run_mode,
        test_name=(test_name_value or None),
        run_type=run_type,
        workflow=(data.get("workflow") or None),
        run_count=run_count,
        provision_setup=provision_setup,
        do_checkout_update=do_checkout_update,
        submitted_by=current_user_id,
    )

    try:
        db.session.add(run_parameter)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"success": False, "error": "Failed to create run"}), 500

    return jsonify({"success": True, "run_id": run_parameter.id}), 201


@run_bp.route("/api/runs", methods=["GET"])
def get_runs():
    """Return run history for the currently logged-in engineer."""
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({"error": "Not logged in"}), 401

    if get_current_role() != "Engineer":
        return jsonify({"error": "Unauthorized"}), 403

    runs = (
        RunParameter.query
        .filter(RunParameter.submitted_by == current_user_id)
        .order_by(RunParameter.submitted_at.desc(), RunParameter.id.desc())
        .all()
    )

    return jsonify({
        "runs": [_serialize_run_entry(run) for run in runs]
    })
