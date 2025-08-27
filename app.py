from flask import Flask, render_template, request, redirect, url_for, session
import json
import os
from datetime import datetime, timedelta
from email_validator import validate_email, EmailNotValidError  # ✅ ajout validation email

app = Flask(__name__)
app.secret_key = "xbKcrhToXM4iJtRKNA@zRbFLcnF7M!J@dnmLyQMx"  # ⚠️ Mets un mot de passe fort ici

SUBSCRIBERS_FILE = 'subscribers.json'
STATS_FILE = 'stats.json'
META_FILE = 'newsletter_meta.json'

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
    if not os.path.exists(SUBSCRIBERS_FILE):
        return []
    with open(SUBSCRIBERS_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []

def save_subscribers(subscribers):
    with open(SUBSCRIBERS_FILE, "w", encoding="utf-8") as f:
        json.dump(subscribers, f, indent=2)

# ==========================
# 🌍 Routes publiques
# ==========================
@app.route("/")
def index():
    subscribers = load_subscribers()
    return render_template("index.html", subscriber_count=len(subscribers))

@app.route("/subscribe", methods=["POST"])
def subscribe():
    email = request.form.get("email", "").strip().lower()

    # ✅ Validation stricte de l'email
    try:
        valid = validate_email(email)
        email = valid.email  # normalisation (ex: suppression d’espaces, accents, etc.)
    except EmailNotValidError:
        return "Adresse email invalide", 400

    subscribers = load_subscribers()
    if email in subscribers:
        return render_template("already_subscribed.html", subscriber_count=len(subscribers))
    else:
        subscribers.append(email)
        save_subscribers(subscribers)
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

# ==========================
# 🔑 Interface Admin
# ==========================
ADMIN_PASSWORD = "o3krs@ipcQ@E88mTNFo5boiok#M!BiXb7c4D$f#g"  # ⚠️ Change ça avant de mettre en ligne

@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        password = request.form.get("password")
        if password == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect(url_for("admin_dashboard"))
        else:
            return "Mot de passe incorrect", 403
    return """
        <form method="post">
            <input type="password" name="password" placeholder="Mot de passe admin" required>
            <button type="submit">Connexion</button>
        </form>
    """

@app.route("/admin/dashboard")
def admin_dashboard():
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    subscribers = load_subscribers()
    return """
        <h1>Gestion des abonnés</h1>
        <ul>
        """ + "".join(
            f"<li>{email} <a href='/admin/delete/{email}'>❌ Supprimer</a></li>"
            for email in subscribers
        ) + "</ul>"

@app.route("/admin/delete/<email>")
def admin_delete(email):
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    subscribers = load_subscribers()
    if email in subscribers:
        subscribers.remove(email)
        save_subscribers(subscribers)
    return redirect(url_for("admin_dashboard"))