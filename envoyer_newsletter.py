from datetime import datetime
import json
import shutil

# Copie de la nouvelle newsletter
shutil.copyfile("nouvelle_edition.html", "newsletter_new.html")

# Enregistrement de la date d’envoi
meta = {
    "last_sent": datetime.now().isoformat()
}
with open("newsletter_meta.json", "w", encoding="utf-8") as f:
    json.dump(meta, f, indent=2)

print("✅ Nouvelle newsletter enregistrée. Publication dans 48h.")
