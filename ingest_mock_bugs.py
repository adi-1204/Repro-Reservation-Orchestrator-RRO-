"""
Ingest bugs from mock_bugs.json into the database.
Handles the Ultra-Minimalist Logical ID Schema.

Usage:
    python ingest_mock_bugs.py
"""

import json
import os
from sqlalchemy import text
from app import create_app, db
from app.models.bug import Bug
from app.models.bug_comments import BugComment
from app.models.bug_tests import BugTest
from app.models.bug_stations import BugStation
from app.models.build import Build

MOCK_BUGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mock_bugs.json")

def ingest():
    app = create_app()
    with app.app_context():
        print("--- Starting Minimalist Ingestion ---")
        
        # Ensure structure is correct
        print("--- Preparing database ---")
        try:
            db.session.execute(text("ALTER TABLE Bugs ADD COLUMN assignee_email VARCHAR(100)"))
        except:
            pass
        db.session.commit()
        
        # 1. Ensure Build entity exists for bug foreign keys
        release_v = "3.3.1.648"
        if not Build.query.get(release_v):
            db.session.add(Build(version=release_v))
            db.session.flush()

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

            # UPSERT Bug
            bug = Bug.query.get(bug_code)
            if not bug:
                bug = Bug(bug_id=bug_code)
                db.session.add(bug)
            
            bug.bug_name = row.get("Bug Name")
            bug.priority = (row.get("Priority") or "P2").strip()
            bug.build_id = b_val
            bug.component = (row.get("Component") or "").strip() # Use component instead of summary if model was changed
            bug.bug_type = "repro" if (row.get("Status") or "").upper() == "REPRODUCE" else "test"
            bug.status = "running" if bug.bug_type == "repro" else "pending"
            
            db.session.flush()

            # Clear associated data ONLY for this bug to avoid duplicates
            BugComment.query.filter_by(bug_id=bug_code).delete()
            BugTest.query.filter_by(bug_id=bug_code).delete()
            BugStation.query.filter_by(bug_id=bug_code).delete()
            MLAnalysis.query.filter_by(bug_id=bug_code).delete()
            db.session.flush()

            # Minimalist Comments
            from datetime import datetime
            for c in (row.get("Comments") or []):
                creation_time = None
                if c.get("creation_time"):
                    try:
                        # Parse ISO 8601 format: "2024-03-01T08:14:22Z"
                        creation_time = datetime.fromisoformat(c.get("creation_time").replace('Z', '+00:00'))
                    except:
                        creation_time = datetime.utcnow()
                else:
                    creation_time = datetime.utcnow()
                
                db.session.add(BugComment(
                    bug_id=bug.bug_code, 
                    creator=c.get("creator"), 
                    text=c.get("text"),
                    creation_time=creation_time
                ))

            # Minimalist Tests
            for t in (row.get("Tests") or []):
                db.session.add(BugTest(
                    bug_id=bug.bug_code,
                    test_name=t.get("test_name"),
                    station_name=t.get("station_name"),
                    build_id=b_val,
                    configuration=t.get("configuration")
                ))
            
            # No single-build-to-bug mapping required here; Build stores only the version.

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
