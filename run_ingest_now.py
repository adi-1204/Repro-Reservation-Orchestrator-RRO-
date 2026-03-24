import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import create_app, db
from app.models.user import User
from app.models.bug import Bug
from app.models.ml_analysis import MLAnalysis
import chathpe_client
from bugzilla_ingest import BugzillaIngester

app = create_app()
with app.app_context():
    db.create_all()
    email_map = {e.email.lower(): e.id for e in User.query.filter_by(role="Engineer").all()}
    print("Engineers:", list(email_map.keys()), flush=True)

    creds = chathpe_client.load_creds_from_config(app.config)
    print("ChatHPE creds OK", flush=True)

    ingester = BugzillaIngester(
        release_version="4.6.0.66",
        bugz_user=app.config["BUGZ_USER"],
        bugz_password=app.config["BUGZ_PASSWORD"],
    )
    result = ingester.ingest(db.session, email_map, chathpe_creds=creds)
    print("Ingest result:", result, flush=True)

    print("\n=== DB after ingestion ===", flush=True)
    for b in Bug.query.all():
        ml = MLAnalysis.query.filter_by(bug_id=b.id).first()
        print(f"Bug {b.bug_code} type={b.bug_type}: ml_analysis={'YES' if ml else 'NO'}", flush=True)
        if ml:
            print(f"  repro_actions:   {repr((ml.repro_actions or '')[:100])}", flush=True)
            print(f"  config_changes:  {repr((ml.config_changes or '')[:100])}", flush=True)
            print(f"  repro_readiness: {repr((ml.repro_readiness or '')[:100])}", flush=True)
            print(f"  summary:         {repr((ml.summary or '')[:100])}", flush=True)
