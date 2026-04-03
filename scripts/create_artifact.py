import os
import requests

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

# ===== STEP 2: COLLECT FILES FROM matillion/ FOLDER =====
# Walk the matillion/ folder and collect all orchestration & transformation files.
print(f"\n📁 Scanning '{MATILLION_FOLDER}/' ...")

if not os.path.isdir(MATILLION_FOLDER):
    raise FileNotFoundError(
        f"❌ Folder '{MATILLION_FOLDER}' not found in workspace. "
        "Ensure the repo is checked out and the folder exists on this branch."
    )

supported_extensions = (".orch.yaml", ".tran.yaml", ".yaml", ".yml", ".json", ".sql")
collected_files = []

for root, dirs, files in os.walk(MATILLION_FOLDER):
    dirs[:] = [d for d in dirs if not d.startswith(".")]
    for filename in sorted(files):
        if filename.endswith(supported_extensions):
            filepath = os.path.join(root, filename)
            collected_files.append(filepath)
            print(f"   + {filepath}")

if not collected_files:
    raise FileNotFoundError(
        f"❌ No supported files found in '{MATILLION_FOLDER}/'. "
        "Expected .orch.yaml, .tran.yaml, .yaml, .yml, .json, or .sql files."
    )

print(f"\n📦 Total files found: {len(collected_files)}")

# ===== STEP 3: CREATE ARTIFACT WITH FILES =====
# Postman shows the API uses multipart/form-data with a 'file' field.
# We open all collected files and attach them all under the 'file' key.
# requests handles the multipart boundary and Content-Type automatically
# when you pass the `files=` argument — do NOT set Content-Type manually.
artifact_url = f"https://us1.api.matillion.com/dpc/v1/projects/{PROJECT_ID}/artifacts"

headers = {
    "Authorization":   f"Bearer {access_token}",
    "environmentName": ENVIRONMENT_NAME,
    "branch":          BRANCH,
    "versionName":     version_name,
    # ⚠️  Do NOT set Content-Type here — requests sets it automatically
    # with the correct multipart boundary when files= is used.
}

# Build multipart file list — multiple files all under the key "file"
file_handles = []
multipart_files = []
for filepath in collected_files:
    fh = open(filepath, "rb")
    file_handles.append(fh)
    filename = os.path.basename(filepath)
    multipart_files.append(("file", (filename, fh, "application/octet-stream")))

print(f"\n🚀 Creating artifact '{version_name}' ...")

try:
    response = requests.post(
        artifact_url,
        headers=headers,
        files=multipart_files,
        timeout=60,
    )
finally:
    for fh in file_handles:
        fh.close()

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