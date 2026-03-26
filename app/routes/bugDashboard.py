from flask import Blueprint, render_template, jsonify, request, redirect, url_for
from app.extensions import db
from app.models.bug import Bug
from app.models.bug_comments import BugComment
from app.models.ml_analysis import MLAnalysis
from app.models.bug_tests import BugTest
from app.models.bug_stations import BugStation
from app.models.user import User
from app.models.workgroup import Workgroup
from app.models.workgroupAssignment import WorkgroupAssignment
from app.auth_utils import get_current_auth_token, get_current_role, get_current_user, get_current_user_id
from sqlalchemy import select

bug = Blueprint("bugDashboard", __name__)


# --------------------------------------------------
# BUG MANAGEMENT PAGE
# --------------------------------------------------
@bug.route("/bug_management")
def bug_management():
    current_user_id = get_current_user_id()
    current_role = get_current_role()

    if not current_user_id:
        return redirect(url_for("auth.login"))

    workgroup_id = request.args.get('workgroup_id', type=int)

    # Engineers must use the engineer-specific bug management page,
    # which includes reserve controls and engineer-only behaviors.
    if current_role == "Engineer":
        if workgroup_id:
            return redirect(url_for("engineer.engineer_bug_management", workgroup_id=workgroup_id))
        return redirect(url_for("engineer.engineer_bug_management"))

    workgroup = None
    
    if workgroup_id:
        workgroup = Workgroup.query.get(workgroup_id)
        if not workgroup:
            return redirect(url_for("manager.manager_dashboard"))
        
        # Authorization: Only the manager who owns this workgroup can view it
        if current_role == 'Manager' and workgroup.manager_id != current_user_id:
            return redirect(url_for("manager.manager_dashboard"))

    return render_template("bugManagement.html", workgroup=workgroup, auth_token=get_current_auth_token())

# --------------------------------------------------
# GET ALL BUGS
# --------------------------------------------------
@bug.route("/api/bugs", methods=["GET"])
def get_bugs():

    user_id = get_current_user_id()
    role = get_current_role()

    if not user_id:
        return jsonify({"error": "Not logged in"}), 401

    workgroup_id = request.args.get('workgroup_id', type=int)
    my_only = request.args.get('my_only', 'false').lower() == 'true'

    # Authorization check for workgroup access
    if workgroup_id:
        workgroup = Workgroup.query.get(workgroup_id)
        if not workgroup:
            return jsonify({"error": "Workgroup not found"}), 404
        
        # Only the manager who owns this workgroup can view its bugs
        if role == 'Manager' and workgroup.manager_id != user_id:
            return jsonify({"error": "Unauthorized"}), 403

    query = Bug.query

    if workgroup_id:
        query = query.filter(Bug.workgroup_id == workgroup_id)

        # Engineers can narrow the workgroup view to only their assigned bugs.
        if role == "Engineer" and my_only:
            query = query.filter(Bug.engineer_id == user_id)

    elif role == "Manager":
        # Only include bugs whose engineer belongs to a workgroup managed by this manager.
        # Unassigned bugs (engineer_id IS NULL) are excluded — they have no engineer link.
        engineer_ids = select(WorkgroupAssignment.employee_id).join(
            Workgroup,
            Workgroup.id == WorkgroupAssignment.workgroup_id
        ).where(
            Workgroup.manager_id == user_id
        )
        query = query.filter(Bug.engineer_id.in_(engineer_ids))

    elif role == "Engineer":
        # Engineers only see their own bugs
        query = query.filter(Bug.engineer_id == user_id)

    bugs = query.all()

    repro = []
    test = []

    for b in bugs:

        data = {
            "db_id": b.id,
            "id": b.bug_code,
            "bug_name": b.bug_name,
            "engineer_name": (
                f"{b.engineer.first_name} {b.engineer.last_name or ''}".strip()
                if b.engineer else "Unassigned"
            ),
            "priority": b.priority,
            "engineer": {
                "name": b.engineer.full_name if b.engineer else "Unassigned",
                "initials": (
                    (b.engineer.first_name[0] + b.engineer.last_name[0]).upper()
                    if b.engineer else "--"
                ),
                "color": "#7c3aed"
            },
            "summary": b.summary or "",
            "tests": [t.test_name for t in b.tests],
            "stations": [s.station_name for s in b.stations],
            "config": b.station_config,
            "resourceGroup": b.resource_group
        }

        if b.bug_type == "repro":
            repro.append(data)
        else:
            test.append(data)

    return jsonify({
        "repro": repro,
        "test": test
    })

