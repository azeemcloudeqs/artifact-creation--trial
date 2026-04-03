import os
import zipfile
import requests
import tempfile

# ===== CONFIG (FROM GITHUB SECRETS) =====
CLIENT_ID     = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
PROJECT_ID    = os.getenv("PROJECT_ID")

ENVIRONMENT_NAME = "dev"
BRANCH           = "dev"
MATILLION_FOLDER = "matillion"

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

# ===== STEP 2: SCAN FILES FIRST — DISPLAY BEFORE ZIPPING =====
if not os.path.isdir(MATILLION_FOLDER):
    raise FileNotFoundError(
        f"❌ Folder '{MATILLION_FOLDER}' not found. "
        "Ensure the repo is checked out and the folder exists on this branch."
    )

# Collect all file paths first
all_files = []
for root, dirs, files in os.walk(MATILLION_FOLDER):
    dirs[:] = [d for d in dirs if not d.startswith(".")]
    for filename in sorted(files):
        filepath = os.path.join(root, filename)
        all_files.append(os.path.relpath(filepath, start="."))

if not all_files:
    raise FileNotFoundError(f"❌ No files found in '{MATILLION_FOLDER}/'.")

# Display all file paths that will go into the artifact
print(f"\n📂 Files in '{MATILLION_FOLDER}/' to be included in artifact ({len(all_files)} files):")
print("-----------------------------------")
for path in all_files:
    print(f"   {path}")
print("-----------------------------------")

# ===== STEP 3: ZIP THE ENTIRE matillion/ FOLDER =====
zip_path = tempfile.mktemp(suffix=".zip")
print(f"\n📦 Zipping folder ...")

with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
    for path in all_files:
        zf.write(path, path)

zip_size_kb = os.path.getsize(zip_path) / 1024
print(f"✅ Zip ready ({zip_size_kb:.1f} KB)")

# ===== STEP 4: POST ZIP AS ARTIFACT =====
artifact_url = f"https://us1.api.matillion.com/dpc/v1/projects/{PROJECT_ID}/artifacts"

headers = {
    "Authorization":   f"Bearer {access_token}",
    "environmentName": ENVIRONMENT_NAME,
    "branch":          BRANCH,
    "versionName":     version_name,
}

zip_filename = f"{version_name}.zip"
print(f"\n🚀 Creating artifact '{version_name}' ...")

with open(zip_path, "rb") as zf:
    response = requests.post(
        artifact_url,
        headers=headers,
        files=[("file", (zip_filename, zf, "application/zip"))],
        timeout=120,
    )

os.remove(zip_path)

# ===== STEP 5: HANDLE RESPONSE =====
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

print(f"\n✅ Artifact created successfully__: {version_name}")