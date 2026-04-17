"""
Complete bug ingestion script with all data mapping.
Maps mock_bugs.json to database with proper field assignments.
"""

import json
import os
from datetime import datetime
from sqlalchemy import text
from app import create_app, db
from app.models.bug import Bug
from app.models.bug_comments import BugComment
from app.models.bug_tests import BugTest
from app.models.bug_stations import BugStation
from app.models.build import Build
from app.models.ml_analysis import MLAnalysis
import sys

# Ensure stdout can handle UTF-8 symbols on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding='utf-8')


MOCK_BUGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mock_bugs.json")


def ingest():
    """Ingest all bugs with complete data mapping."""
    app = create_app()
    with app.app_context():
        print("=" * 60)
        print("  COMPLETE BUG INGESTION")
        print("=" * 60)
        
        # Clear associated data ONLY (preserving Users, Builds, Workgroups)
        print("\n1. Preparing database...")
        try:
            db.session.execute(text("ALTER TABLE Bugs ADD COLUMN assignee_email VARCHAR(100)"))
        except:
            pass
        
        db.session.commit()
        print("   ✓ Database structure verified")
        
        # Load mock data
        print("\n2. Loading mock_bugs.json...")
        with open(MOCK_BUGS_FILE, "r", encoding="utf-8-sig") as f:
            bugs_data = json.load(f)
        print(f"   ✓ Loaded {len(bugs_data)} bugs")
        
        # Process each bug
        print("\n3. Ingesting bugs with complete mapping...")
        for bug_row in bugs_data:
            bug_id = str(bug_row.get("Bug Id", "")).strip()
            if not bug_id:
                continue
            
            # Get/Create Build
            build_version = str(bug_row.get("Build", "")).strip()
            if not Build.query.filter_by(version=build_version).first():
                db.session.add(Build(version=build_version))
                db.session.flush()
            
            # Map Bug Status to internal status
            bug_status = str(bug_row.get("Status", "")).upper()
            status_map = {
                "OPEN": "pending",
                "REPRODUCE": "running",
                "CLOSED": "completed",
                "VERIFIED": "completed"
            }
            mapped_status = status_map.get(bug_status, "pending")
            
            # UPSERT Bug with ALL fields
            bug = Bug.query.get(bug_id)
            if not bug:
                bug = Bug(bug_id=bug_id)
                db.session.add(bug)
            
            bug.bug_name = bug_row.get("Bug Name", "")
            bug.bug_type = "repro" if bug_status == "REPRODUCE" else "test"
            bug.priority = bug_row.get("Priority", "P2")
            bug.status = mapped_status
            bug.build_id = build_version
            bug.product = bug_row.get("Product", "")
            bug.component = bug_row.get("Component", "")
            bug.reporter = bug_row.get("Reporter", "")
            bug.severity = bug_row.get("Severity", "normal").lower()
            bug.whiteboard = bug_row.get("Whiteboard", "")
            bug.developer_progress = bug_row.get("Developer Progress", "")
            bug.assignee_email = bug_row.get("Assignee", "")
            
            db.session.flush()

            # Clear existing associated data for this bug to avoid duplicates on re-ingest
            BugComment.query.filter_by(bug_id=bug_id).delete()
            BugTest.query.filter_by(bug_id=bug_id).delete()
            BugStation.query.filter_by(bug_id=bug_id).delete()
            MLAnalysis.query.filter_by(bug_id=bug_id).delete()
            db.session.flush()
            
            # Add Comments with creation_time
            for comment_data in bug_row.get("Comments", []):
                creation_time = None
                if comment_data.get("creation_time"):
                    try:
                        # Parse ISO 8601: "2024-03-01T08:14:22Z"
                        time_str = comment_data.get("creation_time").replace('Z', '+00:00')
                        creation_time = datetime.fromisoformat(time_str)
                    except:
                        creation_time = datetime.utcnow()
                else:
                    creation_time = datetime.utcnow()
                
                comment = BugComment(
                    bug_id=bug_id,
                    creator=comment_data.get("creator", ""),
                    text=comment_data.get("text", ""),
                    creation_time=creation_time
                )
                db.session.add(comment)
            
            # Add Tests with proper station mapping
            for test_data in bug_row.get("Tests", []):
                test = BugTest(
                    bug_id=bug_id,
                    test_name=test_data.get("test_name", ""),
                    station_name=test_data.get("station_name", ""),
                    build_id=build_version,
                    configuration=test_data.get("configuration")
                )
                db.session.add(test)
                db.session.flush()
                
                # Add Station if not exists
                station = BugStation(
                    bug_id=bug_id,
                    station_name=test_data.get("station_name", "")
                )
                db.session.add(station)
            
            # Add ML Analysis mock data
            ml = MLAnalysis(
                bug_id=bug_id,
                repro_actions="Steps to reproduce the issue",
                config_changes="Configuration changes needed",
                repro_readiness="Ready for reproduction",
                summary=f"Analysis for {bug_row.get('Bug Name', bug_id)}",
                generated_at=datetime.utcnow()
            )
            db.session.add(ml)
        
        db.session.commit()
        
        # Verification
        print("\n4. Verification:")
        bug_count = Bug.query.count()
        comment_count = BugComment.query.count()
        test_count = BugTest.query.count()
        ml_count = MLAnalysis.query.count()
        
        print(f"   ✓ Bugs: {bug_count}")
        print(f"   ✓ Comments: {comment_count}")
        print(f"   ✓ Tests: {test_count}")
        print(f"   ✓ ML Analysis: {ml_count}")
        
        # Check for NULL components
        null_components = Bug.query.filter(Bug.component.is_(None)).count()
        print(f"   ✓ NULL components: {null_components}")
        
        print("\n" + "=" * 60)
        print("  INGESTION COMPLETE")
        print("=" * 60)


if __name__ == "__main__":
    ingest()