# --------------------------------------------------
# BUG STATISTICS
# --------------------------------------------------
@bug.route("/api/bugs/stats", methods=["GET"])
def bug_stats():

    user_id = get_current_user_id()
    role = get_current_role()

    if not user_id:
        return jsonify({"error": "Not logged in"}), 401

    workgroup_id = request.args.get('workgroup_id', type=int)
    my_only = request.args.get('my_only', 'false').lower() == 'true'

    # Authorization check for workgroup access
    if workgroup_id:
        workgroup = Workgroup.query.get(workgroup_id)
        if not workgroup:
            return jsonify({"error": "Workgroup not found"}), 404
        
        # Only the manager who owns this workgroup can view its stats
        if role == 'Manager' and workgroup.manager_id != user_id:
            return jsonify({"error": "Unauthorized"}), 403

    if workgroup_id:
        query = Bug.query.filter(Bug.workgroup_id == workgroup_id)
        if role == "Engineer" and my_only:
            query = query.filter(Bug.engineer_id == user_id)

        total = query.count()
        repro = query.filter(Bug.bug_type == "repro").count()
        test = query.filter(Bug.bug_type == "test").count()
        pending = query.filter(Bug.status == "pending").count()
        running = query.filter(Bug.status == "running").count()
        completed = query.filter(Bug.status == "completed").count()

        return jsonify({
            "totalBugs": total,
            "reproBugs": repro,
            "testBugs": test,
            "pendingActions": pending,
            "runningBugs": running,
            "completedBugs": completed,
        })

    query = Bug.query
    if role == "Manager":
        engineer_ids_subq = (
            db.session.query(db.func.distinct(WorkgroupAssignment.employee_id))
            .join(Workgroup, WorkgroupAssignment.workgroup_id == Workgroup.id)
            .filter(Workgroup.manager_id == user_id)
            .subquery()
        )
        query = query.filter(Bug.engineer_id.in_(engineer_ids_subq))
    elif role == "Engineer":
        query = query.filter(Bug.engineer_id == user_id)

    total = query.count()
    repro = query.filter(Bug.bug_type == "repro").count()
    test = query.filter(Bug.bug_type == "test").count()
    pending = query.filter(Bug.status == "pending").count()
    running = query.filter(Bug.status == "running").count()
    completed = query.filter(Bug.status == "completed").count()

    return jsonify({
        "totalBugs": total,
        "reproBugs": repro,
        "testBugs": test,
        "pendingActions": pending,
        "runningBugs": running,
        "completedBugs": completed,
    })



# --------------------------------------------------
# SEARCH BUGS (autocomplete suggestions)
# --------------------------------------------------
@bug.route("/api/bugs/search", methods=["GET"])
def search_bugs():

    user_id = get_current_user_id()
    role = get_current_role()

    if not user_id:
        return jsonify({"error": "Not logged in"}), 401

    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])

    workgroup_id = request.args.get("workgroup_id", type=int)
    my_only = request.args.get('my_only', 'false').lower() == 'true'
    pattern = f"%{q}%"
    MAX_SUGGESTIONS = 7

    # ── Build base query with same role-based filtering as get_bugs ──
    base_query = Bug.query

    if workgroup_id:
        engineer_ids = db.session.query(WorkgroupAssignment.employee_id).filter(
            WorkgroupAssignment.workgroup_id == workgroup_id
        ).all()
        engineer_ids = [e[0] for e in engineer_ids]
        if not engineer_ids:
            return jsonify([])
        base_query = base_query.filter(Bug.engineer_id.in_(engineer_ids))

        if role == "Engineer" and my_only:
            base_query = base_query.filter(Bug.engineer_id == user_id)
    elif role == "Manager":
        engineer_ids = select(WorkgroupAssignment.employee_id).join(
            Workgroup, Workgroup.id == WorkgroupAssignment.workgroup_id
        ).where(Workgroup.manager_id == user_id)
        base_query = base_query.filter(Bug.engineer_id.in_(engineer_ids))
    elif role == "Engineer":
        base_query = base_query.filter(Bug.engineer_id == user_id)

    # ── Collect suggestions from four categories ──
    suggestions = []
    seen = set()

    def add_suggestion(type_label, value, bug_code):
        key = (type_label, value)
        if key not in seen and len(suggestions) < MAX_SUGGESTIONS:
            seen.add(key)
            suggestions.append({
                "type": type_label,
                "value": value,
                "bug_code": bug_code
            })

    # 1) Bug ID matches
    bug_id_matches = base_query.filter(Bug.bug_code.ilike(pattern)).limit(MAX_SUGGESTIONS).all()
    for b in bug_id_matches:
        add_suggestion("Bug ID", b.bug_code, b.bug_code)

    # 2) Engineer name matches
    if len(suggestions) < MAX_SUGGESTIONS:
        engineer_bugs = base_query.join(User, Bug.engineer_id == User.id).filter(
            or_(
                User.first_name.ilike(pattern),
                User.last_name.ilike(pattern),
                db.func.concat(User.first_name, ' ', User.last_name).ilike(pattern)
            )
        ).limit(MAX_SUGGESTIONS).all()
        for b in engineer_bugs:
            if b.engineer:
                add_suggestion("Engineer", b.engineer.full_name, b.bug_code)

    # 3) Test name matches
    if len(suggestions) < MAX_SUGGESTIONS:
        test_bugs = base_query.join(BugTest, Bug.id == BugTest.bug_id).filter(
            BugTest.test_name.ilike(pattern)
        ).limit(MAX_SUGGESTIONS).all()
        for b in test_bugs:
            for t in b.tests:
                if q.lower() in t.test_name.lower():
                    add_suggestion("Test", t.test_name, b.bug_code)

    # 4) Station name matches
    if len(suggestions) < MAX_SUGGESTIONS:
        station_bugs = base_query.join(BugStation, Bug.id == BugStation.bug_id).filter(
            BugStation.station_name.ilike(pattern)
        ).limit(MAX_SUGGESTIONS).all()
        for b in station_bugs:
            for s in b.stations:
                if q.lower() in s.station_name.lower():
                    add_suggestion("Station", s.station_name, b.bug_code)

    return jsonify(suggestions)


