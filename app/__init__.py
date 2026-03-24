import threading
import time

from flask import Flask
from app.config import Config
from app.extensions import db, login_manager, migrate, mail
from app.routes.auth import auth
from app.routes.managerDashboard import manager
from app.routes.engineer import engineer
from app.routes.bugDashboard import bug

_RETRY_INTERVAL_SECS = 30 * 60   # 30 minutes


def _start_analysis_retry_scheduler(app):
    """Start a daemon thread that retries ML analysis for pending bugs every 30 mins."""

    def _loop():
        # Wait one cycle before the first run so the app finishes starting up.
        time.sleep(60)
        while True:
            try:
                with app.app_context():
                    import chathpe_client
                    from bugzilla_ingest import retry_pending_analysis
                    try:
                        creds = chathpe_client.load_creds_from_config(app.config)
                    except ValueError as exc:
                        print(f"[Retry Scheduler] ChatHPE creds unavailable: {exc}", flush=True)
                        time.sleep(_RETRY_INTERVAL_SECS)
                        continue
                    print("[Retry Scheduler] Running pending analysis check...", flush=True)
                    retry_pending_analysis(db.session, creds)
            except Exception as exc:
                print(f"[Retry Scheduler] Unexpected error: {exc}", flush=True)
            time.sleep(_RETRY_INTERVAL_SECS)

    t = threading.Thread(target=_loop, name="ml-analysis-retry", daemon=True)
    t.start()
    print("[Retry Scheduler] Started — will retry pending analysis every 30 min.", flush=True)


def create_app():
    flask_app = Flask(__name__)
    flask_app.config.from_object(Config)

    db.init_app(flask_app)
    login_manager.init_app(flask_app)
    migrate.init_app(flask_app, db)
    mail.init_app(flask_app)

    login_manager.login_view = "auth.login_page"

    import app.auth_utils  # <-- important

    flask_app.register_blueprint(auth)
    flask_app.register_blueprint(manager)
    flask_app.register_blueprint(engineer)
    flask_app.register_blueprint(bug)

    # Start background ML analysis retry scheduler (30-min interval)
    _start_analysis_retry_scheduler(flask_app)

    return flask_app