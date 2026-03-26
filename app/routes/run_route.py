"""
app/routes/run.py
-----------------
Handles the Run page (GET) and the mock run submission endpoint (POST).
"""

import random
import string
import uuid
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, redirect, render_template, request, url_for

from app.auth_utils import (
    get_current_auth_token,
    get_current_role,
    get_current_user_id,
)

run_bp = Blueprint("run", __name__)


# ── Page route ────────────────────────────────────────────────────────────────

@run_bp.route("/run", methods=["GET"])
def run_page():
    """Serve the Run page. Engineers only."""
    if not get_current_user_id():
        return redirect(url_for("auth.login"))
    if get_current_role() != "Engineer":
        return redirect(url_for("auth.login"))
    return render_template("run.html", auth_token=get_current_auth_token())


# ── Mock submit endpoint ───────────────────────────────────────────────────────

@run_bp.route("/api/run/submit", methods=["POST"])
def submit_run():
    """
    Accepts the run payload from the frontend and returns a realistic-looking
    mock result. Nothing is actually executed — this is for UI testing only.

    Expected JSON body (all fields optional except bugToRepro):
    {
        "runMode":       "run_tests" | "config_and_execute",
        "bugToRepro":    { "bug_code": "...", "bug_name": "..." },
        "selectedTests": ["TestA", "TestB"],
        "runOptionsMode":"quick" | "comprehensive",
        "workflow":      "smoke",
        "runCount":      3,
        "provisionSetup": ["setup1 ★"],   // comprehensive only
        "doCheckout":    true              // comprehensive only
    }
    """
    if not get_current_user_id():
        return jsonify({"error": "Not logged in"}), 401

    data = request.get_json(silent=True) or {}

    bug       = data.get("bugToRepro") or {}
    tests     = data.get("selectedTests") or []
    run_count = int(data.get("runCount") or 1)
    workflow  = data.get("workflow") or ""
    mode      = data.get("runOptionsMode") or "quick"
    run_mode  = data.get("runMode") or "run_tests"

    # ── Generate a fake job ID ──
    job_id = "JOB-" + uuid.uuid4().hex[:8].upper()

    # ── Simulate per-test results ──
    # Each test gets a random passed/failed/skipped status and a fake duration.
    def _rand_duration():
        secs = random.uniform(0.4, 8.5)
        return f"{secs:.2f}s"

    def _rand_status():
        # 70% pass, 20% fail, 10% skipped — realistic for a repro run
        r = random.random()
        if r < 0.70:
            return "passed"
        elif r < 0.90:
            return "failed"
        return "skipped"

    test_results = []
    for name in (tests if tests else ["DefaultTest"]):
        for run_num in range(1, run_count + 1):
            label = name if run_count == 1 else f"{name} (run {run_num})"
            test_results.append({
                "name":     label,
                "status":   _rand_status(),
                "duration": _rand_duration(),
            })

    # ── Overall job status ──
    if any(t["status"] == "failed" for t in test_results):
        overall_status = "failed"
    else:
        overall_status = "completed"

    # ── Fake total duration ──
    total_secs = sum(float(t["duration"][:-1]) for t in test_results)
    total_duration = f"{total_secs:.2f}s"

    # ── Fake run log ──
    now = datetime.utcnow()

    def _ts(offset_secs):
        return (now + timedelta(seconds=offset_secs)).strftime("%H:%M:%S")

    logs = [
        {"time": _ts(0),  "message": f"[{job_id}] Job queued"},
        {"time": _ts(1),  "message": f"Loading bug {bug.get('bug_code', '???')}"},
    ]

    if data.get("doCheckout"):
        logs.append({"time": _ts(2), "message": "Checking out latest code..."})
        logs.append({"time": _ts(3), "message": "Checkout complete."})

    if data.get("provisionSetup"):
        for item in data["provisionSetup"]:
            logs.append({"time": _ts(4), "message": f"Provision: {item}"})

    if workflow:
        logs.append({"time": _ts(5), "message": f"Workflow: {workflow}"})

    logs.append({"time": _ts(6), "message": f"Scheduling {len(tests)} test(s) × {run_count} run(s)"})

    offset = 7
    for t in test_results:
        logs.append({"time": _ts(offset),     "message": f"  START  {t['name']}"})
        logs.append({"time": _ts(offset + 1), "message": f"  {t['status'].upper():8s} {t['name']} ({t['duration']})"})
        offset += 2

    logs.append({"time": _ts(offset), "message": f"Job finished — status: {overall_status.upper()}"})

    return jsonify({
        "job_id":         job_id,
        "status":         overall_status,
        "bug_code":       bug.get("bug_code", "—"),
        "run_mode":       run_mode.replace("_", " ").title(),
        "options_mode":   mode.replace("_", " ").title(),
        "run_count":      run_count,
        "workflow":       workflow,
        "total_duration": total_duration,
        "tests":          test_results,
        "logs":           logs,
    })
