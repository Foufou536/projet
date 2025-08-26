from flask import Flask, render_template, request, redirect
import json
import os
from datetime import datetime, timedelta

app = Flask(__name__)

SUBSCRIBERS_FILE = 'subscribers.json'
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

# Autres fonctions existantes conservées (inchangées) :
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

@app.route("/")
def index():
    subscribers = load_subscribers()
    return render_template("index.html", subscriber_count=len(subscribers))

@app.route("/subscribe", methods=["POST"])
def subscribe():
    email = request.form.get("email", "").strip().lower()
    if "@" not in email or "." not in email:
        return "Adresse email invalide", 400

    subscribers = load_subscribers()
    if email in subscribers:
        return render_template("already_subscribed.html", subscriber_count=len(subscribers))
    else:
        subscribers.append(email)
        save_subscribers(subscribers)
        return render_template("success.html", subscriber_count=len(subscribers))

# ✅ Nouvelle route propre pour afficher la newsletter avec délai de 48h
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

if __name__ == "__main__":
    app.run(debug=True)

@app.route("/newsletter-test")
def newsletter_test():
    return app.send_static_file("newsletter_draft.html")