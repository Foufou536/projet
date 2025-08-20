import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Charger les emails depuis subscribers.json
with open("subscribers.json", "r") as file:
    subscribers = json.load(file)

# Charger le contenu HTML de la newsletter
with open("email_newsletter.html", "r", encoding="utf-8") as f:
    newsletter_html = f.read()

# Config mail
EMAIL = "lesbonnesaffairesaurillac@gmail.com"
PASSWORD = "lpef rbys duiq orvz"
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# Envoi de la newsletter à chaque abonné
with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
    server.starttls()
    server.login(EMAIL, PASSWORD)
    
    for recipient in subscribers:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "📰 Votre Newsletter Hebdo"
        msg["From"] = EMAIL
        msg["To"] = recipient

        # Ajouter le contenu HTML (images hébergées en ligne)
        html_part = MIMEText(newsletter_html, "html")
        msg.attach(html_part)

        server.sendmail(EMAIL, recipient, msg.as_string())
        print(f"✅ Newsletter envoyée à {recipient}")
