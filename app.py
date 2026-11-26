"""Tier 2: Flask REST API for the secure three-tier capstone."""
import datetime
import logging
import re
from functools import wraps
from logging.handlers import RotatingFileHandler

import jwt
from dotenv import load_dotenv
from flask import Flask, g, jsonify, request, send_from_directory
import os
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_sqlalchemy import SQLAlchemy
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()
from config import Config, DEFAULT_SECRET  # noqa: E402

db = SQLAlchemy()
limiter = Limiter(key_func=get_remote_address)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)


class Note(db.Model):
    __tablename__ = "notes"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    content = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)


def setup_logging(app):
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handlers = [logging.StreamHandler()]
    if app.config["LOG_FILE"]:
        handlers.append(RotatingFileHandler(app.config["LOG_FILE"], maxBytes=2_000_000, backupCount=3))
    app.logger.handlers.clear()
    for h in handlers:
        h.setFormatter(fmt)
        app.logger.addHandler(h)
    app.logger.setLevel(logging.INFO)


def create_app(overrides=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if overrides:
        app.config.update(overrides)
    if not app.testing and app.config["SECRET_KEY"] == DEFAULT_SECRET:
        raise RuntimeError("Set a strong SECRET_KEY environment variable before starting.")
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)  # trust nginx's X-Forwarded-For
    setup_logging(app)
    db.init_app(app)
    limiter.init_app(app)
    limiter.enabled = not app.testing

    def make_token(user):
        exp = datetime.datetime.utcnow() + datetime.timedelta(hours=app.config["TOKEN_HOURS"])
        return jwt.encode({"sub": str(user.id), "exp": exp}, app.config["SECRET_KEY"], algorithm="HS256")

    def login_required(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            header = request.headers.get("Authorization", "")
            if not header.startswith("Bearer "):
                return jsonify(error="Missing token"), 401
            try:
                data = jwt.decode(header[7:], app.config["SECRET_KEY"], algorithms=["HS256"])
                g.user = db.session.get(User, int(data["sub"]))
            except (jwt.PyJWTError, ValueError):
                return jsonify(error="Invalid or expired token"), 401
            if g.user is None:
                return jsonify(error="User not found"), 401
            return fn(*a, **kw)
        return wrapper

    @app.after_request
    def security_headers(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.get("/api/health")
    def health():
        try:
            db.session.execute(db.text("SELECT 1"))
            return jsonify(status="ok", database="up")
        except Exception:
            app.logger.exception("health check: database unreachable")
            return jsonify(status="degraded", database="down"), 503

    @app.post("/api/register")
    @limiter.limit("10/hour")
    def register():
        d = request.get_json(silent=True) or {}
        name = str(d.get("name", "")).strip()
        email = str(d.get("email", "")).strip().lower()
        pw = str(d.get("password", ""))
        if not (2 <= len(name) <= 80):
            return jsonify(error="Name must be 2-80 characters"), 400
        if not EMAIL_RE.match(email) or len(email) > 120:
            return jsonify(error="Enter a valid email"), 400
        if len(pw) < 8 or not re.search(r"[A-Za-z]", pw) or not re.search(r"\d", pw):
            return jsonify(error="Password needs 8+ characters with letters and a number"), 400
        if User.query.filter_by(email=email).first():
            return jsonify(error="Email already registered"), 409
        user = User(name=name, email=email, password_hash=generate_password_hash(pw))
        db.session.add(user)
        db.session.commit()
        app.logger.info("REGISTER ok user_id=%s ip=%s", user.id, request.remote_addr)
        return jsonify(message="Account created"), 201

    @app.post("/api/login")
    @limiter.limit("5/minute")
    def login():
        d = request.get_json(silent=True) or {}
        email = str(d.get("email", "")).strip().lower()
        user = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.password_hash, str(d.get("password", ""))):
            app.logger.warning("LOGIN failed email=%s ip=%s", email[:60], request.remote_addr)
            return jsonify(error="Invalid email or password"), 401
        app.logger.info("LOGIN ok user_id=%s ip=%s", user.id, request.remote_addr)
        return jsonify(token=make_token(user), user={"name": user.name, "email": user.email})

    @app.get("/api/me")
    @login_required
    def me():
        return jsonify(name=g.user.name, email=g.user.email)

    @app.get("/api/notes")
    @login_required
    def list_notes():
        rows = Note.query.filter_by(user_id=g.user.id).order_by(Note.id.desc()).all()
        return jsonify([{"id": n.id, "content": n.content, "created_at": n.created_at.isoformat()} for n in rows])

    @app.post("/api/notes")
    @login_required
    def add_note():
        text = str((request.get_json(silent=True) or {}).get("content", "")).strip()
        if not 1 <= len(text) <= 500:
            return jsonify(error="Note must be 1-500 characters"), 400
        n = Note(user_id=g.user.id, content=text)
        db.session.add(n)
        db.session.commit()
        return jsonify(id=n.id, content=n.content), 201

    @app.delete("/api/notes/<int:note_id>")
    @login_required
    def delete_note(note_id):
        n = Note.query.filter_by(id=note_id, user_id=g.user.id).first()  # owner check
        if not n:
            return jsonify(error="Not found"), 404
        db.session.delete(n)
        db.session.commit()
        return jsonify(message="Deleted")

    @app.errorhandler(429)
    def too_many(_):
        return jsonify(error="Too many attempts. Try again later."), 429

    @app.errorhandler(500)
    def server_error(_):
        return jsonify(error="Internal server error"), 500

        # Serve frontend files
    frontend_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "frontend")
    )

    @app.get("/")
    def home():
        return send_from_directory(frontend_dir, "index.html")

    @app.get("/<path:filename>")
    def frontend_files(filename):
        return send_from_directory(frontend_dir, filename)

    with app.app_context():
        db.create_all()

    return app
