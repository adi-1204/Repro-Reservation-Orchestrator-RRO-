"""
Ingest bugs from mock_bugs.json into the database.

Usage:
    python ingest_mock_bugs.py
"""

import json
import os
import re
import sys
from datetime import datetime

from app import create_app, db
from app.models.bug import Bug
from app.models.bug_comments import BugComment
from app.models.bug_tests import BugTest
from app.models.ml_analysis import MLAnalysis
from app.models.user import User
from app.models.workgroup import Workgroup
from app.models.workgroupAssignment import WorkgroupAssignment
from werkzeug.security import generate_password_hash


MOCK_BUGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mock_bugs.json")


def normalize_spaces(value):
    return re.sub(r"\s+", " ", value).strip()


def parse_execution_datetime(raw_value):
    if not raw_value:
        return None

    clean = raw_value.strip()
    if clean.endswith(" UTC"):
        clean = clean[:-4]

    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(clean, fmt)
        except ValueError:
            continue

    return None


def parse_iso_datetime(raw_value):
    if not raw_value:
        return None

    clean = raw_value.strip()
    if clean.endswith("Z"):
        clean = clean[:-1]

    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(clean, fmt)
        except ValueError:
            continue

    return None


def parse_int(raw_value):
    if raw_value is None:
        return None

    try:
        return int(str(raw_value).strip())
    except (TypeError, ValueError):
        return None


def parse_comment_metadata(comment_text):
    parsed = {}

    if not comment_text:
        return parsed

    for line in comment_text.splitlines():
        clean_line = line.strip()
        if not clean_line or ":" not in clean_line:
            continue

        key, value = clean_line.split(":", 1)
        key = normalize_spaces(key)
        value = value.strip()
        parsed[key] = value

    raw_test_name = parsed.get("Test Name")
    test_name = None
    if raw_test_name:
        test_name = raw_test_name.replace("\\", "/").rsplit("/", 1)[-1]

    test_ring_name = parsed.get("Test Ring Name")
    number_of_nodes = parse_int(parsed.get("Number Of Nodes"))

    return {
        "test_name": test_name,
        "test_plan_name": parsed.get("Test Plan Name"),
        "test_ring_name": test_ring_name,
        "execution_start": parse_execution_datetime(parsed.get("Execution Start")),
        "execution_end": parse_execution_datetime(parsed.get("Execution End")),
        "controller_types": parsed.get("Controller Types"),
        "number_of_nodes": number_of_nodes,
        "failure_type": parsed.get("Failure Type"),
        "build_version": parsed.get("Build Version"),
        "nfs_path": parsed.get("NFS Path"),
        "odin_link": parsed.get("Odin Link"),
        "signature": parsed.get("Signature"),
        "station_name": test_ring_name,
        "configuration": f"N{number_of_nodes}" if number_of_nodes else None,
    }


def map_bug_status(source_status):
    status = (source_status or "").strip().upper()

    if status == "REPRODUCE":
        return "running"
    if status == "OPEN":
        return "pending"
    if status in ("CLOSED", "VERIFIED"):
        return "completed"

    return "pending"


def map_bug_type(source_status):
    status = (source_status or "").strip().upper()
    return "repro" if status == "REPRODUCE" else "test"


def get_metadata_comment(comments):
    if not comments:
        return {}

    first = comments[0]
    if isinstance(first, dict):
        return first

    return {}


