"""Force-run ML analysis retry right now using the current .env credentials."""
from app import create_app
from app.extensions import db
import chathpe_client
from bugzilla_ingest import retry_pending_analysis

app = create_app()
with app.app_context():
    creds = chathpe_client.load_creds_from_config(app.config)
    print(f"JWT prefix: {(creds.get('jwt_token') or '')[:30]}...")
    result = retry_pending_analysis(db.session, creds)
    print(f"Done — {result} bug(s) analysed.")
