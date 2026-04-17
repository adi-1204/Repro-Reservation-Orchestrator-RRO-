from app.extensions import login_manager, mail
from app.models.user import User
from itsdangerous import URLSafeTimedSerializer
from flask_mail import Message
from flask import current_app, url_for, session, jsonify, request, redirect
from functools import wraps
from datetime import datetime, timedelta
import secrets


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


_tab_auth_sessions = {}


def _utcnow():
    return datetime.utcnow()


def _prune_expired_tab_auth_sessions():
    now = _utcnow()
    expired_tokens = [
        token
        for token, auth_session in _tab_auth_sessions.items()
        if auth_session["expires_at"] <= now
    ]
    for token in expired_tokens:
        _tab_auth_sessions.pop(token, None)


def create_tab_auth_session(user):
    _prune_expired_tab_auth_sessions()

    ttl_seconds = int(current_app.config.get("TAB_SESSION_TTL_SECONDS", 28800))
    token = secrets.token_urlsafe(32)
    _tab_auth_sessions[token] = {
        "user_id": user.id,
        "role": user.role,
        "expires_at": _utcnow() + timedelta(seconds=ttl_seconds),
    }
    return token


def revoke_tab_auth_session(token):
    if not token:
        return
    _tab_auth_sessions.pop(token, None)


def get_request_auth_token():
    header_token = request.headers.get("X-RRO-Auth-Token", "").strip()
    if header_token:
        return header_token

    query_token = request.args.get("auth_token", "").strip()
    if query_token:
        return query_token

    return None


def get_auth_context():
    token = get_request_auth_token()

    if token is not None:
        _prune_expired_tab_auth_sessions()
        auth_session = _tab_auth_sessions.get(token)
        if not auth_session:
            return None

        user = User.query.get(auth_session["user_id"])
        if not user or user.role != auth_session["role"]:
            revoke_tab_auth_session(token)
            return None

        return {
            "user": user,
            "user_id": user.id,
            "role": user.role,
            "auth_token": token,
            "source": "tab-token",
        }

    if "user_id" not in session:
        return None

    user = User.query.get(session["user_id"])
    if not user:
        session.clear()
        return None

    return {
        "user": user,
        "user_id": user.id,
        "role": session.get("role") or user.role,
        "auth_token": None,
        "source": "cookie-session",
    }


def get_current_user():
    context = get_auth_context()
    return context["user"] if context else None


def get_current_user_id():
    context = get_auth_context()
    return context["user_id"] if context else None


def get_current_role():
    context = get_auth_context()
    return context["role"] if context else None


def get_current_auth_token():
    context = get_auth_context()
    return context["auth_token"] if context else None


#  FIX 4: Role-enforcement decorators.
# Every sensitive route MUST use these instead of only checking "user_id in session".
# This closes the hole where an engineer could POST to /api/workgroups (manager-only).

def login_required(f):
    """Blocks any unauthenticated request."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not get_auth_context():
            if request.method == "GET" and not request.path.startswith("/api/"):
                return redirect(url_for("auth.login"))
            return jsonify({"error": "Not logged in"}), 401
        return f(*args, **kwargs)
    return decorated


def manager_required(f):
    """Blocks anyone who is not a Manager — even if they are logged in."""
    @wraps(f)
    def decorated(*args, **kwargs):
        context = get_auth_context()
        if not context:
            return jsonify({"error": "Not logged in"}), 401
        if context["role"] != "Manager":
            return jsonify({"error": "Access denied: Manager role required"}), 403
        return f(*args, **kwargs)
    return decorated


def engineer_required(f):
    """Blocks anyone who is not an Engineer — even if they are logged in."""
    @wraps(f)
    def decorated(*args, **kwargs):
        context = get_auth_context()
        if not context:
            return jsonify({"error": "Not logged in"}), 401
        if context["role"] != "Engineer":
            return jsonify({"error": "Access denied: Engineer role required"}), 403
        return f(*args, **kwargs)
    return decorated


# ── Password reset helpers ────────────────────────────────────────────────────

def generate_reset_token(email):
    serializer = URLSafeTimedSerializer(current_app.config['SERIALIZER_SECRET_KEY'])
    return serializer.dumps(email, salt='password-reset-salt')


def verify_reset_token(token, max_age=1800):
    serializer = URLSafeTimedSerializer(current_app.config['SERIALIZER_SECRET_KEY'])
    try:
        email = serializer.loads(token, salt='password-reset-salt', max_age=max_age)
    except Exception:
        return None
    return email


def send_reset_email(user):
    token = generate_reset_token(user.email)
    reset_url = url_for('auth.reset_password', token=token, _external=True)

    msg = Message(
        subject='RRO Platform — Password Reset Request',
        recipients=[user.email],
        html=(
            f'<p>Hi {user.first_name},</p>'
            f'<p>Click the link below to reset your password. '
            f'This link expires in 30 minutes.</p>'
            f'<p><a href="{reset_url}">{reset_url}</a></p>'
            f'<p>If you did not request this, ignore this email.</p>'
        )
    )
    mail.send(msg)
