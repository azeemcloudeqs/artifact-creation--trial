import os
import requests

# ===== CONFIG (FROM GITHUB SECRETS) =====
CLIENT_ID = os.getenv("MATILLION_CLIENT_ID")
CLIENT_SECRET = os.getenv("MATILLION_CLIENT_SECRET")

PROJECT_ID = "4c84dfc3-59f9-46cb-ab74-140dc213f2e2"
ENVIRONMENT_NAME = "dev"
BRANCH = "dev"

# ===== METADATA =====
commit_id = os.getenv("GITHUB_SHA", "local_commit")
username = os.getenv("USERNAME", "unknown_user")
user_email = os.getenv("USER_EMAIL", "unknown_email")

version_name = f"v_{commit_id[:7]}"

print("🚀 Creating Artifact:", version_name)
print("👤 User:", username)
print("📧 Email:", user_email)

# ===== STEP 1: GET TOKEN =====
token_url = "https://id.core.matillion.com/oauth/dpc/token"

token_res = requests.post(
    token_url,
    data={
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    },
    headers={"Content-Type": "application/x-www-form-urlencoded"}
)

if token_res.status_code != 200:
    raise Exception("❌ Token Error: " + token_res.text)

access_token = token_res.json().get("access_token")
print("✅ Token Generated")

# ===== STEP 2: CREATE ARTIFACT =====
artifact_url = f"https://us1.api.matillion.com/dpc/v1/projects/{PROJECT_ID}/artifacts"

headers = {
    "Authorization": f"Bearer {access_token}",
    "environmentName": ENVIRONMENT_NAME,
    "branch": BRANCH,
    "versionName": version_name,
    "Content-Type": "application/json"
}

# JSON body (IMPORTANT)
response = requests.post(
    artifact_url,
    headers=headers
)

# ===== STEP 3: HANDLE RESPONSE =====
print("Status Code:", response.status_code)
print("Response:", response.text)

if response.status_code not in [200, 201]:
    raise Exception("❌ Artifact creation failed")

# Optional: parse response
try:
    data = response.json()
    print("📦 Artifact ID:", data.get("id"))
    print("🏷 Version:", data.get("versionName"))
    print("🕒 Created At:", data.get("createdAt"))
except:
    print("ℹ️ No JSON response body")

print(" Artifact Created Successfully:", version_name)
