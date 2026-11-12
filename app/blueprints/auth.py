"""User & Account Management: login, logout and access checks."""

from datetime import timedelta
from functools import wraps

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash

from common.db import connect

auth_bp = Blueprint("auth", __name__)


def _safe_next(value):
    if value and value.startswith("/") and not value.startswith("//"):
        return value
    return None


def login_required(view):
    """Send anonymous visitors to /login. Week 5 session style, not Flask-Login."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in.")
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def role_required(*roles):
    """Require an authenticated user whose role is one of ``roles``."""

    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if session.get("role") not in roles:
                flash("You do not have permission to view that page.")
                if session.get("role") == "librarian":
                    return redirect(url_for("desk.index"))
                return redirect(url_for("catalogue.index"))
            return view(*args, **kwargs)

        return wrapped

    return decorator


def librarian_required(view):
    return role_required("librarian")(view)


@auth_bp.record_once
def _configure_sessions(state):
    state.app.config.setdefault("PERMANENT_SESSION_LIFETIME", timedelta(minutes=60))


@auth_bp.app_context_processor
def inject_current_user():
    if not session.get("user_id"):
        return {"current_user": None}
    return {
        "current_user": {
            "user_id": session.get("user_id"),
            "username": session.get("username"),
            "role": session.get("role"),
            "reader_category": session.get("reader_category"),
        }
    }


def _find_user(username):
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT user_id, username, password_hash, role, reader_category
            FROM user
            WHERE username = %s
            """,
            (username,),
        )
        return cursor.fetchone()


@auth_bp.get("/login")
def login():
    next_url = _safe_next(request.args.get("next")) or ""
    if session.get("user_id"):
        return redirect(next_url or url_for("home"))
    return render_template("auth/login.html", username="", next_url=next_url)


@auth_bp.post("/login")
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    next_url = _safe_next(request.form.get("next") or request.args.get("next")) or ""
    try:
        user = _find_user(username)
    except Exception as exc:
        flash(f"Could not reach the database: {exc}")
        return render_template("auth/login.html", username=username, next_url=next_url), 503

    password_matches = False
    if user:
        password_matches = check_password_hash(user["password_hash"], password)
    if not password_matches:
        flash("Username or password is incorrect.")
        return render_template("auth/login.html", username=username, next_url=next_url), 401

    session.clear()
    session.permanent = True
    session["user_id"] = user["user_id"]
    session["username"] = user["username"]
    session["role"] = user["role"]
    session["reader_category"] = user["reader_category"]
    current_app.logger.info("login success user_id=%s", user["user_id"])

    if next_url:
        return redirect(next_url, code=303)
    if user["role"] == "librarian":
        return redirect(url_for("desk.index"), code=303)
    return redirect(url_for("catalogue.index"), code=303)


@auth_bp.post("/logout")
def logout():
    session.clear()
    flash("You have been logged out.")
    return redirect(url_for("home"), code=303)
