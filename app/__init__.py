"""Know Book website shell. Module owners fill in blueprint logic later."""

import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, render_template

from app.blueprints.account import account_bp
from app.blueprints.auth import auth_bp
from app.blueprints.catalogue import catalogue_bp
from app.blueprints.desk import desk_bp
from app.blueprints.reservations import reservations_bp

ROOT = Path(__file__).resolve().parents[1]


def create_app():
    load_dotenv(ROOT / ".env")
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "knowbook-shell-secret")

    app.register_blueprint(auth_bp)
    app.register_blueprint(catalogue_bp)
    app.register_blueprint(account_bp)
    app.register_blueprint(desk_bp)
    app.register_blueprint(reservations_bp)

    @app.get("/")
    def home():
        return render_template("home.html")

    return app
