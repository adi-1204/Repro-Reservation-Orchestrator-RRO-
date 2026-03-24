from flask import Blueprint, jsonify, render_template, request, redirect, url_for, current_app
from app.extensions import db
from app.models.user import User
from app.models.workgroup import Workgroup
from app.models.workgroupAssignment import WorkgroupAssignment
from app.models.bug import Bug
from app.models.bug_tests import BugTest
from app.models.bug_stations import BugStation
from app.models.bug_comments import BugComment
from app.models.ml_analysis import MLAnalysis
from sqlalchemy.exc import IntegrityError
from app.auth_utils import (
    get_current_auth_token,
    get_current_role,
    get_current_user_id,
    login_required,
    manager_required,
)
from datetime import datetime
import threading
import logging

log = logging.getLogger(__name__)

manager = Blueprint("manager", __name__)

# ---------------------------------------------------------------------------
# In-memory ingestion status store: workgroup_id -> status dict
# Keys: status ("idle"|"running"|"done"|"error"), ingested, updated, errors
# ---------------------------------------------------------------------------
_ingest_jobs: dict = {}
_ingest_jobs_lock = threading.Lock()


def _run_ingestion_thread(app, workgroup_id, release_version):
    """
    Background thread: fetch real Bugzilla bugs for the workgroup's build
    version, upsert them into the database, then run ChatHPE analysis on
    any newly ingested bugs.

    All credentials come from the Flask app config (sourced from .env).
    No company data is written outside the local database.
    """
    print(f"[Ingestion] Starting for workgroup {workgroup_id}, build {release_version}", flush=True)
    with _ingest_jobs_lock:
        _ingest_jobs[workgroup_id] = {"status": "running", "ingested": 0, "updated": 0, "errors": []}

    try:
        with app.app_context():
            from bugzilla_ingest import BugzillaIngester
            import chathpe_client

            # Build email → User.id map so Bugzilla assignee emails are linked
            # to the correct engineer records in the DB.
            engineers = User.query.filter_by(role="Engineer").all()
            email_map = {e.email.lower(): e.id for e in engineers}
            print(f"[Ingestion] Found {len(engineers)} engineers in DB.", flush=True)

            # Load ChatHPE creds from config (sourced from .env)
            chathpe_creds = None
            try:
                chathpe_creds = chathpe_client.load_creds_from_config(app.config)
            except ValueError as exc:
                print(f"[Ingestion] ChatHPE creds missing/invalid ({exc}) — analysis will be skipped.", flush=True)

            ingester = BugzillaIngester(
                release_version=release_version,
                bugz_user=app.config.get("BUGZ_USER"),
                bugz_password=app.config.get("BUGZ_PASSWORD"),
            )
            result = ingester.ingest(db.session, email_map, chathpe_creds=chathpe_creds)
            print(f"[Ingestion] Bugzilla result: {result}", flush=True)

            with _ingest_jobs_lock:
                _ingest_jobs[workgroup_id] = {
                    "status": "done",
                    "ingested": result.get("ingested", 0),
                    "updated":  result.get("updated", 0),
                    "errors":   result.get("errors", []),
                }
            print(f"[Ingestion] Done for workgroup {workgroup_id}.", flush=True)

    except Exception as exc:
        print(f"[Ingestion] ERROR for workgroup {workgroup_id}: {exc}", flush=True)
        log.error("Ingestion thread error for workgroup %d: %s", workgroup_id, exc)
        with _ingest_jobs_lock:
            _ingest_jobs[workgroup_id] = {
                "status":  "error",
                "ingested": 0,
                "updated":  0,
                "errors":  [str(exc)],
            }


def _trigger_ingestion(workgroup_id, release_version):
    """Launch the ingestion background thread for the given workgroup."""
    app = current_app._get_current_object()
    t = threading.Thread(
        target=_run_ingestion_thread,
        args=(app, workgroup_id, release_version),
        daemon=True,
    )
    t.start()


@manager.route("/manager", methods=["GET"])
@login_required
def manager_dashboard():
    #  FIX 5: Also verify the role at the page level so an engineer
    # cannot navigate directly to /manager by typing the URL.
    if get_current_role() != "Manager":
        return redirect(url_for("auth.login"))
    return render_template("managerDashboard.html", auth_token=get_current_auth_token())


