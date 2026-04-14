"""
Ingest bugs from mock_bugs.json into the database.
Handles the Ultra-Minimalist Logical ID Schema.

Usage:
    python ingest_mock_bugs.py
"""

import json
import os
import sys
from sqlalchemy import text
from app import create_app, db
from app.models.bug import Bug
from app.models.bug_comments import BugComment
from app.models.bug_tests import BugTest
from app.models.bug_stations import BugStation
from app.models.build import Build
from app.models.user import User
from app.models.workgroup import Workgroup
from app.models.workgroupAssignment import WorkgroupAssignment
from werkzeug.security import generate_password_hash

MOCK_BUGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mock_bugs.json")

def ingest():
    app = create_app()
    with app.app_context():
        print("--- Starting Minimalist Ingestion ---")
        
        # 0. Setup SQL environment
        db.session.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        
        # 1. Ensure Core Entities (Manager, Workgroup, Build)
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

        release_v = "3.3.1.648"
        if not Build.query.get(release_v):
            db.session.add(Build(version=release_v))
            db.session.flush()

        workgroup = Workgroup.query.filter_by(manager_id=manager.id).first()
        if not workgroup:
            workgroup = Workgroup(
                name="Main Workgroup",
                release_version=release_v,
                status="Active",
                manager_id=manager.id
            )
            db.session.add(workgroup)
            db.session.flush()

        # 2. Clear Child Tables for fresh data
        BugComment.query.delete()
        BugTest.query.delete()
        BugStation.query.delete()

        # 3. Load Data
        with open(MOCK_BUGS_FILE, "r", encoding="utf-8-sig") as handle:
            bug_rows = json.load(handle)

        for row in bug_rows:
            bug_code = str(row.get("Bug Id", "")).strip()
            if not bug_code: continue

            # Maintain Build Record
            b_val = str(row.get("Build", release_v)).strip()
            if not Build.query.get(b_val):
                db.session.add(Build(version=b_val))
                db.session.flush()

            # Ensure Engineer
            assignee_email = (row.get("Assignee") or "").strip()
            engineer = None
            if assignee_email:
                engineer = User.query.filter_by(email=assignee_email).first()
                if not engineer:
                    engineer = User(
                        first_name=assignee_email.split(".")[0].capitalize(),
                        last_name="Engineer",
                        email=assignee_email,
                        password=generate_password_hash("Engineer@123"),
                        role="Engineer"
                    )
                    db.session.add(engineer)
                    db.session.flush()
                
                if not WorkgroupAssignment.query.filter_by(workgroup_id=workgroup.id, employee_id=engineer.id).first():
                    db.session.add(WorkgroupAssignment(workgroup_id=workgroup.id, employee_id=engineer.id))

            # UPSERT Bug
            bug = Bug.query.filter_by(bug_code=bug_code).first()
            if not bug:
                bug = Bug(bug_code=bug_code)
            
            bug.bug_name = row.get("Bug Name")
            bug.priority = (row.get("Priority") or "P2").strip()
            bug.engineer_id = engineer.id if engineer else None
            bug.build_id = b_val
            bug.resource_group = b_val
            bug.summary = (row.get("Component") or "").strip()
            bug.bug_type = "repro" if (row.get("Status") or "").upper() == "REPRODUCE" else "test"
            bug.status = "running" if bug.bug_type == "repro" else "pending"
            
            db.session.add(bug)
            db.session.flush()

            # Minimalist Comments
            for c in (row.get("Comments") or []):
                db.session.add(BugComment(bug_id=bug.bug_code, creator=c.get("creator"), text=c.get("text")))

            # Minimalist Tests
            for t in (row.get("Tests") or []):
                db.session.add(BugTest(
                    bug_id=bug.bug_code,
                    test_name=t.get("test_name"),
                    station_name=t.get("station_name"),
                    build_id=b_val,
                    configuration=t.get("configuration")
                ))
            
            build_rec = Build.query.get(b_val)
            if build_rec and not build_rec.bug_id:
                build_rec.bug_id = bug.bug_code

            # Minimalist ML Analysis mock
            from app.models.ml_analysis import MLAnalysis
            from datetime import datetime
            
            ml_analysis = MLAnalysis.query.filter_by(bug_id=bug.bug_code).first()
            if not ml_analysis:
                ml_analysis = MLAnalysis(bug_id=bug.bug_code)
                db.session.add(ml_analysis)
            
            ml_analysis.repro_actions = "1. Setup station \\n2. Deploy build \\n3. Run test script"
            ml_analysis.config_changes = "Change parameter " + bug.bug_code + " to True."
            ml_analysis.repro_readiness = "Ready to reproduce"
            ml_analysis.summary = "Mock analysis for " + bug.bug_name
            ml_analysis.generated_at = datetime.utcnow()

        db.session.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
        db.session.commit()
        print(f"Ingest complete. Mapped {len(bug_rows)} bugs.")

if __name__ == "__main__":
    ingest()
