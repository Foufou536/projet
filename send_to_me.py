import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# 🔑 Mets ton email et ton mot de passe/clé d'application Gmail
MY_EMAIL = "lesbonnesaffairesaurillac@gmail.com"
MY_PASSWORD = "lpef rbys duiq orvz"  # clé sécurisée Gmail
TO_EMAIL = "bessonpierre15@gmail.com"   # tu t'envoies à toi-même

# Charger la newsletter email
with open("email_newsletter.html", "r", encoding="utf-8") as f:
    newsletter_html = f.read()

# Préparer le mail
msg = MIMEMultipart("alternative")
msg["Subject"] = "TEST - Newsletter"
msg["From"] = MY_EMAIL
msg["To"] = TO_EMAIL

# Ajouter la version HTML
msg.attach(MIMEText(newsletter_html, "html"))

# Envoi via Gmail SMTP
with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
    server.login(MY_EMAIL, MY_PASSWORD)
    server.sendmail(MY_EMAIL, TO_EMAIL, msg.as_string())

print("✅ Newsletter envoyée en test à", TO_EMAIL)
