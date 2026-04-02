import os
import requests

# ===== CONFIG (FROM GITHUB SECRETS) =====
CLIENT_ID     = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
PROJECT_ID    = os.getenv("PROJECT_ID")

ENVIRONMENT_NAME = "dev"
BRANCH           = "dev"

# ===== METADATA =====
commit_id  = os.getenv("COMMIT_ID",  "local_commit")
username   = os.getenv("USERNAME",   "unknown_user")
user_email = os.getenv("USER_EMAIL", "unknown_email")
pr_number  = os.getenv("PR_NUMBER",  "unknown_pr")

version_name = f"v_{commit_id[:7]}"

print("===================================")
print(f"  Artifact  : {version_name}")
print(f"  User      : {username}")
print(f"  Email     : {user_email}")
print(f"  PR Number : {pr_number}")
print(f"  Commit ID : {commit_id}")
print("===================================")

# ===== VALIDATION =====
missing = [k for k, v in {
    "CLIENT_ID":     CLIENT_ID,
    "CLIENT_SECRET": CLIENT_SECRET,
    "PROJECT_ID":    PROJECT_ID,
}.items() if not v]

if missing:
    raise EnvironmentError(f"❌ Missing required env vars: {', '.join(missing)}")

# ===== STEP 1: GET TOKEN =====
token_url = "https://id.core.matillion.com/oauth/dpc/token"

token_res = requests.post(
    token_url,
    data={
        "grant_type":    "client_credentials",
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    },
    headers={"Content-Type": "application/x-www-form-urlencoded"},
    timeout=30,
)

if token_res.status_code != 200:
    raise Exception(f"❌ Token Error ({token_res.status_code}): {token_res.text}")

access_token = token_res.json().get("access_token")
print("✅ Token generated")

# ===== STEP 2: CREATE ARTIFACT =====
artifact_url = f"https://us1.api.matillion.com/dpc/v1/projects/{PROJECT_ID}/artifacts"

# Content-Type is set manually (not via json=) so we control the body separately.
# The API requires the header to be present but does not accept a body payload —
# so we send Content-Type: application/json with an empty byte string as the body.
headers = {
    "Authorization":   f"Bearer {access_token}",
    "Content-Type":    "application/json",
    "environmentName": ENVIRONMENT_NAME,
    "branch":          BRANCH,
    "versionName":     version_name,
}

print(f"\n🚀 Creating artifact '{version_name}' ...")

response = requests.post(
    artifact_url,
    headers=headers,
    data=b"",        # empty body — avoids requests auto-setting any Content-Type
    timeout=60,
)

# ===== STEP 3: HANDLE RESPONSE =====
print(f"\nStatus Code : {response.status_code}")
print(f"Response    : {response.text}")

if response.status_code not in (200, 201):
    raise Exception(
        f"❌ Artifact creation failed ({response.status_code}): {response.text}"
    )

try:
    data = response.json()
    print("\n========== ARTIFACT DETAILS ==========")
    print(f"  Artifact ID  : {data.get('id',          'N/A')}")
    print(f"  Version Name : {data.get('versionName', 'N/A')}")
    print(f"  Created At   : {data.get('createdAt',   'N/A')}")
    print(f"  Status       : {data.get('status',      'N/A')}")
    print("======================================")
except (ValueError, KeyError):
    print("ℹ️  No JSON body in response")

print(f"\n✅ Artifact created successfully: {version_name}")