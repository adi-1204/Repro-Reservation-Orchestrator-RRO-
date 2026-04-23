from flask import Blueprint, render_template, jsonify, request, redirect, url_for
from datetime import datetime, timedelta
from app.extensions import db
from app.models.bug import Bug
from app.models.bug_comments import BugComment
from app.models.ml_analysis import MLAnalysis
from app.models.bug_tests import BugTest
from app.models.bug_stations import BugStation
from app.models.user import User
from app.models.workgroup import Workgroup
from app.models.workgroupAssignment import WorkgroupAssignment
from app.models.reservation_by_name import ReservationByName
from app.auth_utils import get_current_auth_token, get_current_role, get_current_user, get_current_user_id
from sqlalchemy import select, or_
from app.models.run_parameters import RunParameter

bug = Blueprint("bugDashboard", __name__)


def _normalize_station_list(stations_value):
    if isinstance(stations_value, str):
        stations_value = stations_value.split(',')

    normalized = []
    seen = set()

    for station in stations_value or []:
        station_name = str(station).strip()
        if not station_name:
            continue
        station_key = station_name.lower()
        if station_key in seen:
            continue
        seen.add(station_key)
        normalized.append(station_name)

    return normalized


def _get_active_bug_stations(user_id, bug_id):
    existing_rows = ReservationByName.query.filter_by(user_id=user_id, bug_id=bug_id).filter(
        ReservationByName.status != "rejected"
    ).all()

    station_map = {}
    for row in existing_rows:
        for station_name in _normalize_station_list(row.stations):
            station_map.setdefault(station_name.lower(), station_name)

    return station_map


def _get_allowed_repro_build_ids(user_id):
    build_rows = (
        db.session.query(Bug.build_id)
        .filter(
            Bug.engineer_id == user_id,
            Bug.bug_type == "repro",
            Bug.build_id.isnot(None),
        )
        .distinct()
        .order_by(Bug.build_id.asc())
        .all()
    )

    return [row[0] for row in build_rows if row and row[0]]


def _split_station_list(stations_value):
    if isinstance(stations_value, str):
        stations_value = stations_value.split(',')

    stations = []
    seen = set()

    for station in stations_value or []:
        station_name = str(station).strip()
        if not station_name:
            continue

        station_key = station_name.lower()
        if station_key in seen:
            continue

        seen.add(station_key)
        stations.append(station_name)

    return stations


