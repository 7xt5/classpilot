import json
import subprocess
import sys
import time
import urllib.parse
import urllib.request

CLIENT_ID = "178c6fc778ccc68e1d6a"  # Official GitHub CLI OAuth Client ID
REPO_OWNER = "7xt5"
REPO_NAME = "classpilot"


def request_json(url: str, data: dict) -> dict:
    encoded = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=encoded,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "ClassPilot-Publisher/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    print("Requesting GitHub Device Verification Code...", flush=True)
    device_data = request_json(
        "https://github.com/login/device/code",
        {"client_id": CLIENT_ID, "scope": "repo"},
    )
    user_code = device_data["user_code"]
    verification_uri = device_data["verification_uri"]
    device_code = device_data["device_code"]
    interval = int(device_data.get("interval", 5))

    print("=" * 60, flush=True)
    print(f"GITHUB VERIFICATION URL : {verification_uri}", flush=True)
    print(f"ONE-TIME DEVICE CODE    : {user_code}", flush=True)
    print("=" * 60, flush=True)
    print("Waiting for user to enter the code at the URL above...", flush=True)

    while True:
        time.sleep(interval)
        token_resp = request_json(
            "https://github.com/login/oauth/access_token",
            {
                "client_id": CLIENT_ID,
                "device_code": device_code,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            },
        )
        if "access_token" in token_resp:
            access_token = token_resp["access_token"]
            print("\n[AUTHORIZED] GitHub account connected! Pushing ClassPilot code...", flush=True)
            auth_remote = f"https://x-access-token:{access_token}@github.com/{REPO_OWNER}/{REPO_NAME}.git"
            res = subprocess.run(
                ["git", "push", "-u", auth_remote, "main", "--force"],
                capture_output=True,
                text=True,
            )
            if res.returncode == 0:
                subprocess.run(
                    ["git", "remote", "set-url", "origin", auth_remote],
                    capture_output=True,
                )
                print(f"[SUCCESS] All files pushed to https://github.com/{REPO_OWNER}/{REPO_NAME}", flush=True)
                return 0
            else:
                print(f"[ERROR] git push failed:\n{res.stderr}", flush=True)
                return 1

        err = token_resp.get("error", "")
        if err == "authorization_pending":
            continue
        elif err == "slow_down":
            interval += 5
        else:
            print(f"[ERROR] Device flow failed: {token_resp}", flush=True)
            return 1


if __name__ == "__main__":
    sys.exit(main())
