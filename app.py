import os
import json
import time
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash
from email_validator import validate_email, EmailNotValidError
from dotenv import load_dotenv
from flask_wtf.csrf import CSRFProtect, generate_csrf
import psycopg2
from psycopg2.extras import RealDictCursor

# ==========================
# 🔐 Chargement variables d'environnement
# ==========================
load_dotenv()

app = Flask(__name__)

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "motdepasse_par_defaut")
app.secret_key = os.getenv("SECRET_KEY", "cle_secrete_par_defaut")

# Activer la protection CSRF
csrf = CSRFProtect(app)

@app.context_processor
def inject_csrf_token():
    return dict(csrf_token=generate_csrf)

# ==========================
# 📁 Fichiers utilisés (pour les stats seulement)
# ==========================
STATS_FILE = 'stats.json'
META_FILE = 'newsletter_meta.json'

# ==========================
# 🗄️ Connexion PostgreSQL
# ==========================
DATABASE_URL = os.getenv("DATABASE_URL")  # ⚠️ doit être configuré sur Render et en local dans .env

def get_db_connection():
    return psycopg2.connect(DATABASE_URL, sslmode="require", cursor_factory=RealDictCursor)

# Création de la table si elle n’existe pas
def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS subscribers (
            id SERIAL PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            subscribed_at TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

init_db()

# ==========================
# 📩 Newsletter
# ==========================
def load_newsletter_content():
    use_new = False
    if os.path.exists(META_FILE):
        with open(META_FILE, "r", encoding="utf-8") as f:
            meta = json.load(f)
            sent_time = datetime.fromisoformat(meta.get("last_sent", "1970-01-01T00:00:00"))
            if datetime.now() >= sent_time + timedelta(hours=48):
                use_new = True

    filename = "newsletter_new.html" if use_new else "newsletter_content.html"
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "<p>La newsletter n'est pas encore disponible.</p>"

# ==========================
# 👥 Gestion abonnés via PostgreSQL
# ==========================
def load_subscribers():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT email FROM subscribers ORDER BY subscribed_at DESC")
    subscribers = [row["email"] for row in cur.fetchall()]
    cur.close()
    conn.close()
    return subscribers

def save_subscriber(email):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO subscribers (email) VALUES (%s) ON CONFLICT DO NOTHING", (email,))
        conn.commit()
    except Exception as e:
        print(f"Erreur insertion subscriber: {e}")
    finally:
        cur.close()
        conn.close()

def delete_subscriber_db(email):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM subscribers WHERE email = %s", (email,))
    conn.commit()
    cur.close()
    conn.close()

# ==========================
# 🌍 Routes publiques
# ==========================
@app.route("/")
def index():
    subscribers = load_subscribers()
    session["form_start_time"] = time.time()
    return render_template("index.html", subscriber_count=len(subscribers))

@app.route("/subscribe", methods=["POST"])
def subscribe():
    email = request.form.get("email", "").strip().lower()
    honeypot = request.form.get("website", "")

    if honeypot != "":
        return "Suspicious activity detected", 400

    start_time = session.get("form_start_time", 0)
    if time.time() - start_time < 2:
        return "Formulaire soumis trop rapidement", 400

    try:
        valid = validate_email(email)
        email = valid.email
    except EmailNotValidError:
        return "Adresse email invalide", 400

    subscribers = load_subscribers()
    if email in subscribers:
        return render_template("already_subscribed.html", subscriber_count=len(subscribers))
    else:
        save_subscriber(email)
        subscribers.append(email)  # pour l’affichage après ajout
        return render_template("success.html", subscriber_count=len(subscribers))

@app.route("/newsletter")
def newsletter():
    content = load_newsletter_content()
    return render_template("newsletter_page.html", newsletter_content=content)

@app.route("/stats")
def stats():
    try:
        subscribers = load_subscribers()
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            stats = json.load(f)
        return render_template("stats.html",
                               nb_abonnes=len(subscribers),
                               vues=stats.get("views", 0))
    except Exception as e:
        return f"Erreur lors de l'affichage des stats : {e}"

@app.route("/apropos")
def apropos():
    return render_template("apropos.html")

@app.route("/commercant")
def commercant():
    return render_template("commercant.html")

@app.route("/newsletter-test")
def newsletter_test():
    return app.send_static_file("newsletter_draft.html")
    
@app.route('/ads.txt')
def ads_txt():
    return app.send_static_file('ads.txt'), 200, {'Content-Type': 'text/plain'}

# ==========================
# 🔑 Interface Admin
# ==========================
login_attempts = {}

@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    user_ip = request.remote_addr
    now = datetime.now()

    if user_ip in login_attempts:
        login_attempts[user_ip] = [
            t for t in login_attempts[user_ip] if now - t < timedelta(minutes=10)
        ]

    if request.method == "POST":
        password = request.form.get("password")

        if user_ip in login_attempts and len(login_attempts[user_ip]) >= 5:
            flash("⛔ Trop de tentatives. Réessayez dans 10 minutes.", "danger")
            return redirect(url_for("admin_login"))

        if password == ADMIN_PASSWORD:
            session["admin"] = True
            session["last_active"] = time.time()
            flash("Connexion réussie ✅", "success")
            return redirect(url_for("admin_dashboard"))
        else:
            login_attempts.setdefault(user_ip, []).append(now)
            flash("Mot de passe incorrect ❌", "danger")
            return redirect(url_for("admin_login"))

    return render_template("admin_login.html")

@app.route("/admin/dashboard")
def admin_dashboard():
    if not session.get("admin"):
        flash("Accès refusé 🚫", "danger")
        return redirect(url_for("admin_login"))

    if time.time() - session.get("last_active", 0) > 600:
        session.clear()
        flash("Session expirée ⏳", "warning")
        return redirect(url_for("admin_login"))

    session["last_active"] = time.time()

    subscribers = load_subscribers()
    return render_template("admin_dashboard.html", subscribers=subscribers)

@app.route("/admin/delete/<email>", methods=["POST"])
def delete_subscriber(email):
    if not session.get("admin"):
        flash("Accès refusé 🚫", "danger")
        return redirect(url_for("admin_login"))

    delete_subscriber_db(email)
    flash(f"✅ {email} a été supprimé", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/logout")
def admin_logout():
    session.clear()
    flash("Déconnexion réussie 👋", "success")
    return redirect(url_for("admin_login"))