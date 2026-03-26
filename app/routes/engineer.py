from flask import Blueprint, render_template, redirect, url_for, request, jsonify, session
from app.models.user import User
from app.models.workgroup import Workgroup
from app.models.workgroupAssignment import WorkgroupAssignment
from app.auth_utils import (
    engineer_required,
    get_current_auth_token,
    get_current_role,
    get_current_user_id,
    revoke_tab_auth_session,
    get_request_auth_token,
)

engineer = Blueprint("engineer", __name__)


@engineer.route("/engineer_dashboard", methods=["GET", "POST"])
def engineer_dashboard():
    engineer_id = get_current_user_id()
    if not engineer_id:
        return redirect(url_for("auth.login"))

    #  FIX 6: Block a manager from accessing the engineer dashboard by URL
    if get_current_role() != "Engineer":
        return redirect(url_for("auth.login"))

    filter_type = request.args.get("filter", "all")
    current_user = User.query.get(engineer_id)

    assignments = WorkgroupAssignment.query.filter_by(employee_id=engineer_id).all()

    workgroups = []
    all_workgroups = []
    active = 0
    completed = 0

    for a in assignments:
        wg = Workgroup.query.get(a.workgroup_id)
        if not wg:
            continue

        all_workgroups.append(wg)

        if wg.is_completed == "Completed":
            completed += 1
        else:
            active += 1

        engineer_assignments = WorkgroupAssignment.query.filter_by(workgroup_id=wg.id).all()
        engineers = []
        for ea in engineer_assignments:
            user = User.query.get(ea.employee_id)
            if user:
                engineers.append(user)

        wg.engineer_list = engineers

        if filter_type == "active" and wg.is_completed != "Completed":
            workgroups.append(wg)
        elif filter_type == "completed" and wg.is_completed == "Completed":
            workgroups.append(wg)
        elif filter_type == "all":
            workgroups.append(wg)

    return render_template(
        "engineerDashboard.html",
        current_user=current_user,
        workgroups=workgroups,
        total=len(all_workgroups),
        active=active,
        completed=completed,
        filter_type=filter_type,
        auth_token=get_current_auth_token(),
    )


@engineer.route("/api/engineer/workgroups", methods=["GET"])
@engineer_required         #  Manager cannot read engineer's workgroup list
def get_engineer_workgroups():
    engineer_id = get_current_user_id()
    filter_type = request.args.get("filter", "all")

    assignments = WorkgroupAssignment.query.filter_by(employee_id=engineer_id).all()
    workgroups = []

    for a in assignments:
        wg = Workgroup.query.get(a.workgroup_id)
        if not wg:
            continue
        if filter_type == "active" and wg.is_completed:
            continue
        if filter_type == "completed" and not wg.is_completed:
            continue

        engineer_assignments = WorkgroupAssignment.query.filter_by(workgroup_id=wg.id).all()
        engineers = [
            {"id": u.id, "first_name": u.first_name, "last_name": u.last_name}
            for ea in engineer_assignments
            if (u := User.query.get(ea.employee_id))
        ]

        workgroups.append({
            "id": wg.id,
            "name": wg.name,
            "release_version": wg.release_version,
            "is_completed": "Completed" if wg.is_completed else "Active",
            "manager": {
                "id": wg.manager.id if wg.manager else None,
                "first_name": wg.manager.first_name if wg.manager else "",
                "last_name": wg.manager.last_name if wg.manager else "",
            },
            "engineers": engineers,
        })

    return jsonify(workgroups)


@engineer.route("/api/engineer/stats", methods=["GET"])
@engineer_required         #  Manager cannot read engineer stats
def get_engineer_stats():
    engineer_id = get_current_user_id()
    assignments = WorkgroupAssignment.query.filter_by(employee_id=engineer_id).all()

    total = active = completed = 0
    for a in assignments:
        wg = Workgroup.query.get(a.workgroup_id)
        if not wg:
            continue
        total += 1
        if wg.is_completed:
            completed += 1
        else:
            active += 1

    return jsonify({"total": total, "active": active, "completed": completed})


@engineer.route("/engineer/bug_management", methods=["GET"])
def engineer_bug_management():
    user_id = get_current_user_id()
    role = get_current_role()
    workgroup_id = request.args.get("workgroup_id", type=int)

    if not user_id:
        return redirect(url_for("auth.login"))
    if role != "Engineer":
        return redirect(url_for("auth.login"))

    return render_template("engineerBugManagement.html", auth_token=get_current_auth_token())

@engineer.route("/run", methods=["GET"])
def run_page():
    if not get_current_user_id():
        return redirect(url_for("auth.login"))
    if get_current_role() != "Engineer":
        return redirect(url_for("auth.login"))
    return render_template("run.html", auth_token=get_current_auth_token())


@engineer.route("/engineer_logout")
def logout():
    revoke_tab_auth_session(get_request_auth_token())
    session.clear()
    return redirect(url_for("auth.login"))