# --------------------------------------------------
# GET BUG TEST METADATA
# --------------------------------------------------
@bug.route("/api/bugs/<int:bug_id>/tests", methods=["GET"])
def get_bug_tests(bug_id):

    user_id = get_current_user_id()

    if not user_id:
        return jsonify({"error": "Not logged in"}), 401

    bug_record = Bug.query.get(bug_id)
    if not bug_record:
        return jsonify({"error": "Bug not found"}), 404

    bug_tests = BugTest.query.filter_by(bug_id=bug_id).all()

    return jsonify({
        "bug_code": bug_record.bug_code,
        "bug_name": bug_record.bug_name,
        "tests": [
            {
                "id": bug_test.id,
                "test_name": bug_test.test_name,
                "test_plan_name": bug_test.test_plan_name,
                "test_ring_name": bug_test.test_ring_name,
                "station_name": bug_test.station_name,
                "number_of_nodes": bug_test.number_of_nodes,
                "controller_types": bug_test.controller_types,
                "failure_type": bug_test.failure_type,
                "build_version": bug_test.build_version,
                "configuration": bug_test.configuration,
                "execution_start": bug_test.execution_start.isoformat() if bug_test.execution_start else None,
                "execution_end": bug_test.execution_end.isoformat() if bug_test.execution_end else None,
                "nfs_path": bug_test.nfs_path,
                "odin_link": bug_test.odin_link,
                "signature": bug_test.signature,
            }
            for bug_test in bug_tests
        ]
    })


# --------------------------------------------------
# GET STATION NAMES (for reserve modal dropdown)
# --------------------------------------------------
@bug.route("/api/stations", methods=["GET"])
def get_stations():
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"error": "Not logged in"}), 401

    station_names = (
        db.session.query(db.func.distinct(BugTest.station_name))
        .filter(BugTest.station_name.isnot(None))
        .all()
    )
    stations = sorted([s[0] for s in station_names if s[0]])
    return jsonify({"stations": stations})


# --------------------------------------------------
# RESERVE STATION (stub - accepts data, does not persist)
# --------------------------------------------------
@bug.route("/api/reservations", methods=["POST"])
def create_reservation():
    user_id = get_current_user_id()
    role = get_current_role()
    if not user_id:
        return jsonify({"error": "Not logged in"}), 401
    if role != "Engineer":
        return jsonify({"error": "Only engineers can reserve stations"}), 403

    data = request.json
    print(f"[Reservation] Received: {data}", flush=True)

    return jsonify({
        "message": "Reservation received (stub)",
        "data": data,
    }), 201
# --------------------------------------------------
# GET BUG ML ANALYSIS
# --------------------------------------------------
@bug.route("/api/bugs/<int:bug_id>/analysis", methods=["GET"])
def get_bug_analysis(bug_id):

    user_id = get_current_user_id()

    if not user_id:
        return jsonify({"error": "Not logged in"}), 401

    bug_record = Bug.query.get(bug_id)
    if not bug_record:
        return jsonify({"error": "Bug not found"}), 404

    analysis = MLAnalysis.query.filter_by(bug_id=bug_id).first()

    return jsonify({
        "bug_code": bug_record.bug_code,
        "analysis": {
            "repro_actions": analysis.repro_actions,
            "config_changes": analysis.config_changes,
            "repro_readiness": analysis.repro_readiness,
            "summary": analysis.summary,
            "generated_at": analysis.generated_at.isoformat() if analysis.generated_at else None,
        } if analysis else None
    })


# --------------------------------------------------
# GET BUG COMMENTS
# --------------------------------------------------
@bug.route("/api/bugs/<int:bug_id>/comments", methods=["GET"])
def get_bug_comments(bug_id):

    user_id = get_current_user_id()

    if not user_id:
        return jsonify({"error": "Not logged in"}), 401

    bug_record = Bug.query.get(bug_id)
    if not bug_record:
        return jsonify({"error": "Bug not found"}), 404

    comments = BugComment.query.filter_by(bug_id=bug_id).order_by(BugComment.comment_bugzilla_id.asc()).all()

    return jsonify({
        "bug_code": bug_record.bug_code,
        "comments": [
            {
                "id": comment.id,
                "comment_bugzilla_id": comment.comment_bugzilla_id,
                "creator": comment.creator,
                "creation_time": comment.creation_time.isoformat() if comment.creation_time else None,
                "text": comment.text,
            }
            for comment in comments
        ]
    })

