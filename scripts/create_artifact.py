import requests
import json
import os
import sys

# ===== ARGS (passed from GitHub Actions yml) =====
client_id     = sys.argv[1]
client_secret = sys.argv[2]
project_id    = sys.argv[3]
env_name      = sys.argv[4]
commit_id     = sys.argv[5]

API_BASE_URL = "https://us1.api.matillion.com/dpc/v1"


# ══════════════════════════════════════════════════════════════════════════════
# AUTH
# ══════════════════════════════════════════════════════════════════════════════

def get_token() -> str:
    token_url = "https://id.core.matillion.com/oauth/dpc/token"
    payload = (
        "grant_type=client_credentials"
        f"&client_id={client_id}"
        f"&client_secret={client_secret}"
        "&audience=https%3A%2F%2Fapi.matillion.com"
    )
    response = requests.post(
        token_url,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data=payload,
        timeout=30,
    )
    response.raise_for_status()
    access_token = response.json().get("access_token")
    if not access_token:
        raise Exception("Failed to retrieve access token.")
    print("✅ Token generated\n")
    return access_token


# ══════════════════════════════════════════════════════════════════════════════
# CONTENT TYPE
# ══════════════════════════════════════════════════════════════════════════════

def get_content_type(file_path: str) -> tuple:
    if file_path.endswith(".orch.yaml"):
        return "text/plain",               "[ORCH]"
    elif file_path.endswith(".tran.yaml"):
        return "text/plain",               "[TRAN]"
    elif file_path.endswith((".yaml", ".yml")):
        return "text/plain",               "[YAML]"
    elif file_path.endswith(".json"):
        return "application/json",         "[JSON]"
    elif file_path.endswith(".py"):
        return "text/x-python",            "[PY  ]"
    elif file_path.endswith(".sql"):
        return "text/plain",               "[SQL ]"
    elif file_path.endswith(".txt"):
        return "text/plain",               "[TXT ]"
    elif file_path.endswith(".md"):
        return "text/markdown",            "[MD  ]"
    elif file_path.endswith(".sh"):
        return "text/x-sh",               "[SH  ]"
    elif file_path.endswith(".ps1"):
        return "text/plain",               "[PS1 ]"
    else:
        return "application/octet-stream", "[FILE]"


# ══════════════════════════════════════════════════════════════════════════════
# COLLECT ALL REPO FILES
# Walks entire repo from root — no hardcoded folder paths
# Only skips .git (internal git store)
# ══════════════════════════════════════════════════════════════════════════════

def collect_all_files() -> dict:
    files = {}
    for root, dirs, filenames in os.walk("."):
        dirs[:] = sorted([d for d in dirs if d != ".git"])
        for filename in sorted(filenames):
            abs_path  = os.path.join(root, filename)
            full_path = os.path.relpath(abs_path)
            ctype, _  = get_content_type(full_path)
            with open(abs_path, "rb") as f:
                content = f.read()
            files[full_path] = (full_path, content, ctype)
    return files


# ══════════════════════════════════════════════════════════════════════════════
# CHANGED PIPELINES — read from file written by git diff in yml
# ══════════════════════════════════════════════════════════════════════════════

def get_changed_pipelines() -> list:
    changed = []
    try:
        with open("changed_pipelines.txt", "r") as f:
            for line in f:
                path = line.strip()
                if path:
                    changed.append(path)
    except FileNotFoundError:
        pass
    return changed


# ══════════════════════════════════════════════════════════════════════════════
# PUBLISH
# ══════════════════════════════════════════════════════════════════════════════

def publish_artifact(token: str, all_files: dict) -> None:
    url          = f"{API_BASE_URL}/projects/{project_id}/artifacts"
    version_name = f"v_{commit_id[:7]}"

    headers = {
        "Authorization":   f"Bearer {token}",
        "environmentName": env_name,
        "versionName":     version_name,
    }

    # Must be list of tuples — dict drops content-type in requests
    files_list = [
        (field_name, file_tuple)
        for field_name, file_tuple in all_files.items()
    ]

    print(f"🚀 Publishing artifact '{version_name}' ...")
    response = requests.post(url, headers=headers, files=files_list, timeout=120)

    print(f"Status Code : {response.status_code}")
    print(f"Response    : {response.text}\n")

    if response.status_code in (200, 201):
        return version_name

    elif response.status_code == 500:
        print("⚠️  Got 500 — verifying via GET ...")
        verify = requests.get(
            url,
            headers={"Authorization": f"Bearer {token}", "environmentName": env_name},
            timeout=30,
        )
        if verify.status_code == 200:
            items = verify.json()
            items = items if isinstance(items, list) else items.get("content", [])
            match = next((a for a in items if a.get("versionName") == version_name), None)
            if match:
                return version_name
            else:
                raise Exception(f"❌ Artifact '{version_name}' not found after 500.")
        else:
            raise Exception(f"❌ Verification failed ({verify.status_code}).")
    else:
        raise Exception(f"❌ Artifact creation failed ({response.status_code}): {response.text}")


# ══════════════════════════════════════════════════════════════════════════════
# DISPLAY — shown AFTER artifact is created
# ══════════════════════════════════════════════════════════════════════════════

def display_artifact_summary(all_files: dict, changed_pipelines: list, version_name: str):
    print("\n" + "=" * 60)
    print(f"  ✅ ARTIFACT CREATED SUCCESSFULLY : {version_name}")
    print("=" * 60)

    # ── All files added to the artifact ──────────────────────────────────────
    print(f"\n📦 Files Added to Artifact ({len(all_files)}):")
    print("─" * 60)
    for path, (_, _, ctype) in sorted(all_files.items()):
        _, tag = get_content_type(path)
        print(f"   {tag}  {path}  [{ctype}]")
    print("─" * 60)

    # ── Changed pipelines in this PR ─────────────────────────────────────────
    print(f"\n🔄 Pipelines Changed in This PR ({len(changed_pipelines)}):")
    print("─" * 60)
    if changed_pipelines:
        for p in changed_pipelines:
            if ".orch.yaml" in p:
                ptype = "Orchestration"
            elif ".tran.yaml" in p:
                ptype = "Transformation"
            else:
                ptype = "Other"
            print(f"   [{ptype:>14}]  {p}")
    else:
        print("   None")
    print("─" * 60 + "\n")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 50)
    print(f"  Commit ID : {commit_id}")
    print(f"  Env       : {env_name}")
    print(f"  Project   : {project_id}")
    print("=" * 50 + "\n")

    # ── Step 1: Check changed pipelines ──────────────────────────────────────
    changed_pipelines = get_changed_pipelines()
    if not changed_pipelines:
        print("⚠️  No orchestration or transformation files changed in this PR.")
        print("   Skipping artifact creation.")
        sys.exit(0)

    # ── Step 2: Get token ─────────────────────────────────────────────────────
    token = get_token()

    # ── Step 3: Collect entire repo (no hardcoded folder) ────────────────────
    all_files = collect_all_files()

    # ── Step 6: Publish ───────────────────────────────────────────────────────
    version_name = publish_artifact(token, all_files)

    # ── Step 7: Display summary AFTER artifact is created ─────────────────────
    display_artifact_summary(all_files, changed_pipelines, version_name)


if __name__ == "__main__":
    main()