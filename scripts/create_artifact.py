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

# ===== STEP 2: SCAN FILES =====
if not os.path.isdir(MATILLION_FOLDER):
    raise FileNotFoundError(
        f"❌ Folder '{MATILLION_FOLDER}' not found. "
        "Ensure the repo is checked out and the folder exists on this branch."
    )

# Collect files as:
#   disk_path  = matillion/orchestrations/ORCH_SCD_TYPE_2.orch.yaml  (to open)
#   field_key  = orchestrations/ORCH_SCD_TYPE_2.orch.yaml            (form field name sent to API)
#
# Matillion DPC expects paths relative to the PROJECT root, not including
# the top-level 'matillion/' folder. Stripping it makes the paths match
# Matillion's internal project structure so the artifact recognises the files.

file_entries = []   # list of (disk_path, field_key)

for root, dirs, files in os.walk(MATILLION_FOLDER):
    dirs[:] = [d for d in dirs if not d.startswith(".")]
    for filename in sorted(files):
        disk_path = os.path.join(root, filename)
        # Strip the leading 'matillion/' prefix for the API field key
        field_key = os.path.relpath(disk_path, start=MATILLION_FOLDER)
        file_entries.append((disk_path, field_key))

if not file_entries:
    raise FileNotFoundError(f"❌ No files found in '{MATILLION_FOLDER}/'.")

print(f"\n📂 Files to be included in artifact ({len(file_entries)} files):")
print("-----------------------------------")
for disk_path, field_key in file_entries:
    print(f"   {field_key}  ←  {disk_path}")
print("-----------------------------------")

# ===== STEP 3: POST FILES AS ARTIFACT =====
# Per Matillion DPC docs:
# - multipart/form-data request
# - Each file's FORM FIELD NAME = its path relative to the Matillion project root
#   e.g. 'orchestrations/ORCH_SCD_TYPE_2.orch.yaml'
# - Additional headers: versionName, environmentName, branch, commitHash
artifact_url = f"https://us1.api.matillion.com/dpc/v1/projects/{PROJECT_ID}/artifacts"

headers = {
    "Authorization":   f"Bearer {access_token}",
    "environmentName": ENVIRONMENT_NAME,
    "branch":          BRANCH,
    "versionName":     version_name,
    "commitHash":      commit_id,   # full commit SHA as documented
}

file_handles = []
multipart_files = []
for disk_path, field_key in file_entries:
    fh = open(disk_path, "rb")
    file_handles.append(fh)
    filename = os.path.basename(disk_path)
    multipart_files.append(
        (field_key, (filename, fh, "application/octet-stream"))
    )

print(f"\n🚀 Creating artifact '{version_name}' ...")

try:
    response = requests.post(
        artifact_url,
        headers=headers,
        files=multipart_files,
        timeout=120,
    )
finally:
    for fh in file_handles:
        fh.close()

print(f"\nStatus Code : {response.status_code}")
print(f"Response    : {response.text}")

# ===== STEP 4: HANDLE RESPONSE (500 = known Matillion false negative) =====
artifact_id = None

if response.status_code in (200, 201):
    try:
        data = response.json()
        artifact_id = data.get("id")
        print("\n========== ARTIFACT CREATED ==========")
        print(f"  Artifact ID  : {artifact_id}")
        print(f"  Version Name : {data.get('versionName', 'N/A')}")
        print(f"  Created At   : {data.get('createdAt',   'N/A')}")
        print(f"  Status       : {data.get('status',      'N/A')}")
        print("======================================")
    except (ValueError, KeyError):
        print("ℹ️  No JSON body in response")

elif response.status_code == 500:
    print(f"\n⚠️  Got 500 — verifying if artifact was actually created ...")
    verify_res = requests.get(
        artifact_url,
        headers={
            "Authorization":   f"Bearer {access_token}",
            "environmentName": ENVIRONMENT_NAME,
        },
        timeout=30,
    )
    if verify_res.status_code == 200:
        try:
            items = verify_res.json()
            items = items if isinstance(items, list) else items.get("content", [])
            match = next((a for a in items if a.get("versionName") == version_name), None)
            if match:
                artifact_id = match.get("id")
                print("\n========== ARTIFACT CONFIRMED ==========")
                print(f"  Artifact ID  : {artifact_id}")
                print(f"  Version Name : {match.get('versionName', 'N/A')}")
                print(f"  Created At   : {match.get('createdAt',   'N/A')}")
                print(f"  Status       : {match.get('status',      'N/A')}")
                print("========================================")
            else:
                raise Exception(f"❌ Artifact '{version_name}' not found after 500.")
        except (ValueError, KeyError) as e:
            raise Exception(f"❌ Could not parse verification response: {e}")
    else:
        raise Exception(
            f"❌ Creation failed (500) and verification also failed ({verify_res.status_code})"
        )
else:
    raise Exception(f"❌ Artifact creation failed ({response.status_code}): {response.text}")

print(f"\n✅ Artifact created successfully: {version_name}")