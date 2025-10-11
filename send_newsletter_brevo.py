import os
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

# Configuration Brevo
BREVO_API_KEY = os.getenv("BREVO_API_KEY")  # ou mettez directement "xkeysib-..."
configuration = sib_api_v3_sdk.Configuration()
configuration.api_key['api-key'] = BREVO_API_KEY

# Connexion PostgreSQL
DATABASE_URL = os.getenv("DATABASE_URL")
conn = psycopg2.connect(DATABASE_URL, sslmode="require", cursor_factory=RealDictCursor)
cur = conn.cursor()

# Récupérer les abonnés
cur.execute("SELECT email FROM subscribers")
subscribers = [row["email"] for row in cur.fetchall()]

# Récupérer les soumissions approuvées
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

# Générer le HTML
newsletter_html = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Newsletter Locale</title>
</head>
<body style="font-family: Arial, sans-serif; max-width: 700px; margin: 0 auto; padding: 20px;">
    <h1 style="text-align: center; color: #003366;">LES PLANS MALIN</h1>
"""

for sub in submissions:
    newsletter_html += f'''
    <div style="border: 1px solid #ddd; padding: 20px; border-radius: 8px; margin-bottom: 20px; display: flex; gap: 20px;">
        <div style="flex: 1;">
            <span style="color: #007bff; font-weight: bold; font-size: 12px;">{sub["category"].upper()}</span>
            <h4 style="margin: 5px 0 10px;">{sub["title"]}</h4>
            <p style="margin: 0 0 10px;">{sub["description"]}</p>
'''
    if sub.get("link_url"):
        newsletter_html += f'            <a href="{sub["link_url"]}" style="background-color: #007bff; color: white; padding: 8px 16px; text-decoration: none; border-radius: 4px;">Lire la suite</a>\n'
    
    newsletter_html += '        </div>\n'
    
    if sub.get("image_url"):
        newsletter_html += f'        <img src="{sub["image_url"]}" style="width: 180px; height: auto; border-radius: 8px;">\n'
    
    newsletter_html += '    </div>\n'

newsletter_html += """
    <p style="text-align: center; font-size: 13px; color: #777; margin-top: 30px;">
        Merci de faire vivre notre ville ♥
    </p>
</body>
</html>
"""

# Envoi via Brevo
api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))

for recipient in subscribers:
    send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
        to=[{"email": recipient}],
        sender={"name": "Newsletter Locale", "email": "newsletter@la-newsletter-aurillac.fr"},
        subject="📰 Votre Newsletter Hebdo - Les Plans Malin",
        html_content=newsletter_html
    )
    
    try:
        api_response = api_instance.send_transac_email(send_smtp_email)
        print(f"✅ Newsletter envoyée à {recipient}")
    except ApiException as e:
        print(f"❌ Erreur pour {recipient}: {e}")

print(f"\n🎉 Newsletter envoyée à {len(subscribers)} abonnés !")