import os
import uuid
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.utils import secure_filename
from functools import wraps
from datetime import timedelta

from auth.iam import IAMManager
from mapreduce.engine import MapReduceEngine
from db.database import DatabaseManager

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-prod")
app.permanent_session_lifetime = timedelta(hours=2)

UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"log", "txt"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50MB max

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

iam = IAMManager()
db = DatabaseManager()


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access the dashboard.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Authentication required.", "warning")
            return redirect(url_for("login"))
        if not session.get("is_admin"):
            flash("Admin privileges required.", "danger")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return decorated_function


# ─── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = iam.authenticate(username, password)
        if user:
            session.permanent = True
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["is_admin"] = user["is_admin"]
            db.log_audit(user["id"], "LOGIN", "User logged in")
            flash(f"Welcome back, {user['username']}!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid credentials. Please try again.", "danger")
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    db.log_audit(session["user_id"], "LOGOUT", "User logged out")
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    analyses = db.get_recent_analyses(limit=10)
    return render_template("dashboard.html",
                           username=session["username"],
                           is_admin=session.get("is_admin"),
                           analyses=analyses)


@app.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    if request.method == "POST":
        if "logfile" not in request.files:
            flash("No file selected.", "warning")
            return redirect(request.url)
        file = request.files["logfile"]
        if file.filename == "":
            flash("No file selected.", "warning")
            return redirect(request.url)
        if not allowed_file(file.filename):
            flash("Only .log and .txt files are allowed.", "danger")
            return redirect(request.url)

        filename = secure_filename(file.filename)
        unique_name = f"{uuid.uuid4().hex}_{filename}"
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], unique_name)
        file.save(filepath)

        # Run MapReduce
        engine = MapReduceEngine(filepath)
        results = engine.run()

        # Persist to DB
        analysis_id = db.save_analysis(
            user_id=session["user_id"],
            filename=filename,
            results=results
        )
        db.log_audit(session["user_id"], "UPLOAD", f"Processed file: {filename}")

        # Clean up upload
        try:
            os.remove(filepath)
        except Exception:
            pass

        flash("Log file processed successfully!", "success")
        return redirect(url_for("results", analysis_id=analysis_id))

    return render_template("upload.html", username=session["username"])


@app.route("/results/<analysis_id>")
@login_required
def results(analysis_id):
    analysis = db.get_analysis(analysis_id)
    if not analysis:
        flash("Analysis not found.", "warning")
        return redirect(url_for("dashboard"))
    return render_template("results.html",
                           analysis=analysis,
                           username=session["username"])


@app.route("/history")
@login_required
def history():
    analyses = db.get_all_analyses()
    return render_template("history.html",
                           analyses=analyses,
                           username=session["username"])


@app.route("/audit-log")
@admin_required
def audit_log():
    logs = db.get_audit_log()
    return render_template("audit.html",
                           logs=logs,
                           username=session["username"])


@app.route("/api/analysis/<analysis_id>")
@login_required
def api_analysis(analysis_id):
    analysis = db.get_analysis(analysis_id)
    if not analysis:
        return jsonify({"error": "Not found"}), 404
    return jsonify(analysis)


@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "Cloud Log Analyzer"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
