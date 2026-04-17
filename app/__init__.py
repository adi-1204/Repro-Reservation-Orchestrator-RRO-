import threading
import time

from flask import Flask
from app.config import Config
from app.extensions import db, login_manager, migrate, mail
from app.routes.auth import auth
from app.routes.managerDashboard import manager
from app.routes.engineer import engineer
from app.routes.bugDashboard import bug
from app.routes.run_route import run_bp

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
                        # Even if creds are missing, we can still do reservation cleanup
                    
                    print("[Retry Scheduler] Running pending analysis check...", flush=True)
                    if 'creds' in locals():
                        retry_pending_analysis(db.session, creds)
                    
                    # --- RESERVATION LIFECYCLE MANAGEMENT ---
                    from app.models.reservation_by_name import ReservationByName
                    from app.models.reservation_by_config import ReservationByConfig
                    from datetime import datetime, timedelta
                    
                    now = datetime.utcnow()
                    two_days_ago = now - timedelta(hours=48)
                    one_day_ago = now - timedelta(hours=24)
                    
                    # 1. Auto-Release (Reserved -> Available after 48h)
                    res_name_to_release = ReservationByName.query.filter(
                        ReservationByName.status == 'reserved',
                        ReservationByName.created_at < two_days_ago
                    ).all()
                    for r in res_name_to_release:
                        r.status = 'available'
                    
                    res_config_to_release = ReservationByConfig.query.filter(
                        ReservationByConfig.status == 'reserved',
                        ReservationByConfig.created_at < two_days_ago
                    ).all()
                    for r in res_config_to_release:
                        r.status = 'available'
                    
                    # 2. Auto-Remove (Cancelled -> Deleted after 24h)
                    ReservationByName.query.filter(
                        ReservationByName.status == 'cancelled',
                        ReservationByName.cancelled_at < one_day_ago
                    ).delete()
                    
                    ReservationByConfig.query.filter(
                        ReservationByConfig.status == 'cancelled',
                        ReservationByConfig.cancelled_at < one_day_ago
                    ).delete()
                    
                    db.session.commit()
                    print("[Retry Scheduler] Reservation lifecycle cleanup complete.", flush=True)
                    # ----------------------------------------
            except Exception as exc:
                print(f"[Retry Scheduler] Unexpected error: {exc}", flush=True)
            time.sleep(_RETRY_INTERVAL_SECS)

    t = threading.Thread(target=_loop, name="ml-analysis-retry", daemon=True)
    t.start()
    print("[Retry Scheduler] Started — will retry pending analysis every 30 min.", flush=True)


def create_app(start_scheduler=True):
    flask_app = Flask(__name__)
    flask_app.config.from_object(Config)

    db.init_app(flask_app)
    login_manager.init_app(flask_app)
    migrate.init_app(flask_app, db)
    mail.init_app(flask_app)

    import app.models  # Ensure all SQLAlchemy models are registered for migrations.

    login_manager.login_view = "auth.login_page"

    import app.auth_utils  # <-- important

    flask_app.register_blueprint(auth)
    flask_app.register_blueprint(manager)
    flask_app.register_blueprint(engineer)
    flask_app.register_blueprint(bug)
    flask_app.register_blueprint(run_bp)

    # Start background ML analysis retry scheduler (30-min interval)
    if start_scheduler:
        _start_analysis_retry_scheduler(flask_app)

    return flask_app
