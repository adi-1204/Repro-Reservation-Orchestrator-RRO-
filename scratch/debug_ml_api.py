from app import create_app
from app.models.bug import Bug
from app.models.ml_analysis import MLAnalysis

app = create_app()
with app.app_context():
    bug_id = "100001"
    bug_record = Bug.query.filter_by(bug_id=bug_id).first()
    if not bug_record:
        print(f"Bug {bug_id} not found")
    else:
        analysis = MLAnalysis.query.filter_by(bug_id=bug_record.bug_id).first()
        if not analysis:
            print(f"Analysis for {bug_id} not found")
        else:
            print("Found analysis!")
            res = {
                "bug_id": bug_record.bug_id,
                "analysis": {
                    "repro_actions": analysis.repro_actions,
                    "config_changes": analysis.config_changes,
                    "repro_readiness": analysis.repro_readiness,
                    "summary": analysis.summary,
                    "generated_at": analysis.generated_at.isoformat() if analysis.generated_at else None,
                } if analysis else None
            }
            import json
            print(json.dumps(res, indent=2))