def _count_pending_by_name_actions(reservations, cutoff_time):
    pending = 0

    for reservation in reservations:
        if not reservation.created_at or reservation.created_at < cutoff_time:
            continue
        if str(getattr(reservation, "status", "")).lower() == "rejected":
            continue

        reserved_stations = _split_station_list(reservation.stations)
        if not reserved_stations:
            continue

        matched_stations = {
            (station_name or "").strip().lower()
            for (station_name,) in db.session.query(RunParameter.station_name)
            .filter(
                RunParameter.bug_id == reservation.bug_id,
                RunParameter.submitted_by == reservation.user_id,
                RunParameter.submitted_at >= reservation.created_at,
                RunParameter.station_name.in_(reserved_stations),
            )
            .distinct()
            .all()
        }

        pending += sum(
            1 for station_name in reserved_stations
            if station_name.lower() not in matched_stations
        )

    return pending


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
        # Workgroup-scoped view: show bugs matching this workgroup's
        # build version AND assigned to engineers in THIS workgroup.
        wg_engineer_ids = db.session.query(WorkgroupAssignment.employee_id).filter(
            WorkgroupAssignment.workgroup_id == workgroup_id
        ).subquery()
        query = query.filter(
            Bug.build_id == workgroup.release_version,
            Bug.engineer_id.in_(wg_engineer_ids)
        )

        # Engineers can narrow the workgroup view to only their assigned bugs.
        if role == "Engineer" and my_only:
            query = query.filter(Bug.engineer_id == user_id)

    elif role == "Manager":
        # Navbar view (no workgroup): show bugs matching exactly the assigned engineers AND release
        # versions of ANY of the workgroups managed by this manager.
        query = query.filter(
            db.session.query(WorkgroupAssignment).join(Workgroup).filter(
                Workgroup.manager_id == user_id,
                WorkgroupAssignment.employee_id == Bug.engineer_id,
                Workgroup.release_version == Bug.build_id
            ).exists()
        )

    elif role == "Engineer":
        # Engineers only see bugs from workgroups they are assigned to
        # (matching both engineer assignment AND build version).
        # If the engineer is not assigned to any workgroup, no bugs are shown.
        query = query.filter(
            db.session.query(WorkgroupAssignment).join(Workgroup).filter(
                WorkgroupAssignment.employee_id == user_id,
                Bug.engineer_id == user_id,
                Workgroup.release_version == Bug.build_id
            ).exists()
        )

    bugs = query.all()

    repro = []
    test = []

    for b in bugs:

        data = {
            "id": b.bug_id,
            "bug_name": b.bug_name,
            "engineer_name": (
                f"{b.engineer.first_name} {b.engineer.last_name or ''}".strip()
                if b.engineer else "Unassigned"
            ),
            "priority": b.priority,
            "status": b.status,
            "engineer": {
                "name": b.engineer.full_name if b.engineer else "Unassigned",
                "initials": (
                    (b.engineer.first_name[0] + b.engineer.last_name[0]).upper()
                    if b.engineer else "--"
                ),
                "color": "#7c3aed"
            },
            "component": b.component or "",
            "tests": [t.test_name for t in b.tests],
            "stations": [s.station_name for s in b.stations],
            "build": b.build_id
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

    active_cutoff = datetime.utcnow() - timedelta(hours=48)

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
        # Workgroup-scoped stats: match build version AND assigned engineers
        wg_engineer_ids = db.session.query(WorkgroupAssignment.employee_id).filter(
            WorkgroupAssignment.workgroup_id == workgroup_id
        ).subquery()
        query = Bug.query.filter(
            Bug.build_id == workgroup.release_version,
            Bug.engineer_id.in_(wg_engineer_ids)
        )
        if role == "Engineer" and my_only:
            query = query.filter(Bug.engineer_id == user_id)

        total = query.count()
        repro = query.filter(Bug.bug_type == "repro").count()
        test = query.filter(Bug.bug_type == "test").count()

        # Pending Actions = active reservation rows visible in the table
        pending = 0
        from app.models.reservation_by_config import ReservationByConfig
        
        applicable_bug_ids = {b.bug_id for b in query.all()}

        # By Name
        if applicable_bug_ids:
            name_res_query = ReservationByName.query.filter(ReservationByName.bug_id.in_(applicable_bug_ids))
            if role == "Engineer":
                name_res_query = name_res_query.filter(ReservationByName.user_id == user_id)
            elif role == "Manager":
                name_res_query = name_res_query.filter(ReservationByName.user_id.in_(wg_engineer_ids))

            pending += _count_pending_by_name_actions(name_res_query.all(), active_cutoff)

        # By Config
        config_res_query = ReservationByConfig.query.filter(
            ReservationByConfig.resource_group == workgroup.release_version
        )
        if role == "Engineer":
            config_res_query = config_res_query.filter(ReservationByConfig.user_id == user_id)
        elif role == "Manager":
            config_res_query = config_res_query.filter(ReservationByConfig.user_id.in_(wg_engineer_ids))

        pending += config_res_query.filter(
            ReservationByConfig.created_at.isnot(None),
            ReservationByConfig.created_at >= active_cutoff,
            ReservationByConfig.status != "rejected",
        ).count()

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
        query = query.filter(
            db.session.query(WorkgroupAssignment).join(Workgroup).filter(
                Workgroup.manager_id == user_id,
                WorkgroupAssignment.employee_id == Bug.engineer_id,
                Workgroup.release_version == Bug.build_id
            ).exists()
        )
    elif role == "Engineer":
        # Engineers only see stats for bugs from workgroups they are assigned to
        query = query.filter(
            db.session.query(WorkgroupAssignment).join(Workgroup).filter(
                WorkgroupAssignment.employee_id == user_id,
                Bug.engineer_id == user_id,
                Workgroup.release_version == Bug.build_id
            ).exists()
        )

    total = query.count()
    repro = query.filter(Bug.bug_type == "repro").count()
    test = query.filter(Bug.bug_type == "test").count()

    # Pending Actions = active reservation rows visible in the table
    pending = 0
    from app.models.reservation_by_config import ReservationByConfig
    
    applicable_bug_ids = {b.bug_id for b in query.all()}

    # By Name
    if applicable_bug_ids:
        name_res_query = ReservationByName.query.filter(ReservationByName.bug_id.in_(applicable_bug_ids))
        if role == "Engineer":
            name_res_query = name_res_query.filter(ReservationByName.user_id == user_id)
        elif role == "Manager":
            managed_engineers = db.session.query(WorkgroupAssignment.employee_id).join(Workgroup).filter(
                Workgroup.manager_id == user_id
            ).subquery()
            name_res_query = name_res_query.filter(ReservationByName.user_id.in_(managed_engineers))

        pending += _count_pending_by_name_actions(name_res_query.all(), active_cutoff)

    # By Config
    if role == "Engineer":
        pending += ReservationByConfig.query.filter(
            ReservationByConfig.user_id == user_id,
            ReservationByConfig.created_at.isnot(None),
            ReservationByConfig.created_at >= active_cutoff,
            ReservationByConfig.status != "rejected",
        ).count()
    elif role == "Manager":
        managed_engineers = db.session.query(WorkgroupAssignment.employee_id).join(Workgroup).filter(
            Workgroup.manager_id == user_id
        ).subquery()
        managed_releases = db.session.query(Workgroup.release_version).filter(
            Workgroup.manager_id == user_id
        ).subquery()
        pending += ReservationByConfig.query.filter(
            ReservationByConfig.user_id.in_(managed_engineers),
            ReservationByConfig.resource_group.in_(managed_releases),
            ReservationByConfig.created_at.isnot(None),
            ReservationByConfig.created_at >= active_cutoff,
            ReservationByConfig.status != "rejected",
        ).count()

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
        workgroup = Workgroup.query.get(workgroup_id)
        if workgroup:
            wg_engineer_ids = db.session.query(WorkgroupAssignment.employee_id).filter(
                WorkgroupAssignment.workgroup_id == workgroup_id
            ).subquery()
            base_query = base_query.filter(
                Bug.build_id == workgroup.release_version,
                Bug.engineer_id.in_(wg_engineer_ids)
            )
        else:
            return jsonify([])

        if role == "Engineer" and my_only:
            base_query = base_query.filter(Bug.engineer_id == user_id)
    elif role == "Manager":
        base_query = base_query.filter(
            db.session.query(WorkgroupAssignment).join(Workgroup).filter(
                Workgroup.manager_id == user_id,
                WorkgroupAssignment.employee_id == Bug.engineer_id,
                Workgroup.release_version == Bug.build_id
            ).exists()
        )
    elif role == "Engineer":
        # Engineers only see search results for bugs from their assigned workgroups
        base_query = base_query.filter(
            db.session.query(WorkgroupAssignment).join(Workgroup).filter(
                WorkgroupAssignment.employee_id == user_id,
                Bug.engineer_id == user_id,
                Workgroup.release_version == Bug.build_id
            ).exists()
        )

    # ── Collect suggestions from four categories ──
    suggestions = []
    seen = set()

    def add_suggestion(type_label, value, bug_id):
        key = (type_label, value)
        if key not in seen and len(suggestions) < MAX_SUGGESTIONS:
            seen.add(key)
            suggestions.append({
                "type": type_label,
                "value": value,
                "bug_id": bug_id
            })

    # 1) Bug ID matches
    bug_id_matches = base_query.filter(Bug.bug_id.ilike(pattern)).limit(MAX_SUGGESTIONS).all()
    for b in bug_id_matches:
        add_suggestion("Bug ID", b.bug_id, b.bug_id)

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
                add_suggestion("Engineer", b.engineer.full_name, b.bug_id)

    # 3) Test name matches
    if len(suggestions) < MAX_SUGGESTIONS:
        test_bugs = base_query.join(BugTest, Bug.bug_id == BugTest.bug_id).filter(
            BugTest.test_name.ilike(pattern)
        ).limit(MAX_SUGGESTIONS).all()
        for b in test_bugs:
            for t in b.tests:
                if q.lower() in t.test_name.lower():
                    add_suggestion("Test", t.test_name, b.bug_id)

    # 4) Station name matches
    if len(suggestions) < MAX_SUGGESTIONS:
        station_bugs = base_query.join(BugStation, Bug.bug_id == BugStation.bug_id).filter(
            BugStation.station_name.ilike(pattern)
        ).limit(MAX_SUGGESTIONS).all()
        for b in station_bugs:
            for s in b.stations:
                if q.lower() in s.station_name.lower():
                    add_suggestion("Station", s.station_name, b.bug_id)

    return jsonify(suggestions)


# --------------------------------------------------
# GET BUG TEST METADATA
# --------------------------------------------------
@bug.route("/api/bugs/<string:bug_id>/tests", methods=["GET"])
def get_bug_tests(bug_id):

    user_id = get_current_user_id()
    role = get_current_role()

    if not user_id:
        return jsonify({"error": "Not logged in"}), 401

    bug_record = Bug.query.filter_by(bug_id=bug_id).first()
    if not bug_record:
        return jsonify({"error": "Bug not found"}), 404
    if role == "Engineer" and bug_record.engineer_id != user_id:
        return jsonify({"error": "You can view tests only for bugs assigned to you."}), 403

    bug_tests = BugTest.query.filter_by(bug_id=bug_record.bug_id).all()

    completed_rows = ReservationByName.query.filter(
        ReservationByName.bug_id == bug_record.bug_id,
        ReservationByName.status == "completed"
    ).all()

    completed_station_set = set()

    for row in completed_rows:
        stations = [s.strip() for s in (row.stations or "").split(',') if s.strip()]
        completed_station_set.update(stations)

    return jsonify({
        "bug_id": bug_record.bug_id,
        "bug_name": bug_record.bug_name,
        "tests": [
            {
                "id": bug_test.id,
                "test_name": bug_test.test_name,
                "station_name": bug_test.station_name,
                "completed": bug_test.station_name in completed_station_set   # ✅ ADD THIS
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
# GET COMPLETED RESERVATION STATIONS FOR A BUG
# --------------------------------------------------
@bug.route("/api/bugs/<string:bug_id>/reservation-stations", methods=["GET"])
def get_bug_reservation_stations(bug_id):
    """Get stations from completed 'by_name' reservations for a specific bug."""
    from app.models.reservation_by_name import ReservationByName
    
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"error": "Not logged in"}), 401
    
    # Find completed reservations for this bug by the current user
    completed_reservations = ReservationByName.query.filter_by(
        user_id=user_id,
        bug_id=bug_id,
        status='completed'
    ).all()
    
    # Extract all stations from completed reservations
    stations = set()
    for reservation in completed_reservations:
        if reservation.stations:
            station_list = [s.strip() for s in reservation.stations.split(',') if s.strip()]
            stations.update(station_list)
    
    return jsonify({
        "stations": sorted(list(stations)),
        "has_completed_reservation": len(stations) > 0
    })


# --------------------------------------------------
# GET RESERVATIONS (engineer's own reservations)
# --------------------------------------------------
@bug.route("/api/reservations", methods=["GET"])
def get_reservations():
    from app.models.reservation_by_name import ReservationByName
    from app.models.reservation_by_config import ReservationByConfig

    user_id = get_current_user_id()
    role = get_current_role()

    if not user_id:
        return jsonify({"error": "Not logged in"}), 401
    if role != "Engineer":
        return jsonify({"error": "Only engineers can view reservations"}), 403

    workgroup_id = request.args.get('workgroup_id', type=int)
    release_version = None
    if workgroup_id:
        wg = Workgroup.query.get(workgroup_id)
        release_version = wg.release_version if wg else None

    # by_name: filter by release_version via bug's build_id
    by_name_q = ReservationByName.query.filter_by(user_id=user_id)
    if release_version:
        by_name_q = by_name_q.join(Bug, ReservationByName.bug_id == Bug.bug_id).filter(
            Bug.build_id == release_version
        )
    by_name = by_name_q.all()

    # by_config: filter by release_version == resource_group
    by_config_q = ReservationByConfig.query.filter_by(user_id=user_id)
    if release_version:
        by_config_q = by_config_q.filter(ReservationByConfig.resource_group == release_version)
    by_config = by_config_q.all()

    reservations = []

    for row in by_name:
        stations = [s.strip() for s in (row.stations or "").split(',') if s.strip()]
        reservations.append({
            "id": row.id,
            "type": "by_name",
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "bug_id": row.bug_id,
            "stations": stations,
            "specify_station": bool(row.specify_station),
            "status": row.status   # ✅ ADD THIS
        })

    for row in by_config:
        reservations.append({
            "id": row.id,
            "type": "by_config",
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "resource_group": row.resource_group,
            "number_of_nodes": row.number_of_nodes,
            "code_floor": row.code_floor,
            "number_of_pds": row.number_of_pds,
            "rc": bool(row.rc),
            "status": row.status   # ✅ ADD THIS
        })

    reservations.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    return jsonify({"reservations": reservations})


# --------------------------------------------------
# RESERVE STATION (stores reservation details)
# --------------------------------------------------
@bug.route("/api/reservations", methods=["POST"])
def create_reservation():
    from app.models.reservation_by_name import ReservationByName
    from app.models.reservation_by_config import ReservationByConfig

    user_id = get_current_user_id()
    role = get_current_role()
    if not user_id:
        return jsonify({"error": "Not logged in"}), 401
    if role != "Engineer":
        return jsonify({"error": "Only engineers can reserve stations"}), 403

    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400

    res_type = data.get('type')
    try:
        if res_type == 'by_name':
            bug_id = str(data.get('bug_id') or '').strip()
            if not bug_id:
                return jsonify({"error": "Bug ID is required"}), 400

            bug_record = Bug.query.filter_by(bug_id=bug_id, engineer_id=user_id).first()
            if not bug_record or bug_record.bug_type != "repro":
                return jsonify({"error": "Select a repro bug assigned to you"}), 400

            stations = _normalize_station_list(data.get('stations', []))
            if not stations:
                return jsonify({"error": "Please select at least one station"}), 400
            if len(stations) > 3:
                return jsonify({"error": "You can reserve up to 3 stations for the same bug"}), 400

            existing_station_map = _get_active_bug_stations(user_id, bug_id)
            duplicate_stations = [station for station in stations if station.lower() in existing_station_map]
            if duplicate_stations:
                duplicate_label = ", ".join(duplicate_stations)
                return jsonify({
                    "error": f"Station(s) already reserved for bug {bug_id}: {duplicate_label}"
                }), 400

            total_station_count = len(existing_station_map) + len(stations)
            if total_station_count > 3:
                remaining = max(0, 3 - len(existing_station_map))
                return jsonify({
                    "error": f"You can reserve up to 3 stations for bug {bug_id}. You already have {len(existing_station_map)} reserved, so only {remaining} more station(s) can be added."
                }), 400

            stations_str = ",".join(stations)
            
            new_res = ReservationByName(
                user_id=user_id,
                bug_id=bug_id,
                stations=stations_str,
                specify_station=data.get('specify_station', False),
                status='completed',   # or 'pending'
                created_at=datetime.now()
            )
            db.session.add(new_res)
            db.session.commit()
            
            return jsonify({
                "message": "Reservation by name stored successfully",
                "reservation_id": new_res.id
            }), 201

        elif res_type == 'by_config':
            resource_group = str(data.get('resource_group') or '').strip()
            if not resource_group:
                return jsonify({"error": "Build ID is required"}), 400

            allowed_build_ids = _get_allowed_repro_build_ids(user_id)
            if resource_group not in allowed_build_ids:
                return jsonify({"error": "Select a build ID from your repro bugs"}), 400

            new_res = ReservationByConfig(
                user_id=user_id,
                resource_group=resource_group,
                number_of_nodes=data.get('number_of_nodes'),
                code_floor=data.get('code_floor'),
                number_of_pds=data.get('number_of_pds'),
                rc=data.get('rc', False),
                status='completed',
                created_at=datetime.now()
            )
            db.session.add(new_res)
            db.session.commit()
            
            return jsonify({
                "message": "Reservation by config stored successfully",
                "reservation_id": new_res.id
            }), 201
        
        else:
            return jsonify({"error": f"Invalid reservation type: {res_type}"}), 400

    except Exception as e:
        db.session.rollback()
        print(f"[Reservation Error] {str(e)}", flush=True)
        return jsonify({"error": "Failed to store reservation", "details": str(e)}), 500


# --------------------------------------------------
# CANCEL RESERVATION
# --------------------------------------------------
@bug.route("/api/reservations/cancel", methods=["POST"])
def cancel_reservation():
    from app.models.reservation_by_name import ReservationByName
    from app.models.reservation_by_config import ReservationByConfig

    user_id = get_current_user_id()
    role = get_current_role()

    if not user_id:
        return jsonify({"error": "Not logged in"}), 401
    if role != "Engineer":
        return jsonify({"error": "Only engineers can cancel reservations"}), 403

    data = request.get_json(silent=True) or {}
    reservation_type = data.get("type")
    reservation_id = data.get("id")

    if reservation_type not in {"by_name", "by_config"}:
        return jsonify({"error": "Invalid reservation type"}), 400
    if not reservation_id:
        return jsonify({"error": "Reservation id is required"}), 400

    model = ReservationByName if reservation_type == "by_name" else ReservationByConfig
    reservation = model.query.filter_by(id=reservation_id, user_id=user_id).first()

    if not reservation:
        return jsonify({"error": "Reservation not found"}), 404

    try:
        reservation.status = 'rejected'
        db.session.commit()
        return jsonify({"message": "Reservation cancelled successfully", "id": reservation.id}), 200
    except Exception as e:
        db.session.rollback()
        print(f"[Reservation Cancel Error] {str(e)}", flush=True)
        return jsonify({"error": "Failed to cancel reservation", "details": str(e)}), 500
# --------------------------------------------------
# GET BUG ML ANALYSIS
# --------------------------------------------------
@bug.route("/api/bugs/<string:bug_id>/analysis", methods=["GET"])
def get_bug_analysis(bug_id):

    user_id = get_current_user_id()

    if not user_id:
        return jsonify({"error": "Not logged in"}), 401

    bug_record = Bug.query.filter_by(bug_id=bug_id).first()
    if not bug_record:
        return jsonify({"error": "Bug not found"}), 404

    analysis = MLAnalysis.query.filter_by(bug_id=bug_record.bug_id).first()

    return jsonify({
        "bug_id": bug_record.bug_id,
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
@bug.route("/api/bugs/<string:bug_id>/comments", methods=["GET"])
def get_bug_comments(bug_id):

    user_id = get_current_user_id()

    if not user_id:
        return jsonify({"error": "Not logged in"}), 401

    bug_record = Bug.query.filter_by(bug_id=bug_id).first()
    if not bug_record:
        return jsonify({"error": "Bug not found"}), 404

    comments = BugComment.query.filter_by(bug_id=bug_record.bug_id).order_by(BugComment.id.asc()).all()

    return jsonify({
        "bug_id": bug_record.bug_id,
        "comments": [
            {
                "id": comment.id,
                "creator": comment.creator,
                "text": comment.text,
            }
            for comment in comments
        ]
    })

