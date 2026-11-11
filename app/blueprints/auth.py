"""User & Account Management: login and logout routes only."""

from flask import Blueprint, flash, redirect, render_template, url_for

auth_bp = Blueprint("auth", __name__)


@auth_bp.get("/login")
def login():
    return render_template("auth/login.html")


@auth_bp.post("/login")
def login_submit():
    # Account management fills in credential checks and session creation.
    flash("Login is not implemented yet.")
    return redirect(url_for("auth.login"))


@auth_bp.post("/logout")
def logout():
    # Account management fills in session clearing.
    flash("Logout is not implemented yet.")
    return redirect(url_for("home"))
