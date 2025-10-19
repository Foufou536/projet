import os
import json
import time
from datetime import datetime, timedelta, date
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from email_validator import validate_email, EmailNotValidError
from dotenv import load_dotenv
from flask_wtf.csrf import CSRFProtect, generate_csrf
import psycopg2
from psycopg2.extras import RealDictCursor
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import re

# ==========================
# 🔐 Chargement variables d'environnement
# ==========================
load_dotenv()

app = Flask(__name__)

# MOT DE PASSE ADMIN depuis variable d'environnement
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin2025")

app.secret_key = os.getenv("SECRET_KEY", "cle_secrete_par_defaut_123456")

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
DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    return psycopg2.connect(DATABASE_URL, sslmode="require", cursor_factory=RealDictCursor)

# Création des tables
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
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            company_name TEXT NOT NULL,
            phone TEXT,
            status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
            created_at TIMESTAMP DEFAULT NOW(),
            approved_at TIMESTAMP
        )
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS submissions (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            image_url TEXT,
            link_url TEXT,
            category TEXT DEFAULT 'general',
            status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'scheduled', 'published')),
            created_at TIMESTAMP DEFAULT NOW(),
            scheduled_for DATE,
            published_at TIMESTAMP
        )
    """)
    
    conn.commit()
    cur.close()
    conn.close()

init_db()

# ==========================
# 🛡️ Décorateurs d'authentification
# ==========================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Vous devez être connecté pour accéder à cette page.", "warning")
            return redirect(url_for('user_login'))
        return f(*args, **kwargs)
    return decorated_function

def approved_user_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('user_login'))
        
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT status FROM users WHERE id = %s", (session['user_id'],))
        user = cur.fetchone()
        cur.close()
        conn.close()
        
        if not user or user['status'] != 'approved':
            flash("Votre compte doit être approuvé pour accéder à cette fonctionnalité.", "warning")
            return redirect(url_for('user_dashboard'))
        return f(*args, **kwargs)
    return decorated_function

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
# 👥 Gestion abonnés
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
        subscribers.append(email)
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
# 🔐 Authentification utilisateurs
# ==========================
@app.route("/register", methods=["GET", "POST"])
def user_register():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()
        company_name = request.form.get("company_name", "").strip()
        phone = request.form.get("phone", "").strip()
        
        if not email or not password or not company_name:
            flash("Tous les champs obligatoires doivent être remplis.", "error")
            return render_template("auth/register.html")
        
        if len(password) < 6:
            flash("Le mot de passe doit contenir au moins 6 caractères.", "error")
            return render_template("auth/register.html")
        
        try:
            validate_email(email)
        except EmailNotValidError:
            flash("Adresse email invalide.", "error")
            return render_template("auth/register.html")
        
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cur.fetchone():
            flash("Un compte existe déjà avec cette adresse email.", "error")
            cur.close()
            conn.close()
            return render_template("auth/register.html")
        
        password_hash = generate_password_hash(password)
        cur.execute("""
            INSERT INTO users (email, password_hash, company_name, phone)
            VALUES (%s, %s, %s, %s)
        """, (email, password_hash, company_name, phone))
        conn.commit()
        cur.close()
        conn.close()
        
        flash("Inscription réussie ! Votre compte sera examiné sous peu.", "success")
        return redirect(url_for('user_login'))
    
    return render_template("auth/register.html")

@app.route("/login", methods=["GET", "POST"])
def user_login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()
        
        if not email or not password:
            flash("Email et mot de passe requis.", "error")
            return render_template("auth/login.html")
        
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, password_hash, status FROM users WHERE email = %s", (email,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['user_email'] = email
            flash("Connexion réussie !", "success")
            return redirect(url_for('user_dashboard'))
        else:
            flash("Email ou mot de passe incorrect.", "error")
    
    return render_template("auth/login.html")

@app.route("/logout")
def user_logout():
    session.pop('user_id', None)
    session.pop('user_email', None)
    flash("Déconnexion réussie.", "info")
    return redirect(url_for('index'))

@app.route("/dashboard")
@login_required
def user_dashboard():
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT * FROM users WHERE id = %s", (session['user_id'],))
    user = cur.fetchone()
    
    cur.execute("""
        SELECT * FROM submissions 
        WHERE user_id = %s 
        ORDER BY created_at DESC
    """, (session['user_id'],))
    submissions = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return render_template("auth/dashboard.html", user=user, submissions=submissions)

# ==========================
# 📝 Système de soumissions
# ==========================
@app.route("/submit", methods=["GET", "POST"])
@approved_user_required
def submit_newsletter():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        image_url = request.form.get("image_url", "").strip()
        link_url = request.form.get("link_url", "").strip()
        category = request.form.get("category", "general")
        
        if not title or not description:
            flash("Titre et description sont obligatoires.", "error")
            return render_template("submission/create.html")
        
        url_pattern = re.compile(r'^https?://')
        if image_url and not url_pattern.match(image_url):
            flash("L'URL de l'image doit commencer par http:// ou https://", "error")
            return render_template("submission/create.html")
        
        if link_url and not url_pattern.match(link_url):
            flash("L'URL du lien doit commencer par http:// ou https://", "error")
            return render_template("submission/create.html")
        
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO submissions (user_id, title, description, image_url, link_url, category)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (session['user_id'], title, description, image_url, link_url, category))
        conn.commit()
        cur.close()
        conn.close()
        
        flash("Votre soumission a été envoyée ! Elle sera examinée prochainement.", "success")
        return redirect(url_for('user_dashboard'))
    
    return render_template("submission/create.html")

@app.route("/edit_submission/<int:submission_id>", methods=["GET", "POST"])
@approved_user_required
def edit_submission(submission_id):
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT * FROM submissions WHERE id = %s AND user_id = %s", (submission_id, session['user_id']))
    submission = cur.fetchone()
    
    if not submission:
        flash("Soumission introuvable", "error")
        cur.close()
        conn.close()
        return redirect(url_for('user_dashboard'))
    
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        image_url = request.form.get("image_url", "").strip()
        link_url = request.form.get("link_url", "").strip()
        category = request.form.get("category", "general")
        
        cur.execute("""
            UPDATE submissions 
            SET title = %s, description = %s, image_url = %s, link_url = %s, category = %s
            WHERE id = %s
        """, (title, description, image_url, link_url, category, submission_id))
        conn.commit()
        cur.close()
        conn.close()
        
        flash("Soumission modifiée avec succès", "success")
        return redirect(url_for('user_dashboard'))
    
    cur.close()
    conn.close()
    return render_template("submission/edit.html", submission=submission)

@app.route("/delete_submission/<int:submission_id>", methods=["POST"])
@login_required
def delete_submission(submission_id):
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Vérifier que la soumission appartient bien à l'utilisateur
    cur.execute("SELECT * FROM submissions WHERE id = %s AND user_id = %s", (submission_id, session['user_id']))
    submission = cur.fetchone()
    
    if not submission:
        flash("Soumission introuvable ou vous n'avez pas l'autorisation", "error")
        cur.close()
        conn.close()
        return redirect(url_for('user_dashboard'))
    
    # Supprimer la soumission
    cur.execute("DELETE FROM submissions WHERE id = %s", (submission_id,))
    conn.commit()
    cur.close()
    conn.close()
    
    flash("🗑️ Soumission supprimée avec succès", "success")
    return redirect(url_for('user_dashboard'))

# ==========================
# 🔧 Fonction helper
# ==========================
def generate_html_code(submissions):
    html = ""
    for sub in submissions:
        html += f'''
    <div style="border: 1px solid #ddd; padding: 20px; border-radius: 8px; margin-bottom: 20px; display: flex; gap: 20px; align-items: flex-start;">
        <div style="flex: 1;">
            <span style="color: #007bff; font-weight: bold; font-size: 12px;">{sub["category"].upper()}</span>
            <h4 style="margin: 5px 0 10px; color: #333;">{sub["title"]}</h4>
            <p style="margin: 0 0 10px; color: #666;">{sub["description"]}</p>
'''
        if sub.get("link_url"):
            html += f'            <a href="{sub["link_url"]}" style="background-color: #007bff; color: white; padding: 8px 16px; text-decoration: none; border-radius: 4px; display: inline-block;">Lire la suite</a>\n'
        
        html += '        </div>\n'
        
        if sub.get("image_url"):
            html += f'        <img src="{sub["image_url"]}" style="width: 180px; height: auto; border-radius: 8px;" alt="{sub["title"]}">\n'
        
        html += '    </div>\n'
    
    return html

@app.context_processor
def utility_processor():
    return dict(generate_html_code=generate_html_code)

# ==========================
# 🔑 Interface Admin SIMPLIFIÉE
# ==========================
@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        password = request.form.get("password", "")
        
        print(f"🔍 DEBUG - Password reçu: '{password}'")
        print(f"🔍 DEBUG - Password attendu: '{ADMIN_PASSWORD}'")
        
        if password == ADMIN_PASSWORD:
            session["admin"] = True
            session["last_active"] = time.time()
            flash("✅ Connexion réussie", "success")
            return redirect(url_for("admin_dashboard"))
        else:
            flash("❌ Mot de passe incorrect", "danger")
            return redirect(url_for("admin_login"))
    
    return render_template("admin_login.html")

@app.route("/admin/dashboard")
def admin_dashboard():
    if not session.get("admin"):
        flash("🚫 Accès refusé", "danger")
        return redirect(url_for("admin_login"))

    if time.time() - session.get("last_active", 0) > 3600:
        session.clear()
        flash("⏳ Session expirée", "warning")
        return redirect(url_for("admin_login"))

    session["last_active"] = time.time()

    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT COUNT(*) as count FROM subscribers")
    subscriber_count = cur.fetchone()['count']
    
    cur.execute("SELECT COUNT(*) as count FROM users WHERE status = 'pending'")
    pending_users = cur.fetchone()['count']
    
    cur.execute("SELECT COUNT(*) as count FROM submissions WHERE status = 'pending'")
    pending_submissions = cur.fetchone()['count']
    
    cur.execute("SELECT email FROM subscribers ORDER BY subscribed_at DESC")
    subscribers = [row["email"] for row in cur.fetchall()]
    
    cur.execute("""
        SELECT u.*, 
               (SELECT COUNT(*) FROM submissions s WHERE s.user_id = u.id) as submission_count
        FROM users u 
        ORDER BY u.created_at DESC
    """)
    users = cur.fetchall()
    
    cur.execute("""
        SELECT s.*, u.email as user_email, u.company_name 
        FROM submissions s
        JOIN users u ON s.user_id = u.id
        ORDER BY s.created_at DESC
    """)
    submissions = cur.fetchall()
    
    cur.close()
    conn.close()

    return render_template("admin/dashboard.html", 
                         subscribers=subscribers,
                         users=users,
                         submissions=submissions,
                         stats={
                             'subscriber_count': subscriber_count,
                             'pending_users': pending_users,
                             'pending_submissions': pending_submissions
                         })

@app.route("/admin/generate_newsletter")
def generate_newsletter():
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT s.*, u.company_name 
        FROM submissions s
        JOIN users u ON s.user_id = u.id
        WHERE s.status = 'approved'
        ORDER BY s.category, s.created_at DESC
    """)
    submissions = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return render_template("admin/generate_newsletter.html", submissions=submissions)