@manager.route("/api/stats", methods=["GET"])
@manager_required          #  Engineer cannot call this anymore
def get_stats():
    manager_id = get_current_user_id()

    total = Workgroup.query.filter_by(manager_id=manager_id).count()
    active = Workgroup.query.filter_by(manager_id=manager_id, status="Active").count()
    completed = Workgroup.query.filter_by(manager_id=manager_id, status="Completed").count()
    engineers = User.query.filter_by(role="Engineer").count()

    return jsonify({
        "total": total,
        "active": active,
        "completed": completed,
        "engineers": engineers
    })


@manager.route("/api/workgroups", methods=["GET"])
@manager_required
def get_workgroups():
    manager_id = get_current_user_id()
    print(f"Fetching workgroups for manager_id: {manager_id}")  # Debug log
    workgroups = Workgroup.query.filter_by(manager_id=manager_id).all()
    print(f"Found {len(workgroups)} workgroups")  # Debug log

    result = []
    for wg in workgroups:
        assignments = WorkgroupAssignment.query.filter_by(workgroup_id=wg.id).all()
        engineers = []
        for a in assignments:
            eng = User.query.get(a.employee_id)
            if eng:
                engineers.append({"id": eng.id, "name": f"{eng.first_name} {eng.last_name}"})

        result.append({
            "id": wg.id,
            "name": wg.name,
            "release_version": wg.release_version,
            "is_completed": wg.is_completed,
            "created_at": wg.created_at.isoformat() if wg.created_at else None,
            "engineers": engineers
        })

    return jsonify(result)


@manager.route("/api/workgroups", methods=["POST"])
@manager_required
def create_workgroup():
    data = request.get_json(silent=True) or {}
    print(f"Creating workgroup: {data}")  # Debug log

    name = (data.get("name") or "").strip()
    release_version = (data.get("release_version") or "").strip()

    if not name:
        return jsonify({"error": "Workgroup name is required."}), 400
    if not release_version:
        return jsonify({"error": "Release version is required."}), 400

    # Friendly pre-check; DB unique constraint remains the final race-safe guard.
    existing = Workgroup.query.filter_by(name=name).first()
    if existing:
        return jsonify({"error": "Workgroup name already exists. Please choose a unique name."}), 409

    try:
        wg = Workgroup(
            name=name,
            release_version=release_version,
            manager_id=get_current_user_id(),
            status="Completed" if data.get("is_completed", False) else "Active"
        )

        db.session.add(wg)
        db.session.flush()  # Get the ID before committing
        print(f"Workgroup created with ID: {wg.id}")  # Debug log

        engineer_ids = data.get("engineer_ids", [])
        print(f"Engineer IDs to assign: {engineer_ids}")  # Debug log
        
        for eid in engineer_ids:
            assignment = WorkgroupAssignment(workgroup_id=wg.id, employee_id=eid)
            db.session.add(assignment)
            print(f"Added assignment: workgroup={wg.id}, engineer={eid}")  # Debug log

        db.session.commit()
        print("Committed to database")  # Debug log
        
        # Verify assignments were saved
        saved_assignments = WorkgroupAssignment.query.filter_by(workgroup_id=wg.id).all()
        print(f"Verified {len(saved_assignments)} assignments saved")  # Debug log

        # Fetch engineers for response
        assignments = WorkgroupAssignment.query.filter_by(workgroup_id=wg.id).all()
        engineers = []
        for a in assignments:
            eng = User.query.get(a.employee_id)
            if eng:
                engineers.append({"id": eng.id, "name": f"{eng.first_name} {eng.last_name}"})

        # Trigger background ingestion of real Bugzilla bugs + ChatHPE analysis
        _trigger_ingestion(wg.id, release_version)

        return jsonify({
            "id": wg.id,
            "name": wg.name,
            "release_version": wg.release_version,
            "is_completed": wg.is_completed,
            "created_at": wg.created_at.isoformat() if wg.created_at else None,
            "engineers": engineers,
            "ingestion_started": True,
        })
    except IntegrityError as e:
        db.session.rollback()
        print(f"Integrity error creating workgroup: {str(e)}")  # Debug log
        return jsonify({"error": "Workgroup name already exists. Please choose a unique name."}), 409
    except Exception as e:
        db.session.rollback()
        print(f"Error creating workgroup: {str(e)}")  # Debug log
        return jsonify({"error": str(e)}), 500


