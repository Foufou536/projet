import requests

# VOS VRAIES VALEURS ICI
MAILGUN_API_KEY = "8b22cbee-c0eaa06d"
MAILGUN_DOMAIN = "la-newsletter-aurillac.fr"
VOTRE_EMAIL_TEST = "cplkillerx@gmail.com"

# HTML simple pour tester
html = """
<html>
<body>
    <h1>Test Newsletter</h1>
    <p>Ceci est un test d'envoi via Mailgun.</p>
</body>
</html>
"""

# Envoi
response = requests.post(
    f"https://api.mailgun.net/v3/{MAILGUN_DOMAIN}/messages",
    auth=("api", MAILGUN_API_KEY),
    data={
        "from": f"Newsletter <newsletter@{MAILGUN_DOMAIN}>",
        "to": VOTRE_EMAIL_TEST,
        "subject": "Test Newsletter",
        "html": html
    }
)

if response.status_code == 200:
    print("Email envoyé avec succès !")
else:
    print(f"Erreur : {response.text}")