@app.route("/admin/approve_user/<int:user_id>", methods=["POST"])
def approve_user(user_id):
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET status = 'approved', approved_at = NOW() WHERE id = %s", (user_id,))
    conn.commit()
    cur.close()
    conn.close()
    
    flash("✅ Utilisateur approuvé", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/reject_user/<int:user_id>", methods=["POST"])
def reject_user(user_id):
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET status = 'rejected' WHERE id = %s", (user_id,))
    conn.commit()
    cur.close()
    conn.close()
    
    flash("❌ Utilisateur rejeté", "info")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/approve_submission/<int:submission_id>", methods=["POST"])
def approve_submission(submission_id):
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE submissions SET status = 'approved' WHERE id = %s", (submission_id,))
    conn.commit()
    cur.close()
    conn.close()
    
    flash("✅ Soumission approuvée", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/reject_submission/<int:submission_id>", methods=["POST"])
def reject_submission(submission_id):
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE submissions SET status = 'rejected' WHERE id = %s", (submission_id,))
    conn.commit()
    cur.close()
    conn.close()
    
    flash("Soumission rejetée", "info")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/delete/<email>", methods=["POST"])
def delete_subscriber(email):
    if not session.get("admin"):
        flash("🚫 Accès refusé", "danger")
        return redirect(url_for("admin_login"))

    delete_subscriber_db(email)
    flash(f"✅ {email} supprimé", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/logout")
def admin_logout():
    session.clear()
    flash("👋 Déconnexion réussie", "success")
    return redirect(url_for("admin_login"))

if __name__ == "__main__":
    app.run(debug=True)