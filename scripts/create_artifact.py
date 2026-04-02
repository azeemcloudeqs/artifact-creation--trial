import os
import requests

# ===== CONFIG =====
CLIENT_ID = "2ea22e3a-29a7-486c-bf0b-5d94aca51ac0"
CLIENT_SECRET = "XALRXYRfCPsz9bSmcJwppAPNLSdAbSOc"
PROJECT_ID = "4c84dfc3-59f9-46cb-ab74-140dc213f2e2"
ENVIRONMENT_NAME = "dev"
BRANCH = "dev"

# ===== METADATA =====
commit_id = os.getenv("GITHUB_SHA", "local_commit")
version_name = f"v_{commit_id[:7]}"

print(" Creating Artifact:", version_name)

# ===== TOKEN =====
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
    raise Exception(" Token Error: " + token_res.text)

access_token = token_res.json()["access_token"]
print(" Token Generated")

# ===== CREATE ARTIFACT =====

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

# ===== RESPONSE =====
print("Status Code:", response.status_code)
print("Response:", response.text)

if response.status_code not in [200, 201]:
    raise Exception(" Artifact creation failed")

print(" Artifact Created Successfully:", version_name)