def ingest():
    app = create_app()
    with app.app_context():
        # 1. Ensure Manager exists
        manager_email = "rishinatarajsundar@gmail.com"
        manager = User.query.filter_by(email=manager_email).first()
        if not manager:
            manager = User(
                first_name="Rishi",
                last_name="Manager",
                email=manager_email,
                password=generate_password_hash("Admin@123"),
                role="Manager"
            )
            db.session.add(manager)
            db.session.flush()
            print(f"Created manager: {manager_email}")
        else:
            # For debugging convenience, reset password to known value
            manager.password = generate_password_hash("Admin@123")
            db.session.add(manager)
            print(f"Updated manager password: {manager_email}")

        # 2. Ensure Default Workgroup exists
        workgroup = Workgroup.query.filter_by(manager_id=manager.id).first()
        if not workgroup:
            workgroup = Workgroup(
                name="Main Workgroup",
                release_version="V1.0", # Shorter version to fit String(10)
                status="Active",
                manager_id=manager.id
            )
            db.session.add(workgroup)
            db.session.flush()
            print(f"Created workgroup: {workgroup.name}")

        with open(MOCK_BUGS_FILE, "r", encoding="utf-8-sig") as handle:
            bug_rows = json.load(handle)

        inserted_bugs = 0
        skipped_bugs = 0
        tests_created = 0
        created_comments = 0
        created_ml = 0

        try:
            for row in bug_rows:
                bug_code = str(row.get("Bug Id", "")).strip()
                if not bug_code:
                    continue

                source_status = row.get("Status")
                assignee_email = (row.get("Assignee") or "").strip()

                engineer = None
                if assignee_email:
                    engineer = User.query.filter(db.func.lower(User.email) == assignee_email.lower()).first()
                    if not engineer:
                        first = assignee_email.split(".")[0].capitalize()[:10]
                        engineer = User(
                            first_name=first,
                            last_name="Engineer",
                            email=assignee_email,
                            password=generate_password_hash("Engineer@123"),
                            role="Engineer"
                        )
                        db.session.add(engineer)
                        db.session.flush()
                        print(f"Created engineer: {assignee_email}")
                    
                    # Ensure engineer is assigned to the workgroup
                    assignment = WorkgroupAssignment.query.filter_by(
                        workgroup_id=workgroup.id,
                        employee_id=engineer.id
                    ).first()
                    if not assignment:
                        assignment = WorkgroupAssignment(
                            workgroup_id=workgroup.id,
                            employee_id=engineer.id
                        )
                        db.session.add(assignment)
                        print(f"Assigned {assignee_email} to {workgroup.name}")

                existing = Bug.query.filter_by(bug_code=bug_code).first()

                source_status = row.get("Status")
                assignee_email = (row.get("Assignee") or "").strip()

                engineer = None
                if assignee_email:
                    engineer = User.query.filter(db.func.lower(User.email) == assignee_email.lower()).first()

                if existing:
                    print(f"Skipping bug {bug_code} -- already exists")
                    skipped_bugs += 1
                    bug = existing
                else:
                    bug = Bug(
                        bug_code=bug_code,
                        bug_name=row.get("Bug Name", None),
                        priority=(row.get("Priority") or "P2").strip(),
                        status=map_bug_status(source_status),
                        engineer_id=engineer.id if engineer else None,
                        bug_type=map_bug_type(source_status),
                        resource_group=workgroup.release_version, # Fix: match workgroup version
                        summary=(row.get("Component") or "").strip() or None,
                    )
                    db.session.add(bug)
                    db.session.flush()
                    inserted_bugs += 1

                comments = row.get("Comments") or []
                metadata_comment = get_metadata_comment(comments)
                comment_zero_text = metadata_comment.get("text", "") if isinstance(metadata_comment, dict) else ""

                # Always refresh tests even if bug already existed.
                BugTest.query.filter_by(bug_id=bug.id).delete()

                tests_array = row.get("Tests", [])
                if not tests_array:
                    parsed_fallback = parse_comment_metadata(comment_zero_text)
                    tests_array = [{
                        "test_name": parsed_fallback.get("test_name"),
                        "station_name": parsed_fallback.get("station_name"),
                        "build_version": parsed_fallback.get("build_version"),
                        "configuration": parsed_fallback.get("configuration"),
                    }]

                for idx, test_entry in enumerate(tests_array):
                    test_entry = test_entry if isinstance(test_entry, dict) else {}
                    if idx == 0:
                        # First test includes full parsed metadata from comment[0].text.
                        parsed = parse_comment_metadata(comment_zero_text)
                    else:
                        parsed = {}

                    bug_test = BugTest(
                        bug_id=bug.id,
                        test_name=test_entry.get("test_name"),
                        station_name=test_entry.get("station_name"),
                        build_version=test_entry.get("build_version"),
                        configuration=test_entry.get("configuration"),
                        test_plan_name=parsed.get("test_plan_name"),
                        test_ring_name=parsed.get("test_ring_name"),
                        execution_start=parsed.get("execution_start"),
                        execution_end=parsed.get("execution_end"),
                        controller_types=parsed.get("controller_types"),
                        number_of_nodes=parsed.get("number_of_nodes"),
                        failure_type=parsed.get("failure_type"),
                        nfs_path=parsed.get("nfs_path"),
                        odin_link=parsed.get("odin_link"),
                        signature=parsed.get("signature"),
                    )
                    db.session.add(bug_test)
                    tests_created += 1

                if existing:
                    bug.bug_name = row.get("Bug Name", None)
                    bug.engineer_id = engineer.id if engineer else None
                    bug.resource_group = workgroup.release_version
                    db.session.add(bug)

                if not existing:
                    for comment in comments:
                        comment_obj = BugComment(
                            bug_id=bug.id,
                            comment_bugzilla_id=parse_int(comment.get("id")) if isinstance(comment, dict) else None,
                            creator=(comment.get("creator") if isinstance(comment, dict) else None),
                            creation_time=parse_iso_datetime(comment.get("creation_time")) if isinstance(comment, dict) else None,
                            text=(comment.get("text") if isinstance(comment, dict) else None),
                        )
                        db.session.add(comment_obj)
                        created_comments += 1

                    ml_analysis = MLAnalysis(
                        bug_id=bug.id,
                        repro_actions=None,
                        config_changes=None,
                        repro_readiness=None,
                        summary=None,
                    )
                    db.session.add(ml_analysis)
                    created_ml += 1

            db.session.commit()

            print("Ingest complete.")
            print(f"  Bugs inserted: {inserted_bugs}")
            print(f"  Bugs skipped:  {skipped_bugs}")
            print(f"  Tests created: {tests_created}")
            print(f"  Comments created: {created_comments}")
            print(f"  ML Analysis placeholders created: {created_ml}")
        except Exception as exc:
            db.session.rollback()
            print(f"Ingest failed: {exc}")
            sys.exit(1)


if __name__ == "__main__":
    ingest()
