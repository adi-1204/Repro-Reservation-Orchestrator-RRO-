from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db
from app.models.user import User
from app.auth_utils import (
    create_tab_auth_session,
    generate_reset_token,
    get_auth_context,
    get_request_auth_token,
    revoke_tab_auth_session,
    verify_reset_token,
    send_reset_email,
)

auth = Blueprint('auth', __name__)

# ---------------- LOGIN ----------------
@auth.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            #  FIX 1: Always clear the session before setting new user data.
            # This prevents stale role/user_id from a previous login persisting
            # when two users log in sequentially in the same browser tab.
            session.clear()

            session['user_id'] = user.id
            session['role'] = user.role
            #  FIX 2: Make the session permanent and bind it tightly
            session.permanent = True

            auth_token = create_tab_auth_session(user)

            if user.role == "Engineer":
                return redirect(url_for('engineer.engineer_dashboard', auth_token=auth_token))
            elif user.role == "Manager":
                return redirect(url_for('manager.manager_dashboard', auth_token=auth_token))
            else:
                flash(f"Unknown role: {user.role}", "danger")
        else:
            flash("Invalid Email or Password", "danger")

    return render_template("login.html")


# ---------------- REGISTER ----------------
@auth.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        role = request.form['role']
        email = request.form['email']
        password_raw = request.form['password']
        confirm_password = request.form['confirm_password']

        if password_raw != confirm_password:
            flash("Passwords do not match!", "danger")
            return redirect(url_for('auth.register'))

        if len(password_raw) < 6:
            flash("Password must be at least 6 characters", "danger")
            return redirect(url_for('auth.register'))

        existing_user = User.query.filter_by(email=email).first()

        if existing_user:
            flash("Email already registered", "danger")
            return redirect(url_for('auth.register'))
        else:
            hashed_password = generate_password_hash(password_raw)

            new_user = User(
                first_name=first_name,
                last_name=last_name,
                email=email,
                password=hashed_password,
                role=role
            )

            db.session.add(new_user)
            db.session.flush() # flush to get new_user.id
            
            # Map bugs to this newly registered engineer
            if role == 'Engineer':
                from app.models.bug import Bug
                Bug.query.filter_by(assignee_email=email).update({"engineer_id": new_user.id})
                
            db.session.commit()

            flash("Account created successfully! Please sign in.", "success")
            return redirect(url_for('auth.login'))

    return render_template("register.html")


# ---------------- FORGOT PASSWORD ----------------
@auth.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        user = User.query.filter_by(email=email).first()

        if not user:
            flash("Account doesn't exist. Please check the email address or register.", "danger")
            return render_template("forgot_password.html")

        try:
            send_reset_email(user)
        except Exception as e:
            print(f"EMAIL ERROR: {e}")
            flash("Unable to send email. Please try again later.", "danger")
            return render_template("forgot_password.html")

        flash("Reset link sent! Please check your inbox (and spam folder) for the password reset email.", "success")
        return redirect(url_for('auth.forgot_password'))

    return render_template("forgot_password.html")


# ---------------- RESET PASSWORD ----------------
@auth.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    email = verify_reset_token(token)
    if email is None:
        flash("The reset link is invalid or has expired.", "danger")
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            flash("Passwords do not match!", "danger")
            return render_template("reset_password.html", token=token)

        user = User.query.filter_by(email=email).first()
        if user is None:
            flash("User not found.", "danger")
            return redirect(url_for('auth.forgot_password'))

        user.password = generate_password_hash(password)
        db.session.commit()

        flash("Your password has been reset successfully!", "success")
        return redirect(url_for('auth.login'))

    return render_template("reset_password.html", token=token)


# ---------------- SHARED: Current User (used by both dashboards) ----------------
@auth.route("/api/auth/me", methods=["GET"])
def get_current_user():
    """
     FIX 3: Moved /api/auth/me to the AUTH blueprint (neutral ground).
    Previously it lived on the manager blueprint, so engineer dashboards
    calling this endpoint were reading the manager's session context.
    """
    context = get_auth_context()
    if not context:
        return {"error": "Not logged in"}, 401

    user = context["user"]

    return {
        "id": user.id,
        "name": user.first_name,
        "fullName": f"{user.first_name} {user.last_name}",
        "email": user.email,
        "role": user.role
    }


# ---------------- SHARED: Logout ----------------
@auth.route("/api/auth/logout", methods=["POST"])
def logout():
    revoke_tab_auth_session(get_request_auth_token())
    session.clear()
    return {"message": "Logged out"}