@manager.route("/api/workgroups/<int:id>", methods=["PATCH"])
@manager_required          #  Engineer cannot edit workgroups
def update_workgroup(id):
    data = request.get_json(silent=True) or {}
    wg = Workgroup.query.get_or_404(id)

    proposed_name = None
    if "name" in data:
        proposed_name = (data["name"] or "").strip()
        if not proposed_name:
            return jsonify({"error": "Workgroup name is required."}), 400

        existing = Workgroup.query.filter(
            Workgroup.name == proposed_name,
            Workgroup.id != id
        ).first()
        if existing:
            return jsonify({"error": "Workgroup name already exists. Please choose a unique name."}), 409

    if proposed_name is not None:
        wg.name = proposed_name

    version_changed = False
    if "release_version" in data:
        release_version = (data["release_version"] or "").strip()
        if not release_version:
            return jsonify({"error": "Release version is required."}), 400
        if wg.release_version != release_version:
            version_changed = True
        wg.release_version = release_version
    if "is_completed" in data:
        wg.status = "Completed" if data["is_completed"] else "Active"

    engineers_changed = False
    if "engineer_ids" in data:
        new_ids = set(data["engineer_ids"])
        existing = WorkgroupAssignment.query.filter_by(workgroup_id=id).all()
        existing_ids = {a.employee_id for a in existing}

        remove_ids = existing_ids - new_ids
        add_ids = new_ids - existing_ids

        if remove_ids or add_ids:
            engineers_changed = True

        if remove_ids:
            WorkgroupAssignment.query.filter(
                WorkgroupAssignment.workgroup_id == id,
                WorkgroupAssignment.employee_id.in_(remove_ids)
            ).delete(synchronize_session=False)

        for eid in add_ids:
            db.session.add(WorkgroupAssignment(workgroup_id=id, employee_id=eid))

    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        print(f"Integrity error updating workgroup: {str(e)}")  # Debug log
        return jsonify({"error": "Workgroup name already exists. Please choose a unique name."}), 409

    # Re-trigger ingestion if build version or engineer roster changed
    if version_changed or engineers_changed:
        _trigger_ingestion(wg.id, wg.release_version)

    assignments = WorkgroupAssignment.query.filter_by(workgroup_id=id).all()
    engineers = []
    for a in assignments:
        eng = User.query.get(a.employee_id)
        engineers.append({"id": eng.id, "name": f"{eng.first_name} {eng.last_name}"})

    return jsonify({
        "id": wg.id,
        "name": wg.name,
        "release_version": wg.release_version,
        "is_completed": wg.is_completed,
        "created_at": wg.created_at,
        "engineers": engineers
    })


@manager.route("/api/workgroups/<int:id>", methods=["DELETE"])
@manager_required          #  Engineer cannot delete workgroups
def delete_workgroup(id):
    wg = Workgroup.query.get_or_404(id)

    # Find all bugs linked to this workgroup's build version.
    # resource_group is always set to the workgroup's release_version during
    # ingestion, so this filter reliably finds every bug for this workgroup.
    bugs = Bug.query.filter_by(resource_group=wg.release_version).all()
    bug_ids = [b.id for b in bugs]

    if bug_ids:
        MLAnalysis.query.filter(MLAnalysis.bug_id.in_(bug_ids)).delete(synchronize_session=False)
        BugComment.query.filter(BugComment.bug_id.in_(bug_ids)).delete(synchronize_session=False)
        BugTest.query.filter(BugTest.bug_id.in_(bug_ids)).delete(synchronize_session=False)
        BugStation.query.filter(BugStation.bug_id.in_(bug_ids)).delete(synchronize_session=False)
        Bug.query.filter(Bug.id.in_(bug_ids)).delete(synchronize_session=False)

    WorkgroupAssignment.query.filter_by(workgroup_id=id).delete()
    db.session.delete(wg)
    db.session.commit()
    return jsonify({"message": "Workgroup deleted"})


@manager.route("/api/engineers", methods=["GET"])
@manager_required
def get_engineers():
    engineers = User.query.filter_by(role="Engineer").all()
    return jsonify([
        {"id": e.id, "name": f"{e.first_name} {e.last_name}", "email": e.email}
        for e in engineers
    ])


@manager.route("/api/workgroups/<int:id>/ingest_status", methods=["GET"])
@manager_required
def ingest_status(id):
    """
    Poll the background ingestion status for a workgroup.

    Response JSON:
        { "status": "idle"|"running"|"done"|"error",
          "ingested": <int>,
          "updated":  <int>,
          "errors":   [<str>, ...] }
    """
    with _ingest_jobs_lock:
        job = _ingest_jobs.get(id)

    if job is None:
        return jsonify({"status": "idle", "ingested": 0, "updated": 0, "errors": []})

    return jsonify({
        "status":   job.get("status", "idle"),
        "ingested": job.get("ingested", 0),
        "updated":  job.get("updated", 0),
        "errors":   job.get("errors", []),
    })
