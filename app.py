from flask import Flask, render_template, request, redirect
from flask_sqlalchemy import SQLAlchemy
import json
import os
from datetime import datetime, timedelta

app = Flask(__name__)

# --- Configuration base de données ---
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# --- Modèle pour les abonnés ---
class Subscriber(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)

STATS_FILE = 'stats.json'
META_FILE = 'newsletter_meta.json'

# Charger le contenu de la newsletter (ancienne ou nouvelle selon la date)
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

# --- Routes ---
@app.route("/")
def index():
    total = Subscriber.query.count()
    return render_template("index.html", subscriber_count=total)

@app.route("/subscribe", methods=["POST"])
def subscribe():
    email = request.form.get("email", "").strip().lower()
    if "@" not in email or "." not in email:
        return "Adresse email invalide", 400

    existing = Subscriber.query.filter_by(email=email).first()
    if existing:
        return render_template("already_subscribed.html", subscriber_count=Subscriber.query.count())

    new_sub = Subscriber(email=email)
    db.session.add(new_sub)
    db.session.commit()

    return render_template("success.html", subscriber_count=Subscriber.query.count())

@app.route("/newsletter")
def newsletter():
    content = load_newsletter_content()
    return render_template("newsletter_page.html", newsletter_content=content)

@app.route("/stats")
def stats():
    try:
        total = Subscriber.query.count()
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            stats = json.load(f)
        return render_template("stats.html",
                               nb_abonnes=total,
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

# --- Création de la base au démarrage ---
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)