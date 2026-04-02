import os
import json
import requests

# ===== CONFIG (FROM GITHUB SECRETS / ENV) =====
CLIENT_ID     = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
PROJECT_ID    = os.getenv("PROJECT_ID")

ENVIRONMENT_NAME = "dev"
BRANCH           = "dev"
MATILLION_FOLDER = "matillion"          # folder in your repo

# ===== METADATA =====
commit_id  = os.getenv("COMMIT_ID", "local_commit")
username   = os.getenv("USERNAME",  "unknown_user")
user_email = os.getenv("USER_EMAIL","unknown_email")
pr_number  = os.getenv("PR_NUMBER", "unknown_pr")

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
    "CLIENT_ID": CLIENT_ID,
    "CLIENT_SECRET": CLIENT_SECRET,
    "PROJECT_ID":PROJECT_ID,
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

# ===== STEP 2: COLLECT MATILLION FILES =====
# Reads every file inside the matillion/ folder and sends them in the payload.
# Matillion DPC expects files as a list of { "path": "...", "content": "..." } objects.
print(f"\n📁 Scanning '{MATILLION_FOLDER}/' for orchestration & transformation files...")

files_payload = []
supported_extensions = {".orch.yaml", ".tran.yaml", ".yaml", ".yml", ".json", ".sql"}

if not os.path.isdir(MATILLION_FOLDER):
    raise FileNotFoundError(
        f"❌ Folder '{MATILLION_FOLDER}' not found. "
        "Make sure your workflow checks out the repo and the folder exists."
    )

for root, dirs, files in os.walk(MATILLION_FOLDER):
    # Skip hidden dirs (e.g. .git inside submodules)
    dirs[:] = [d for d in dirs if not d.startswith(".")]
    for filename in sorted(files):
        if any(filename.endswith(ext) for ext in supported_extensions) or "." not in filename:
            filepath = os.path.join(root, filename)
            rel_path = os.path.relpath(filepath, start=".")   # keep full relative path
            with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
                content = fh.read()
            files_payload.append({"path": rel_path, "content": content})
            print(f"   + {rel_path}")

if not files_payload:
    print("⚠️  No supported files found in the matillion folder — artifact will be empty.")

print(f"\n📦 Total files to include: {len(files_payload)}")

# ===== STEP 3: CREATE ARTIFACT =====
artifact_url = (
    f"https://us1.api.matillion.com/dpc/v1/projects/{PROJECT_ID}/artifacts"
)

headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type":  "application/json",
    "environmentName": ENVIRONMENT_NAME,
    "branch":          BRANCH,
    "versionName":     version_name,
}

# Build a structured body that carries metadata + files
body = {
    "versionName":   version_name,
    "environmentName": ENVIRONMENT_NAME,
    "branch":        BRANCH,
    "metadata": {
        "commitId":  commit_id,
        "username":  username,
        "userEmail": user_email,
        "prNumber":  pr_number,
    },
    "files": files_payload,
}

print(f"\n🚀 Creating artifact '{version_name}' ...")
response = requests.post(
    artifact_url,
    headers=headers,
    json=body,          # <-- was missing entirely in the original script
    timeout=60,
)

# ===== STEP 4: HANDLE RESPONSE =====
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