"""Run once to generate gmail_token.json"""
from google_auth_oauthlib.flow import InstalledAppFlow
import json
import os
from dotenv import load_dotenv

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
CLIENT_SECRETS = {
    "installed": {
        "client_id": os.getenv("GMAIL_CLIENT_ID"),
        "client_secret": os.getenv("GMAIL_CLIENT_SECRET"),
        "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token"
    }
}

# Write temp secrets file
with open("client_secrets.json", "w") as f:
    json.dump(CLIENT_SECRETS, f)

flow = InstalledAppFlow.from_client_secrets_file("client_secrets.json", SCOPES)
creds = flow.run_local_server(port=0)

with open("gmail_token.json", "w") as f:
    f.write(creds.to_json())

print("✅ gmail_token.json created successfully.")